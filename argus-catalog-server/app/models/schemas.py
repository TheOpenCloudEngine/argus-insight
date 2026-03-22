"""Pydantic schemas for ML Model Registry.

Request/response models for the /api/v1/models endpoints.
The UC-compatible API (uc_compat.py) converts between UC protobuf format
and these schemas internally.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModelVersionStatus(str, Enum):
    PENDING_REGISTRATION = "PENDING_REGISTRATION"
    READY = "READY"
    FAILED_REGISTRATION = "FAILED_REGISTRATION"


# ---------------------------------------------------------------------------
# RegisteredModel schemas
# ---------------------------------------------------------------------------

class RegisteredModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    owner: str | None = None
    storage_location: str | None = None
    platform_id: int | None = None


class RegisteredModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    owner: str | None = None


class RegisteredModelResponse(BaseModel):
    id: int
    name: str
    urn: str
    platform_id: int | None = None
    description: str | None = None
    owner: str | None = None
    storage_location: str | None = None
    max_version_number: int
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None

    model_config = {"from_attributes": True}


class PaginatedRegisteredModels(BaseModel):
    items: list[RegisteredModelResponse]
    total: int
    page: int
    page_size: int


class ModelSummary(BaseModel):
    """Joined summary for model list view (registered_models + latest version + catalog_models)."""

    id: int
    name: str
    description: str | None = None
    owner: str | None = None
    max_version_number: int
    status: str
    # Latest version info
    latest_version_status: str | None = None
    # From catalog_models (latest version)
    sklearn_version: str | None = None
    python_version: str | None = None
    model_size_bytes: int | None = None
    access_count: int = 0
    updated_at: datetime


class PaginatedModelSummaries(BaseModel):
    items: list[ModelSummary]
    total: int
    page: int
    page_size: int


class ModelVersionStatusCount(BaseModel):
    status: str
    count: int


class ModelSizeInfo(BaseModel):
    model_name: str
    model_size_bytes: int


class ModelVersionCount(BaseModel):
    model_name: str
    version_count: int


class AccessDataPoint(BaseModel):
    date: str
    count: int


class ModelStats(BaseModel):
    """Dashboard statistics for MLFlow Models page."""

    total_models: int
    total_versions: int
    ready_models: int
    ready_versions: int
    pending_count: int
    failed_count: int
    total_access: int
    status_distribution: list[ModelVersionStatusCount]
    model_sizes: list[ModelSizeInfo]
    versions_per_model: list[ModelVersionCount]
    daily_access_1d: list[AccessDataPoint]
    daily_access_7d: list[AccessDataPoint]
    daily_access_30d: list[AccessDataPoint]
    access_by_model: dict[str, int]
    total_publish: int
    daily_publish_1d: list[AccessDataPoint]
    daily_publish_7d: list[AccessDataPoint]
    daily_publish_30d: list[AccessDataPoint]


# ---------------------------------------------------------------------------
# ModelVersion schemas
# ---------------------------------------------------------------------------

class ModelVersionCreate(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=255)
    source: str | None = None
    run_id: str | None = None
    run_link: str | None = None
    description: str | None = None


class ModelVersionUpdate(BaseModel):
    description: str | None = None
    source: str | None = None


class ModelVersionFinalize(BaseModel):
    status: ModelVersionStatus = Field(
        ..., description="READY or FAILED_REGISTRATION"
    )
    status_message: str | None = None


class ModelVersionResponse(BaseModel):
    id: int
    model_id: int
    model_name: str
    version: int
    source: str | None = None
    run_id: str | None = None
    run_link: str | None = None
    description: str | None = None
    status: str
    status_message: str | None = None
    storage_location: str | None = None
    artifact_count: int = 0
    artifact_size: int = 0
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None

    model_config = {"from_attributes": True}


class PaginatedModelVersions(BaseModel):
    items: list[ModelVersionResponse]
    total: int
    page: int
    page_size: int
