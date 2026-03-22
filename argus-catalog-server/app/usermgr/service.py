"""User management service.

Provides CRUD operations for users and roles against the database.
This is the business logic layer — called by the router endpoints and
responsible for all database interactions via SQLAlchemy async sessions.

Architecture notes:
- All public functions accept an AsyncSession as the first parameter.
- Functions that modify data call session.commit() and session.refresh()
  to persist changes and reload updated fields (e.g., updated_at).
- The _build_user_response() helper resolves the role_id foreign key to
  a role name string for the API response.
- Password hashing uses SHA-256 via the _hash_password() helper.
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
    """Hash a password using SHA-256.

    Encodes the plaintext password to UTF-8 bytes and returns the
    hexadecimal digest. Used when creating new users or changing passwords.
    """
    return hashlib.sha256(password.encode()).hexdigest()


async def _get_role_by_name(session: AsyncSession, name: str) -> ArgusRole | None:
    """Look up a role by its unique name.

    Args:
        session: Active database session.
        name: Role name to search for (e.g., "Admin", "User").

    Returns:
        The ArgusRole ORM instance if found, or None.
    """
    result = await session.execute(select(ArgusRole).where(ArgusRole.name == name))
    return result.scalars().first()


async def _build_user_response(session: AsyncSession, user: ArgusUser) -> UserResponse:
    """Build a UserResponse from an ORM user object, resolving role name.

    Performs an additional query to look up the role name from the role_id
    foreign key. Returns "Unknown" if the role record is missing (should
    not happen with proper foreign key constraints).

    Args:
        session: Active database session.
        user: The ArgusUser ORM instance to convert.

    Returns:
        A fully populated UserResponse Pydantic model.
    """
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
    """Check if a username or email already exists in the database.

    Performs exact-match queries against the argus_users table. Only checks
    the fields that are provided (non-None). Used for real-time uniqueness
    validation in the user creation form.

    Args:
        session:  Active database session.
        username: Username to check (optional).
        email:    Email to check (optional).

    Returns:
        Dictionary with boolean flags for each checked field.
        Example: {"username_exists": True, "email_exists": False}
    """
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
    """Create a new user account.

    Resolves the role name to a role_id, hashes the password, inserts the
    new user record, and returns the created user with resolved role name.

    Args:
        session: Active database session.
        req: Validated user creation request containing all required fields.

    Returns:
        The newly created user as a UserResponse.

    Raises:
        ValueError: If the specified role name does not exist in the database.
    """
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
    """Delete a user by ID. Returns True if deleted.

    Looks up the user by primary key, deletes the record if found,
    and commits the transaction. This operation is permanent.

    Args:
        session: Active database session.
        user_id: The primary key of the user to delete.

    Returns:
        True if the user was found and deleted, False if not found.
    """
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
    """Modify user profile fields.

    Applies partial updates — only non-None fields in the request are changed.
    Username and role_id are not modifiable through this function.

    Args:
        session: Active database session.
        user_id: The primary key of the user to modify.
        req: Partial update request with optional fields.

    Returns:
        The updated user as a UserResponse, or None if the user was not found.
    """
    result = await session.execute(select(ArgusUser).where(ArgusUser.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    # Apply only the fields that were explicitly provided in the request.
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
    """Change a user's role.

    Resolves the new role name to a role_id and updates the user's foreign key.

    Args:
        session: Active database session.
        user_id: The primary key of the user whose role to change.
        req: Request containing the new role name.

    Returns:
        The updated user as a UserResponse, or None if the user was not found.

    Raises:
        ValueError: If the specified role name does not exist in the database.
    """
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
    """Activate a user account.

    Sets the user's status to "active", allowing them to log in to the platform.

    Args:
        session: Active database session.
        user_id: The primary key of the user to activate.

    Returns:
        The updated user as a UserResponse, or None if the user was not found.
    """
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
    """Deactivate a user account.

    Sets the user's status to "inactive", preventing the user from logging in.
    The account is preserved and can be reactivated later via activate_user().

    Args:
        session: Active database session.
        user_id: The primary key of the user to deactivate.

    Returns:
        The updated user as a UserResponse, or None if the user was not found.
    """
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
    """Get a single user by ID.

    Looks up the user by primary key and returns the full profile
    with resolved role name.

    Args:
        session: Active database session.
        user_id: The primary key of the user to retrieve.

    Returns:
        The user as a UserResponse, or None if not found.
    """
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

    Builds a dynamic query based on the provided filter parameters:
    1. Joins argus_users with argus_roles to resolve role names.
    2. Applies optional WHERE clauses for status, role, and search.
    3. Counts total matching rows for pagination metadata.
    4. Orders by created_at DESC and applies OFFSET/LIMIT.

    Args:
        session:   Active database session.
        status:    Filter by user status ('active' or 'inactive').
                   Uses IN clause (currently single value, but extensible).
        role:      Filter by role name ('Admin' or 'User').
                   Uses IN clause for consistency with status filter.
        search:    Case-insensitive partial match (ILIKE '%search%') across
                   username, first_name, last_name, email, and phone_number.
                   The '%' wildcards are added automatically around the search term.
        page:      Page number (1-based). Defaults to 1.
        page_size: Number of items per page. Defaults to 10.

    Returns:
        PaginatedUserResponse with items, total count, page, and page_size.
    """
    # Base query: join users with roles to get role name in results.
    base = (
        select(ArgusUser, ArgusRole.name.label("role_name"))
        .join(ArgusRole, ArgusUser.role_id == ArgusRole.id)
    )

    # Filter by account status (exact match).
    if status:
        base = base.where(ArgusUser.status.in_([status]))

    # Filter by role name (exact match).
    if role:
        base = base.where(ArgusRole.name.in_([role]))

    # Free-text search across multiple fields using ILIKE for case-insensitive matching.
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

    # Count total matching rows (before pagination) for the response metadata.
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Apply ordering (newest first) and pagination (offset + limit).
    # page_size=0 means "return all rows" (no pagination).
    query = base.order_by(ArgusUser.created_at.desc())
    if page_size > 0:
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.all()

    # Map each (ArgusUser, role_name) tuple to a UserResponse Pydantic model.
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
    """List all roles.

    Returns all role records ordered by ID. Used by the UI to populate
    role dropdowns and filter options.

    Args:
        session: Active database session.

    Returns:
        List of RoleResponse models (converted from ArgusRole ORM objects).
    """
    result = await session.execute(select(ArgusRole).order_by(ArgusRole.id))
    roles = result.scalars().all()
    return [RoleResponse.model_validate(r) for r in roles]


