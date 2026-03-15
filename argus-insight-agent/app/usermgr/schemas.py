"""User management schemas."""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class OperationResult(BaseModel):
    """Generic success/failure result."""

    success: bool
    message: str


class BackupResult(BaseModel):
    """Result of a file backup operation."""

    success: bool
    backup_path: str
    message: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserInfo(BaseModel):
    """Parsed user entry from /etc/passwd."""

    username: str
    uid: int
    gid: int
    comment: str = ""
    home: str = ""
    shell: str = ""


class UserDetail(BaseModel):
    """Detailed user information including group membership."""

    username: str
    uid: int
    gid: int
    comment: str = ""
    home: str = ""
    shell: str = ""
    primary_group: str = ""
    groups: list[str] = Field(default_factory=list)
    has_sudo: bool = False


class UserCreateRequest(BaseModel):
    """Request to create a new user."""

    username: str = Field(..., description="Username to create")
    group: str | None = Field(None, description="Primary group (default: same as username)")
    shell: str = Field("/bin/bash", description="Login shell")
    create_home: bool = Field(True, description="Create home directory")
    home: str | None = Field(None, description="Home directory path (default: /home/<username>)")
    comment: str = Field("", description="User comment (GECOS field)")


class UserDeleteRequest(BaseModel):
    """Request to delete a user."""

    username: str = Field(..., description="Username to delete")
    remove_home: bool = Field(False, description="Remove home directory and mail spool")


class SudoGrantRequest(BaseModel):
    """Request to grant sudo privileges to a user."""

    username: str = Field(..., description="Username to grant sudo")


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class GroupInfo(BaseModel):
    """Parsed group entry from /etc/group."""

    groupname: str
    gid: int
    members: list[str] = Field(default_factory=list)
