"""User management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.usermgr import service
from app.usermgr.schemas import (
    RoleResponse,
    UserAddRequest,
    UserChangeGroupRequest,
    UserChangeRoleRequest,
    UserModifyRequest,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usermgr", tags=["usermgr"])


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.post("/users", response_model=UserResponse)
async def add_user(req: UserAddRequest, session: AsyncSession = Depends(get_session)):
    """Create a new user."""
    try:
        return await service.add_user(session, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users", response_model=list[UserResponse])
async def list_users(session: AsyncSession = Depends(get_session)):
    """List all users."""
    return await service.list_users(session)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Get user by ID."""
    user = await service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def modify_user(
    user_id: int, req: UserModifyRequest, session: AsyncSession = Depends(get_session)
):
    """Modify user profile fields."""
    user = await service.modify_user(session, user_id, req)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a user."""
    if not await service.delete_user(session, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok", "message": "User deleted"}


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: int, req: UserChangeRoleRequest, session: AsyncSession = Depends(get_session)
):
    """Change a user's role."""
    try:
        user = await service.change_role(session, user_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Activate a user account."""
    user = await service.activate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Deactivate a user account."""
    user = await service.deactivate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/group", response_model=UserResponse)
async def change_group(
    user_id: int, req: UserChangeGroupRequest, session: AsyncSession = Depends(get_session)
):
    """Change a user's group."""
    user = await service.change_group(session, user_id, req)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Role endpoints
# ---------------------------------------------------------------------------

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(session: AsyncSession = Depends(get_session)):
    """List all roles."""
    return await service.list_roles(session)
