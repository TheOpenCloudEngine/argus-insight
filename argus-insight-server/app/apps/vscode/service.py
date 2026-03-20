"""VS Code Server deployment and authentication service.

Manages the lifecycle of per-user code-server instances on K3s:
- Deploy: render K8s manifests, create DNS record, kubectl apply
- Destroy: kubectl delete, remove DNS record, update DB
- Auth: verify cookie tokens for Nginx Ingress auth-url subrequest
"""

from __future__ import annotations

import asyncio
import logging
import string
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import create_token, verify_token
from app.core.database import async_session
from app.core.s3 import ensure_bucket, get_s3_settings
from app.settings.models import ArgusConfiguration
from app.apps.vscode.models import ArgusVscodeInstance

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "kubernetes" / "templates"
K8S_NAMESPACE = "argus-vscode"


def _render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a YAML template with ${VAR} substitution."""
    raw = template_path.read_text()
    tmpl = string.Template(raw)
    return tmpl.safe_substitute(variables)


def _render_vscode_manifests(variables: dict[str, str]) -> str:
    """Render all vscode K8s templates in deterministic order."""
    template_dir = TEMPLATES_DIR / "vscode"
    order = ["secret", "deployment", "service"]
    yaml_files = sorted(
        template_dir.glob("*.yaml"),
        key=lambda p: next((i for i, o in enumerate(order) if o in p.stem), 99),
    )
    parts = [_render_template(f, variables) for f in yaml_files]
    return "\n---\n".join(parts)


async def _kubectl_apply(manifest_yaml: str) -> str:
    """Apply YAML manifest via kubectl."""
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "apply", "-f", "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(manifest_yaml.encode())
    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()
    if proc.returncode != 0:
        logger.error("kubectl apply failed: %s", stderr_str)
        raise RuntimeError(f"kubectl apply failed (rc={proc.returncode}): {stderr_str}")
    logger.info("kubectl apply: %s", stdout_str)
    return stdout_str


async def _kubectl_delete(manifest_yaml: str) -> str:
    """Delete resources via kubectl."""
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "delete", "-f", "-", "--ignore-not-found",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(manifest_yaml.encode())
    stdout_str = stdout.decode().strip()
    if proc.returncode != 0:
        logger.warning("kubectl delete warning: %s", stderr.decode().strip())
    logger.info("kubectl delete: %s", stdout_str)
    return stdout_str


async def _ensure_namespace() -> None:
    """Ensure the argus-vscode namespace exists."""
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "create", "namespace", K8S_NAMESPACE,
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
    await apply_proc.communicate(stdout)


async def _get_pdns_settings(session: AsyncSession) -> dict[str, str]:
    """Read PowerDNS settings from database."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "domain")
    )
    rows = result.scalars().all()
    return {row.config_key: row.config_value for row in rows}


