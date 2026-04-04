"""Pydantic schemas for resource profile API."""

from datetime import datetime

from pydantic import BaseModel, Field


class ResourceProfileCreateRequest(BaseModel):
    """Request body for creating a resource profile."""

    name: str = Field(..., max_length=100)
    description: str | None = None
    cpu_cores: float = Field(..., gt=0, description="Total CPU cores (e.g. 8.0)")
    memory_gb: float = Field(..., gt=0, description="Total memory in GB (e.g. 16.0)")
    is_default: bool = False


class ResourceProfileUpdateRequest(BaseModel):
    """Request body for updating a resource profile."""

    name: str | None = Field(None, max_length=100)
    description: str | None = None
    cpu_cores: float | None = Field(None, gt=0)
    memory_gb: float | None = Field(None, gt=0)
    is_default: bool | None = None


class ResourceProfileResponse(BaseModel):
    """Response body for a resource profile."""

    id: int
    name: str
    display_name: str | None = None
    description: str | None
    cpu_cores: float
    memory_gb: float
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ServiceResourceItem(BaseModel):
    """Resource usage of an individual service."""

    plugin_name: str
    display_name: str | None
    service_id: str | None
    cpu_cores: float
    memory_gb: float


class WorkspaceResourceUsageResponse(BaseModel):
    """Resource usage summary for a workspace."""

    profile: ResourceProfileResponse | None
    cpu_used: float
    cpu_limit: float | None
    memory_used_gb: float
    memory_limit_gb: float | None
    services: list[ServiceResourceItem]


class AssignProfileRequest(BaseModel):
    """Request body for assigning a profile to a workspace."""

    profile_id: int | None = Field(
        None, description="Profile ID to assign, or null to remove assignment"
    )
