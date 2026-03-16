"""Server management service.

Provides read operations for the argus_agents table.
"""

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import ArgusAgent
from app.servermgr.schemas import PaginatedServerResponse, ServerResponse

logger = logging.getLogger(__name__)


async def list_servers(
    session: AsyncSession,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedServerResponse:
    """List servers with optional filtering and pagination."""
    base = select(ArgusAgent)

    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        if status_list:
            base = base.where(ArgusAgent.status.in_(status_list))

    if search:
        pattern = f"%{search}%"
        base = base.where(
            or_(
                ArgusAgent.hostname.ilike(pattern),
                ArgusAgent.ip_address.ilike(pattern),
            )
        )

    # Count total matching rows
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Apply ordering and pagination
    offset = (page - 1) * page_size
    query = base.order_by(ArgusAgent.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.scalars().all()

    items = [
        ServerResponse(
            hostname=agent.hostname,
            ip_address=agent.ip_address,
            version=agent.version,
            os_version=agent.os_version,
            core_count=agent.core_count,
            total_memory=agent.total_memory,
            cpu_usage=agent.cpu_usage,
            memory_usage=agent.memory_usage,
            status=agent.status,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
        for agent in rows
    ]

    return PaginatedServerResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
