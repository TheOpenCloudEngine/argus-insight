"""User management service.

Provides CRUD operations for users and roles against the database.
"""

import hashlib
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.usermgr.models import ArgusRole, ArgusUser
from app.usermgr.schemas import (
    RoleName,
    RoleResponse,
    UserAddRequest,
    UserChangeRoleRequest,
    UserModifyRequest,
    UserResponse,
    UserStatus,
)

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


async def _get_role_by_name(session: AsyncSession, name: str) -> ArgusRole | None:
    """Look up a role by name."""
    result = await session.execute(select(ArgusRole).where(ArgusRole.name == name))
    return result.scalars().first()


async def _build_user_response(session: AsyncSession, user: ArgusUser) -> UserResponse:
    """Build a UserResponse from an ORM user object, resolving role name."""
    result = await session.execute(select(ArgusRole).where(ArgusRole.id == user.role_id))
    role = result.scalars().first()
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        status=UserStatus(user.status),
        role=role.name if role else "Unknown",
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

async def add_user(session: AsyncSession, req: UserAddRequest) -> UserResponse:
    """Create a new user."""
    role = await _get_role_by_name(session, req.role.value)
    if not role:
        raise ValueError(f"Role '{req.role.value}' not found")

    user = ArgusUser(
        username=req.username,
        email=req.email,
        first_name=req.first_name,
        last_name=req.last_name,
        phone_number=req.phone_number,
        password_hash=_hash_password(req.password),
        status=UserStatus.ACTIVE.value,
        role_id=role.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("User created: %s (id=%d)", user.username, user.id)
    return await _build_user_response(session, user)


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    logger.info("User deleted: %s (id=%d)", user.username, user.id)
    return True


async def modify_user(
    session: AsyncSession, user_id: int, req: UserModifyRequest
) -> UserResponse | None:
    """Modify user profile fields."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    if req.first_name is not None:
        user.first_name = req.first_name
    if req.last_name is not None:
        user.last_name = req.last_name
    if req.email is not None:
        user.email = req.email
    if req.phone_number is not None:
        user.phone_number = req.phone_number

    await session.commit()
    await session.refresh(user)
    logger.info("User modified: %s (id=%d)", user.username, user.id)
    return await _build_user_response(session, user)


async def change_role(
    session: AsyncSession, user_id: int, req: UserChangeRoleRequest
) -> UserResponse | None:
    """Change a user's role."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    role = await _get_role_by_name(session, req.role.value)
    if not role:
        raise ValueError(f"Role '{req.role.value}' not found")

    user.role_id = role.id
    await session.commit()
    await session.refresh(user)
    logger.info("User role changed: %s -> %s (id=%d)", user.username, req.role.value, user.id)
    return await _build_user_response(session, user)


async def activate_user(session: AsyncSession, user_id: int) -> UserResponse | None:
    """Activate a user account."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    user.status = UserStatus.ACTIVE.value
    await session.commit()
    await session.refresh(user)
    logger.info("User activated: %s (id=%d)", user.username, user.id)
    return await _build_user_response(session, user)


async def deactivate_user(session: AsyncSession, user_id: int) -> UserResponse | None:
    """Deactivate a user account."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    user.status = UserStatus.INACTIVE.value
    await session.commit()
    await session.refresh(user)
    logger.info("User deactivated: %s (id=%d)", user.username, user.id)
    return await _build_user_response(session, user)


async def get_user(session: AsyncSession, user_id: int) -> UserResponse | None:
    """Get a single user by ID."""
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None
    return await _build_user_response(session, user)


async def list_users(
    session: AsyncSession,
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
) -> list[UserResponse]:
    """List users with optional filtering.

    Args:
        status: Filter by user status ('active' or 'inactive').
        role: Filter by role name ('Admin' or 'User'). Joins with argus_roles.
        search: LIKE search across username, first_name, last_name, email, phone_number.
    """
    query = select(ArgusUser).join(ArgusRole, ArgusUser.role_id == ArgusRole.id)

    if status:
        query = query.where(ArgusUser.status == status)

    if role:
        query = query.where(ArgusRole.name == role)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                ArgusUser.username.ilike(pattern),
                ArgusUser.first_name.ilike(pattern),
                ArgusUser.last_name.ilike(pattern),
                ArgusUser.email.ilike(pattern),
                ArgusUser.phone_number.ilike(pattern),
            )
        )

    query = query.order_by(ArgusUser.created_at.desc())
    result = await session.execute(query)
    users = result.scalars().all()
    return [await _build_user_response(session, u) for u in users]


# ---------------------------------------------------------------------------
# Role operations
# ---------------------------------------------------------------------------

async def list_roles(session: AsyncSession) -> list[RoleResponse]:
    """List all roles."""
    result = await session.execute(select(ArgusRole).order_by(ArgusRole.id))
    roles = result.scalars().all()
    return [RoleResponse.model_validate(r) for r in roles]


async def seed_roles(session: AsyncSession) -> None:
    """Insert default roles (Admin, User) if they do not exist."""
    for name, desc in [
        (RoleName.ADMIN.value, "Administrator with full access"),
        (RoleName.USER.value, "Standard user with limited access"),
    ]:
        existing = await _get_role_by_name(session, name)
        if not existing:
            session.add(ArgusRole(name=name, description=desc))
            logger.info("Seeded role: %s", name)
    await session.commit()
