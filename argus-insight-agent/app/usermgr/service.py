"""User management service - users, groups, sudo, backup."""

import asyncio
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.usermgr.schemas import (
    BackupResult,
    GroupInfo,
    OperationResult,
    UserDetail,
    UserInfo,
)

logger = logging.getLogger(__name__)

PASSWD_FILE = Path("/etc/passwd")
SHADOW_FILE = Path("/etc/shadow")
GROUP_FILE = Path("/etc/group")
GSHADOW_FILE = Path("/etc/gshadow")
SUDOERS_DIR = Path("/etc/sudoers.d")


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


def _parse_passwd_line(line: str) -> UserInfo | None:
    """Parse a single /etc/passwd line into UserInfo."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(":")
    if len(parts) < 7:
        return None
    return UserInfo(
        username=parts[0],
        uid=int(parts[2]),
        gid=int(parts[3]),
        comment=parts[4],
        home=parts[5],
        shell=parts[6],
    )


def _parse_group_line(line: str) -> GroupInfo | None:
    """Parse a single /etc/group line into GroupInfo."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(":")
    if len(parts) < 4:
        return None
    members = [m for m in parts[3].split(",") if m]
    return GroupInfo(
        groupname=parts[0],
        gid=int(parts[2]),
        members=members,
    )


def _gid_to_groupname(gid: int) -> str:
    """Resolve a GID to a group name from /etc/group."""
    if not GROUP_FILE.is_file():
        return str(gid)
    for line in GROUP_FILE.read_text(encoding="utf-8").splitlines():
        info = _parse_group_line(line)
        if info and info.gid == gid:
            return info.groupname
    return str(gid)


def _user_groups(username: str) -> list[str]:
    """Get all group names that a user belongs to (from /etc/group)."""
    if not GROUP_FILE.is_file():
        return []
    groups = []
    for line in GROUP_FILE.read_text(encoding="utf-8").splitlines():
        info = _parse_group_line(line)
        if info and username in info.members:
            groups.append(info.groupname)
    return groups


def _has_sudo(username: str) -> bool:
    """Check if a user has sudo privileges."""
    # Check /etc/sudoers.d/ for a file granting sudo
    sudoers_file = SUDOERS_DIR / username
    if sudoers_file.is_file():
        return True

    # Check if user is in wheel or sudo group
    groups = _user_groups(username)
    return "wheel" in groups or "sudo" in groups


# ---------------------------------------------------------------------------
# 1. Backup user/group files
# ---------------------------------------------------------------------------


def backup_user_files() -> BackupResult:
    """Backup /etc/passwd, /etc/shadow, /etc/group, /etc/gshadow to zip."""
    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d%H%M%S")
    zip_name = f"users_{date_str}.zip"
    zip_path = backup_dir / zip_name

    targets = [PASSWD_FILE, SHADOW_FILE, GROUP_FILE, GSHADOW_FILE]
    found = [t for t in targets if t.is_file()]

    if not found:
        return BackupResult(
            success=False,
            backup_path=str(zip_path),
            message="No user/group files found to backup",
        )

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in found:
                zf.write(f, f.name)

        logger.info("Backed up user/group files to %s", zip_path)
        return BackupResult(
            success=True,
            backup_path=str(zip_path),
            message=f"Backed up {len(found)} files: {', '.join(f.name for f in found)}",
        )
    except OSError as e:
        return BackupResult(
            success=False,
            backup_path=str(zip_path),
            message=str(e),
        )


# ---------------------------------------------------------------------------
# 2. Grant sudo
# ---------------------------------------------------------------------------


async def grant_sudo(username: str) -> OperationResult:
    """Grant sudo privileges to a user via /etc/sudoers.d/."""
    # Verify user exists
    users = list_users()
    if not any(u.username == username for u in users):
        return OperationResult(
            success=False,
            message=f"User not found: {username}",
        )

    if _has_sudo(username):
        return OperationResult(
            success=True,
            message=f"User {username} already has sudo privileges",
        )

    # Create sudoers.d entry
    SUDOERS_DIR.mkdir(parents=True, exist_ok=True)
    sudoers_file = SUDOERS_DIR / username

    try:
        sudoers_file.write_text(
            f"{username} ALL=(ALL) NOPASSWD:ALL\n",
            encoding="utf-8",
        )
        # sudoers files must be 0440
        sudoers_file.chmod(0o440)
        logger.info("Granted sudo to user: %s", username)
        return OperationResult(
            success=True,
            message=f"Sudo privileges granted to {username}",
        )
    except OSError as e:
        return OperationResult(success=False, message=str(e))


