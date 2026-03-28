"""App instance lifecycle API endpoints.

All endpoints use {app_type} path parameter to identify the app,
making this router fully generic — no app-specific code needed.
"""

import logging

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apps import service
from app.apps.models import ArgusApp, ArgusAppInstance
from app.apps.schemas import (
    InstanceDestroyResponse,
    InstanceLaunchResponse,
    InstanceStatusResponse,
    MyInstanceResponse,
)
from app.core.auth import CurrentUser
from app.core.database import get_session
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/instances", tags=["apps-instances"])


# ---------------------------------------------------------------------------
# Instance lifecycle
# ---------------------------------------------------------------------------

@router.get("/{app_type}/status", response_model=InstanceStatusResponse)
async def get_status(
    app_type: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get current user's instance status for the given app type."""
    app = await service.get_app_by_type(session, app_type)
    instance = await service.get_instance(session, app, int(user.sub))

    if not instance or instance.status == "deleted":
        return InstanceStatusResponse(exists=False)

    import json
    steps = []
    if instance.deploy_steps:
        try:
            steps = json.loads(instance.deploy_steps)
        except Exception:
            pass

    return InstanceStatusResponse(
        exists=True,
        instance_id=instance.instance_id,
        status=instance.status,
        hostname=instance.hostname,
        url=f"https://{instance.hostname}",
        app_type=app_type,
        deploy_steps=steps,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


@router.post("/{app_type}/launch", response_model=InstanceLaunchResponse)
async def launch(
    app_type: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Deploy an app instance for the current user."""
    app = await service.get_app_by_type(session, app_type)

    # Get domain from configuration
    result = await session.execute(
        select(ArgusConfiguration).where(
            ArgusConfiguration.category == "domain",
            ArgusConfiguration.config_key == "domain_name",
        )
    )
    row = result.scalar_one_or_none()
    if not row or not row.config_value:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Domain not configured. Please configure it in Settings > Domain.",
        )

    instance = await service.launch_instance(
        session, app, int(user.sub), user.username, row.config_value,
    )

    return InstanceLaunchResponse(
        status=instance.status,
        hostname=instance.hostname,
        url=f"https://{instance.hostname}",
        message=f"{app.display_name} is being deployed. This may take a minute.",
    )


@router.delete("/{app_type}/destroy", response_model=InstanceDestroyResponse)
async def destroy(
    app_type: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Destroy the current user's app instance."""
    app = await service.get_app_by_type(session, app_type)
    await service.destroy_instance(session, app, int(user.sub))
    return InstanceDestroyResponse(
        status="deleting",
        message=f"{app.display_name} is being destroyed.",
    )


# ---------------------------------------------------------------------------
# Auth (Nginx Ingress auth-url subrequest)
# ---------------------------------------------------------------------------

@router.get("/{app_type}/auth-verify")
async def auth_verify(
    app_type: str,
    request: Request,
    argus_app_token: str | None = Cookie(None),
    x_original_url: str | None = Header(None),
    x_forwarded_host: str | None = Header(None),
    x_original_host: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Nginx Ingress auth-url subrequest endpoint."""
    if not argus_app_token:
        logger.info("Auth verify: no cookie for %s", app_type)
        return Response(status_code=401)

    app = await service.get_app_by_type(session, app_type)

    # Nginx Ingress sends X-Original-URL (e.g. https://argus-vscode-admin.dev.net/...)
    # Extract the hostname from it if available
    host = ""
    if x_original_url:
        from urllib.parse import urlparse
        parsed = urlparse(x_original_url)
        host = parsed.hostname or ""
    if not host:
        host = x_original_host or x_forwarded_host or request.headers.get("host", "")

    if service.verify_auth(argus_app_token, host, app):
        return Response(status_code=200)

    logger.info("Auth verify: token mismatch for %s host=%s", app_type, host)
    return Response(status_code=401)


@router.get("/{app_type}/auth-launch")
async def auth_launch(
    app_type: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Generate a launch URL that the browser opens directly on the backend.

    Returns a URL like http://server:4500/api/v1/apps/instances/vscode/auth-redirect?token=xxx
    The browser navigates there, the backend sets the cookie and redirects to the app.
    """
    app = await service.get_app_by_type(session, app_type)
    instance = await service.get_instance(session, app, int(user.sub))

    if not instance or instance.status != "running":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No running {app.display_name} instance found.")

    app_token = service.create_app_token(
        user.username, instance.instance_id, app_type, user.role,
    )

    return {"token": app_token}


@router.get("/{app_type}/auth-redirect")
async def auth_redirect(
    app_type: str,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Browser navigates here directly (not via Next.js proxy).

    Validates the app token, sets the auth cookie, and redirects to the app instance.
    No JWT auth required — the app token in the query string is the credential.
    """
    payload = service.verify_app_token(token)
    if not payload:
        return Response(content="Invalid or expired token", status_code=401)

    token_app_type = payload.get("app_type")
    token_instance_id = payload.get("instance_id")
    if token_app_type != app_type:
        return Response(content="Token app_type mismatch", status_code=401)

    instance = await service.get_instance_by_instance_id(session, token_instance_id)

    if not instance or instance.status != "running":
        return Response(content="No running instance found", status_code=404)

    redirect_url = f"https://{instance.hostname}"
    cookie_domain = f".{instance.domain}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="argus_app_token",
        value=token,
        domain=cookie_domain,
        path="/",
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


# ---------------------------------------------------------------------------
# My instances (across all apps)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[MyInstanceResponse])
async def my_instances(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """List all app instances for the current user."""
    result = await session.execute(
        select(ArgusAppInstance, ArgusApp)
        .join(ArgusApp, ArgusAppInstance.app_id == ArgusApp.id)
        .where(
            ArgusAppInstance.user_id == int(user.sub),
            ArgusAppInstance.status.notin_(["deleted"]),
        )
    )
    items = []
    for instance, app in result.all():
        items.append(MyInstanceResponse(
            id=instance.id,
            app_type=instance.app_type,
            display_name=app.display_name,
            icon=app.icon,
            hostname=instance.hostname,
            url=f"https://{instance.hostname}",
            status=instance.status,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        ))
    return items
