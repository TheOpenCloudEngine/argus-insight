"""User management API endpoints.

Defines the FastAPI router for user and role management operations.
All endpoints are prefixed with `/usermgr` and tagged for OpenAPI grouping.

Endpoint summary:
- GET    /check-user             - Check username/email uniqueness.
- POST   /users                  - Create a new user.
- GET    /users                  - List users with filters and pagination.
- GET    /users/{user_id}        - Get a single user by ID.
- PUT    /users/{user_id}        - Modify user profile fields.
- DELETE /users/{user_id}        - Delete a user permanently.
- PUT    /users/{user_id}/role   - Change a user's role.
- PUT    /users/{user_id}/activate   - Activate a user account.
- PUT    /users/{user_id}/deactivate - Deactivate a user account.
- GET    /roles                  - List all available roles.

All endpoints use dependency injection for the async database session
(`get_session`) and delegate business logic to the service module.
HTTP errors (400, 404) are raised when validation fails or resources
are not found.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.usermgr import service
from app.usermgr.schemas import (
    PaginatedUserResponse,
    RoleResponse,
    UserAddRequest,
    UserChangeRoleRequest,
    UserModifyRequest,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usermgr", tags=["usermgr"])


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.get("/check-user")
async def check_user_exists(
    username: str | None = Query(None, description="Username to check"),
    email: str | None = Query(None, description="Email to check"),
    session: AsyncSession = Depends(get_session),
):
    """Check if a username or email already exists.

    Used by the UI for real-time uniqueness validation when creating a new user.
    At least one of `username` or `email` must be provided; otherwise returns 400.

    Returns a JSON object with boolean flags:
        { "username_exists": true/false, "email_exists": true/false }
    Only the requested fields are included in the response.
    """
    if not username and not email:
        raise HTTPException(status_code=400, detail="Provide username or email")
    return await service.check_user_exists(session, username=username, email=email)


@router.post("/users", response_model=UserResponse)
async def add_user(req: UserAddRequest, session: AsyncSession = Depends(get_session)):
    """Create a new user.

    Accepts user profile data and credentials. The password is hashed before
    storage. The specified role must exist in the database; otherwise returns 400.
    New users are created with "active" status by default.

    Returns the created user with resolved role name.
    """
    try:
        return await service.add_user(session, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users", response_model=PaginatedUserResponse)
async def list_users(
    status: str | None = Query(None, description="Filter by status (active/inactive)"),
    role: str | None = Query(None, description="Filter by role name (Admin/User)"),
    search: str | None = Query(None, description="Search username, name, email, phone"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=0, le=1000, description="Items per page (0 = all)"),
    session: AsyncSession = Depends(get_session),
):
    """List users with optional filters and pagination.

    Supports three types of filtering (all optional, combinable):
    - status: Exact match on account status ("active" or "inactive").
    - role:   Exact match on role name ("Admin" or "User").
    - search: Case-insensitive partial match (ILIKE '%search%') across
              username, first_name, last_name, email, and phone_number.

    Results are ordered by creation date (newest first) and paginated
    according to the `page` and `page_size` parameters.
    """
    return await service.list_users(
        session, status=status, role=role, search=search, page=page, page_size=page_size
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Get user by ID.

    Returns the full user profile including resolved role name.
    Returns 404 if the user does not exist.
    """
    user = await service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def modify_user(
    user_id: int, req: UserModifyRequest, session: AsyncSession = Depends(get_session)
):
    """Modify user profile fields.

    Accepts partial updates — only provided fields are changed.
    Username and role cannot be modified through this endpoint.
    Returns the updated user profile, or 404 if the user does not exist.
    """
    user = await service.modify_user(session, user_id, req)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a user.

    Permanently removes the user account from the database.
    This operation is irreversible. Returns 404 if the user does not exist.
    """
    if not await service.delete_user(session, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok", "message": "User deleted"}


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: int, req: UserChangeRoleRequest, session: AsyncSession = Depends(get_session)
):
    """Change a user's role.

    Updates the user's role_id to point to the specified role.
    Returns 400 if the role name is invalid, or 404 if the user does not exist.
    """
    try:
        user = await service.change_role(session, user_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Activate a user account.

    Sets the user's status to "active", allowing them to log in.
    Returns the updated user profile, or 404 if the user does not exist.
    """
    user = await service.activate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Deactivate a user account.

    Sets the user's status to "inactive", preventing login.
    The account is preserved and can be reactivated later.
    Returns the updated user profile, or 404 if the user does not exist.
    """
    user = await service.deactivate_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Role endpoints
# ---------------------------------------------------------------------------

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(session: AsyncSession = Depends(get_session)):
    """List all roles.

    Returns all role records ordered by ID. Used by the UI to populate
    role selection dropdowns and filter options.
    """
    return await service.list_roles(session)
