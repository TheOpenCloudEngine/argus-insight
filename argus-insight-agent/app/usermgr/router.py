"""User management API routes."""

from fastapi import APIRouter, HTTPException

from app.usermgr.schemas import (
    BackupResult,
    GroupInfo,
    OperationResult,
    SudoGrantRequest,
    UserCreateRequest,
    UserDetail,
    UserInfo,
)
from app.usermgr.service import (
    backup_user_files,
    create_user,
    delete_user,
    get_user_detail,
    grant_sudo,
    list_groups,
    list_users,
)

router = APIRouter(prefix="/user", tags=["user"])


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


@router.post("/backup", response_model=BackupResult)
async def user_backup() -> BackupResult:
    """Backup /etc/passwd, /etc/shadow, /etc/group, /etc/gshadow."""
    return backup_user_files()


# ---------------------------------------------------------------------------
# Sudo
# ---------------------------------------------------------------------------


@router.put("/sudo", response_model=OperationResult)
async def user_sudo_grant(request: SudoGrantRequest) -> OperationResult:
    """Grant sudo privileges to a user."""
    return await grant_sudo(request.username)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserInfo])
async def user_list() -> list[UserInfo]:
    """List all users from /etc/passwd."""
    return list_users()


@router.get("/users/{username}", response_model=UserDetail)
async def user_detail(username: str) -> UserDetail:
    """Get detailed user info including group membership."""
    detail = get_user_detail(username)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"User not found: {username}")
    return detail


@router.post("/users", response_model=OperationResult)
async def user_create(request: UserCreateRequest) -> OperationResult:
    """Create a new system user."""
    return await create_user(
        username=request.username,
        group=request.group,
        shell=request.shell,
        create_home=request.create_home,
        home=request.home,
        comment=request.comment,
    )


@router.delete("/users/{username}", response_model=OperationResult)
async def user_delete(username: str, remove_home: bool = False) -> OperationResult:
    """Delete a system user."""
    return await delete_user(username, remove_home=remove_home)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@router.get("/groups", response_model=list[GroupInfo])
async def group_list() -> list[GroupInfo]:
    """List all groups from /etc/group."""
    return list_groups()
