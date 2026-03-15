"""Agent management service.

Manages agent registration, discovery, health checking, and lifecycle.
Agent information is stored in-memory with periodic health checks.
"""

import logging
import time
import uuid
from datetime import datetime, timezone

import httpx

from app.agent.schemas import AgentHealthResponse, AgentInfo, AgentStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory agent registry
_agents: dict[str, AgentInfo] = {}


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def register_agent(host: str, port: int, name: str | None = None,
                   tags: list[str] | None = None) -> AgentInfo:
    """Register a new agent."""
    agent_id = str(uuid.uuid4())
    display_name = name or f"{host}:{port}"

    agent = AgentInfo(
        id=agent_id,
        host=host,
        port=port,
        name=display_name,
        tags=tags or [],
        status=AgentStatus.UNKNOWN,
        registered_at=_now_iso(),
    )
    _agents[agent_id] = agent
    logger.info("Agent registered: %s (%s:%d)", agent_id, host, port)
    return agent


def unregister_agent(agent_id: str) -> bool:
    """Unregister an agent by ID. Returns True if found and removed."""
    if agent_id in _agents:
        agent = _agents.pop(agent_id)
        logger.info("Agent unregistered: %s (%s:%d)", agent_id, agent.host, agent.port)
        return True
    return False


def get_agent(agent_id: str) -> AgentInfo | None:
    """Get agent info by ID."""
    return _agents.get(agent_id)


def list_agents() -> list[AgentInfo]:
    """List all registered agents."""
    return list(_agents.values())


def update_agent(agent_id: str, name: str | None = None, port: int | None = None,
                 tags: list[str] | None = None) -> AgentInfo | None:
    """Update agent information."""
    agent = _agents.get(agent_id)
    if not agent:
        return None

    if name is not None:
        agent.name = name
    if port is not None:
        agent.port = port
    if tags is not None:
        agent.tags = tags

    _agents[agent_id] = agent
    return agent


async def check_agent_health(agent_id: str) -> AgentHealthResponse | None:
    """Check health of a single agent by calling its /health endpoint."""
    agent = _agents.get(agent_id)
    if not agent:
        return None

    url = f"http://{agent.host}:{agent.port}/health"
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=settings.agent_timeout) as client:
            resp = await client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                agent.status = AgentStatus.ONLINE
                agent.version = data.get("version")
                agent.last_seen_at = _now_iso()
                return AgentHealthResponse(
                    id=agent.id,
                    host=agent.host,
                    port=agent.port,
                    status=AgentStatus.ONLINE,
                    version=data.get("version"),
                    response_time_ms=round(elapsed_ms, 2),
                )
            else:
                agent.status = AgentStatus.OFFLINE
                return AgentHealthResponse(
                    id=agent.id,
                    host=agent.host,
                    port=agent.port,
                    status=AgentStatus.OFFLINE,
                )
    except Exception as e:
        logger.warning("Health check failed for %s:%d - %s", agent.host, agent.port, e)
        agent.status = AgentStatus.OFFLINE
        return AgentHealthResponse(
            id=agent.id,
            host=agent.host,
            port=agent.port,
            status=AgentStatus.OFFLINE,
        )


async def check_all_agents_health() -> list[AgentHealthResponse]:
    """Check health of all registered agents."""
    results = []
    for agent_id in list(_agents.keys()):
        result = await check_agent_health(agent_id)
        if result:
            results.append(result)
    return results
