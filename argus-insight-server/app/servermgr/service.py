"""Server management service.

Provides read operations for the argus_agents table.
"""

import logging

from sqlalchemy import Integer, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import ArgusAgent, ArgusAgentHeartbeat
from app.servermgr.schemas import (
    PaginatedServerResponse,
    RegisterResponse,
    ServerResponse,
    UnregisterResponse,
)

logger = logging.getLogger(__name__)


async def list_servers(
    session: AsyncSession,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedServerResponse:
    """List servers with optional filtering and pagination."""
    heartbeat_seconds = func.extract(
        "epoch", func.now() - ArgusAgentHeartbeat.last_heartbeat_at
    ).cast(Integer).label("last_heartbeat_seconds")

    base = (
        select(ArgusAgent, heartbeat_seconds)
        .outerjoin(ArgusAgentHeartbeat, ArgusAgent.hostname == ArgusAgentHeartbeat.hostname)
    )

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
    rows = result.all()

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
            disk_swap_percent=agent.disk_swap_percent,
            status=agent.status,
            last_heartbeat_seconds=hb_seconds,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
        for agent, hb_seconds in rows
    ]

    return PaginatedServerResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_agent_by_hostname(session: AsyncSession, hostname: str) -> ArgusAgent | None:
    """Look up an agent by hostname. Returns the ORM object or None."""
    result = await session.execute(
        select(ArgusAgent).where(ArgusAgent.hostname == hostname)
    )
    return result.scalar_one_or_none()


async def register_servers(
    session: AsyncSession,
    hostnames: list[str],
) -> RegisterResponse:
    """Register servers by changing status from UNREGISTERED to REGISTERED."""
    stmt = (
        update(ArgusAgent)
        .where(ArgusAgent.hostname.in_(hostnames))
        .where(ArgusAgent.status == "UNREGISTERED")
        .values(status="REGISTERED")
    )
    result = await session.execute(stmt)
    await session.commit()
    return RegisterResponse(updated=result.rowcount)


async def unregister_servers(
    session: AsyncSession,
    hostnames: list[str],
) -> UnregisterResponse:
    """Unregister servers by changing status from REGISTERED to UNREGISTERED."""
    stmt = (
        update(ArgusAgent)
        .where(ArgusAgent.hostname.in_(hostnames))
        .where(ArgusAgent.status == "REGISTERED")
        .values(status="UNREGISTERED")
    )
    result = await session.execute(stmt)
    await session.commit()
    return UnregisterResponse(updated=result.rowcount)
