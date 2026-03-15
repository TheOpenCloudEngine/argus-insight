"""Agent management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import heartbeat_service, service
from app.agent.schemas import (
    AgentHealthResponse,
    AgentInfo,
    AgentRegisterRequest,
    AgentUpdateRequest,
    HeartbeatRequest,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/heartbeat")
async def agent_heartbeat(
    req: HeartbeatRequest,
    session: AsyncSession = Depends(get_session),
):
    """Receive agent heartbeat. Inserts new agents as UNREGISTERED, updates existing."""
    await heartbeat_service.process_heartbeat(session, req)
    return {"status": "ok"}


@router.post("/register", response_model=AgentInfo)
async def register_agent(req: AgentRegisterRequest):
    """Register a new agent."""
    return service.register_agent(
        host=req.host,
        port=req.port,
        name=req.name,
        tags=req.tags,
    )


@router.get("/list", response_model=list[AgentInfo])
async def list_agents():
    """List all registered agents."""
    return service.list_agents()


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """Get agent information by ID."""
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentInfo)
async def update_agent(agent_id: str, req: AgentUpdateRequest):
    """Update agent information."""
    agent = service.update_agent(
        agent_id=agent_id,
        name=req.name,
        port=req.port,
        tags=req.tags,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent."""
    if not service.unregister_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok", "message": "Agent unregistered"}


@router.get("/{agent_id}/health", response_model=AgentHealthResponse)
async def check_agent_health(agent_id: str):
    """Check health of a specific agent."""
    result = await service.check_agent_health(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.post("/health/all", response_model=list[AgentHealthResponse])
async def check_all_agents_health():
    """Check health of all registered agents."""
    return await service.check_all_agents_health()
