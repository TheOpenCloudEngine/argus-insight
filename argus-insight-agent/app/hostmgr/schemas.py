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


# ---------------------------------------------------------------------------
# Ulimit
# ---------------------------------------------------------------------------

# Mapping of ulimit option flags to resource names
ULIMIT_OPTIONS: dict[str, str] = {
    "-n": "open files",
    "-u": "max user processes",
    "-v": "virtual memory",
    "-s": "stack size",
    "-c": "core file size",
}


class UlimitEntry(BaseModel):
    """A single ulimit resource entry."""

    option: str = Field(description="Ulimit flag (e.g. -n, -u)")
    resource: str = Field(description="Resource name (e.g. 'open files')")
    soft: str = Field(description="Soft limit value")
    hard: str = Field(description="Hard limit value")


class UlimitAllResponse(BaseModel):
    """All ulimit values."""

    entries: list[UlimitEntry] = Field(default_factory=list)


class UlimitSetRequest(BaseModel):
    """Request to set a ulimit value."""

    option: str = Field(..., description="Ulimit flag (-n, -u, -v, -s, -c)")
    value: str = Field(..., description="New limit value (number or 'unlimited')")


class LimitsConfEntry(BaseModel):
    """A single entry in /etc/security/limits.conf."""

    domain: str = Field(description="User, group (@group), or * for all")
    type: str = Field(description="soft or hard")
    item: str = Field(description="Resource item (e.g. nofile, nproc)")
    value: str = Field(description="Limit value")


class LimitsConfSetRequest(BaseModel):
    """Request to set max open files in /etc/security/limits.conf."""

    user: str = Field(..., description="Username or '*' for all users")
    soft: str = Field(..., description="Soft limit value (number or 'unlimited')")
    hard: str = Field(..., description="Hard limit value (number or 'unlimited')")


class LimitsConfResponse(BaseModel):
    """Response after updating /etc/security/limits.conf."""

    success: bool
    message: str
    entries: list[LimitsConfEntry] = Field(default_factory=list)
