"""Sync engine - orchestrates the user/group synchronization process.

Flow:
1. Fetch users and groups from the configured source (LDAP/Unix/File)
2. Fetch existing users and groups from Ranger Admin
3. Create/update users in Ranger
4. Create/update groups in Ranger
5. Sync group memberships
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


class SyncEngine:
    """Orchestrates user/group synchronization from source to Ranger."""

    def __init__(self) -> None:
        self.source: SyncSource = _create_source()
        self.ranger = RangerClient()
        self.result = SyncResult()

    def run(self) -> SyncResult:
        """Execute the full sync process."""
        start_time = time.time()
        self.result = SyncResult(source_type=self.source.get_source_type())

        logger.info(
            "Starting user/group sync from '%s' source to Ranger at %s",
            self.source.get_source_type(),
            settings.ranger_url,
        )

        try:
            # Check Ranger connectivity
            if not self.ranger.check_connection():
                self.result.errors.append(
                    f"Cannot connect to Ranger Admin at {settings.ranger_url}"
                )
                return self.result

            # Fetch from source
            logger.info("Fetching users and groups from source...")
            source_users = self.source.get_users()
            source_groups = self.source.get_groups()
            self.result.users_total = len(source_users)
            self.result.groups_total = len(source_groups)

            # Load existing Ranger state
            logger.info("Loading existing users and groups from Ranger...")
            self.ranger.list_users()
            self.ranger.list_groups()

            # Sync groups first (users reference groups)
            logger.info("Syncing %d groups to Ranger...", len(source_groups))
            self._sync_groups(source_groups)

            # Sync users
            logger.info("Syncing %d users to Ranger...", len(source_users))
            self._sync_users(source_users)

            # Sync group memberships
            logger.info("Syncing group memberships...")
            self._sync_memberships(source_users, source_groups)

        except Exception as e:
            logger.exception("Sync failed with error")
            self.result.errors.append(str(e))
        finally:
            self.ranger.close()

        elapsed = time.time() - start_time
        logger.info(
            "Sync completed in %.1fs - users: %d total, %d created, %d updated, %d skipped; "
            "groups: %d total, %d created, %d updated, %d skipped; "
            "memberships updated: %d; errors: %d",
            elapsed,
            self.result.users_total,
            self.result.users_created,
            self.result.users_updated,
            self.result.users_skipped,
            self.result.groups_total,
            self.result.groups_created,
            self.result.groups_updated,
            self.result.groups_skipped,
            self.result.group_memberships_updated,
            len(self.result.errors),
        )

        return self.result

    def _sync_users(self, users: list[UserInfo]) -> None:
        """Sync users to Ranger: create new users, update existing ones."""
        for user in users:
            try:
                existing = self.ranger.get_user_by_name(user.name)
                if existing is None:
                    self.ranger.create_user(
                        name=user.name,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        email=user.email,
                        description=user.description,
                        group_names=user.group_names,
                    )
                    self.result.users_created += 1
                else:
                    if self._user_needs_update(existing, user):
                        update_data = dict(existing)
                        update_data["firstName"] = user.first_name or existing.get("firstName", "")
                        update_data["lastName"] = user.last_name or existing.get("lastName", "")
                        update_data["emailAddress"] = user.email or existing.get("emailAddress", "")
                        update_data["description"] = user.description or existing.get(
                            "description", ""
                        )
                        update_data["groupNameList"] = user.group_names
                        self.ranger.update_user(existing["id"], update_data)
                        self.result.users_updated += 1
                    else:
                        self.result.users_skipped += 1
            except Exception as e:
                msg = f"Failed to sync user '{user.name}': {e}"
                logger.error(msg)
                self.result.errors.append(msg)

    def _sync_groups(self, groups: list[GroupInfo]) -> None:
        """Sync groups to Ranger: create new groups, update existing ones."""
        for group in groups:
            try:
                existing = self.ranger.get_group_by_name(group.name)
                if existing is None:
                    self.ranger.create_group(
                        name=group.name,
                        description=group.description,
                    )
                    self.result.groups_created += 1
                else:
                    if self._group_needs_update(existing, group):
                        update_data = dict(existing)
                        update_data["description"] = group.description or existing.get(
                            "description", ""
                        )
                        self.ranger.update_group(existing["id"], update_data)
                        self.result.groups_updated += 1
                    else:
                        self.result.groups_skipped += 1
            except Exception as e:
                msg = f"Failed to sync group '{group.name}': {e}"
                logger.error(msg)
                self.result.errors.append(msg)

    def _sync_memberships(self, users: list[UserInfo], groups: list[GroupInfo]) -> None:
        """Sync group memberships from source data.

        Combines membership info from both user records (user.group_names)
        and group records (group.member_names).
        """
        # Build a combined membership map: group_name -> set of user_names
        membership_map: dict[str, set[str]] = {}

        for user in users:
            for group_name in user.group_names:
                membership_map.setdefault(group_name, set()).add(user.name)

        for group in groups:
            for member_name in group.member_names:
                membership_map.setdefault(group.name, set()).add(member_name)

        for group_name, member_names in membership_map.items():
            for user_name in member_names:
                try:
                    result = self.ranger.add_user_to_group(user_name, group_name)
                    if result is not None:
                        self.result.group_memberships_updated += 1
                except Exception as e:
                    msg = f"Failed to add user '{user_name}' to group '{group_name}': {e}"
                    logger.error(msg)
                    self.result.errors.append(msg)

    @staticmethod
    def _user_needs_update(existing: dict, source: UserInfo) -> bool:
        """Check if a Ranger user needs to be updated based on source data."""
        if source.first_name and source.first_name != existing.get("firstName", ""):
            return True
        if source.last_name and source.last_name != existing.get("lastName", ""):
            return True
        if source.email and source.email != existing.get("emailAddress", ""):
            return True
        if source.description and source.description != existing.get("description", ""):
            return True

        existing_groups = set(existing.get("groupNameList", []))
        source_groups = set(source.group_names)
        if source_groups and source_groups != existing_groups:
            return True

        return False

    @staticmethod
    def _group_needs_update(existing: dict, source: GroupInfo) -> bool:
        """Check if a Ranger group needs to be updated based on source data."""
        if source.description and source.description != existing.get("description", ""):
            return True
        return False
