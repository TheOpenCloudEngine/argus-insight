"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser
from app.core.database import get_session
from app.dashboard import service
from app.dashboard.schemas import AdminDashboardResponse, AgentSummary, DashboardOverview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def get_overview():
    """Get dashboard overview with aggregated data from all agents."""
    return service.get_overview()


@router.get("/agents/summary", response_model=AgentSummary)
async def get_agent_summary():
    """Get agent status summary."""
    return service.get_agent_summary()


@router.get("/admin-overview", response_model=AdminDashboardResponse)
async def get_admin_overview(
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated admin dashboard — DB only, zero K8s calls."""
    return await service.get_admin_overview(session)
