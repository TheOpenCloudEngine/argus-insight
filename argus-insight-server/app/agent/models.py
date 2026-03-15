"""SQLAlchemy ORM models for agent management."""

from sqlalchemy import Column, DateTime, Float, String, func

from app.core.database import Base


class ArgusAgent(Base):
    """Agent master table. Stores agent identity and latest resource usage."""

    __tablename__ = "argus_agents"

    hostname = Column(String(255), primary_key=True)
    ip_address = Column(String(45), nullable=False)
    version = Column(String(50))
    kernel_version = Column(String(255))
    os_version = Column(String(255))
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    status = Column(String(20), nullable=False, default="UNREGISTERED")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ArgusAgentHeartbeat(Base):
    """Agent heartbeat tracking table. Stores the last heartbeat timestamp per agent."""

    __tablename__ = "argus_agents_heartbeat"

    hostname = Column(String(255), primary_key=True)
    last_heartbeat_at = Column(DateTime, server_default=func.now())
