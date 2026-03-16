"""Server management API endpoints."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.servermgr import service
from app.servermgr.schemas import (
    ApproveRequest,
    ApproveResponse,
    PaginatedServerResponse,
    UnregisterRequest,
    UnregisterResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/servermgr", tags=["servermgr"])


@router.get("/servers", response_model=PaginatedServerResponse)
async def list_servers(
    status: str | None = Query(None, description="Filter by status (comma-separated for IN)"),
    search: str | None = Query(None, description="LIKE search on hostname, IP address"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    """List servers with optional filters and pagination."""
    return await service.list_servers(
        session, status=status, search=search, page=page, page_size=page_size
    )


@router.post("/servers/approve", response_model=ApproveResponse)
async def approve_servers(
    body: ApproveRequest,
    session: AsyncSession = Depends(get_session),
):
    """Approve servers by changing their status from UNREGISTERED to REGISTERED."""
    return await service.approve_servers(session, hostnames=body.hostnames)


@router.post("/servers/unregister", response_model=UnregisterResponse)
async def unregister_servers(
    body: UnregisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Unregister servers by changing their status from REGISTERED to UNREGISTERED."""
    return await service.unregister_servers(session, hostnames=body.hostnames)
