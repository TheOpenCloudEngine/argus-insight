"""VS Code Server API endpoints."""

import logging

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import get_session
from app.apps.vscode import service
from app.apps.vscode.schemas import (
    VscodeDestroyResponse,
    VscodeLaunchResponse,
    VscodeStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/vscode", tags=["vscode"])


@router.get("/status", response_model=VscodeStatusResponse)
async def get_status(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get current user's VS Code instance status."""
    instance = await service.get_instance_status(session, int(user.sub))

    if not instance or instance.status == "deleted":
        return VscodeStatusResponse(exists=False)

    url = f"https://{instance.hostname}"
    return VscodeStatusResponse(
        exists=True,
        status=instance.status,
        hostname=instance.hostname,
        url=url,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


@router.post("/launch", response_model=VscodeLaunchResponse)
async def launch(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Deploy a code-server instance for the current user.

    Reads the domain from the database configuration (category='domain',
    key='domain_name'). Creates K8s resources, registers DNS, and
    tracks the instance in the database.
    """
    # Get domain from settings
    from sqlalchemy import select
    from app.settings.models import ArgusConfiguration

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
    domain = row.config_value

    instance = await service.launch_instance(
        session,
        user_id=int(user.sub),
        username=user.username,
        domain=domain,
    )

    url = f"https://{instance.hostname}"
    return VscodeLaunchResponse(
        status=instance.status,
        hostname=instance.hostname,
        url=url,
        message="VS Code Server is being deployed. This may take a minute.",
    )


@router.delete("/destroy", response_model=VscodeDestroyResponse)
async def destroy(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Destroy the current user's code-server instance."""
    await service.destroy_instance(session, int(user.sub))
    return VscodeDestroyResponse(
        status="deleting",
        message="VS Code Server is being destroyed.",
    )


@router.get("/auth-verify")
async def auth_verify(
    request: Request,
    argus_vscode_token: str | None = Cookie(None),
    x_original_host: str | None = Header(None),
):
    """Nginx Ingress auth-url subrequest endpoint.

    Verifies the argus_vscode_token cookie and checks that the token's
    username matches the hostname being accessed.

    Returns 200 if authenticated, 401 otherwise.
    """
    if not argus_vscode_token:
        logger.info("Auth verify: no cookie")
        return Response(status_code=401)

    host = x_original_host or request.headers.get("host", "")
    if service.verify_vscode_auth(argus_vscode_token, host):
        return Response(status_code=200)

    logger.info("Auth verify: token mismatch for host %s", host)
    return Response(status_code=401)


@router.get("/auth-cookie")
async def auth_cookie(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Set authentication cookie and redirect to code-server.

    Creates an argus_vscode_token cookie scoped to .argus-insight.{domain}
    and redirects the user to their code-server URL.
    """
    instance = await service.get_instance_status(session, int(user.sub))

    if not instance or instance.status != "running":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="No running VS Code instance found.",
        )

    token = service.create_vscode_token(user.username, user.role)
    redirect_url = f"https://{instance.hostname}"
    cookie_domain = f".argus-insight.{instance.domain}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="argus_vscode_token",
        value=token,
        domain=cookie_domain,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400,
    )
    return response
