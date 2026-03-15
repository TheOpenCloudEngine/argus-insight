"""Host management schemas."""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class OperationResult(BaseModel):
    """Generic success/failure result."""

    success: bool
    message: str


class BackupResult(BaseModel):
    """Result of a file backup operation."""

    success: bool
    backup_path: str
    message: str


class FileContent(BaseModel):
    """Content of a system file."""

    path: str
    content: str


class FileUpdateRequest(BaseModel):
    """Request to update a system file."""

    content: str = Field(..., description="New file content")


# ---------------------------------------------------------------------------
# Hostname
# ---------------------------------------------------------------------------


class HostnameInfo(BaseModel):
    """Current hostname information."""

    hostname: str = Field(description="Short hostname (hostname)")
    fqdn: str = Field(description="Fully qualified domain name (hostname -f)")


class HostnameValidation(BaseModel):
    """Result of hostname validation."""

    hostname: str
    fqdn: str
    is_consistent: bool = Field(description="True if hostname and FQDN are properly configured")
    message: str


class HostnameChangeRequest(BaseModel):
    """Request to change the hostname."""

    hostname: str = Field(..., description="New hostname to set")


# ---------------------------------------------------------------------------
# /etc/resolv.conf
# ---------------------------------------------------------------------------


class NameserverInfo(BaseModel):
    """Parsed nameserver entry from /etc/resolv.conf."""

    address: str


class ResolvConfInfo(BaseModel):
    """Parsed /etc/resolv.conf information."""

    nameservers: list[NameserverInfo]
    search_domains: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    raw: str = Field("", description="Raw file content")


class NameserverUpdateRequest(BaseModel):
    """Request to update nameservers in /etc/resolv.conf."""

    nameservers: list[str] = Field(..., description="List of nameserver IP addresses")
