"""User management schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class RoleName(str, Enum):
    """Available role names."""

    ADMIN = "Admin"
    USER = "User"


# ---------------------------------------------------------------------------
# Role schemas
# ---------------------------------------------------------------------------

class RoleResponse(BaseModel):
    """Role information returned to the client."""

    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# User request schemas
# ---------------------------------------------------------------------------

class UserAddRequest(BaseModel):
    """Request to create a new user."""

    username: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str | None = Field(None, max_length=30)
    password: str = Field(..., min_length=4, max_length=128)
    role: RoleName = Field(RoleName.USER, description="Role name (Admin or User)")


class UserModifyRequest(BaseModel):
    """Request to modify user profile fields."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=30)


class UserChangeRoleRequest(BaseModel):
    """Request to change a user's role."""

    role: RoleName


# ---------------------------------------------------------------------------
# User response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """User information returned to the client."""

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    phone_number: str | None = None
    status: UserStatus
    role: str
    created_at: datetime
    updated_at: datetime
