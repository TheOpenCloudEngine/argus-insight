"""OCI Model Hub Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# OCI Model
# ---------------------------------------------------------------------------

class OciModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = None
    description: str | None = None
    readme: str | None = None
    task: str | None = None
    framework: str | None = None
    language: str | None = None
    license: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    owner: str | None = None
    status: str = "draft"


class OciModelUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    task: str | None = None
    framework: str | None = None
    language: str | None = None
    license: str | None = None
    owner: str | None = None
    status: str | None = None


class OciModelSummary(BaseModel):
    """Card view summary for list page."""
    id: int
    name: str
    display_name: str | None = None
    description: str | None = None
    task: str | None = None
    framework: str | None = None
    language: str | None = None
    license: str | None = None
    source_type: str | None = None
    owner: str | None = None
    version_count: int = 0
    total_size: int = 0
    download_count: int = 0
    status: str = "draft"
    tags: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OciModelDetail(BaseModel):
    """Full detail with readme, tags, lineage."""
    id: int
    name: str
    display_name: str | None = None
    description: str | None = None
    readme: str | None = None
    task: str | None = None
    framework: str | None = None
    language: str | None = None
    license: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_revision: str | None = None
    bucket: str | None = None
    storage_prefix: str | None = None
    owner: str | None = None
    version_count: int = 0
    total_size: int = 0
    download_count: int = 0
    status: str = "draft"
    tags: list[dict] = Field(default_factory=list)
    lineage: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedOciModels(BaseModel):
    items: list[OciModelSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

class OciModelVersionResponse(BaseModel):
    id: int
    model_id: int
    version: int
    manifest: str | None = None
    content_digest: str | None = None
    file_count: int = 0
    total_size: int = 0
    extra_metadata: dict | None = None
    status: str = "ready"
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

class LineageCreate(BaseModel):
    source_type: str = Field(..., description="dataset, model, or external")
    source_id: str = Field(...)
    source_name: str | None = None
    relation_type: str = Field(..., description="trained_on, derived_from, fine_tuned_from, distilled_from")
    description: str | None = None


class LineageResponse(BaseModel):
    id: int
    model_id: int
    source_type: str
    source_id: str
    source_name: str | None = None
    relation_type: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class HuggingFaceImportRequest(BaseModel):
    hf_model_id: str = Field(..., description="HuggingFace model ID (e.g. bert-base-uncased)")
    name: str | None = Field(None, description="Override model name (default: hf_model_id)")
    description: str | None = None
    owner: str | None = None
    task: str | None = None
    framework: str | None = None
    language: str | None = None
    revision: str = "main"


class ImportResponse(BaseModel):
    name: str
    version: int
    file_count: int
    total_size: int
    status: str
