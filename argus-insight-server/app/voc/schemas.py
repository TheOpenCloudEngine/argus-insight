"""Pydantic schemas for VOC issue tracker."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VocCategory(str, Enum):
    RESOURCE_REQUEST = "resource_request"
    SERVICE_ISSUE = "service_issue"
    FEATURE_REQUEST = "feature_request"
    ACCOUNT = "account"
    GENERAL = "general"


class VocPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VocStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Issue schemas
# ---------------------------------------------------------------------------

class VocIssueCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    category: VocCategory = VocCategory.GENERAL
    priority: VocPriority = VocPriority.MEDIUM
    workspace_id: int | None = None
    workspace_name: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    resource_detail: dict | None = None


class VocIssueUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, min_length=1)
    category: VocCategory | None = None
    priority: VocPriority | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    resource_detail: dict | None = None


class VocStatusChangeRequest(BaseModel):
    status: VocStatus


class VocAssigneeChangeRequest(BaseModel):
    assignee_user_id: int | None = None
    assignee_username: str | None = None


class VocPriorityChangeRequest(BaseModel):
    priority: VocPriority


class VocIssueResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    priority: str
    status: str
    author_user_id: int
    author_username: str | None = None
    assignee_user_id: int | None = None
    assignee_username: str | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    resource_detail: dict | None = None
    comment_count: int = 0
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedVocIssueResponse(BaseModel):
    items: list[VocIssueResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------

class VocCommentCreateRequest(BaseModel):
    body: str = Field(..., min_length=1)
    body_plain: str | None = None
    parent_id: int | None = None


class VocCommentResponse(BaseModel):
    id: int
    issue_id: int
    parent_id: int | None = None
    author_user_id: int
    author_username: str | None = None
    body: str
    body_plain: str | None = None
    is_system: bool = False
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class VocDashboardResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    avg_resolution_hours: float | None = None
