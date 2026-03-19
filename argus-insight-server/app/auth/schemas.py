"""Authentication schemas."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Login response with access token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")


class UserInfo(BaseModel):
    """Current user information."""

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    phone_number: str = ""
    role: str = "user"


class UserSelfUpdateRequest(BaseModel):
    """Request to update the current user's own profile."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=30)
