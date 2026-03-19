"""Unix source - reads users and groups from /etc/passwd and /etc/group."""

import grp
import logging
import pwd

from app.core.config import settings
from app.core.models import GroupInfo, UserInfo
from app.source.base import SyncSource

logger = logging.getLogger(__name__)


class UnixSource(SyncSource):
    """Sync source that reads from Unix /etc/passwd and /etc/group."""

    def get_source_type(self) -> str:
        return "unix"

    def get_users(self) -> list[UserInfo]:
        """Read all users from /etc/passwd, filtering by min_uid."""
        users: list[UserInfo] = []
        min_uid = settings.sync_min_uid
        user_filter = set(settings.sync_user_filter)

        try:
            for pw in pwd.getpwall():
                if pw.pw_uid < min_uid:
                    continue
                if user_filter and pw.pw_name not in user_filter:
                    continue

                # Parse GECOS field for name info
                gecos = pw.pw_gecos or ""
                gecos_parts = gecos.split(",")
                full_name = gecos_parts[0] if gecos_parts else ""
                name_parts = full_name.split(None, 1)
                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                # Find groups this user belongs to
                group_names = self._get_user_groups(pw.pw_name, pw.pw_gid)

                users.append(
                    UserInfo(
                        name=pw.pw_name,
                        first_name=first_name,
                        last_name=last_name,
                        group_names=group_names,
                    )
                )
        except Exception:
            logger.exception("Failed to read users from /etc/passwd")
            raise

        logger.info("Unix source: found %d users (min_uid=%d)", len(users), min_uid)
        return users

    def get_groups(self) -> list[GroupInfo]:
        """Read all groups from /etc/group, filtering by min_gid."""
        groups: list[GroupInfo] = []
        min_gid = settings.sync_min_gid
        group_filter = set(settings.sync_group_filter)

        try:
            for gr in grp.getgrall():
                if gr.gr_gid < min_gid:
                    continue
                if group_filter and gr.gr_name not in group_filter:
                    continue

                groups.append(
                    GroupInfo(
                        name=gr.gr_name,
                        member_names=list(gr.gr_mem),
                    )
                )
        except Exception:
            logger.exception("Failed to read groups from /etc/group")
            raise

        logger.info("Unix source: found %d groups (min_gid=%d)", len(groups), min_gid)
        return groups

    def _get_user_groups(self, username: str, primary_gid: int) -> list[str]:
        """Get all group names for a user (primary + supplementary)."""
        group_names = []

        # Primary group
        try:
            primary_group = grp.getgrgid(primary_gid)
            group_names.append(primary_group.gr_name)
        except KeyError:
            pass

        # Supplementary groups
        for gr in grp.getgrall():
            if username in gr.gr_mem and gr.gr_name not in group_names:
                group_names.append(gr.gr_name)

        return group_names
