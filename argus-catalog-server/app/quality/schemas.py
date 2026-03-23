"""Data quality Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ColumnProfile(BaseModel):
    """Per-column profiling statistics."""
    column_name: str
    column_type: str
    total_count: int = 0
    null_count: int = 0
    null_percent: float = 0.0
    unique_count: int = 0
    unique_percent: float = 0.0
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    top_values: list[dict] | None = None   # [{"value": "X", "count": 10}, ...]


class ProfileResponse(BaseModel):
    id: int
    dataset_id: int
    row_count: int
    columns: list[ColumnProfile] = Field(default_factory=list)
    profiled_at: datetime


# ---------------------------------------------------------------------------
# Quality Rule
# ---------------------------------------------------------------------------

class QualityRuleCreate(BaseModel):
    dataset_id: int
    rule_name: str = Field(..., min_length=1, max_length=255)
    check_type: str        # NOT_NULL, UNIQUE, MIN_VALUE, MAX_VALUE, ACCEPTED_VALUES, REGEX, ROW_COUNT, FRESHNESS
    column_name: str | None = None
    expected_value: str | None = None   # JSON string
    threshold: float = 100.0
    severity: str = "WARNING"


class QualityRuleUpdate(BaseModel):
    rule_name: str | None = None
    check_type: str | None = None
    column_name: str | None = None
    expected_value: str | None = None
    threshold: float | None = None
    severity: str | None = None
    is_active: str | None = None


class QualityRuleResponse(BaseModel):
    id: int
    dataset_id: int
    rule_name: str
    check_type: str
    column_name: str | None = None
    expected_value: str | None = None
    threshold: float
    severity: str
    is_active: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Quality Result
# ---------------------------------------------------------------------------

class QualityResultResponse(BaseModel):
    id: int
    rule_id: int
    rule_name: str | None = None
    check_type: str | None = None
    column_name: str | None = None
    dataset_id: int
    passed: str
    actual_value: str | None = None
    detail: str | None = None
    severity: str | None = None
    checked_at: datetime


# ---------------------------------------------------------------------------
# Quality Score
# ---------------------------------------------------------------------------

class QualityScoreResponse(BaseModel):
    id: int
    dataset_id: int
    score: float
    total_rules: int
    passed_rules: int
    warning_rules: int
    failed_rules: int
    scored_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Run Check Response
# ---------------------------------------------------------------------------

class RunCheckResponse(BaseModel):
    dataset_id: int
    score: float
    total_rules: int
    passed: int
    failed: int
    results: list[QualityResultResponse] = Field(default_factory=list)
