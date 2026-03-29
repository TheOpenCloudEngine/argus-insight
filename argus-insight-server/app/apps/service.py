"""App instance lifecycle and authentication service.

Orchestrates deploy/destroy of per-user app instances.
Delegates K8s, DNS, and S3 operations to workspace_provisioner modules.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apps.models import ArgusApp, ArgusAppInstance
from app.core.database import async_session

logger = logging.getLogger(__name__)

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
    """Extract instance_id from hostname like argus-vscode-f7a3b2c1.dev.net."""
    if not host:
        return None
    prefix = f"argus-{app.app_type}-"
    first_part = host.split(".")[0]
    if first_part.startswith(prefix):
        return first_part[len(prefix):]
    return None


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
            "hostname_pattern": "argus-vscode-{instance_id}.{domain}",
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
# Instance queries
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


# ---------------------------------------------------------------------------
# Step tracking
# ---------------------------------------------------------------------------

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


async def _set_status(pk: int, status: str, steps: list[dict] | None = None) -> None:
    """Update instance status (and optionally steps)."""
    async with async_session() as session:
        result = await session.execute(
            select(ArgusAppInstance).where(ArgusAppInstance.id == pk)
        )
        inst = result.scalar_one_or_none()
        if inst:
            inst.status = status
            if steps is not None:
                inst.deploy_steps = json.dumps(steps)
            await session.commit()


# ---------------------------------------------------------------------------
# Instance lifecycle — deploy
# ---------------------------------------------------------------------------

async def launch_instance(
    session: AsyncSession,
    app: ArgusApp,
    user_id: int,
    username: str,
    domain: str,
) -> ArgusAppInstance:
    """Deploy an app instance for the user."""
    existing = await get_instance(session, app, user_id)
    if existing and existing.status in ("deploying", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Instance already exists with status: {existing.status}",
        )

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
                         user_id, username, domain, hostname, namespace)
    )
    return instance


async def _deploy_instance(
    pk: int,
    instance_id: str,
    app_type: str,
    template_dir: str,
    user_id: int,
    username: str,
    domain: str,
    hostname: str,
    namespace: str,
) -> None:
    """Background task to deploy K8s resources and update status."""
    from workspace_provisioner.workflow.steps.app_deploy import (
        build_variables, deploy_manifests, ensure_namespace,
        get_server_ip, prepare_s3, register_app_dns, wait_for_ready,
    )

    steps: list[dict] = []

    async def _step(name: str, coro):
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
        s3 = await _step("Prepare S3 storage", prepare_s3(username, user_id))
        await _step("Create namespace", ensure_namespace(namespace))

        async with async_session() as session:
            server_ip = await get_server_ip(session)

        # Find workspace bucket for this user
        workspace_bucket = ""
        try:
            from sqlalchemy import select as sa_select
            from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
            async with async_session() as ws_session:
                ws_result = await ws_session.execute(
                    sa_select(ArgusWorkspace.name).join(
                        ArgusWorkspaceMember,
                        ArgusWorkspaceMember.workspace_id == ArgusWorkspace.id,
                    ).where(
                        ArgusWorkspaceMember.user_id == user_id,
                        ArgusWorkspace.status == "active",
                    ).limit(1)
                )
                ws_name = ws_result.scalar()
                if ws_name:
                    workspace_bucket = f"workspace-{ws_name}"
        except Exception:
            pass

        variables = await build_variables(
            username, instance_id, app_type, namespace, hostname, domain, s3, server_ip,
            workspace_bucket=workspace_bucket,
        )

        await _step("Apply K8s manifests", deploy_manifests(template_dir, variables))

        async with async_session() as session:
            await _step("Register DNS", register_app_dns(session, hostname, server_ip))

        ready = await _step("Wait for deployment ready",
                            wait_for_ready(app_type, instance_id, namespace))

        if not ready:
            steps.append({"step": "Deployment readiness", "status": "failed", "message": "Timed out"})

        await _set_status(pk, "running" if ready else "failed", steps)
        logger.info("App %s instance %s deployed: status=%s", app_type, hostname,
                     "running" if ready else "failed")

    except Exception:
        logger.error("Failed to deploy %s for %s", app_type, username, exc_info=True)
        await _set_status(pk, "failed", steps)


# ---------------------------------------------------------------------------
# Instance lifecycle — destroy
# ---------------------------------------------------------------------------

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
            user_id, instance.username, instance.domain, instance.hostname, instance.k8s_namespace,
        )
    )


async def _destroy_instance(
    pk: int,
    instance_id: str,
    app_type: str,
    template_dir: str,
    user_id: int,
    username: str,
    domain: str,
    hostname: str,
    namespace: str,
) -> None:
    """Background task to delete K8s resources with step-by-step tracking."""
    from workspace_provisioner.workflow.steps.app_deploy import (
        build_variables, delete_app_dns, delete_manifests,
        get_server_ip, prepare_s3, verify_pods_deleted,
    )

    steps: list[dict] = []

    async def _step(name: str, coro):
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
            return None

    try:
        s3 = await prepare_s3(username, user_id)

        async with async_session() as session:
            server_ip = await get_server_ip(session)

        variables = await build_variables(
            username, instance_id, app_type, namespace, hostname, domain, s3, server_ip,
        )

        await _step("Delete K8s resources", delete_manifests(template_dir, variables))
        await _step("Verify pods terminated", verify_pods_deleted(app_type, instance_id, namespace))

        async with async_session() as session:
            await _step("Delete DNS record", delete_app_dns(session, hostname))

        has_errors = any(s["status"] == "failed" for s in steps)
        final_status = "deleted" if not has_errors else "failed"
        await _set_status(pk, final_status, steps)

        if has_errors:
            logger.warning("App %s instance %s destroyed with errors", app_type, hostname)
        else:
            logger.info("App %s instance %s destroyed successfully", app_type, hostname)

    except Exception:
        logger.error("Failed to destroy %s for %s", app_type, username, exc_info=True)
        await _set_status(pk, "failed", steps)
