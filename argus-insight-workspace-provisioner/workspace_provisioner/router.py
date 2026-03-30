"""Workspace provisioning API endpoints.

Defines the FastAPI router for workspace lifecycle management.
All endpoints are prefixed with `/workspace` and tagged for OpenAPI grouping.

Endpoint summary:
- POST   /workspaces                          - Create workspace and trigger provisioning
- GET    /workspaces                          - List workspaces with pagination
- GET    /workspaces/{workspace_id}           - Get workspace details
- DELETE /workspaces/{workspace_id}           - Delete a workspace
- POST   /workspaces/{workspace_id}/members   - Add a member
- GET    /workspaces/{workspace_id}/members   - List members
- DELETE /workspaces/{workspace_id}/members/{member_id} - Remove a member
- GET    /workspaces/{workspace_id}/workflow   - Get provisioning workflow status
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from workspace_provisioner import service
from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.schemas import (
    AuditLogResponse,
    PaginatedAuditLogResponse,
    WorkspaceServiceResponse,
    PaginatedWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceCredentialResponse,
    WorkspaceDeleteRequest,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspacePipelineResponse,
    WorkspaceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["workspace"])

# GitLab client singleton - initialized by init_gitlab_client()
_gitlab_client: GitLabClient | None = None


def init_gitlab_client(url: str, private_token: str) -> None:
    """Initialize the GitLab client singleton.

    Called during application startup with configuration values.

    Args:
        url: GitLab server URL (e.g., "https://gitlab-global.argus-insight.dev.net").
        private_token: GitLab API token with admin privileges.
    """
    global _gitlab_client
    logger.info("Initializing GitLab client: %s", url)
    _gitlab_client = GitLabClient(url=url, private_token=private_token)
    logger.info("GitLab client initialized successfully")


def _get_gitlab_client() -> GitLabClient:
    """FastAPI dependency to get the GitLab client."""
    if _gitlab_client is None:
        logger.error("GitLab client not initialized, returning 503")
        raise HTTPException(
            status_code=503, detail="GitLab client not initialized"
        )
    return _gitlab_client


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------

@router.get("/workspaces/check")
async def check_workspace_name(
    name: str = Query(..., description="Workspace name to check"),
    session: AsyncSession = Depends(get_session),
):
    """Check if a workspace name already exists (excluding deleted)."""
    from workspace_provisioner.models import ArgusWorkspace
    result = await session.execute(
        select(ArgusWorkspace).where(
            ArgusWorkspace.name == name,
            ArgusWorkspace.status != "deleted",
        )
    )
    ws = result.scalars().first()
    return {"exists": ws is not None, "name": name}


# ---------------------------------------------------------------------------
# Workspace service auth (must be before /workspaces/{workspace_id})
# ---------------------------------------------------------------------------

import base64
import hashlib
import hmac
import json as json_module
import time
from urllib.parse import urlparse

from fastapi import Cookie, Header, Request, Response

_WS_AUTH_SECRET = "argus-workspace-auth-secret-key"
_WS_AUTH_EXPIRY = 86400  # 24 hours


def _create_ws_token(username: str, workspace_name: str, role: str) -> str:
    payload = {
        "sub": username, "workspace": workspace_name,
        "role": role, "exp": int(time.time()) + _WS_AUTH_EXPIRY,
    }
    payload_json = json_module.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
    sig = hmac.new(_WS_AUTH_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(json_module.dumps({"payload": payload_b64, "sig": sig}).encode()).decode()


def _verify_ws_token(token: str, workspace_name: str) -> dict | None:
    try:
        outer = json_module.loads(base64.urlsafe_b64decode(token))
        payload_b64 = outer["payload"]
        expected_sig = hmac.new(_WS_AUTH_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(outer["sig"], expected_sig):
            return None
        payload = json_module.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        if payload.get("workspace") != workspace_name:
            return None
        return payload
    except Exception:
        return None


@router.get("/workspaces/auth-verify")
async def workspace_auth_verify(
    request: Request,
    workspace: str = Query(""),
    service_id: str = Query(""),
    argus_ws_token: str | None = Cookie(None),
    x_original_url: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Nginx Ingress auth-url subrequest endpoint for workspace services.

    Supports both workspace name and service_id based lookups.
    With service_id hostnames, the service_id is extracted from the hostname
    and mapped to the workspace name via argus_workspace_services.
    """
    if not argus_ws_token:
        return Response(status_code=401)

    ws_name = workspace

    # If no workspace name, try to resolve from service_id
    if not ws_name and service_id:
        from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
        svc_result = await session.execute(
            select(ArgusWorkspaceService).where(
                ArgusWorkspaceService.service_id == service_id
            )
        )
        svc = svc_result.scalars().first()
        if svc:
            ws_result = await session.execute(
                select(ArgusWorkspace.name).where(ArgusWorkspace.id == svc.workspace_id)
            )
            ws_name = ws_result.scalar() or ""

    # Fallback: extract from X-Original-URL hostname
    if not ws_name and x_original_url:
        parsed = urlparse(x_original_url)
        host = parsed.hostname or ""
        parts = host.split(".")
        if parts:
            prefix_parts = parts[0].split("-")
            if len(prefix_parts) >= 3:
                # Try service_id lookup from hostname (e.g., argus-mlflow-67e8a400a3f1)
                potential_sid = prefix_parts[-1]
                from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
                svc_result = await session.execute(
                    select(ArgusWorkspaceService).where(
                        ArgusWorkspaceService.service_id == potential_sid
                    )
                )
                svc = svc_result.scalars().first()
                if svc:
                    ws_result = await session.execute(
                        select(ArgusWorkspace.name).where(
                            ArgusWorkspace.id == svc.workspace_id
                        )
                    )
                    ws_name = ws_result.scalar() or ""

    if not ws_name:
        return Response(status_code=401)
    payload = _verify_ws_token(argus_ws_token, ws_name)
    if payload:
        return Response(status_code=200)
    return Response(status_code=403)


