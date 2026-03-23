"""Pydantic schemas for AI metadata generation API."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Common request body for generation endpoints."""
    apply: bool = Field(False, description="Apply generated metadata directly (True) or preview only (False)")
    force: bool = Field(False, description="Regenerate even if metadata already exists")
    language: str | None = Field(None, description="Target language override (en, ko, etc.)")


class BulkGenerateRequest(BaseModel):
    """Request body for bulk generation."""
    generation_types: list[str] = Field(
        default=["description"],
        description="Types to generate: description, columns, tags, pii",
    )
    apply: bool = False
    language: str | None = None
    platform_id: int | None = Field(None, description="Filter by platform ID")
    empty_only: bool = Field(True, description="Only process datasets with empty descriptions")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ColumnDescriptionResult(BaseModel):
    field_path: str
    description: str
    confidence: float
    had_existing: bool


class GenerateDescriptionResponse(BaseModel):
    dataset_id: int
    description: str = ""
    confidence: float = 0.0
    applied: bool = False
    skipped: bool = False
    reason: str | None = None
    log_id: int | None = None


class GenerateColumnsResponse(BaseModel):
    dataset_id: int
    columns: list[ColumnDescriptionResult] = Field(default_factory=list)
    total_generated: int = 0
    applied: bool = False
    skipped: bool = False
    reason: str | None = None


class TagSuggestion(BaseModel):
    name: str
    description: str = ""


class TagSuggestionResponse(BaseModel):
    dataset_id: int
    suggested_tags: list[str] = Field(default_factory=list)
    new_tags: list[TagSuggestion] = Field(default_factory=list)
    applied_tags: list[str] = Field(default_factory=list)
    created_tags: list[str] = Field(default_factory=list)
    applied: bool = False
    log_id: int | None = None


class PIIColumnResult(BaseModel):
    name: str
    pii_type: str
    confidence: float
    reason: str = ""


class PIIDetectionResponse(BaseModel):
    dataset_id: int
    pii_columns: list[PIIColumnResult] = Field(default_factory=list)
    applied: bool = False
    log_id: int | None = None


class GenerateAllResponse(BaseModel):
    dataset_id: int
    description: dict
    columns: dict
    tags: dict
    pii: dict


class BulkGenerateResponse(BaseModel):
    total: int
    processed: int
    errors: int
    results: list[dict] = Field(default_factory=list)


class SuggestionItem(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    field_name: str | None = None
    generation_type: str
    generated_text: str
    provider: str
    model: str
    created_at: str | None = None


class ApplyRejectResponse(BaseModel):
    id: int
    applied: bool = False
    rejected: bool = False
    already_applied: bool = False


class AIStatsResponse(BaseModel):
    total_generations: int
    applied_count: int
    pending_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    description_coverage: dict
    by_type: dict
    provider: str | None = None
    model: str | None = None
