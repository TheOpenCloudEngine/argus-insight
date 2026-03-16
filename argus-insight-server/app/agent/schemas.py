"""Agent management schemas."""

from enum import Enum

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent connection status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    # Heartbeat-based statuses
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"
    DISCONNECTED = "DISCONNECTED"


class AgentRegisterRequest(BaseModel):
    """Request to register a new agent."""

    host: str = Field(..., description="Agent hostname or IP address")
    port: int = Field(4501, description="Agent port number")
    name: str | None = Field(None, description="Display name for the agent")
    tags: list[str] = Field(default_factory=list, description="Tags for grouping agents")


class AgentUpdateRequest(BaseModel):
    """Request to update an existing agent."""

    name: str | None = Field(None, description="Display name for the agent")
    port: int | None = Field(None, description="Agent port number")
    tags: list[str] | None = Field(None, description="Tags for grouping agents")


class AgentInfo(BaseModel):
    """Agent information."""

    id: str = Field(..., description="Unique agent identifier")
    host: str = Field(..., description="Agent hostname or IP address")
    port: int = Field(..., description="Agent port number")
    name: str = Field(..., description="Display name")
    tags: list[str] = Field(default_factory=list, description="Tags")
    status: AgentStatus = Field(AgentStatus.UNKNOWN, description="Current status")
    version: str | None = Field(None, description="Agent software version")
    registered_at: str = Field(..., description="Registration timestamp (ISO 8601)")
    last_seen_at: str | None = Field(None, description="Last health check timestamp (ISO 8601)")


class HeartbeatRequest(BaseModel):
    """Heartbeat payload sent by agents."""

    hostname: str = Field(..., description="Agent hostname")
    ip_address: str = Field(..., description="Agent IP address")
    version: str | None = Field(None, description="Agent software version")
    kernel_version: str | None = Field(None, description="OS kernel version")
    os_version: str | None = Field(None, description="OS distribution and version")
    cpu_count: int | None = Field(None, description="Logical CPU count")
    core_count: int | None = Field(None, description="Physical core count")
    total_memory: int | None = Field(None, description="Total memory in bytes")
    cpu_usage: float | None = Field(None, description="Total CPU usage percentage")
    memory_usage: float | None = Field(None, description="Total memory usage percentage")


class AgentHealthResponse(BaseModel):
    """Agent health check result."""

    id: str
    host: str
    port: int
    status: AgentStatus
    version: str | None = None
    response_time_ms: float | None = None
