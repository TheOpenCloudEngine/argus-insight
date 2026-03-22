"""Pydantic schemas for lineage alerts and subscriptions."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlertType(str, Enum):
    SCHEMA_CHANGE = "SCHEMA_CHANGE"
    LINEAGE_BROKEN = "LINEAGE_BROKEN"
    SYNC_FAILED = "SYNC_FAILED"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BREAKING = "BREAKING"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ScopeType(str, Enum):
    DATASET = "DATASET"
    PIPELINE = "PIPELINE"
    PLATFORM = "PLATFORM"
    ALL = "ALL"


# ---------------------------------------------------------------------------
# Alert schemas
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    source_dataset_id: int
    source_dataset_name: str | None = None
    source_platform_type: str | None = None
    affected_dataset_id: int | None = None
    affected_dataset_name: str | None = None
    affected_platform_type: str | None = None
    lineage_id: int | None = None
    change_summary: str
    change_detail: str | None = None
    status: str
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class AlertUpdateStatus(BaseModel):
    status: AlertStatus
    resolved_by: str | None = None


class PaginatedAlerts(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Subscription schemas
# ---------------------------------------------------------------------------

class SubscriptionCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)
    scope_type: ScopeType = ScopeType.ALL
    scope_id: int | None = None
    channels: str = "IN_APP"
    severity_filter: AlertSeverity = AlertSeverity.WARNING


class SubscriptionResponse(BaseModel):
    id: int
    user_id: str
    scope_type: str
    scope_id: int | None = None
    channels: str
    severity_filter: str
    is_active: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alert summary (for bell badge)
# ---------------------------------------------------------------------------

class AlertSummary(BaseModel):
    total_open: int = 0
    breaking_count: int = 0
    warning_count: int = 0
    info_count: int = 0
