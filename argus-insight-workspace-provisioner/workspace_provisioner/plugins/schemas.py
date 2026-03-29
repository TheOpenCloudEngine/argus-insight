"""Pydantic v2 schemas for the plugin management API.

Defines request/response models for plugin discovery, ordering,
validation, and rescanning operations.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PluginVersionResponse(BaseModel):
    """Metadata for a single version of a plugin."""

    version: str
    display_name: str
    description: str
    status: str  # stable | beta | deprecated
    release_date: str | None = None
    min_k8s_version: str | None = None
    changelog: str | None = None
    upgradeable_from: list[str] = []
    config_schema: dict | None = None  # JSON Schema for UI form generation


class PluginResponse(BaseModel):
    """Full plugin descriptor including all versions and admin config."""

    name: str
    display_name: str
    description: str
    icon: str
    category: str
    depends_on: list[str] = []
    provides: list[str] = []
    requires: list[str] = []
    tags: list[str] = []
    source: str  # builtin | external
    versions: list[PluginVersionResponse] = []
    default_version: str
    # Admin config (from DB, null if not configured yet)
    enabled: bool | None = None
    display_order: int | None = None
    selected_version: str | None = None


class PluginOrderItem(BaseModel):
    """Single item in a plugin order update request."""

    plugin_name: str
    enabled: bool = True
    display_order: int
    selected_version: str | None = None
    default_config: dict | None = None


class PluginOrderUpdateRequest(BaseModel):
    """Request to update the global plugin order and configuration."""

    plugins: list[PluginOrderItem]


class PluginOrderValidateRequest(BaseModel):
    """Request to validate a proposed plugin order (dry-run)."""

    plugin_names: list[str]
    versions: dict[str, str] | None = None


class PluginOrderValidateResponse(BaseModel):
    """Validation result for a proposed plugin order."""

    valid: bool
    violations: list[str] = []
    suggested_order: list[str] = []


class PluginRescanResponse(BaseModel):
    """Response after rescanning plugin directories."""

    total_plugins: int
    new_plugins: list[str] = []
    removed_plugins: list[str] = []


# ---------------------------------------------------------------------------
# Pipeline CRUD schemas
# ---------------------------------------------------------------------------


class PipelineCreateRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"
    )
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    created_by: str | None = None
    plugins: list[PluginOrderItem] = []


class PipelineUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    plugins: list[PluginOrderItem] | None = None


class PipelineResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: str | None = None
    version: int = 1
    created_by: str | None = None
    plugins: list[PluginOrderItem] = []
    created_at: datetime
    updated_at: datetime


class PipelineListResponse(BaseModel):
    items: list[PipelineResponse]
    total: int