async def _register_dns(
    session: AsyncSession, hostname: str, server_ip: str
) -> None:
    """Register A record in PowerDNS for the VS Code hostname."""
    cfg = await _get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        logger.warning("PowerDNS not configured, skipping DNS registration")
        return

    domain_name = cfg["domain_name"]
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/localhost"

    body = {
        "rrsets": [
            {
                "name": fqdn,
                "type": "A",
                "ttl": 300,
                "changetype": "REPLACE",
                "records": [{"content": server_ip, "disabled": False}],
            },
        ],
    }
    logger.info("Registering DNS: %s -> %s", fqdn, server_ip)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{base_url}/zones/{zone}",
                json=body,
                headers={"X-API-Key": cfg["pdns_api_key"]},
            )
        if resp.status_code not in (200, 204):
            logger.warning("DNS registration returned %d: %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.warning("DNS registration failed for %s", hostname, exc_info=True)


async def _delete_dns(session: AsyncSession, hostname: str) -> None:
    """Remove A record from PowerDNS."""
    cfg = await _get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        return

    domain_name = cfg["domain_name"]
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/localhost"

    body = {
        "rrsets": [
            {
                "name": fqdn,
                "type": "A",
                "changetype": "DELETE",
            },
        ],
    }
    logger.info("Deleting DNS record: %s", fqdn)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.patch(
                f"{base_url}/zones/{zone}",
                json=body,
                headers={"X-API-Key": cfg["pdns_api_key"]},
            )
    except Exception:
        logger.warning("DNS deletion failed for %s", hostname, exc_info=True)


async def _get_s3_deploy_settings() -> dict[str, str]:
    """Get S3 settings for the sidecar container."""
    cfg = await get_s3_settings()
    return {
        "S3_ENDPOINT": cfg.get("object_storage_endpoint", "http://localhost:9000"),
        "S3_ACCESS_KEY": cfg.get("object_storage_access_key", "minioadmin"),
        "S3_SECRET_KEY": cfg.get("object_storage_secret_key", "minioadmin"),
        "S3_USE_SSL": cfg.get("object_storage_use_ssl", "false"),
    }


def _build_hostname(username: str, domain: str) -> str:
    """Build the full hostname for a VS Code instance."""
    return f"argus-vscode-{username}.argus-insight.{domain}"


def _extract_username_from_host(host: str) -> str | None:
    """Extract username from hostname like argus-vscode-{username}.argus-insight.{domain}."""
    if not host:
        return None
    parts = host.split(".")
    if not parts:
        return None
    prefix = parts[0]  # argus-vscode-{username}
    if prefix.startswith("argus-vscode-"):
        return prefix[len("argus-vscode-"):]
    return None


async def get_instance_status(
    session: AsyncSession, user_id: int
) -> ArgusVscodeInstance | None:
    """Get the current user's VS Code instance."""
    result = await session.execute(
        select(ArgusVscodeInstance).where(ArgusVscodeInstance.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def launch_instance(
    session: AsyncSession,
    user_id: int,
    username: str,
    domain: str,
) -> ArgusVscodeInstance:
    """Deploy a code-server instance for the user.

    Creates the K8s resources (Secret, Deployment, Service, Ingress),
    registers the DNS record, and tracks the instance in the database.
    """
    # Check for existing instance
    existing = await get_instance_status(session, user_id)
    if existing and existing.status in ("deploying", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Instance already exists with status: {existing.status}",
        )

    # If there's a failed/deleted instance, remove it first
    if existing:
        await session.delete(existing)
        await session.flush()

    hostname = _build_hostname(username, domain)

    # Create DB record
    instance = ArgusVscodeInstance(
        user_id=user_id,
        username=username,
        domain=domain,
        k8s_namespace=K8S_NAMESPACE,
        hostname=hostname,
        status="deploying",
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance)

    # Run deployment in background
    instance_id = instance.id
    asyncio.create_task(
        _deploy_instance(instance_id, username, domain, hostname)
    )

    return instance


async def _deploy_instance(
    instance_id: int,
    username: str,
    domain: str,
    hostname: str,
) -> None:
    """Background task to deploy K8s resources and update status."""
    try:
        # Get S3 settings
        s3 = await _get_s3_deploy_settings()

        # Ensure the user's S3 bucket exists
        bucket_name = f"user-{username}"
        await ensure_bucket(bucket_name)

        # Ensure namespace exists
        await _ensure_namespace()

        # Get server IP for auth-url (use domain settings)
        async with async_session() as session:
            pdns_cfg = await _get_pdns_settings(session)
        server_ip = pdns_cfg.get("pdns_ip", "127.0.0.1")

        # Render and apply manifests
        variables = {
            "USERNAME": username,
            "K8S_NAMESPACE": K8S_NAMESPACE,
            "HOSTNAME": hostname,
            "DOMAIN": domain,
            "S3_ENDPOINT": s3["S3_ENDPOINT"],
            "S3_ACCESS_KEY": s3["S3_ACCESS_KEY"],
            "S3_SECRET_KEY": s3["S3_SECRET_KEY"],
            "S3_USE_SSL": s3["S3_USE_SSL"],
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = _render_vscode_manifests(variables)
        await _kubectl_apply(manifests)

        # Register DNS
        async with async_session() as session:
            await _register_dns(session, hostname, server_ip)

        # Wait for deployment to be ready
        ready = await _wait_for_deployment(username)

        # Update status
        async with async_session() as session:
            result = await session.execute(
                select(ArgusVscodeInstance).where(ArgusVscodeInstance.id == instance_id)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "running" if ready else "failed"
                await session.commit()

        logger.info(
            "VS Code instance %s deployed: status=%s",
            hostname, "running" if ready else "failed",
        )

    except Exception:
        logger.error("Failed to deploy VS Code for %s", username, exc_info=True)
        async with async_session() as session:
            result = await session.execute(
                select(ArgusVscodeInstance).where(ArgusVscodeInstance.id == instance_id)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "failed"
                await session.commit()


async def _wait_for_deployment(username: str, timeout: int = 180) -> bool:
    """Wait for the code-server deployment to become ready."""
    resource = f"deployment/argus-vscode-{username}"
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "rollout", "status", resource,
        f"--namespace={K8S_NAMESPACE}",
        f"--timeout={timeout}s",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "Rollout status failed for %s: %s",
            resource, stderr.decode().strip(),
        )
        return False
    logger.info("Deployment %s ready", resource)
    return True


async def destroy_instance(
    session: AsyncSession, user_id: int
) -> None:
    """Destroy the user's code-server instance."""
    instance = await get_instance_status(session, user_id)
    if not instance:
        raise HTTPException(status_code=404, detail="No VS Code instance found")

    instance.status = "deleting"
    await session.commit()

    username = instance.username
    domain = instance.domain
    hostname = instance.hostname
    instance_id = instance.id

    # Run deletion in background
    asyncio.create_task(
        _destroy_instance(instance_id, username, domain, hostname)
    )


async def _destroy_instance(
    instance_id: int,
    username: str,
    domain: str,
    hostname: str,
) -> None:
    """Background task to delete K8s resources."""
    try:
        # Get S3 settings to render manifests
        s3 = await _get_s3_deploy_settings()

        async with async_session() as session:
            pdns_cfg = await _get_pdns_settings(session)
        server_ip = pdns_cfg.get("pdns_ip", "127.0.0.1")

        variables = {
            "USERNAME": username,
            "K8S_NAMESPACE": K8S_NAMESPACE,
            "HOSTNAME": hostname,
            "DOMAIN": domain,
            "S3_ENDPOINT": s3["S3_ENDPOINT"],
            "S3_ACCESS_KEY": s3["S3_ACCESS_KEY"],
            "S3_SECRET_KEY": s3["S3_SECRET_KEY"],
            "S3_USE_SSL": s3["S3_USE_SSL"],
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = _render_vscode_manifests(variables)
        await _kubectl_delete(manifests)

        # Delete DNS record
        async with async_session() as session:
            await _delete_dns(session, hostname)

        # Update DB
        async with async_session() as session:
            result = await session.execute(
                select(ArgusVscodeInstance).where(
                    ArgusVscodeInstance.id == instance_id
                )
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "deleted"
                await session.commit()

        logger.info("VS Code instance destroyed: %s", hostname)

    except Exception:
        logger.error("Failed to destroy VS Code for %s", username, exc_info=True)
        async with async_session() as session:
            result = await session.execute(
                select(ArgusVscodeInstance).where(
                    ArgusVscodeInstance.id == instance_id
                )
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "failed"
                await session.commit()


def verify_vscode_auth(token: str, host: str) -> bool:
    """Verify a VS Code auth token against the requested host.

    The token's 'sub' claim (username) must match the username
    extracted from the hostname.
    """
    payload = verify_token(token)
    if payload is None:
        return False

    token_username = payload.get("sub")
    host_username = _extract_username_from_host(host)

    if not token_username or not host_username:
        return False

    return token_username == host_username


def create_vscode_token(username: str, role: str) -> str:
    """Create a token for VS Code authentication cookie."""
    return create_token(username, role)
