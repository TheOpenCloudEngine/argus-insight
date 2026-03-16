"""Server management API endpoints."""

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.servermgr import service
from app.servermgr.schemas import (
    PaginatedServerResponse,
    RegisterRequest,
    RegisterResponse,
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


@router.post("/servers/register", response_model=RegisterResponse)
async def register_servers(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register servers by changing their status from UNREGISTERED to REGISTERED."""
    return await service.register_servers(session, hostnames=body.hostnames)


@router.post("/servers/unregister", response_model=UnregisterResponse)
async def unregister_servers(
    body: UnregisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Unregister servers by changing their status from REGISTERED to UNREGISTERED."""
    return await service.unregister_servers(session, hostnames=body.hostnames)


@router.get("/servers/{hostname}/inspect")
async def server_inspect(hostname: str):
    """Proxy host inspection request to the agent identified by hostname."""
    from app.core.database import async_session

    async with async_session() as session:
        agent = await service.get_agent_by_hostname(session, hostname)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {hostname}")

    agent_url = f"http://{agent.ip_address}:4501/api/v1/host/inspect"
    logger.info("Inspect proxy: hostname=%s url=%s", hostname, agent_url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(agent_url)
            return resp.json()
    except httpx.RequestError as e:
        logger.error("Inspect proxy error: hostname=%s err=%s", hostname, e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.get("/servers/{hostname}/top")
async def server_top(hostname: str, limit: int = Query(50, ge=1, le=500)):
    """Proxy top (htop-style) request to the agent identified by hostname."""
    from app.core.database import async_session

    async with async_session() as session:
        agent = await service.get_agent_by_hostname(session, hostname)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {hostname}")

    agent_url = f"http://{agent.ip_address}:4501/api/v1/sysmon/top?limit={limit}"
    logger.info("Top proxy: hostname=%s url=%s", hostname, agent_url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(agent_url)
            return resp.json()
    except httpx.RequestError as e:
        logger.error("Top proxy error: hostname=%s err=%s", hostname, e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.get("/servers/{hostname}/processes")
async def server_processes(
    hostname: str,
    sort_by: str = Query("pid", description="Sort field"),
    limit: int = Query(0, ge=0, description="Max processes (0 = all)"),
):
    """Proxy process list request to the agent identified by hostname."""
    from app.core.database import async_session

    async with async_session() as session:
        agent = await service.get_agent_by_hostname(session, hostname)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {hostname}")

    agent_url = (
        f"http://{agent.ip_address}:4501/api/v1/process/list"
        f"?sort_by={sort_by}&limit={limit}"
    )
    logger.info("Processes proxy: hostname=%s url=%s", hostname, agent_url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(agent_url)
            return resp.json()
    except httpx.RequestError as e:
        logger.error("Processes proxy error: hostname=%s err=%s", hostname, e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.post("/servers/{hostname}/processes/kill")
async def server_process_kill(hostname: str, body: dict):
    """Proxy process signal (kill) request to the agent identified by hostname."""
    from app.core.database import async_session

    async with async_session() as session:
        agent = await service.get_agent_by_hostname(session, hostname)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {hostname}")

    agent_url = f"http://{agent.ip_address}:4501/api/v1/process/signal"
    logger.info("Process kill proxy: hostname=%s pid=%s", hostname, body.get("pid"))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(agent_url, json=body)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except httpx.RequestError as e:
        logger.error("Process kill proxy error: hostname=%s err=%s", hostname, e)
        raise HTTPException(status_code=502, detail=f"Agent communication failed: {e}")


@router.websocket("/servers/{hostname}/terminal/ws")
async def server_terminal_ws(
    websocket: WebSocket,
    hostname: str,
) -> None:
    """Relay a WebSocket terminal session between UI and an agent identified by hostname.

    Looks up the agent's IP address from the argus_agents table, then opens
    a WebSocket to the agent's terminal endpoint and relays messages bidirectionally.

    The DB session is opened briefly for the lookup and closed before the
    long-lived WebSocket relay to avoid holding a connection pool slot.
    """
    from app.core.database import async_session

    async with async_session() as session:
        agent = await service.get_agent_by_hostname(session, hostname)

    if not agent:
        await websocket.close(code=4004, reason=f"Agent not found: {hostname}")
        return

    await websocket.accept()
    agent_ws_url = f"ws://{agent.ip_address}:4501/api/v1/terminal/ws"
    logger.info("Terminal proxy opening: hostname=%s url=%s", hostname, agent_ws_url)

    agent_ws = None
    try:
        import websockets

        agent_ws = await websockets.connect(
            agent_ws_url,
            close_timeout=5,
        )

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
        logger.error("Terminal proxy error: hostname=%s err=%s", hostname, e)
    finally:
        # Ensure the agent-side WebSocket is always closed so the agent
        # can clean up the PTY session promptly (important when the
        # browser refreshes or is force-closed).
        if agent_ws is not None:
            try:
                await agent_ws.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("Terminal proxy closed: hostname=%s", hostname)
