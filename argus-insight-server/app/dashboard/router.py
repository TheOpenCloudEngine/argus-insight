"""Dashboard API endpoints."""

from fastapi import APIRouter

from app.dashboard import service
from app.dashboard.schemas import AgentSummary, DashboardOverview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def get_overview():
    """Get dashboard overview with aggregated data from all agents."""
    return service.get_overview()


@router.get("/agents/summary", response_model=AgentSummary)
async def get_agent_summary():
    """Get agent status summary."""
    return service.get_agent_summary()