async def seed_roles(session: AsyncSession) -> None:
    """Insert default roles (Admin, User) if they do not exist.

    Called during application startup (lifespan) to ensure the required
    roles are always present in the database. Skips roles that already exist
    to make this function idempotent (safe to call multiple times).

    Args:
        session: Active database session.
    """
    for name, desc in [
        (RoleName.ADMIN.value, "Administrator with full access"),
        (RoleName.USER.value, "Standard user with limited access"),
    ]:
        existing = await _get_role_by_name(session, name)
        if not existing:
            session.add(ArgusRole(name=name, description=desc))
            logger.info("Seeded role: %s", name)
    await session.commit()


async def seed_admin_user(session: AsyncSession) -> None:
    """Create a default admin user if no users exist (local auth mode).

    Only runs when auth_type is 'local' and the argus_users table is empty.
    Default credentials: admin / admin (should be changed after first login).
    """
    from app.core.config import settings
    if settings.auth_type != "local":
        return

    count = (await session.execute(select(func.count()).select_from(ArgusUser))).scalar() or 0
    if count > 0:
        return

    admin_role = await _get_role_by_name(session, RoleName.ADMIN.value)
    if not admin_role:
        return

    user = ArgusUser(
        username="admin",
        email="admin@argus.local",
        first_name="Admin",
        last_name="User",
        password_hash=_hash_password("admin"),
        status="active",
        role_id=admin_role.id,
    )
    session.add(user)
    await session.commit()
    logger.info("Seeded default admin user: admin/admin (change password after first login)")
