"""Data catalog schemas for request/response validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DatasetOrigin(str, Enum):
    PROD = "PROD"
    DEV = "DEV"
    STAGING = "STAGING"


class DatasetStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


class OwnerType(str, Enum):
    TECHNICAL_OWNER = "TECHNICAL_OWNER"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    DATA_STEWARD = "DATA_STEWARD"


# ---------------------------------------------------------------------------
# Platform schemas
# ---------------------------------------------------------------------------

class PlatformCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    logo_url: str | None = None


class PlatformResponse(BaseModel):
    id: int
    name: str
    display_name: str
    logo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schema field schemas
# ---------------------------------------------------------------------------

class SchemaFieldCreate(BaseModel):
    field_path: str = Field(..., min_length=1, max_length=500)
    field_type: str = Field(..., min_length=1, max_length=100)
    native_type: str | None = None
    description: str | None = None
    nullable: str = "true"
    ordinal: int = 0


class SchemaFieldResponse(BaseModel):
    id: int
    field_path: str
    field_type: str
    native_type: str | None = None
    description: str | None = None
    nullable: str
    ordinal: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tag schemas
# ---------------------------------------------------------------------------

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    color: str = "#3b82f6"


class TagResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Glossary term schemas
# ---------------------------------------------------------------------------

class GlossaryTermCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    source: str | None = None
    parent_id: int | None = None


class GlossaryTermResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    source: str | None = None
    parent_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Owner schemas
# ---------------------------------------------------------------------------

class OwnerCreate(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=200)
    owner_type: OwnerType = OwnerType.TECHNICAL_OWNER


class OwnerResponse(BaseModel):
    id: int
    dataset_id: int
    owner_name: str
    owner_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dataset schemas
# ---------------------------------------------------------------------------

class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform_id: int
    description: str | None = None
    origin: DatasetOrigin = DatasetOrigin.PROD
    qualified_name: str | None = None
    schema_fields: list[SchemaFieldCreate] = Field(default_factory=list)
    tags: list[int] = Field(default_factory=list, description="Tag IDs to attach")
    owners: list[OwnerCreate] = Field(default_factory=list)


class DatasetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    origin: DatasetOrigin | None = None
    qualified_name: str | None = None
    status: DatasetStatus | None = None


class DatasetResponse(BaseModel):
    id: int
    urn: str
    name: str
    platform: PlatformResponse
    description: str | None = None
    origin: str
    qualified_name: str | None = None
    status: str
    schema_fields: list[SchemaFieldResponse] = Field(default_factory=list)
    tags: list[TagResponse] = Field(default_factory=list)
    owners: list[OwnerResponse] = Field(default_factory=list)
    glossary_terms: list[GlossaryTermResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DatasetSummary(BaseModel):
    """Lightweight dataset representation for list views."""
    id: int
    urn: str
    name: str
    platform_name: str
    platform_display_name: str
    description: str | None = None
    origin: str
    status: str
    tag_count: int = 0
    owner_count: int = 0
    schema_field_count: int = 0
    created_at: datetime
    updated_at: datetime


class PaginatedDatasets(BaseModel):
    items: list[DatasetSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Search schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = ""
    platform: str | None = None
    origin: str | None = None
    tag: str | None = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    datasets: PaginatedDatasets


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class CatalogStats(BaseModel):
    total_datasets: int
    total_platforms: int
    total_tags: int
    total_glossary_terms: int
    datasets_by_platform: list[dict]
    datasets_by_origin: list[dict]
    recent_datasets: list[DatasetSummary]
