"""Host management service - hostname, /etc/hosts, /etc/resolv.conf."""

import asyncio
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.hostmgr.schemas import (
    BackupResult,
    FileContent,
    HostnameInfo,
    HostnameValidation,
    NameserverInfo,
    OperationResult,
    ResolvConfInfo,
)

logger = logging.getLogger(__name__)

HOSTS_FILE = Path("/etc/hosts")
RESOLV_CONF = Path("/etc/resolv.conf")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run(cmd: str) -> tuple[int, str, str]:
    """Run a shell command and return (exit_code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode(errors="replace").strip(),
        stderr.decode(errors="replace").strip(),
    )


def _backup_file(source: Path, prefix: str) -> BackupResult:
    """Backup a single file to backup_dir as prefix_YYYYMMDD.zip."""
    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    zip_name = f"{prefix}_{date_str}.zip"
    zip_path = backup_dir / zip_name

    if not source.is_file():
        return BackupResult(
            success=False,
            backup_path=str(zip_path),
            message=f"File not found: {source}",
        )

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, source.name)

        logger.info("Backed up %s to %s", source, zip_path)
        return BackupResult(
            success=True,
            backup_path=str(zip_path),
            message=f"Backed up {source.name} to {zip_name}",
        )
    except OSError as e:
        return BackupResult(
            success=False,
            backup_path=str(zip_path),
            message=str(e),
        )


# ---------------------------------------------------------------------------
# 1. Hostname change
# ---------------------------------------------------------------------------


async def change_hostname(hostname: str) -> OperationResult:
    """Change the system hostname using hostnamectl."""
    logger.info("Changing hostname to: %s", hostname)
    exit_code, stdout, stderr = await _run(f"hostnamectl set-hostname {hostname}")
    if exit_code != 0:
        return OperationResult(
            success=False,
            message=f"Failed to set hostname: {stderr}",
        )
    return OperationResult(
        success=True,
        message=f"Hostname changed to {hostname}",
    )


# ---------------------------------------------------------------------------
# 2. Hostname validation
# ---------------------------------------------------------------------------


async def validate_hostname() -> HostnameValidation:
    """Validate hostname by comparing 'hostname' and 'hostname -f'."""
    _, short, _ = await _run("hostname")
    _, fqdn, stderr_f = await _run("hostname -f")

    # hostname -f may fail if DNS is not configured
    if not fqdn:
        fqdn = short

    is_consistent = bool(short and fqdn and (fqdn == short or fqdn.startswith(short + ".")))

    if is_consistent:
        message = f"Hostname is consistent: {short} / {fqdn}"
    else:
        message = f"Hostname mismatch: hostname={short}, hostname -f={fqdn}"

    return HostnameValidation(
        hostname=short,
        fqdn=fqdn,
        is_consistent=is_consistent,
        message=message,
    )


# ---------------------------------------------------------------------------
# 3. Hostname info
# ---------------------------------------------------------------------------


async def get_hostname() -> HostnameInfo:
    """Get current hostname and FQDN."""
    _, short, _ = await _run("hostname")
    _, fqdn, _ = await _run("hostname -f")
    if not fqdn:
        fqdn = short
    return HostnameInfo(hostname=short, fqdn=fqdn)


# ---------------------------------------------------------------------------
# 4. /etc/hosts read
# ---------------------------------------------------------------------------


def read_hosts_file() -> FileContent:
    """Read /etc/hosts file content."""
    if not HOSTS_FILE.is_file():
        raise FileNotFoundError(f"File not found: {HOSTS_FILE}")
    return FileContent(
        path=str(HOSTS_FILE),
        content=HOSTS_FILE.read_text(encoding="utf-8"),
    )


# ---------------------------------------------------------------------------
# 5. /etc/hosts update
# ---------------------------------------------------------------------------


def update_hosts_file(content: str) -> OperationResult:
    """Update /etc/hosts file content."""
    try:
        HOSTS_FILE.write_text(content, encoding="utf-8")
        logger.info("Updated %s", HOSTS_FILE)
        return OperationResult(success=True, message=f"Updated {HOSTS_FILE}")
    except OSError as e:
        return OperationResult(success=False, message=str(e))


# ---------------------------------------------------------------------------
# 6. /etc/hosts backup
# ---------------------------------------------------------------------------


def backup_hosts_file() -> BackupResult:
    """Backup /etc/hosts to backup_dir as hosts_YYYYMMDD.zip."""
    return _backup_file(HOSTS_FILE, "hosts")


# ---------------------------------------------------------------------------
# 7. /etc/resolv.conf read
# ---------------------------------------------------------------------------


def read_resolv_conf() -> FileContent:
    """Read /etc/resolv.conf file content."""
    if not RESOLV_CONF.is_file():
        raise FileNotFoundError(f"File not found: {RESOLV_CONF}")
    return FileContent(
        path=str(RESOLV_CONF),
        content=RESOLV_CONF.read_text(encoding="utf-8"),
    )


# ---------------------------------------------------------------------------
# 8. /etc/resolv.conf update
# ---------------------------------------------------------------------------


def update_resolv_conf(content: str) -> OperationResult:
    """Update /etc/resolv.conf file content."""
    try:
        RESOLV_CONF.write_text(content, encoding="utf-8")
        logger.info("Updated %s", RESOLV_CONF)
        return OperationResult(success=True, message=f"Updated {RESOLV_CONF}")
    except OSError as e:
        return OperationResult(success=False, message=str(e))


# ---------------------------------------------------------------------------
# 9. /etc/resolv.conf backup
# ---------------------------------------------------------------------------


def backup_resolv_conf() -> BackupResult:
    """Backup /etc/resolv.conf to backup_dir as resolv_YYYYMMDD.zip."""
    return _backup_file(RESOLV_CONF, "resolv")


# ---------------------------------------------------------------------------
# 10. /etc/resolv.conf nameserver list
# ---------------------------------------------------------------------------


def get_nameservers() -> ResolvConfInfo:
    """Parse /etc/resolv.conf and return structured nameserver info."""
    if not RESOLV_CONF.is_file():
        return ResolvConfInfo(nameservers=[], raw="")

    raw = RESOLV_CONF.read_text(encoding="utf-8")
    nameservers = []
    search_domains: list[str] = []
    options: list[str] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue

        parts = line.split()
        if not parts:
            continue

        directive = parts[0].lower()
        if directive == "nameserver" and len(parts) >= 2:
            nameservers.append(NameserverInfo(address=parts[1]))
        elif directive in ("search", "domain") and len(parts) >= 2:
            search_domains.extend(parts[1:])
        elif directive == "options" and len(parts) >= 2:
            options.extend(parts[1:])

    return ResolvConfInfo(
        nameservers=nameservers,
        search_domains=search_domains,
        options=options,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# 11. /etc/resolv.conf nameserver update
# ---------------------------------------------------------------------------


def update_nameservers(nameservers: list[str]) -> OperationResult:
    """Update nameserver entries in /etc/resolv.conf.

    Preserves existing search, domain, and options directives.
    Only replaces nameserver lines.
    """
    if not nameservers:
        return OperationResult(
            success=False,
            message="At least one nameserver is required",
        )

    if not RESOLV_CONF.is_file():
        # Create new file with just nameservers
        content = "\n".join(f"nameserver {ns}" for ns in nameservers) + "\n"
        return update_resolv_conf(content)

    raw = RESOLV_CONF.read_text(encoding="utf-8")

    # Remove existing nameserver lines, preserve everything else
    preserved_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("nameserver"):
            continue
        preserved_lines.append(line)

    # Build new content: preserved lines + new nameservers
    new_lines = preserved_lines[:]
    # Remove trailing empty lines
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    # Add nameservers
    for ns in nameservers:
        new_lines.append(f"nameserver {ns}")

    new_lines.append("")  # trailing newline
    content = "\n".join(new_lines)

    try:
        RESOLV_CONF.write_text(content, encoding="utf-8")
        logger.info("Updated nameservers in %s: %s", RESOLV_CONF, nameservers)
        return OperationResult(
            success=True,
            message=f"Updated nameservers: {', '.join(nameservers)}",
        )
    except OSError as e:
        return OperationResult(success=False, message=str(e))
