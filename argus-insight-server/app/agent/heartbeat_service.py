"""Heartbeat processing service.

Handles agent heartbeat reception: inserts new agents as UNREGISTERED,
updates existing agents with latest metrics, and tracks heartbeat timestamps.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import ArgusAgent, ArgusAgentHeartbeat
from app.agent.schemas import HeartbeatRequest

logger = logging.getLogger(__name__)


async def process_heartbeat(session: AsyncSession, req: HeartbeatRequest) -> None:
    """Process an agent heartbeat.

    1. argus_agents: INSERT if new (status=UNREGISTERED), UPDATE metrics if exists.
    2. argus_agents_heartbeat: UPSERT last_heartbeat_at=now().
    """
    logger.debug("Heartbeat received: %s", json.dumps(req.model_dump(), ensure_ascii=False))

    now = datetime.now(timezone.utc)

    # --- argus_agents ---
    result = await session.execute(
        select(ArgusAgent).where(ArgusAgent.hostname == req.hostname)
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        # First heartbeat from this agent: INSERT as UNREGISTERED
        agent = ArgusAgent(
            hostname=req.hostname,
            ip_address=req.ip_address,
            version=req.version,
            kernel_version=req.kernel_version,
            os_version=req.os_version,
            cpu_usage=req.cpu_usage,
            memory_usage=req.memory_usage,
            status="UNREGISTERED",
            created_at=now,
            updated_at=now,
        )
        session.add(agent)
        logger.info("New agent registered: hostname=%s, status=UNREGISTERED", req.hostname)
    else:
        # Existing agent: UPDATE dynamic fields only (keep current status)
        agent.ip_address = req.ip_address
        agent.version = req.version
        agent.kernel_version = req.kernel_version
        agent.os_version = req.os_version
        agent.cpu_usage = req.cpu_usage
        agent.memory_usage = req.memory_usage
        agent.updated_at = now

    # --- argus_agents_heartbeat ---
    hb_result = await session.execute(
        select(ArgusAgentHeartbeat).where(ArgusAgentHeartbeat.hostname == req.hostname)
    )
    heartbeat = hb_result.scalar_one_or_none()

    if heartbeat is None:
        heartbeat = ArgusAgentHeartbeat(
            hostname=req.hostname,
            last_heartbeat_at=now,
        )
        session.add(heartbeat)
    else:
        heartbeat.last_heartbeat_at = now

    await session.commit()
