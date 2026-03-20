"""Pydantic request/response schemas for VS Code Server."""

from datetime import datetime

from pydantic import BaseModel, Field


class VscodeStatusResponse(BaseModel):
    """Response for GET /vscode/status."""

    exists: bool = Field(description="Whether an instance exists for this user")
    status: str | None = Field(None, description="Instance status if exists")
    hostname: str | None = Field(None, description="Full hostname if exists")
    url: str | None = Field(None, description="Full URL to access code-server")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VscodeLaunchResponse(BaseModel):
    """Response for POST /vscode/launch."""

    status: str = Field(description="Instance status after launch")
    hostname: str = Field(description="Full hostname")
    url: str = Field(description="Full URL to access code-server")
    message: str = Field(description="Human-readable status message")


class VscodeDestroyResponse(BaseModel):
    """Response for DELETE /vscode/destroy."""

    status: str
    message: str


class VscodeAuthCookieResponse(BaseModel):
    """Response for GET /vscode/auth-cookie (redirect happens before this)."""

    redirect_url: str
