"""Generic app deployment and authentication service.

Manages the lifecycle of per-user app instances on K3s.
App-agnostic: uses ArgusApp.template_dir and hostname_pattern
to render K8s manifests and build hostnames dynamically.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import string
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apps.models import ArgusApp, ArgusAppInstance
from app.core.database import async_session
from app.core.s3 import ensure_bucket, get_s3_settings
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "kubernetes" / "templates"

# Cookie token settings
_APP_COOKIE_SECRET = "argus-insight-app-cookie-secret"
_APP_COOKIE_EXPIRY = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Cookie token helpers
# ---------------------------------------------------------------------------

def create_app_token(username: str, instance_id: str, app_type: str, role: str) -> str:
    """Create an HMAC-based auth cookie token for an app instance."""
    payload = {
        "sub": username,
        "instance_id": instance_id,
        "app_type": app_type,
        "role": role,
        "exp": int(time.time()) + _APP_COOKIE_EXPIRY,
    }
    data = json.dumps(payload).encode()
    sig = _hmac.new(_APP_COOKIE_SECRET.encode(), data, hashlib.sha256).hexdigest()
    return urlsafe_b64encode(json.dumps({"payload": payload, "sig": sig}).encode()).decode()


def verify_app_token(token: str) -> dict | None:
    """Verify and decode an app cookie token. Returns payload or None."""
    try:
        token_data = json.loads(urlsafe_b64decode(token))
        payload = token_data["payload"]
        data = json.dumps(payload).encode()
        expected = _hmac.new(_APP_COOKIE_SECRET.encode(), data, hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(token_data["sig"], expected):
            return None
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def verify_auth(token: str, host: str, app: ArgusApp) -> bool:
    """Verify a cookie token against the requested host and app type."""
    payload = verify_app_token(token)
    if payload is None:
        return False

    token_instance_id = payload.get("instance_id")
    token_app_type = payload.get("app_type")
    host_instance_id = extract_instance_id_from_host(host, app)

    if not token_instance_id or not host_instance_id:
        return False

    return token_instance_id == host_instance_id and token_app_type == app.app_type


# ---------------------------------------------------------------------------
# Hostname helpers
# ---------------------------------------------------------------------------

def generate_instance_id() -> str:
    """Generate a unique 8-char hex ID from UUID4."""
    import uuid
    return uuid.uuid4().hex[:8]


def build_hostname(app: ArgusApp, instance_id: str, domain: str) -> str:
    """Build the full hostname for an app instance using the pattern."""
    return app.hostname_pattern.format(
        app_type=app.app_type, instance_id=instance_id, domain=domain,
    )


def extract_instance_id_from_host(host: str, app: ArgusApp) -> str | None:
    """Extract instance_id from hostname.

    The pattern 'argus-{app_type}-{instance_id}.{domain}'
    produces hostnames like 'argus-vscode-f7a3b2c1.dev.net'.
    """
    if not host:
        return None
    prefix = f"argus-{app.app_type}-"
    first_part = host.split(".")[0]
    if first_part.startswith(prefix):
        return first_part[len(prefix):]
    return None


# ---------------------------------------------------------------------------
# K8s helpers
# ---------------------------------------------------------------------------

def _render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a YAML template with ${VAR} substitution."""
    raw = template_path.read_text()
    tmpl = string.Template(raw)
    return tmpl.safe_substitute(variables)


def render_manifests(app: ArgusApp, variables: dict[str, str]) -> str:
    """Render all K8s templates for an app in deterministic order."""
    template_dir = TEMPLATES_DIR / app.template_dir
    if not template_dir.is_dir():
        raise RuntimeError(f"Template directory not found: {template_dir}")

    order = ["secret", "deployment", "service"]
    yaml_files = sorted(
        template_dir.glob("*.yaml"),
        key=lambda p: next((i for i, o in enumerate(order) if o in p.stem), 99),
    )
    parts = [_render_template(f, variables) for f in yaml_files]
    return "\n---\n".join(parts)


async def kubectl_apply(manifest_yaml: str) -> str:
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


async def kubectl_delete(manifest_yaml: str) -> str:
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


async def ensure_namespace(namespace: str) -> None:
    """Ensure a K8s namespace exists."""
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
    await apply_proc.communicate(stdout)


