"""ORM models for conversation history and agent task logs."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class Conversation(Base):
    """Persisted conversation session."""

    __tablename__ = "de_agent_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False, default="anonymous")
    title = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    total_steps = Column(Integer, nullable=False, default=0)
    total_prompt_tokens = Column(Integer, nullable=False, default=0)
    total_completion_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ConversationMessage(Base):
    """Individual messages within a conversation."""

    __tablename__ = "de_agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, tool
    content = Column(Text, nullable=False)
    step_type = Column(String(30), nullable=True)  # thinking, tool_call, answer, etc.
    tool_name = Column(String(100), nullable=True)
    tool_params = Column(Text, nullable=True)
    tool_result = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentTaskLog(Base):
    """Audit log of agent tool executions."""

    __tablename__ = "de_agent_task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    tool_params = Column(Text, nullable=True)
    result_success = Column(String(10), nullable=False, default="true")
    result_summary = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    executed_at = Column(DateTime, nullable=False, server_default=func.now())
