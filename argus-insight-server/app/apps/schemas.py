"""Pydantic schemas for the app platform."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# App Registry (catalog)
# ---------------------------------------------------------------------------

class AppResponse(BaseModel):
    id: int
    app_type: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    template_dir: str
    default_namespace: str
    hostname_pattern: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AppCreateRequest(BaseModel):
    app_type: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    template_dir: str = Field(..., min_length=1, max_length=100)
    default_namespace: str = Field("argus-apps", max_length=255)
    hostname_pattern: str = Field(
        "argus-{app_type}-{username}.{domain}",
        max_length=255,
    )
    enabled: bool = True


class AppUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    template_dir: str | None = Field(None, min_length=1, max_length=100)
    default_namespace: str | None = Field(None, max_length=255)
    hostname_pattern: str | None = Field(None, max_length=255)
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# App Instances
# ---------------------------------------------------------------------------

class DeployStep(BaseModel):
    step: str
    status: str  # running | completed | failed
    message: str = ""


class InstanceStatusResponse(BaseModel):
    exists: bool
    instance_id: str | None = None
    status: str | None = None
    hostname: str | None = None
    url: str | None = None
    app_type: str | None = None
    deploy_steps: list[DeployStep] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InstanceLaunchResponse(BaseModel):
    status: str
    hostname: str
    url: str
    message: str


class InstanceDestroyResponse(BaseModel):
    status: str
    message: str


class MyInstanceResponse(BaseModel):
    id: int
    app_type: str
    display_name: str
    icon: str | None = None
    hostname: str
    url: str
    status: str
    created_at: datetime
    updated_at: datetime
