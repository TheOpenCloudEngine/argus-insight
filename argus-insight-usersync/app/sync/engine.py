"""Sync engine - orchestrates the user/group synchronization process.

Follows the same flow as the real Apache Ranger UserSync (PolicyMgrUserGroupBuilder):

1. Load existing group-user mappings from Ranger (GET /ugsync/groupusers)
2. Fetch users and groups from the configured source (LDAP/Unix/File)
3. Build VXUser/VXGroup payloads and bulk push to Ranger (POST /ugsync/users, groups)
4. Compute membership deltas (addUsers/delUsers) and bulk push (POST /ugsync/groupusers)
5. Optionally mark deleted users/groups as not-visible
6. Post audit info
"""

import logging
import time

from app.core.config import settings
from app.core.models import GroupInfo, SyncResult, UserInfo
from app.ranger.client import RangerClient
from app.source.base import SyncSource

logger = logging.getLogger(__name__)


def _create_source() -> SyncSource:
    """Create a sync source based on configuration."""
    source_type = settings.sync_source.lower()

    if source_type == "ldap":
        from app.source.ldap_source import LdapSource

        return LdapSource()
    elif source_type == "file":
        from app.source.file_source import FileSource

        return FileSource()
    elif source_type == "unix":
        from app.source.unix_source import UnixSource

        return UnixSource()
    else:
        raise ValueError(f"Unknown sync source type: {source_type}")


def _sync_source_label(source_type: str) -> str:
    """Return the syncSource label used in Ranger payloads."""
    return {"ldap": "LDAP", "unix": "Unix", "file": "File"}.get(
        source_type, source_type.capitalize()
    )


