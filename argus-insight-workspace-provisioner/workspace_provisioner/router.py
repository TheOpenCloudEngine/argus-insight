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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from workspace_provisioner import service
from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.schemas import (
    PaginatedWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceCredentialResponse,
    WorkspaceDeleteRequest,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkflowExecutionResponse,
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
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List workspaces with optional status filter and pagination."""
    logger.info("GET /workspaces - status=%s, page=%d, page_size=%d", status, page, page_size)
    return await service.list_workspaces(session, status=status, page=page, page_size=page_size)


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
    session: AsyncSession = Depends(get_session),
):
    """Remove a member from a workspace."""
    logger.info("DELETE /workspaces/%d/members/%d", workspace_id, member_id)
    if not await service.remove_member(session, member_id):
        logger.info("DELETE /workspaces/%d/members/%d - not found", workspace_id, member_id)
        raise HTTPException(status_code=404, detail="Member not found")
    logger.info("DELETE /workspaces/%d/members/%d - removed", workspace_id, member_id)
    return {"status": "ok", "message": "Member removed"}


# ---------------------------------------------------------------------------
# Workflow status endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/workflow",
    response_model=list[WorkflowExecutionResponse],
)
async def get_workflow_status(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get provisioning workflow execution status for a workspace.

    Returns all workflow executions (most recent first) with detailed
    step-by-step status. Use this to monitor provisioning progress
    after creating a workspace.
    """
    logger.info("GET /workspaces/%d/workflow", workspace_id)
    return await service.get_workflow_status(session, workspace_id)
