"""Conversation session management.

Each chat session maintains its own message history, step log,
and pending approval state.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StepType(Enum):
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"


@dataclass
class AgentStep:
    """A single step in the agent's execution trace."""

    type: StepType
    content: str = ""
    tool_name: str | None = None
    tool_params: dict | None = None
    tool_result: str | None = None
    tool_call_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "tool_result": self.tool_result,
            "tool_call_id": self.tool_call_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PendingApproval:
    """A tool call waiting for user approval."""

    step_index: int
    tool_name: str
    tool_params: dict
    tool_call_id: str
    description: str


class ConversationSession:
    """Manages conversation state for one chat session."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.messages: list[dict] = []
        self.steps: list[AgentStep] = []
        self.pending_approval: PendingApproval | None = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append({"role": "user", "content": content})
        self.updated_at = datetime.now()

    def add_assistant_message(self, content: dict) -> None:
        """Add an assistant message (may contain tool_use blocks)."""
        self.messages.append(content)
        self.updated_at = datetime.now()

    def add_tool_result_message(self, message: dict) -> None:
        """Add a tool result message to the conversation."""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def add_step(self, step: AgentStep) -> int:
        """Add an execution step and return its index."""
        self.steps.append(step)
        return len(self.steps) - 1

    def set_pending_approval(
        self,
        step_index: int,
        tool_name: str,
        tool_params: dict,
        tool_call_id: str,
        description: str,
    ) -> None:
        """Set a pending approval for a tool call."""
        self.pending_approval = PendingApproval(
            step_index=step_index,
            tool_name=tool_name,
            tool_params=tool_params,
            tool_call_id=tool_call_id,
            description=description,
        )

    def clear_pending_approval(self) -> PendingApproval | None:
        """Clear and return the pending approval."""
        approval = self.pending_approval
        self.pending_approval = None
        return approval

    def add_tokens(self, prompt: int, completion: int) -> None:
        self.total_prompt_tokens += prompt
        self.total_completion_tokens += completion

    def get_messages(self) -> list[dict]:
        """Return a copy of the message history."""
        return list(self.messages)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "has_pending_approval": self.pending_approval is not None,
        }
