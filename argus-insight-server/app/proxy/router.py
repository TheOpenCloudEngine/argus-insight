"""Proxy API endpoints for forwarding requests to agents."""

import logging

from fastapi import APIRouter, HTTPException

from app.proxy import service
from app.proxy.schemas import (
    ProxyCommandRequest,
    ProxyCommandResponse,
    ProxyPackageRequest,
    ProxyPackageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post("/{agent_id}/command/execute", response_model=ProxyCommandResponse)
async def proxy_command(agent_id: str, req: ProxyCommandRequest):
    """Execute a command on a remote agent."""
    try:
        data = await service.proxy_command(
            agent_id, req.command, req.timeout, req.cwd
        )
        from app.agent.service import get_agent

        agent = get_agent(agent_id)
        return ProxyCommandResponse(
            agent_id=agent_id,
            host=agent.host if agent else "unknown",
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            return_code=data.get("return_code"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Proxy command failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.get("/{agent_id}/monitor/system")
async def proxy_monitor(agent_id: str):
    """Get system monitor data from a remote agent."""
    try:
        return await service.proxy_monitor(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Proxy monitor failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.post("/{agent_id}/package/manage", response_model=ProxyPackageResponse)
async def proxy_package_manage(agent_id: str, req: ProxyPackageRequest):
    """Manage a package on a remote agent."""
    try:
        data = await service.proxy_package_manage(agent_id, req.action, req.name)
        from app.agent.service import get_agent

        agent = get_agent(agent_id)
        return ProxyPackageResponse(
            agent_id=agent_id,
            host=agent.host if agent else "unknown",
            success=data.get("success", True),
            message=data.get("message", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Proxy package manage failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.get("/{agent_id}/package/list")
async def proxy_package_list(agent_id: str):
    """List installed packages on a remote agent."""
    try:
        return await service.proxy_package_list(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Proxy package list failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.api_route(
    "/{agent_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def proxy_generic(agent_id: str, path: str):
    """Generic proxy endpoint for forwarding any request to an agent.

    This catches all requests not handled by specific proxy endpoints
    and forwards them to the target agent's /api/v1/{path}.
    """
    from fastapi import Request

    # This is a catch-all - actual implementation uses request context
    try:
        status, data = await service.forward_to_agent(
            agent_id, "GET", f"/api/v1/{path}"
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Proxy generic failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")
