"""FastAPI router for resource profile management."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.resource_profile import service
from app.resource_profile.schemas import (
    AssignProfileRequest,
    ResourceProfileCreateRequest,
    ResourceProfileResponse,
    ResourceProfileUpdateRequest,
    WorkspaceResourceUsageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resource-profiles", tags=["resource-profiles"])


@router.post("", response_model=ResourceProfileResponse, status_code=201)
async def create_profile(
    req: ResourceProfileCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new resource profile."""
    return await service.create_resource_profile(session, req)


@router.get("", response_model=list[ResourceProfileResponse])
async def list_profiles(session: AsyncSession = Depends(get_session)):
    """List all resource profiles."""
    return await service.list_resource_profiles(session)


@router.get("/{profile_id}", response_model=ResourceProfileResponse)
async def get_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a resource profile by ID."""
    p = await service.get_resource_profile(session, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


@router.put("/{profile_id}", response_model=ResourceProfileResponse)
async def update_profile(
    profile_id: int,
    req: ResourceProfileUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update a resource profile."""
    p = await service.update_resource_profile(session, profile_id, req)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a resource profile."""
    deleted = await service.delete_resource_profile(session, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")


# ── Workspace-level endpoints ────────────────────────────────────


workspace_router = APIRouter(prefix="/workspace/workspaces", tags=["workspace-resources"])


@workspace_router.put("/{workspace_id}/resource-profile")
async def assign_workspace_profile(
    workspace_id: int,
    req: AssignProfileRequest,
    session: AsyncSession = Depends(get_session),
):
    """Assign or remove a resource profile for a workspace."""
    ok = await service.assign_profile_to_workspace(session, workspace_id, req.profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True, "workspace_id": workspace_id, "profile_id": req.profile_id}


@workspace_router.get(
    "/{workspace_id}/resource-usage",
    response_model=WorkspaceResourceUsageResponse,
)
async def get_workspace_resource_usage(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get resource usage summary for a workspace."""
    usage = await service.get_workspace_resource_usage(session, workspace_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return usage
