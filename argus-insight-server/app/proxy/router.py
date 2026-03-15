"""Proxy API endpoints for forwarding requests to agents."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

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


@router.websocket("/{agent_id}/terminal/ws")
async def proxy_terminal_ws(websocket: WebSocket, agent_id: str) -> None:
    """Relay a WebSocket terminal session between UI and agent.

    Accepts a WebSocket from the UI, opens a WebSocket to the target agent's
    /api/v1/terminal/ws endpoint, and relays all messages bidirectionally.
    """
    from app.agent.service import get_agent

    agent = get_agent(agent_id)
    if not agent:
        await websocket.close(code=4004, reason=f"Agent not found: {agent_id}")
        return

    await websocket.accept()
    agent_ws_url = f"ws://{agent.host}:{agent.port}/api/v1/terminal/ws"
    logger.info("Terminal proxy opening: agent=%s url=%s", agent_id, agent_ws_url)

    try:
        import websockets

        async with websockets.connect(agent_ws_url) as agent_ws:

            async def ui_to_agent() -> None:
                """Forward messages from UI WebSocket to agent WebSocket."""
                try:
                    while True:
                        message = await websocket.receive()
                        if "text" in message:
                            await agent_ws.send(message["text"])
                        elif "bytes" in message:
                            await agent_ws.send(message["bytes"])
                except WebSocketDisconnect:
                    pass

            async def agent_to_ui() -> None:
                """Forward messages from agent WebSocket to UI WebSocket."""
                try:
                    async for data in agent_ws:
                        if isinstance(data, bytes):
                            await websocket.send_bytes(data)
                        else:
                            await websocket.send_text(data)
                except websockets.ConnectionClosed:
                    pass

            ui_task = asyncio.create_task(ui_to_agent())
            agent_task = asyncio.create_task(agent_to_ui())

            done, pending = await asyncio.wait(
                [ui_task, agent_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error("Terminal proxy error: agent=%s err=%s", agent_id, e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("Terminal proxy closed: agent=%s", agent_id)


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
