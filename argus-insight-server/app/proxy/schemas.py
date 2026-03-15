"""Proxy module schemas."""

from pydantic import BaseModel, Field


class ProxyCommandRequest(BaseModel):
    """Request to execute a command on an agent."""

    command: str = Field(..., description="Shell command to execute")
    timeout: int | None = Field(None, description="Execution timeout in seconds")
    cwd: str | None = Field(None, description="Working directory")


class ProxyCommandResponse(BaseModel):
    """Response from command execution on an agent."""

    agent_id: str
    host: str
    stdout: str = ""
    stderr: str = ""
    return_code: int | None = None
    error: str | None = None


class ProxyPackageRequest(BaseModel):
    """Request to manage a package on an agent."""

    action: str = Field(..., description="Action: install, remove, update")
    name: str = Field(..., description="Package name")


class ProxyPackageResponse(BaseModel):
    """Response from package operation on an agent."""

    agent_id: str
    host: str
    success: bool
    message: str = ""
    error: str | None = None