# ---------------------------------------------------------------------------
# 3. List users
# ---------------------------------------------------------------------------


def list_users() -> list[UserInfo]:
    """Read and parse /etc/passwd."""
    if not PASSWD_FILE.is_file():
        return []
    results = []
    for line in PASSWD_FILE.read_text(encoding="utf-8").splitlines():
        info = _parse_passwd_line(line)
        if info:
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# 4. List groups
# ---------------------------------------------------------------------------


def list_groups() -> list[GroupInfo]:
    """Read and parse /etc/group."""
    if not GROUP_FILE.is_file():
        return []
    results = []
    for line in GROUP_FILE.read_text(encoding="utf-8").splitlines():
        info = _parse_group_line(line)
        if info:
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# 5. User detail (info + groups)
# ---------------------------------------------------------------------------


def get_user_detail(username: str) -> UserDetail | None:
    """Get detailed user information including group membership."""
    users = list_users()
    user = next((u for u in users if u.username == username), None)
    if user is None:
        return None

    primary_group = _gid_to_groupname(user.gid)
    groups = _user_groups(username)
    # Include primary group in the list
    if primary_group not in groups:
        groups.insert(0, primary_group)

    return UserDetail(
        username=user.username,
        uid=user.uid,
        gid=user.gid,
        comment=user.comment,
        home=user.home,
        shell=user.shell,
        primary_group=primary_group,
        groups=groups,
        has_sudo=_has_sudo(username),
    )


# ---------------------------------------------------------------------------
# 6. Create user
# ---------------------------------------------------------------------------


async def create_user(
    username: str,
    group: str | None = None,
    shell: str = "/bin/bash",
    create_home: bool = True,
    home: str | None = None,
    comment: str = "",
) -> OperationResult:
    """Create a new system user via useradd."""
    # Check if user already exists
    users = list_users()
    if any(u.username == username for u in users):
        return OperationResult(
            success=False,
            message=f"User already exists: {username}",
        )

    cmd_parts = ["useradd"]

    # Group: default to username
    target_group = group or username
    cmd_parts.extend(["-g", target_group])

    # Ensure the group exists; create if not
    groups = list_groups()
    if not any(g.groupname == target_group for g in groups):
        rc, _, err = await _run(f"groupadd {target_group}")
        if rc != 0:
            return OperationResult(
                success=False,
                message=f"Failed to create group {target_group}: {err}",
            )

    # Shell
    cmd_parts.extend(["-s", shell])

    # Home directory
    if create_home:
        cmd_parts.append("-m")
        if home:
            cmd_parts.extend(["-d", home])
    else:
        cmd_parts.append("-M")

    # Comment (GECOS)
    if comment:
        cmd_parts.extend(["-c", f'"{comment}"'])

    cmd_parts.append(username)
    cmd = " ".join(cmd_parts)

    exit_code, stdout, stderr = await _run(cmd)
    if exit_code != 0:
        return OperationResult(
            success=False,
            message=f"Failed to create user {username}: {stderr}",
        )

    logger.info("Created user: %s", username)
    return OperationResult(
        success=True,
        message=f"User {username} created successfully",
    )


# ---------------------------------------------------------------------------
# 7. Delete user
# ---------------------------------------------------------------------------


async def delete_user(username: str, remove_home: bool = False) -> OperationResult:
    """Delete a system user via userdel."""
    # Check if user exists
    users = list_users()
    if not any(u.username == username for u in users):
        return OperationResult(
            success=False,
            message=f"User not found: {username}",
        )

    cmd = "userdel"
    if remove_home:
        cmd += " -r"
    cmd += f" {username}"

    exit_code, stdout, stderr = await _run(cmd)
    if exit_code != 0:
        return OperationResult(
            success=False,
            message=f"Failed to delete user {username}: {stderr}",
        )

    # Clean up sudoers entry if exists
    sudoers_file = SUDOERS_DIR / username
    if sudoers_file.is_file():
        try:
            sudoers_file.unlink()
            logger.info("Removed sudoers entry for %s", username)
        except OSError:
            pass

    logger.info("Deleted user: %s", username)
    return OperationResult(
        success=True,
        message=f"User {username} deleted successfully",
    )