# ---------------------------------------------------------------------------
# DNS helpers (PowerDNS)
# ---------------------------------------------------------------------------

async def _get_pdns_settings(session: AsyncSession) -> dict[str, str]:
    """Read PowerDNS settings from database."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "domain")
    )
    return {row.config_key: row.config_value for row in result.scalars().all()}


async def register_dns(session: AsyncSession, hostname: str, server_ip: str) -> None:
    """Register A record in PowerDNS."""
    cfg = await _get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        logger.warning("PowerDNS not configured, skipping DNS registration")
        return

    domain_name = cfg["domain_name"]
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/localhost"

    body = {"rrsets": [{"name": fqdn, "type": "A", "ttl": 300, "changetype": "REPLACE",
                        "records": [{"content": server_ip, "disabled": False}]}]}
    logger.info("Registering DNS: %s -> %s", fqdn, server_ip)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(f"{base_url}/zones/{zone}", json=body,
                                      headers={"X-API-Key": cfg["pdns_api_key"]})
        if resp.status_code not in (200, 204):
            logger.warning("DNS registration returned %d: %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.warning("DNS registration failed for %s", hostname, exc_info=True)


async def delete_dns(session: AsyncSession, hostname: str) -> None:
    """Remove A record from PowerDNS."""
    cfg = await _get_pdns_settings(session)
    if not cfg.get("pdns_ip") or not cfg.get("domain_name"):
        return

    domain_name = cfg["domain_name"]
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/localhost"

    body = {"rrsets": [{"name": fqdn, "type": "A", "changetype": "DELETE"}]}
    logger.info("Deleting DNS record: %s", fqdn)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.patch(f"{base_url}/zones/{zone}", json=body,
                               headers={"X-API-Key": cfg["pdns_api_key"]})
    except Exception:
        logger.warning("DNS deletion failed for %s", hostname, exc_info=True)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

async def get_s3_deploy_settings() -> dict[str, str]:
    """Get S3 settings for the sidecar container."""
    cfg = await get_s3_settings()
    return {
        "S3_ENDPOINT": cfg.get("object_storage_endpoint", "http://localhost:9000"),
        "S3_ACCESS_KEY": cfg.get("object_storage_access_key", "minioadmin"),
        "S3_SECRET_KEY": cfg.get("object_storage_secret_key", "minioadmin"),
        "S3_USE_SSL": cfg.get("object_storage_use_ssl", "false"),
    }


# ---------------------------------------------------------------------------
# App registry helpers
# ---------------------------------------------------------------------------

async def get_app_by_type(session: AsyncSession, app_type: str) -> ArgusApp:
    """Get an app by type, raising 404 if not found or disabled."""
    result = await session.execute(
        select(ArgusApp).where(ArgusApp.app_type == app_type)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_type}' not found")
    if not app.enabled:
        raise HTTPException(status_code=403, detail=f"App '{app_type}' is disabled")
    return app


async def seed_apps(session: AsyncSession) -> None:
    """Seed default apps if not present."""
    defaults = [
        {
            "app_type": "vscode",
            "display_name": "VS Code Server",
            "description": "Browser-based VS Code with S3 workspace storage",
            "icon": "Code",
            "template_dir": "vscode",
            "default_namespace": "argus-apps",
            "hostname_pattern": "argus-vscode-{username}.argus-insight.{domain}",
        },
    ]
    for d in defaults:
        result = await session.execute(
            select(ArgusApp).where(ArgusApp.app_type == d["app_type"])
        )
        if result.scalar_one_or_none() is None:
            session.add(ArgusApp(**d))
            logger.info("Seeded app: %s", d["app_type"])
    await session.commit()


# ---------------------------------------------------------------------------
# Instance lifecycle
# ---------------------------------------------------------------------------

async def get_instance(
    session: AsyncSession, app: ArgusApp, user_id: int
) -> ArgusAppInstance | None:
    """Get the user's latest active instance for a specific app."""
    result = await session.execute(
        select(ArgusAppInstance).where(
            ArgusAppInstance.app_id == app.id,
            ArgusAppInstance.user_id == user_id,
            ArgusAppInstance.status.notin_(["deleted"]),
        ).order_by(ArgusAppInstance.id.desc())
    )
    return result.scalars().first()


