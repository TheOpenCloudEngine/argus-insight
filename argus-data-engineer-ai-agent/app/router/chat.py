"""Chat API router — main conversation interface.

Provides REST endpoints for sending messages, managing sessions,
approving/denying tool executions, and WebSocket streaming.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.agent.engine import AgentEngine
from app.agent.session import ConversationSession
from app.core.auth import OptionalUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# In-memory session store (will be persisted to DB in future phases)
# ---------------------------------------------------------------------------
_sessions: dict[str, ConversationSession] = {}
_engine: AgentEngine | None = None


def set_engine(engine: AgentEngine) -> None:
    """Set the agent engine (called at startup)."""
    global _engine
    _engine = engine


def _get_engine() -> AgentEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Agent engine not initialized")
    return _engine


def _get_or_create_session(session_id: str | None) -> ConversationSession:
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    session = ConversationSession(session_id)
    _sessions[session.session_id] = session
    return session


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    session_id: str | None = Field(None, description="Existing session ID to continue")
    message: str = Field(..., description="User message / prompt")
    auto_approve: bool = Field(False, description="Auto-approve all tool executions")
    context: dict | None = Field(None, description="Optional context (dataset_id, platform_id)")


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    session_id: str
    answer: str | None = None
    steps: list[dict] = []
    status: str  # completed, awaiting_approval, max_steps_exceeded
    pending_action: dict | None = None
    tokens: dict | None = None


class ApprovalRequest(BaseModel):
    """Request body for approving/denying a tool execution."""

    approved: bool = Field(..., description="True to approve, False to deny")


class SessionInfo(BaseModel):
    """Brief session information."""

    session_id: str
    created_at: str
    updated_at: str
    step_count: int
    has_pending_approval: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: OptionalUser,
):
    """Send a message to the agent and get a response.

    The agent will:
    1. Search the catalog for relevant data
    2. Use tools to gather information
    3. Generate code or provide analysis
    4. Return the final answer (or pause for approval)
    """
    engine = _get_engine()
    session = _get_or_create_session(request.session_id)

    # If auto_approve, temporarily override settings
    if request.auto_approve:
        from app.core.config import settings

        original = settings.agent_auto_approve_writes
        settings.agent_auto_approve_writes = True

    try:
        # Prepend context to message if provided
        message = request.message
        if request.context:
            ctx_str = json.dumps(request.context, ensure_ascii=False)
            message = f"[Context: {ctx_str}]\n\n{message}"

        result = await engine.run(message, session)
    finally:
        if request.auto_approve:
            settings.agent_auto_approve_writes = original

    return ChatResponse(**result)


@router.post("/{session_id}/approve", response_model=ChatResponse)
async def approve_action(
    session_id: str,
    request: ApprovalRequest,
    user: OptionalUser,
):
    """Approve or deny a pending tool execution."""
    engine = _get_engine()

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.pending_approval:
        raise HTTPException(status_code=400, detail="No pending approval for this session")

    result = await engine.resume_after_approval(session, request.approved)
    return ChatResponse(**result)


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    user: OptionalUser,
    limit: int = Query(20, ge=1, le=100),
):
    """List recent chat sessions."""
    sessions = sorted(
        _sessions.values(),
        key=lambda s: s.updated_at,
        reverse=True,
    )[:limit]

    return [
        SessionInfo(
            session_id=s.session_id,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            step_count=len(s.steps),
            has_pending_approval=s.pending_approval is not None,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: OptionalUser):
    """Get full session details including all steps."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: OptionalUser):
    """Delete a chat session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del _sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


# ---------------------------------------------------------------------------
# WebSocket — real-time streaming
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming agent responses.

    Protocol:
    - Client sends: {"message": "...", "session_id": "...(optional)"}
    - Server streams: {"event": "thinking|tool_start|tool_result|answer|done", "data": ...}
    """
    await websocket.accept()
    engine = _get_engine()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "data": "Invalid JSON"})
                continue

            message = data.get("message", "")
            session_id = data.get("session_id")
            if not message:
                await websocket.send_json({"event": "error", "data": "Empty message"})
                continue

            session = _get_or_create_session(session_id)
            await websocket.send_json(
                {
                    "event": "session",
                    "data": {"session_id": session.session_id},
                }
            )

            # Run the agent — for now, non-streaming (full result)
            # Future: implement step-by-step streaming via callback
            result = await engine.run(message, session)

            # Stream back each step
            for step in result.get("steps", []):
                event_type = step.get("type", "unknown")
                await websocket.send_json({"event": event_type, "data": step})

            # Send final status
            await websocket.send_json(
                {
                    "event": "done",
                    "data": {
                        "status": result.get("status"),
                        "session_id": session.session_id,
                        "tokens": result.get("tokens"),
                    },
                }
            )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json({"event": "error", "data": str(e)})
        except Exception:
            pass