class SyncEngine:
    """Orchestrates user/group synchronization from source to Ranger.

    Uses the bulk UGSync API for efficient synchronization,
    matching the real Ranger UserSync behavior.
    """

    def __init__(self) -> None:
        self.source: SyncSource = _create_source()
        self.ranger = RangerClient()
        self.result = SyncResult()

    def run(self) -> SyncResult:
        """Execute the full sync process."""
        start_time = time.time()
        source_type = self.source.get_source_type()
        self.result = SyncResult(source_type=source_type)
        sync_label = _sync_source_label(source_type)

        logger.info(
            "Starting user/group sync from '%s' source to Ranger at %s",
            source_type,
            settings.ranger_url,
        )

        try:
            # Step 1: Check Ranger connectivity
            if not self.ranger.check_connection():
                self.result.errors.append(
                    f"Cannot connect to Ranger Admin at {settings.ranger_url}"
                )
                return self.result

            # Step 2: Load existing state from Ranger
            logger.info("Loading existing group-user mappings from Ranger...")
            existing_group_users = self.ranger.load_existing_group_users()

            # Step 3: Fetch users and groups from source
            logger.info("Fetching users and groups from source...")
            source_users = self.source.get_users()
            source_groups = self.source.get_groups()
            self.result.users_total = len(source_users)
            self.result.groups_total = len(source_groups)

            # Step 4: Bulk sync groups to Ranger
            logger.info("Syncing %d groups to Ranger...", len(source_groups))
            self._bulk_sync_groups(source_groups, sync_label)

            # Step 5: Bulk sync users to Ranger
            logger.info("Syncing %d users to Ranger...", len(source_users))
            self._bulk_sync_users(source_users, sync_label)

            # Step 6: Compute and sync membership deltas
            logger.info("Syncing group memberships...")
            source_group_users = self._build_source_membership_map(source_users, source_groups)
            self._sync_membership_deltas(source_group_users, existing_group_users)

            # Step 7: Handle deletions (mark invisible)
            self._handle_deletions(source_users, source_groups, existing_group_users)

            # Step 8: Post audit info
            audit = self.ranger.build_audit_info(
                sync_source=sync_label,
                num_new_users=self.result.users_created,
                num_modified_users=self.result.users_updated,
                num_new_groups=self.result.groups_created,
                num_modified_groups=self.result.groups_updated,
            )
            self.ranger.post_audit_info(audit)

        except Exception as e:
            logger.exception("Sync failed with error")
            self.result.errors.append(str(e))
        finally:
            self.ranger.close()

        elapsed = time.time() - start_time
        logger.info(
            "Sync completed in %.1fs - users: %d total, %d created, %d updated; "
            "groups: %d total, %d created, %d updated; "
            "memberships updated: %d; errors: %d",
            elapsed,
            self.result.users_total,
            self.result.users_created,
            self.result.users_updated,
            self.result.groups_total,
            self.result.groups_created,
            self.result.groups_updated,
            self.result.group_memberships_updated,
            len(self.result.errors),
        )

        return self.result

    def _bulk_sync_users(self, users: list[UserInfo], sync_label: str) -> None:
        """Build VXUser payloads and push via bulk API."""
        vx_users = []
        for user in users:
            vx_users.append(
                self.ranger.build_vx_user(
                    name=user.name,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=user.email,
                    description=user.description,
                    group_names=user.group_names,
                    sync_source=sync_label,
                )
            )

        try:
            count = self.ranger.bulk_sync_users(vx_users, sync_label)
            # Ranger bulk API handles create vs update internally;
            # we report the total pushed count as created+updated
            self.result.users_created = count
        except Exception as e:
            msg = f"Failed to bulk sync users: {e}"
            logger.error(msg)
            self.result.errors.append(msg)

    def _bulk_sync_groups(self, groups: list[GroupInfo], sync_label: str) -> None:
        """Build VXGroup payloads and push via bulk API."""
        vx_groups = []
        for group in groups:
            vx_groups.append(
                self.ranger.build_vx_group(
                    name=group.name,
                    description=group.description,
                    sync_source=sync_label,
                )
            )

        try:
            count = self.ranger.bulk_sync_groups(vx_groups, sync_label)
            self.result.groups_created = count
        except Exception as e:
            msg = f"Failed to bulk sync groups: {e}"
            logger.error(msg)
            self.result.errors.append(msg)

    @staticmethod
    def _build_source_membership_map(
        users: list[UserInfo], groups: list[GroupInfo]
    ) -> dict[str, set[str]]:
        """Build combined membership map from source user and group data.

        Returns: {group_name: set of user_names}
        """
        membership: dict[str, set[str]] = {}

        for user in users:
            for group_name in user.group_names:
                membership.setdefault(group_name, set()).add(user.name)

        for group in groups:
            for member_name in group.member_names:
                membership.setdefault(group.name, set()).add(member_name)

        return membership

    def _sync_membership_deltas(
        self,
        source_map: dict[str, set[str]],
        existing_map: dict[str, set[str]],
    ) -> None:
        """Compute and push membership deltas (addUsers/delUsers per group)."""
        all_groups = set(source_map.keys()) | set(existing_map.keys())
        group_user_infos = []

        for group_name in all_groups:
            source_members = source_map.get(group_name, set())
            existing_members = existing_map.get(group_name, set())

            add_users = list(source_members - existing_members)
            del_users = list(existing_members - source_members)

            if add_users or del_users:
                group_user_infos.append(
                    {
                        "groupName": group_name,
                        "addUsers": add_users,
                        "delUsers": del_users,
                    }
                )

        if group_user_infos:
            try:
                count = self.ranger.bulk_sync_group_users(group_user_infos)
                self.result.group_memberships_updated = count
            except Exception as e:
                msg = f"Failed to sync group memberships: {e}"
                logger.error(msg)
                self.result.errors.append(msg)

    def _handle_deletions(
        self,
        source_users: list[UserInfo],
        source_groups: list[GroupInfo],
        existing_group_users: dict[str, set[str]],
    ) -> None:
        """Mark users/groups as not-visible if they exist in Ranger but not in source.

        This is a soft-delete -- Ranger keeps the records but hides them.
        """
        source_user_names = {u.name for u in source_users}
        source_group_names = {g.name for g in source_groups}

        # Collect all existing usernames from group memberships
        existing_user_names: set[str] = set()
        for members in existing_group_users.values():
            existing_user_names.update(members)

        deleted_users = list(existing_user_names - source_user_names)
        deleted_groups = list(set(existing_group_users.keys()) - source_group_names)

        if deleted_users:
            try:
                self.ranger.mark_users_invisible(deleted_users)
                logger.info("Marked %d deleted users as not-visible", len(deleted_users))
            except Exception as e:
                logger.warning("Failed to mark deleted users: %s", e)

        if deleted_groups:
            try:
                self.ranger.mark_groups_invisible(deleted_groups)
                logger.info(
                    "Marked %d deleted groups as not-visible",
                    len(deleted_groups),
                )
            except Exception as e:
                logger.warning("Failed to mark deleted groups: %s", e)