async def get_instance_by_instance_id(
    session: AsyncSession, instance_id: str,
) -> ArgusAppInstance | None:
    """Get an instance by its unique short ID."""
    result = await session.execute(
        select(ArgusAppInstance).where(ArgusAppInstance.instance_id == instance_id)
    )
    return result.scalar_one_or_none()


async def launch_instance(
    session: AsyncSession,
    app: ArgusApp,
    user_id: int,
    username: str,
    domain: str,
) -> ArgusAppInstance:
    """Deploy an app instance for the user."""
    # Check for existing active instance
    existing = await get_instance(session, app, user_id)
    if existing and existing.status in ("deploying", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Instance already exists with status: {existing.status}",
        )

    # Clean up failed/deleting instances
    if existing:
        await session.delete(existing)
        await session.flush()

    short_id = generate_instance_id()
    hostname = build_hostname(app, short_id, domain)
    namespace = app.default_namespace

    instance = ArgusAppInstance(
        instance_id=short_id,
        app_id=app.id,
        user_id=user_id,
        username=username,
        app_type=app.app_type,
        domain=domain,
        k8s_namespace=namespace,
        hostname=hostname,
        status="deploying",
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance)

    asyncio.create_task(
        _deploy_instance(instance.id, short_id, app.app_type, app.template_dir,
                         username, domain, hostname, namespace)
    )
    return instance


async def _update_steps(pk: int, steps: list[dict]) -> None:
    """Persist deploy steps to the instance record."""
    async with async_session() as session:
        result = await session.execute(
            select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
        )
        inst = result.scalar_one_or_none()
        if inst:
            inst.deploy_steps = json.dumps(steps)
            await session.commit()


