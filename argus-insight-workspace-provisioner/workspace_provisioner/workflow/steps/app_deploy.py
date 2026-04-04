"""Generic app instance deploy/teardown step.

Uses workspace_provisioner's kubernetes client and dns client to
deploy any app type based on its template_dir and hostname_pattern.
Works with the step tracking system in app/apps/service.py.
"""

import asyncio
import logging

from workspace_provisioner.dns.client import delete_dns, get_pdns_settings, register_dns
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)

logger = logging.getLogger(__name__)


async def ensure_namespace(namespace: str) -> None:
    """Ensure a K8s namespace exists."""
    logger.info("[namespace] Ensuring namespace '%s' exists", namespace)
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "create", "namespace", namespace,
        "--dry-run=client", "-o", "yaml",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    apply_proc = await asyncio.create_subprocess_exec(
        "kubectl", "apply", "-f", "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await apply_proc.communicate(stdout)
    if apply_proc.returncode == 0:
        logger.info("[namespace] Namespace '%s' ready — %s", namespace, out.decode().strip())
    else:
        logger.error("[namespace] Failed to ensure namespace '%s' — %s", namespace, err.decode().strip())
        raise RuntimeError(f"Failed to ensure namespace '{namespace}': {err.decode().strip()}")


async def apply_resource_quota(
    namespace: str, cpu_cores: float, memory_mb: int,
) -> None:
    """Apply a K8s ResourceQuota to a workspace namespace.

    This enforces the resource profile limits at the K8s level,
    preventing any Pod (plugin, ML Job, user Pod, etc.) from
    collectively exceeding the workspace's allocated resources.

    Args:
        namespace: K8s namespace (e.g. argus-ws-mlops7)
        cpu_cores: CPU limit in cores (e.g. 8.0)
        memory_mb: Memory limit in MiB (e.g. 8192)
    """
    import json

    memory_gi = f"{memory_mb / 1024:.0f}Gi"
    cpu_str = str(int(cpu_cores)) if cpu_cores == int(cpu_cores) else f"{cpu_cores:.1f}"

    quota_manifest = json.dumps({
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {
            "name": "workspace-quota",
            "namespace": namespace,
        },
        "spec": {
            "hard": {
                "requests.cpu": cpu_str,
                "requests.memory": memory_gi,
                "limits.cpu": cpu_str,
                "limits.memory": memory_gi,
            },
        },
    })

    logger.info("[quota] Applying ResourceQuota to '%s': cpu=%s, memory=%s",
                namespace, cpu_str, memory_gi)

    proc = await asyncio.create_subprocess_exec(
        "kubectl", "apply", "-f", "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(quota_manifest.encode())
    if proc.returncode == 0:
        logger.info("[quota] ResourceQuota applied to '%s' — %s", namespace, out.decode().strip())
    else:
        logger.warning("[quota] Failed to apply ResourceQuota to '%s' — %s",
                       namespace, err.decode().strip())


async def update_resource_quota(namespace: str, cpu_cores: float, memory_mb: int) -> None:
    """Update an existing ResourceQuota when the profile is changed.

    Same as apply_resource_quota (kubectl apply is idempotent).
    """
    await apply_resource_quota(namespace, cpu_cores, memory_mb)


async def prepare_s3(username: str, user_id: int) -> dict[str, str]:
    """Prepare S3 bucket, create per-user credentials, and store in user table.

    If the user already has S3 credentials in the DB, reuse them.
    Otherwise, generate new access key / secret key via MinIO admin API.
    """
    import secrets

    from sqlalchemy import select
    from app.core.database import async_session
    from app.core.s3 import ensure_bucket, get_s3_settings
    from app.usermgr.models import ArgusUser

    logger.info("[s3] Loading S3 settings for user '%s' (id=%d)", username, user_id)
    cfg = await get_s3_settings()
    endpoint = cfg.get("object_storage_endpoint", "http://localhost:9000")
    root_access = cfg.get("object_storage_access_key", "minioadmin")
    root_secret = cfg.get("object_storage_secret_key", "minioadmin")
    use_ssl = cfg.get("object_storage_use_ssl", "false")
    bucket_name = f"user-{username}"

    # Ensure bucket exists
    logger.info("[s3] Ensuring bucket '%s' exists at %s", bucket_name, endpoint)
    await ensure_bucket(bucket_name)
    logger.info("[s3] Bucket '%s' ready", bucket_name)

    # Check if user already has S3 credentials
    async with async_session() as session:
        result = await session.execute(
            select(ArgusUser).where(ArgusUser.id == user_id)
        )
        user = result.scalars().first()

    if user and user.s3_access_key and user.s3_secret_key:
        logger.info("[s3] Reusing existing S3 credentials for '%s'", username)
        return {
            "S3_ENDPOINT": endpoint,
            "S3_ACCESS_KEY": user.s3_access_key,
            "S3_SECRET_KEY": user.s3_secret_key,
            "S3_USE_SSL": use_ssl,
        }

    # Generate per-user credentials
    access_key = f"user-{username}"
    secret_key = secrets.token_urlsafe(24)
    logger.info("[s3] Creating MinIO user '%s' with bucket policy for '%s'", access_key, bucket_name)

    try:
        from workspace_provisioner.minio.client import MinioAdminClient

        # Strip protocol from endpoint for MinIO SDK
        minio_endpoint = endpoint.replace("http://", "").replace("https://", "")
        minio_client = MinioAdminClient(
            endpoint=minio_endpoint,
            root_user=root_access,
            root_password=root_secret,
            secure=(use_ssl == "true"),
        )
        await minio_client.create_user(access_key, secret_key)
        await minio_client.set_user_bucket_policy(access_key, bucket_name)
        logger.info("[s3] MinIO user '%s' created with RW policy on '%s'", access_key, bucket_name)
    except Exception:
        logger.warning("[s3] Failed to create MinIO user '%s', falling back to root credentials",
                       access_key, exc_info=True)
        # Fallback to root credentials
        return {
            "S3_ENDPOINT": endpoint,
            "S3_ACCESS_KEY": root_access,
            "S3_SECRET_KEY": root_secret,
            "S3_USE_SSL": use_ssl,
        }

    # Store credentials in user table
    async with async_session() as session:
        result = await session.execute(
            select(ArgusUser).where(ArgusUser.id == user_id)
        )
        user = result.scalars().first()
        if user:
            user.s3_access_key = access_key
            user.s3_secret_key = secret_key
            user.s3_bucket = bucket_name
            await session.commit()
            logger.info("[s3] S3 credentials stored for user '%s' (bucket=%s)", username, bucket_name)

    return {
        "S3_ENDPOINT": endpoint,
        "S3_ACCESS_KEY": access_key,
        "S3_SECRET_KEY": secret_key,
        "S3_USE_SSL": use_ssl,
    }


async def build_variables(
    username: str,
    instance_id: str,
    app_type: str,
    namespace: str,
    hostname: str,
    domain: str,
    s3: dict[str, str],
    server_ip: str,
    workspace_bucket: str = "",
) -> dict[str, str]:
    """Build template variables for K8s manifest rendering."""
    variables = {
        "USERNAME": username,
        "INSTANCE_ID": instance_id,
        "K8S_NAMESPACE": namespace,
        "HOSTNAME": hostname,
        "DOMAIN": domain,
        "S3_ENDPOINT": s3["S3_ENDPOINT"],
        "S3_ACCESS_KEY": s3["S3_ACCESS_KEY"],
        "S3_SECRET_KEY": s3["S3_SECRET_KEY"],
        "S3_USE_SSL": s3["S3_USE_SSL"],
        "ARGUS_SERVER_HOST": server_ip,
        "APP_TYPE": app_type,
        "USER_BUCKET": f"user-{username}",
        "WORKSPACE_BUCKET": workspace_bucket or f"user-{username}",
    }
    logger.info("[variables] Built template variables: app_type=%s, instance_id=%s, "
                "hostname=%s, namespace=%s, server_ip=%s",
                app_type, instance_id, hostname, namespace, server_ip)
    logger.debug("[variables] Full variables: %s",
                 {k: v for k, v in variables.items() if "KEY" not in k and "SECRET" not in k})
    return variables


async def get_server_ip(session) -> str:
    """Get the server IP from PowerDNS settings."""
    cfg = await get_pdns_settings(session)
    ip = cfg.get("pdns_ip", "127.0.0.1")
    logger.info("[server_ip] Resolved server IP: %s", ip)
    return ip


async def get_pdns_config(session) -> dict[str, str]:
    """Get PowerDNS config for DNS operations."""
    return await get_pdns_settings(session)


async def register_workspace_dns(hostname: str) -> None:
    """Register DNS for a workspace service using server IP from socket."""
    import socket
    from app.core.database import async_session

    try:
        server_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        server_ip = "127.0.0.1"

    async with async_session() as session:
        await register_app_dns(session, hostname, server_ip)


async def delete_workspace_dns(hostname: str) -> None:
    """Delete DNS for a workspace service."""
    from app.core.database import async_session

    async with async_session() as session:
        await delete_app_dns(session, hostname)


async def deploy_manifests(template_dir: str, variables: dict[str, str]) -> str:
    """Render and apply K8s manifests from a template directory."""
    logger.info("[k8s] Rendering manifests from template '%s'", template_dir)
    manifests = render_manifests(template_dir, variables)
    logger.info("[k8s] Applying manifests (%d bytes) to namespace '%s'",
                len(manifests), variables.get("K8S_NAMESPACE", "unknown"))
    result = await kubectl_apply(manifests)
    logger.info("[k8s] Manifests applied successfully")
    return result


async def delete_manifests(template_dir: str, variables: dict[str, str]) -> str:
    """Render and delete K8s manifests."""
    logger.info("[k8s] Rendering manifests from template '%s' for deletion", template_dir)
    manifests = render_manifests(template_dir, variables)
    logger.info("[k8s] Deleting resources from namespace '%s'",
                variables.get("K8S_NAMESPACE", "unknown"))
    result = await kubectl_delete(manifests)
    logger.info("[k8s] Resources deleted successfully")
    return result


async def wait_for_ready(app_type: str, instance_id: str, namespace: str, timeout: int = 180) -> bool:
    """Wait for the deployment to become ready."""
    resource = f"deployment/argus-{app_type}-{instance_id}"
    logger.info("[rollout] Waiting for %s in namespace '%s' (timeout=%ds)", resource, namespace, timeout)
    ready = await kubectl_rollout_status(resource, namespace=namespace, timeout=timeout)
    if ready:
        logger.info("[rollout] %s is ready", resource)
    else:
        logger.warning("[rollout] %s timed out after %ds", resource, timeout)
    return ready


async def register_app_dns(session, hostname: str, server_ip: str) -> None:
    """Register DNS for an app instance."""
    logger.info("[dns] Registering DNS for hostname '%s' -> %s", hostname, server_ip)
    cfg = await get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        logger.warning("[dns] PowerDNS not configured (pdns_ip=%s, domain_name=%s), skipping",
                       cfg.get("pdns_ip"), cfg.get("domain_name"))
        return
    await register_dns(
        pdns_ip=cfg["pdns_ip"],
        pdns_port=cfg["pdns_port"],
        pdns_api_key=cfg["pdns_api_key"],
        domain_name=cfg["domain_name"],
        hostname=hostname,
        target_ip=server_ip,
    )
    logger.info("[dns] DNS registration completed for '%s'", hostname)


async def delete_app_dns(session, hostname: str) -> None:
    """Delete DNS for an app instance."""
    logger.info("[dns] Deleting DNS for hostname '%s'", hostname)
    cfg = await get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        logger.warning("[dns] PowerDNS not configured, skipping DNS deletion for '%s'", hostname)
        return
    await delete_dns(
        pdns_ip=cfg["pdns_ip"],
        pdns_port=cfg["pdns_port"],
        pdns_api_key=cfg["pdns_api_key"],
        domain_name=cfg["domain_name"],
        hostname=hostname,
    )
    logger.info("[dns] DNS deletion completed for '%s'", hostname)


async def verify_pods_deleted(
    app_type: str, instance_id: str, namespace: str, timeout: int = 60,
) -> None:
    """Wait until pods for the deployment are fully terminated."""
    label = f"app.kubernetes.io/name=code-server,app.kubernetes.io/instance={instance_id}"
    logger.info("[pods] Verifying pod termination: label=%s, namespace=%s, timeout=%ds",
                label, namespace, timeout)
    deadline = asyncio.get_event_loop().time() + timeout
    pods = ""
    poll_count = 0

    while asyncio.get_event_loop().time() < deadline:
        proc = await asyncio.create_subprocess_exec(
            "kubectl", "get", "pods", "-n", namespace, "-l", label,
            "--no-headers", "-o", "custom-columns=NAME:.metadata.name",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        pods = stdout.decode().strip()
        poll_count += 1
        if not pods:
            logger.info("[pods] All pods terminated for %s-%s in %s (after %d polls)",
                        app_type, instance_id, namespace, poll_count)
            return
        logger.info("[pods] Still running (poll #%d): %s", poll_count, pods.replace("\n", ", "))
        await asyncio.sleep(3)

    logger.error("[pods] Pods not terminated after %ds (%d polls): %s", timeout, poll_count, pods)
    raise RuntimeError(f"Pods not terminated after {timeout}s: {pods}")
