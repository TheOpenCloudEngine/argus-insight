"""Host management API routes."""

from fastapi import APIRouter, HTTPException

from app.hostmgr.schemas import (
    BackupResult,
    FileContent,
    FileUpdateRequest,
    HostnameChangeRequest,
    HostnameInfo,
    HostnameValidation,
    NameserverUpdateRequest,
    OperationResult,
    ResolvConfInfo,
)
from app.hostmgr.service import (
    backup_hosts_file,
    backup_resolv_conf,
    change_hostname,
    get_hostname,
    get_nameservers,
    read_hosts_file,
    read_resolv_conf,
    update_hosts_file,
    update_nameservers,
    update_resolv_conf,
    validate_hostname,
)

router = APIRouter(prefix="/host", tags=["host"])


# ---------------------------------------------------------------------------
# Hostname
# ---------------------------------------------------------------------------


@router.get("/hostname", response_model=HostnameInfo)
async def hostname_get() -> HostnameInfo:
    """Get current hostname and FQDN."""
    return await get_hostname()


@router.put("/hostname", response_model=OperationResult)
async def hostname_change(request: HostnameChangeRequest) -> OperationResult:
    """Change the system hostname."""
    return await change_hostname(request.hostname)


@router.get("/hostname/validate", response_model=HostnameValidation)
async def hostname_validate() -> HostnameValidation:
    """Validate hostname consistency (hostname vs hostname -f)."""
    return await validate_hostname()


# ---------------------------------------------------------------------------
# /etc/hosts
# ---------------------------------------------------------------------------


@router.get("/hosts", response_model=FileContent)
async def hosts_read() -> FileContent:
    """Read /etc/hosts file."""
    try:
        return read_hosts_file()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/hosts", response_model=OperationResult)
async def hosts_update(request: FileUpdateRequest) -> OperationResult:
    """Update /etc/hosts file."""
    return update_hosts_file(request.content)


@router.post("/hosts/backup", response_model=BackupResult)
async def hosts_backup() -> BackupResult:
    """Backup /etc/hosts file."""
    return backup_hosts_file()


# ---------------------------------------------------------------------------
# /etc/resolv.conf
# ---------------------------------------------------------------------------


@router.get("/resolv", response_model=FileContent)
async def resolv_read() -> FileContent:
    """Read /etc/resolv.conf file."""
    try:
        return read_resolv_conf()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/resolv", response_model=OperationResult)
async def resolv_update(request: FileUpdateRequest) -> OperationResult:
    """Update /etc/resolv.conf file."""
    return update_resolv_conf(request.content)


@router.post("/resolv/backup", response_model=BackupResult)
async def resolv_backup() -> BackupResult:
    """Backup /etc/resolv.conf file."""
    return backup_resolv_conf()


@router.get("/resolv/nameservers", response_model=ResolvConfInfo)
async def resolv_nameservers() -> ResolvConfInfo:
    """Get parsed nameserver list from /etc/resolv.conf."""
    return get_nameservers()


@router.put("/resolv/nameservers", response_model=OperationResult)
async def resolv_nameservers_update(
    request: NameserverUpdateRequest,
) -> OperationResult:
    """Update nameserver entries in /etc/resolv.conf."""
    return update_nameservers(request.nameservers)
