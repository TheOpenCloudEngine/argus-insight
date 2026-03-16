"""Server management schemas."""

from datetime import datetime

from pydantic import BaseModel


class ServerResponse(BaseModel):
    """Server (agent) information returned to the client."""

    hostname: str
    ip_address: str
    version: str | None = None
    os_version: str | None = None
    core_count: int | None = None
    total_memory: int | None = None
    cpu_usage: float | None = None
    memory_usage: float | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class PaginatedServerResponse(BaseModel):
    """Paginated list of servers."""

    items: list[ServerResponse]
    total: int
    page: int
    page_size: int
