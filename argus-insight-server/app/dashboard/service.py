"""Dashboard service.

Aggregates data from multiple agents to provide a unified dashboard view.
"""

import logging

from app.agent.schemas import AgentStatus
from app.agent.service import list_agents
from app.dashboard.schemas import AgentSummary, DashboardOverview

logger = logging.getLogger(__name__)


def get_agent_summary() -> AgentSummary:
    """Get a summary of agent statuses."""
    agents = list_agents()
    return AgentSummary(
        total=len(agents),
        online=sum(1 for a in agents if a.status == AgentStatus.ONLINE),
        offline=sum(1 for a in agents if a.status == AgentStatus.OFFLINE),
        unknown=sum(1 for a in agents if a.status == AgentStatus.UNKNOWN),
    )


def get_overview() -> DashboardOverview:
    """Get the full dashboard overview."""
    return DashboardOverview(
        agents=get_agent_summary(),
    )
