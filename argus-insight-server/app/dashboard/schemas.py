"""Dashboard schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agent.schemas import AgentStatus


class AgentSummary(BaseModel):
    """Summary of agent statuses."""

    total: int = Field(0, description="Total number of registered agents")
    online: int = Field(0, description="Number of online agents")
    offline: int = Field(0, description="Number of offline agents")
    unknown: int = Field(0, description="Number of agents with unknown status")


class DashboardOverview(BaseModel):
    """Dashboard overview combining agent summary and system-level stats."""

    agents: AgentSummary


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

class WorkspaceStatItem(BaseModel):
    id: int
    name: str
    display_name: str
    status: str
    service_count: int = 0
    cpu_used: float = 0.0
    memory_used_gb: float = 0.0


class RecentVocItem(BaseModel):
    id: int
    title: str
    category: str
    priority: str
    status: str
    workspace_name: str | None = None
    author_username: str | None = None
    created_at: datetime


class RecentActivityItem(BaseModel):
    action: str
    actor_username: str | None = None
    workspace_name: str | None = None
    detail: dict | None = None
    created_at: datetime


class AdminDashboardResponse(BaseModel):
    """Aggregated admin dashboard — DB only, no K8s calls."""

    # Summary cards
    workspaces_total: int = 0
    workspaces_active: int = 0
    users_total: int = 0
    users_active: int = 0
    services_total: int = 0
    services_running: int = 0
    voc_open: int = 0
    voc_critical: int = 0

    # Cluster resource (aggregated from service metadata)
    cluster_cpu_used: float = 0.0
    cluster_cpu_limit: float = 0.0
    cluster_memory_used_gb: float = 0.0
    cluster_memory_limit_gb: float = 0.0
    cluster_storage_gb: float = 0.0

    # Workspace breakdown
    workspace_stats: list[WorkspaceStatItem] = []

    # VOC distribution
    voc_by_status: dict[str, int] = {}
    voc_by_category: dict[str, int] = {}
    voc_by_priority: dict[str, int] = {}

    # Recent items
    recent_voc: list[RecentVocItem] = []
    recent_activity: list[RecentActivityItem] = []