async def _deploy_instance(
    pk: int,
    instance_id: str,
    app_type: str,
    template_dir: str,
    username: str,
    domain: str,
    hostname: str,
    namespace: str,
) -> None:
    """Background task to deploy K8s resources and update status."""
    steps: list[dict] = []

    async def _step(name: str, coro):
        """Run a step, record result, and abort on failure."""
        steps.append({"step": name, "status": "running", "message": ""})
        await _update_steps(pk, steps)
        try:
            result = await coro
            steps[-1] = {"step": name, "status": "completed", "message": "Done"}
            await _update_steps(pk, steps)
            return result
        except Exception as e:
            steps[-1] = {"step": name, "status": "failed", "message": str(e)[:200]}
            await _update_steps(pk, steps)
            raise

    try:
        s3 = await _step("Prepare S3 storage", _prepare_s3(username))

        await _step("Create namespace", ensure_namespace(namespace))

        async with async_session() as session:
            pdns_cfg = await _get_pdns_settings(session)
        server_ip = pdns_cfg.get("pdns_ip", "127.0.0.1")

        app = ArgusApp(app_type=app_type, template_dir=template_dir,
                       default_namespace=namespace, display_name="", hostname_pattern="")

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
        }

        manifests = render_manifests(app, variables)
        await _step("Apply K8s manifests", kubectl_apply(manifests))

        async with async_session() as session:
            await _step("Register DNS", register_dns(session, hostname, server_ip))

        ready = await _step("Wait for deployment ready",
                            _wait_for_deployment(app_type, instance_id, namespace))

        if not ready:
            steps.append({"step": "Deployment readiness", "status": "failed", "message": "Timed out"})
            await _update_steps(pk, steps)

        async with async_session() as session:
            result = await session.execute(
                select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "running" if ready else "failed"
                inst.deploy_steps = json.dumps(steps)
                await session.commit()

        logger.info("App %s instance %s deployed: status=%s", app_type, hostname,
                     "running" if ready else "failed")

    except Exception:
        logger.error("Failed to deploy %s for %s", app_type, username, exc_info=True)
        async with async_session() as session:
            result = await session.execute(
                select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "failed"
                inst.deploy_steps = json.dumps(steps)
                await session.commit()


async def _prepare_s3(username: str) -> dict[str, str]:
    """Prepare S3 bucket and return deploy settings."""
    s3 = await get_s3_deploy_settings()
    bucket_name = f"user-{username}"
    await ensure_bucket(bucket_name)
    return s3


async def _wait_for_deployment(app_type: str, instance_id: str, namespace: str, timeout: int = 180) -> bool:
    """Wait for the deployment to become ready."""
    resource = f"deployment/argus-{app_type}-{instance_id}"
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "rollout", "status", resource,
        f"--namespace={namespace}",
        f"--timeout={timeout}s",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning("Rollout failed for %s: %s", resource, stderr.decode().strip())
        return False
    logger.info("Deployment %s ready", resource)
    return True


async def destroy_instance(
    session: AsyncSession, app: ArgusApp, user_id: int
) -> None:
    """Destroy the user's app instance."""
    instance = await get_instance(session, app, user_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"No {app.display_name} instance found")

    instance.status = "deleting"
    await session.commit()

    asyncio.create_task(
        _destroy_instance(
            instance.id, instance.instance_id, app.app_type, app.template_dir,
            instance.username, instance.domain, instance.hostname, instance.k8s_namespace,
        )
    )


async def _destroy_instance(
    pk: int,
    instance_id: str,
    app_type: str,
    template_dir: str,
    username: str,
    domain: str,
    hostname: str,
    namespace: str,
) -> None:
    """Background task to delete K8s resources with step-by-step tracking."""
    steps: list[dict] = []

    async def _step(name: str, coro):
        """Run a destruction step, record result, continue on failure."""
        steps.append({"step": name, "status": "running", "message": ""})
        await _update_steps(pk, steps)
        try:
            result = await coro
            steps[-1] = {"step": name, "status": "completed", "message": "Done"}
            await _update_steps(pk, steps)
            return result
        except Exception as e:
            msg = str(e)[:200]
            steps[-1] = {"step": name, "status": "failed", "message": msg}
            await _update_steps(pk, steps)
            logger.warning("Destroy step '%s' failed for %s/%s: %s", name, app_type, username, msg)
            # Continue — best-effort cleanup
            return None

    has_errors = False
    try:
        s3 = await get_s3_deploy_settings()

        async with async_session() as session:
            pdns_cfg = await _get_pdns_settings(session)
        server_ip = pdns_cfg.get("pdns_ip", "127.0.0.1")

        app = ArgusApp(app_type=app_type, template_dir=template_dir,
                       default_namespace=namespace, display_name="", hostname_pattern="")

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
        }

        # Step 1: Delete K8s manifests (Ingress, Service, Deployment, Secret)
        manifests = render_manifests(app, variables)
        await _step("Delete K8s resources", kubectl_delete(manifests))

        # Step 2: Verify pods are terminated
        await _step("Verify pods terminated", _verify_pods_deleted(app_type, instance_id, namespace))

        # Step 3: Delete DNS record
        async with async_session() as session:
            await _step("Delete DNS record", delete_dns(session, hostname))

        has_errors = any(s["status"] == "failed" for s in steps)

        # Final status
        final_status = "deleted" if not has_errors else "failed"
        async with async_session() as session:
            result = await session.execute(
                select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = final_status
                inst.deploy_steps = json.dumps(steps)
                await session.commit()

        if has_errors:
            logger.warning("App %s instance %s destroyed with errors", app_type, hostname)
        else:
            logger.info("App %s instance %s destroyed successfully", app_type, hostname)

    except Exception:
        logger.error("Failed to destroy %s for %s", app_type, username, exc_info=True)
        async with async_session() as session:
            result = await session.execute(
                select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
            )
            inst = result.scalar_one_or_none()
            if inst:
                inst.status = "failed"
                inst.deploy_steps = json.dumps(steps)
                await session.commit()


async def _verify_pods_deleted(app_type: str, instance_id: str, namespace: str, timeout: int = 60) -> None:
    """Wait until pods for the deployment are fully terminated."""
    label = f"app.kubernetes.io/name=code-server,app.kubernetes.io/instance={instance_id}"
    deadline = asyncio.get_event_loop().time() + timeout

    while asyncio.get_event_loop().time() < deadline:
        proc = await asyncio.create_subprocess_exec(
            "kubectl", "get", "pods", "-n", namespace, "-l", label,
            "--no-headers", "-o", "custom-columns=NAME:.metadata.name",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        pods = stdout.decode().strip()
        if not pods:
            logger.info("All pods terminated for %s-%s in %s", app_type, instance_id, namespace)
            return
        logger.info("Waiting for pods to terminate: %s", pods.replace("\n", ", "))
        await asyncio.sleep(3)

    remaining = pods if pods else "unknown"
    raise RuntimeError(f"Pods not terminated after {timeout}s: {remaining}")
