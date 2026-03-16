"""User management service.

Provides CRUD operations for users and roles against the database.
"""

import hashlib
import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.usermgr.models import ArgusRole, ArgusUser
from app.usermgr.schemas import (
    PaginatedUserResponse,
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

async def check_user_exists(
    session: AsyncSession, username: str | None = None, email: str | None = None
) -> dict[str, bool]:
    """Check if a username or email already exists."""
    result: dict[str, bool] = {}
    if username:
        row = await session.execute(
            select(ArgusUser).where(ArgusUser.username == username)
        )
        result["username_exists"] = row.scalars().first() is not None
    if email:
        row = await session.execute(
            select(ArgusUser).where(ArgusUser.email == email)
        )
        result["email_exists"] = row.scalars().first() is not None
    return result


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
    page: int = 1,
    page_size: int = 10,
) -> PaginatedUserResponse:
    """List users with optional filtering and pagination.

    Args:
        status: Filter by user status ('active' or 'inactive').
        role: Filter by role name ('Admin' or 'User'). Joins with argus_roles.
        search: LIKE search across username, first_name, last_name, email, phone_number.
        page: Page number (1-based).
        page_size: Number of items per page.
    """
    base = (
        select(ArgusUser, ArgusRole.name.label("role_name"))
        .join(ArgusRole, ArgusUser.role_id == ArgusRole.id)
    )

    if status:
        base = base.where(ArgusUser.status.in_([status]))

    if role:
        base = base.where(ArgusRole.name.in_([role]))

    if search:
        pattern = f"%{search}%"
        base = base.where(
            or_(
                ArgusUser.username.ilike(pattern),
                ArgusUser.first_name.ilike(pattern),
                ArgusUser.last_name.ilike(pattern),
                ArgusUser.email.ilike(pattern),
                ArgusUser.phone_number.ilike(pattern),
            )
        )

    # Count total matching rows
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Apply ordering and pagination
    offset = (page - 1) * page_size
    query = base.order_by(ArgusUser.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.all()

    items = [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            status=UserStatus(user.status),
            role=role_name or "Unknown",
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user, role_name in rows
    ]

    return PaginatedUserResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


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