@router.get("/workspaces/auth-launch")
async def workspace_auth_launch(
    current_user: CurrentUser,
    workspace_name: str = Query(..., alias="workspace"),
    session: AsyncSession = Depends(get_session),
):
    """Generate an auth token for accessing workspace services."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.name == workspace_name)
    )
    ws = result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    member_result = await session.execute(
        select(ArgusWorkspaceMember).where(
            ArgusWorkspaceMember.workspace_id == ws.id,
            ArgusWorkspaceMember.user_id == int(current_user.sub),
        )
    )
    if not member_result.scalars().first():
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    token = _create_ws_token(current_user.username, workspace_name, current_user.role)
    return {"token": token, "workspace": workspace_name}


@router.get("/workspaces/auth-redirect")
async def workspace_auth_redirect(
    workspace: str = Query(...),
    token: str = Query(...),
    redirect: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Browser navigates here. Sets cookie and redirects to service."""
    payload = _verify_ws_token(token, workspace)
    if not payload:
        return Response(content="Invalid or expired token", status_code=401)
    from app.settings.service import get_config_by_category
    domain_cfg = await get_config_by_category(session, "domain")
    domain = domain_cfg.get("domain_name", "")
    redirect_url = redirect or "/"
    response = Response(status_code=302, headers={"Location": redirect_url})
    response.set_cookie(
        key="argus_ws_token", value=token,
        domain=f".{domain}" if domain else None,
        path="/", max_age=_WS_AUTH_EXPIRY, httponly=False, samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------

@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_workspace(
    req: WorkspaceCreateRequest,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Create a new workspace and trigger the provisioning workflow.

    The workspace is created immediately with status "provisioning".
    The provisioning workflow (GitLab project creation, etc.) runs
    asynchronously in the background. Use the GET workflow endpoint
    to monitor progress.
    """
    logger.info("POST /workspaces - name=%s, domain=%s", req.name, req.domain)
    try:
        result = await service.create_workspace(session, req, gitlab_client)
        logger.info("POST /workspaces - workspace created: id=%d, name=%s", result.id, result.name)
        return result
    except ValueError as e:
        logger.error("POST /workspaces - failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workspaces", response_model=PaginatedWorkspaceResponse)
async def list_workspaces(
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by name or display name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List workspaces with optional status/search filter and pagination."""
    logger.info("GET /workspaces - status=%s, search=%s, page=%d, page_size=%d", status, search, page, page_size)
    return await service.list_workspaces(session, status=status, search=search, page=page, page_size=page_size)


@router.get("/workspaces/my")
async def list_my_workspaces(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """List workspaces where the current user is a member."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
    user_id = int(current_user.sub)
    result = await session.execute(
        select(ArgusWorkspace)
        .join(ArgusWorkspaceMember, ArgusWorkspaceMember.workspace_id == ArgusWorkspace.id)
        .where(ArgusWorkspaceMember.user_id == user_id)
        .where(ArgusWorkspace.status != "deleted")
        .order_by(ArgusWorkspace.name)
    )
    workspaces = result.scalars().all()
    return [
        {"id": ws.id, "name": ws.name, "display_name": ws.display_name, "status": ws.status}
        for ws in workspaces
    ]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get workspace details by ID."""
    logger.info("GET /workspaces/%d", workspace_id)
    ws = await service.get_workspace(session, workspace_id)
    if not ws:
        logger.info("GET /workspaces/%d - not found", workspace_id)
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


class DeployPipelineRequest(BaseModel):
    pipeline_id: int


@router.post("/workspaces/{workspace_id}/deploy")
async def deploy_pipeline_to_workspace(
    workspace_id: int,
    req: DeployPipelineRequest,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Deploy a pipeline to an existing workspace."""
    import asyncio
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspacePipeline
    from workspace_provisioner.schemas import WorkspaceCreateRequest

    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check workspace is not already deploying or deleting
    if ws.status == "provisioning":
        raise HTTPException(status_code=400, detail="A deployment is already in progress for this workspace.")
    if ws.status == "deleting":
        raise HTTPException(status_code=400, detail="This workspace is being deleted.")

    # Add pipeline association
    ws_pipeline = ArgusWorkspacePipeline(
        workspace_id=workspace_id,
        pipeline_id=req.pipeline_id,
        deploy_order=0,
        status="pending",
    )
    session.add(ws_pipeline)
    await session.commit()

    # Build a minimal WorkspaceCreateRequest for the provisioning workflow
    fake_req = WorkspaceCreateRequest(
        name=ws.name,
        display_name=ws.display_name,
        domain=ws.domain,
        admin_user_id=ws.created_by,
        pipeline_ids=[req.pipeline_id],
    )

    # Update workspace status
    ws.status = "provisioning"
    await session.commit()

    # Load creator info
    from app.usermgr.models import ArgusUser
    from app.settings.service import get_config_by_category
    creator_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == ws.created_by)
    )
    creator = creator_result.scalars().first()
    creator_info = {}
    if creator:
        gitlab_cfg = await get_config_by_category(session, "gitlab")
        creator_info = {
            "creator_username": creator.username,
            "creator_email": creator.email,
            "creator_name": f"{creator.first_name} {creator.last_name}".strip() or creator.username,
            "creator_password": gitlab_cfg.get("gitlab_password", "") or "Argus!nsight2026",
            "admin_user_id": ws.created_by,
        }

    # Launch provisioning in background
    asyncio.create_task(
        service._run_provisioning_workflow(workspace_id, fake_req, gitlab_client, creator_info)
    )

    logger.info("Deploy pipeline %d to workspace %d", req.pipeline_id, workspace_id)
    return {"status": "ok", "message": f"Pipeline deployment started for workspace '{ws.name}'"}


@router.delete("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def delete_workspace(
    workspace_id: int,
    req: WorkspaceDeleteRequest = WorkspaceDeleteRequest(),
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Delete a workspace and tear down all provisioned resources.

    Sets the workspace status to "deleting" and launches a teardown
    workflow in the background. Use the GET workflow endpoint to
    monitor deletion progress.
    """
    logger.info("DELETE /workspaces/%d", workspace_id)
    try:
        result = await service.delete_workspace(session, workspace_id, gitlab_client, req)
        if not result:
            logger.info("DELETE /workspaces/%d - not found", workspace_id)
            raise HTTPException(status_code=404, detail="Workspace not found")
        logger.info("DELETE /workspaces/%d - deletion started", workspace_id)
        return result
    except ValueError as e:
        logger.error("DELETE /workspaces/%d - failed: %s", workspace_id, e)
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Credential endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/credentials",
    response_model=WorkspaceCredentialResponse,
)
async def get_workspace_credentials(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get service credentials and connection info for a workspace.

    Returns credentials generated during provisioning (GitLab URLs,
    MinIO keys, Airflow password, etc.). Only available after
    provisioning completes successfully.
    """
    logger.info("GET /workspaces/%d/credentials", workspace_id)
    cred = await service.get_workspace_credentials(session, workspace_id)
    if not cred:
        logger.info("GET /workspaces/%d/credentials - not found", workspace_id)
        raise HTTPException(status_code=404, detail="Credentials not found")
    return cred


# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/services",
    response_model=list[WorkspaceServiceResponse],
)
async def get_workspace_services(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all services deployed to a workspace."""
    from workspace_provisioner.models import ArgusWorkspaceService

    result = await session.execute(
        select(ArgusWorkspaceService)
        .where(ArgusWorkspaceService.workspace_id == workspace_id)
        .order_by(ArgusWorkspaceService.created_at)
    )
    services = result.scalars().all()
    return [
        WorkspaceServiceResponse(
            id=s.id, workspace_id=s.workspace_id,
            plugin_name=s.plugin_name, service_id=s.service_id,
            display_name=s.display_name,
            version=s.version, endpoint=s.endpoint,
            username=s.username, password=s.password,
            access_token=s.access_token, status=s.status,
            metadata=s.metadata_json,
            created_at=s.created_at, updated_at=s.updated_at,
        ) for s in services
    ]


@router.delete("/workspaces/{workspace_id}/services/{service_id}")
async def delete_workspace_service(
    workspace_id: int,
    service_id: int,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a workspace service: teardown K8s resources, DNS, DB record, audit log."""
    try:
        await service.delete_workspace_service_with_teardown(
            session=session,
            workspace_id=workspace_id,
            service_db_id=service_id,
            actor_user_id=int(current_user.sub),
            actor_username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Pipeline association endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/pipelines",
    response_model=list[WorkspacePipelineResponse],
)
async def get_workspace_pipelines(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get pipelines associated with a workspace."""
    from workspace_provisioner.models import ArgusWorkspacePipeline
    from workspace_provisioner.plugins.models import ArgusPipeline

    result = await session.execute(
        select(ArgusWorkspacePipeline)
        .where(ArgusWorkspacePipeline.workspace_id == workspace_id)
        .order_by(ArgusWorkspacePipeline.deploy_order)
    )
    ws_pipelines = result.scalars().all()

    responses = []
    for wp in ws_pipelines:
        # Load pipeline name
        p_result = await session.execute(
            select(ArgusPipeline).where(ArgusPipeline.id == wp.pipeline_id)
        )
        pipeline = p_result.scalars().first()
        responses.append(WorkspacePipelineResponse(
            id=wp.id,
            pipeline_id=wp.pipeline_id,
            pipeline_name=pipeline.name if pipeline else None,
            pipeline_display_name=pipeline.display_name if pipeline else None,
            deploy_order=wp.deploy_order,
            status=wp.status,
            created_at=wp.created_at,
        ))
    return responses


# ---------------------------------------------------------------------------
# Membership endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
)
async def add_member(
    workspace_id: int,
    req: WorkspaceMemberAddRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a member to a workspace."""
    logger.info("POST /workspaces/%d/members - user_id=%d, role=%s", workspace_id, req.user_id, req.role)
    ws = await service.get_workspace(session, workspace_id)
    if not ws:
        logger.error("POST /workspaces/%d/members - workspace not found", workspace_id)
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await service.add_member(session, workspace_id, req)


class BulkAddMembersRequest(BaseModel):
    user_ids: list[int]


@router.post(
    "/workspaces/{workspace_id}/members/bulk",
    response_model=list[WorkspaceMemberResponse],
)
async def bulk_add_members(
    workspace_id: int,
    req: BulkAddMembersRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Add multiple members to a workspace with GitLab provisioning.

    For each user:
    1. Check if GitLab user exists (argus-{username}), create if not.
    2. Add as project member (Maintainer level = all except delete repo).
    3. Create project access token.
    4. Add to workspace members.
    """
    import secrets
    from app.usermgr.models import ArgusUser
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember

    # Load workspace
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    results = []
    for user_id in req.user_ids:
        # Check if already a member
        existing = await session.execute(
            select(ArgusWorkspaceMember).where(
                ArgusWorkspaceMember.workspace_id == workspace_id,
                ArgusWorkspaceMember.user_id == user_id,
            )
        )
        if existing.scalars().first():
            continue

        # Load user info
        user_result = await session.execute(
            select(ArgusUser).where(ArgusUser.id == user_id)
        )
        user = user_result.scalars().first()
        if not user:
            continue

        gitlab_username = f"argus-{user.username}"
        gitlab_token = None
        token_name = None

        try:
            # Step 1: Ensure GitLab user exists
            gl_user = await gitlab_client.find_user(gitlab_username)
            if not gl_user:
                safe_password = secrets.token_urlsafe(12) + "!A1a"
                gl_user = await gitlab_client.create_user(
                    username=gitlab_username,
                    password=safe_password,
                    email=user.email or f"{gitlab_username}@argus.local",
                    name=f"{user.first_name} {user.last_name}".strip() or gitlab_username,
                )
                # Save gitlab credentials
                user.gitlab_username = gitlab_username
                user.gitlab_password = safe_password

            # Resolve GitLab project ID from workspace record or service metadata
            gl_project_id = ws.gitlab_project_id
            if not gl_project_id:
                from workspace_provisioner.models import ArgusWorkspaceService
                svc_result = await session.execute(
                    select(ArgusWorkspaceService).where(
                        ArgusWorkspaceService.workspace_id == workspace_id,
                        ArgusWorkspaceService.plugin_name == "argus-gitlab",
                    )
                )
                gl_svc = svc_result.scalars().first()
                if gl_svc and gl_svc.metadata_json:
                    internal = gl_svc.metadata_json.get("internal", gl_svc.metadata_json)
                    gl_project_id = internal.get("project_id")

            # Step 2: Add to project as Maintainer (all permissions except delete repo)
            if gl_project_id:
                await gitlab_client.add_project_member(
                    project_id=gl_project_id,
                    user_id=gl_user["id"],
                    access_level=40,  # Maintainer
                )

                # Step 3: Create project access token
                token_name = f"{gitlab_username}-{ws.name}"
                try:
                    token_info = await gitlab_client.create_project_access_token(
                        project_id=gl_project_id,
                        name=token_name,
                    )
                    gitlab_token = token_info["token"]
                except Exception as e:
                    logger.warning("Failed to create token for %s: %s", gitlab_username, e)

        except Exception as e:
            logger.warning("GitLab provisioning failed for user %d: %s", user_id, e)

        # Step 4: MinIO user creation + workspace bucket access
        minio_provisioned = False
        try:
            from app.settings.service import get_config_by_category
            cfg = await get_config_by_category(session, "argus")
            minio_endpoint = cfg.get("object_storage_endpoint", "")
            minio_access = cfg.get("object_storage_access_key", "")
            minio_secret = cfg.get("object_storage_secret_key", "")
            minio_ssl = cfg.get("object_storage_use_ssl", "false").lower() == "true"

            if minio_endpoint and minio_access and minio_secret:
                from workspace_provisioner.minio.client import MinioAdminClient
                from workspace_provisioner.config import MinioWorkspaceConfig

                ws_config_cfg = await get_config_by_category(session, "deploy_mapping")
                bucket_prefix = "workspace-"  # default
                minio_ep = minio_endpoint.replace("http://", "").replace("https://", "")
                minio_client = MinioAdminClient(
                    endpoint=minio_ep,
                    root_user=minio_access,
                    root_password=minio_secret,
                    secure=minio_ssl,
                )

                bucket_name = f"{bucket_prefix}{ws.name}"
                minio_username = f"user-{user.username}"

                # Create MinIO user (idempotent - returns created=False if exists)
                user_secret = secrets.token_urlsafe(16)
                user_info = await minio_client.create_user(minio_username, user_secret)

                # Set bucket policy for workspace bucket
                await minio_client.set_user_bucket_policy(minio_username, bucket_name)

                # Save S3 credentials if this is a new user
                if user_info.get("created") and not user.s3_access_key:
                    user.s3_access_key = minio_username
                    user.s3_secret_key = user_secret
                    user.s3_bucket = bucket_name

                minio_provisioned = True
                logger.info(
                    "MinIO access granted for member %s: user=%s bucket=%s",
                    user.username, minio_username, bucket_name,
                )
        except Exception as e:
            logger.warning("MinIO provisioning failed for user %d: %s", user_id, e)

        # Step 5: Add workspace member
        member = ArgusWorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role="User",
            gitlab_access_token=gitlab_token,
            gitlab_token_name=token_name,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        resp = await service._build_member_response(session, member, ws.created_by)
        results.append(resp)

        # Audit log
        await service.log_audit(
            session, workspace_id, ws.name, "member_added",
            actor_user_id=int(current_user.sub), actor_username=current_user.username,
            target_user_id=user_id, target_username=user.username,
            detail={
                "role": "User",
                "gitlab_provisioned": gitlab_token is not None,
                "minio_provisioned": minio_provisioned,
            },
        )

    logger.info("Bulk added %d members to workspace %d", len(results), workspace_id)
    return results


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def list_members(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List all members of a workspace."""
    logger.info("GET /workspaces/%d/members", workspace_id)
    return await service.list_members(session, workspace_id)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
async def remove_member(
    workspace_id: int,
    member_id: int,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Remove a member from a workspace and GitLab project."""
    from app.usermgr.models import ArgusUser
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember

    logger.info("DELETE /workspaces/%d/members/%d", workspace_id, member_id)

    # Load member
    member_result = await session.execute(
        select(ArgusWorkspaceMember).where(ArgusWorkspaceMember.id == member_id)
    )
    member = member_result.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing workspace owner
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if ws and ws.created_by == member.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    # Load user info
    user_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == member.user_id)
    )
    user = user_result.scalars().first()

    # Resolve GitLab project ID (workspace record or service metadata)
    gl_project_id = ws.gitlab_project_id if ws else None
    if not gl_project_id and ws:
        from workspace_provisioner.models import ArgusWorkspaceService
        svc_result = await session.execute(
            select(ArgusWorkspaceService).where(
                ArgusWorkspaceService.workspace_id == workspace_id,
                ArgusWorkspaceService.plugin_name == "argus-gitlab",
            )
        )
        gl_svc = svc_result.scalars().first()
        if gl_svc and gl_svc.metadata_json:
            internal = gl_svc.metadata_json.get("internal", gl_svc.metadata_json)
            gl_project_id = internal.get("project_id")

    # Remove from GitLab project
    if gl_project_id and user:
        gitlab_username = f"argus-{user.username}"
        try:
            gl_user = await gitlab_client.find_user(gitlab_username)
            if gl_user:
                await gitlab_client.remove_project_member(
                    project_id=gl_project_id,
                    user_id=gl_user["id"],
                )
        except Exception as e:
            logger.warning("Failed to remove GitLab member: %s", e)

    # Remove from workspace
    if not await service.remove_member(session, member_id):
        raise HTTPException(status_code=404, detail="Member not found")

    # Audit log
    await service.log_audit(
        session, workspace_id, ws.name, "member_removed",
        actor_user_id=int(current_user.sub), actor_username=current_user.username,
        target_user_id=member.user_id, target_username=user.username if user else None,
        detail={"gitlab_removed": gl_project_id is not None},
    )

    logger.info("DELETE /workspaces/%d/members/%d - removed (with GitLab)", workspace_id, member_id)
    return {"status": "ok", "message": "Member removed"}


# ---------------------------------------------------------------------------
# Audit log endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/audit-logs",
    response_model=PaginatedAuditLogResponse,
)
async def get_workspace_audit_logs(
    workspace_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get audit logs for a specific workspace."""
    from sqlalchemy import func as sqlfunc
    from workspace_provisioner.models import ArgusWorkspaceAuditLog

    base = select(ArgusWorkspaceAuditLog).where(
        ArgusWorkspaceAuditLog.workspace_id == workspace_id
    )
    count_q = select(sqlfunc.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(ArgusWorkspaceAuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    logs = result.scalars().all()

    return PaginatedAuditLogResponse(
        items=[
            AuditLogResponse(
                id=l.id, workspace_id=l.workspace_id, workspace_name=l.workspace_name,
                action=l.action, target_user_id=l.target_user_id,
                target_username=l.target_username, actor_user_id=l.actor_user_id,
                actor_username=l.actor_username, detail=l.detail,
                created_at=l.created_at,
            ) for l in logs
        ],
        total=total, page=page, page_size=page_size,
    )
