"""Dashboard schemas."""

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
