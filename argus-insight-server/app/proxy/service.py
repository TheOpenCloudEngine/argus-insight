"""Proxy service for forwarding requests to agents.

Acts as a gateway between the React UI and remote agents,
forwarding API calls and aggregating responses.
"""

import logging
from typing import Any

import httpx

from app.agent.service import get_agent
from app.core.config import settings

logger = logging.getLogger(__name__)


async def forward_to_agent(
    agent_id: str,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Forward an HTTP request to a specific agent.

    Args:
        agent_id: Target agent ID.
        method: HTTP method (GET, POST, PUT, DELETE).
        path: API path on the agent (e.g., /api/v1/command/execute).
        json_body: Optional JSON body for POST/PUT requests.
        params: Optional query parameters.

    Returns:
        Tuple of (status_code, response_body).

    Raises:
        ValueError: If agent not found.
        httpx.HTTPError: If agent communication fails.
    """
    agent = get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")

    url = f"http://{agent.host}:{agent.port}{path}"

    async with httpx.AsyncClient(timeout=settings.agent_timeout) as client:
        resp = await client.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
        )
        return resp.status_code, resp.json()


async def proxy_command(agent_id: str, command: str,
                        timeout: int | None = None,
                        cwd: str | None = None) -> dict[str, Any]:
    """Execute a command on a remote agent."""
    body = {"command": command}
    if timeout is not None:
        body["timeout"] = timeout
    if cwd is not None:
        body["cwd"] = cwd

    status, data = await forward_to_agent(
        agent_id, "POST", "/api/v1/command/execute", json_body=body
    )
    return data


async def proxy_monitor(agent_id: str) -> dict[str, Any]:
    """Get system monitor data from a remote agent."""
    status, data = await forward_to_agent(agent_id, "GET", "/api/v1/monitor/system")
    return data


async def proxy_package_manage(agent_id: str, action: str, name: str) -> dict[str, Any]:
    """Manage a package on a remote agent."""
    body = {"action": action, "name": name}
    status, data = await forward_to_agent(
        agent_id, "POST", "/api/v1/package/manage", json_body=body
    )
    return data


async def proxy_package_list(agent_id: str) -> dict[str, Any]:
    """List installed packages on a remote agent."""
    status, data = await forward_to_agent(agent_id, "GET", "/api/v1/package/list")
    return data
