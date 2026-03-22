"""User management schemas.

Pydantic models for request validation and response serialization in the
user management module. Organized into three sections:

1. **Enums**: UserStatus and RoleName enumerations.
2. **Role schemas**: RoleResponse for listing available roles.
3. **User schemas**: Request models (add, modify, change role) and response
   models (single user, paginated list).

All request models use Pydantic's Field for validation constraints (min/max length,
email format, etc.). Response models use snake_case field names matching the
database column names.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserStatus(str, Enum):
    """User account status.

    - ACTIVE:   The user can log in and use the platform.
    - INACTIVE: The user account is disabled and cannot log in.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class RoleName(str, Enum):
    """Available role identifiers.

    These values must match the `role_id` column in the `argus_roles` table
    and the Keycloak realm role names.
    """

    ADMIN = "argus-admin"
    SUPERUSER = "argus-superuser"
    USER = "argus-user"


# ---------------------------------------------------------------------------
# Role schemas
# ---------------------------------------------------------------------------

class RoleResponse(BaseModel):
    """Role information returned to the client."""

    id: int
    role_id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# User request schemas
# ---------------------------------------------------------------------------

class UserAddRequest(BaseModel):
    """Request to create a new user.

    All fields except phone_number are required. The username and email
    must be unique across all existing users (enforced by the service layer
    and database constraints).

    Fields:
        username:     Unique login identifier (1-100 chars).
        email:        Valid email address (validated by Pydantic's EmailStr).
        first_name:   User's first name (1-100 chars).
        last_name:    User's last name (1-100 chars).
        phone_number: Optional contact phone number (max 30 chars).
        password:     Plaintext password (4-128 chars). Will be hashed before storage.
        role:         Role to assign (defaults to "User" if not specified).
    """

    username: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str | None = Field(None, max_length=30)
    password: str = Field(..., min_length=4, max_length=128)
    role: RoleName = Field(RoleName.USER, description="Role name (Admin or User)")


class UserModifyRequest(BaseModel):
    """Request to modify user profile fields.

    Only provided (non-None) fields will be updated; omitted fields remain
    unchanged. Username and role cannot be modified through this endpoint —
    use the dedicated change-role endpoint for role changes.

    Fields:
        first_name:   Updated first name (1-100 chars).
        last_name:    Updated last name (1-100 chars).
        email:        Updated email address.
        phone_number: Updated phone number (max 30 chars).
    """

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=30)


class UserChangeRoleRequest(BaseModel):
    """Request to change a user's role.

    The new role must be one of the values defined in the RoleName enum.
    The service layer resolves the role name to a role_id in the database.
    """

    role: RoleName


# ---------------------------------------------------------------------------
# User response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """User information returned to the client.

    Contains all user profile fields plus the resolved role name (not role_id).
    The `status` field uses the UserStatus enum for type safety.
    Timestamps are serialized as ISO 8601 datetime strings.

    Fields:
        id:           Unique user identifier (database primary key).
        username:     Login identifier.
        email:        Email address.
        first_name:   First (given) name.
        last_name:    Last (family) name.
        phone_number: Contact phone number (may be null).
        status:       Account status (active/inactive).
        role:         Role name string (e.g., "Admin", "User").
        created_at:   Account creation timestamp.
        updated_at:   Last modification timestamp.
    """

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


class PaginatedUserResponse(BaseModel):
    """Paginated list of users.

    Returned by the GET /users endpoint. Contains the current page of user
    records along with metadata for building pagination controls.

    Fields:
        items:     Array of UserResponse objects for the current page.
        total:     Total number of users matching the applied filters.
        page:      Current page number (1-based).
        page_size: Number of items per page.
    """

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
