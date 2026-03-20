"""Sync engine - orchestrates the user/group synchronization process.

Flow:
1. Load existing users from the Argus database (argus_users table)
2. Fetch users and groups from the configured source (LDAP/Unix/File)
3. Sync users to the database (create new, update changed, reactivate)
4. Deactivate users that no longer exist in the source
"""

import logging
import time

from app.core.config import settings
from app.core.models import GroupInfo, SyncResult, UserInfo
from app.db.client import DatabaseClient
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
    """Orchestrates user/group synchronization from source to Argus database."""

    def __init__(self) -> None:
        self.source: SyncSource = _create_source()
        self.db = DatabaseClient()
        self.result = SyncResult()

    def run(self) -> SyncResult:
        """Execute the full sync process."""
        start_time = time.time()
        source_type = self.source.get_source_type()
        self.result = SyncResult(source_type=source_type)

        logger.info(
            "Starting user/group sync from '%s' source to Argus database",
            source_type,
        )

        try:
            # Step 1: Check database connectivity
            if not self.db.check_connection():
                self.result.errors.append("Cannot connect to Argus database")
                return self.result

            # Step 2: Load existing users from database
            logger.info("Loading existing users from database...")
            existing_users = self.db.load_existing_users()

            # Step 3: Fetch users and groups from source
            logger.info("Fetching users and groups from source...")
            source_users = self.source.get_users()
            source_groups = self.source.get_groups()
            self.result.users_total = len(source_users)
            self.result.groups_total = len(source_groups)

            # Step 4: Sync users to database
            logger.info("Syncing %d users to database...", len(source_users))
            user_dicts = self._build_user_dicts(source_users, source_groups)
            self._sync_users(user_dicts, existing_users)

            # Step 5: Deactivate removed users
            self._handle_deactivations(source_users, existing_users)

        except Exception as e:
            logger.exception("Sync failed with error")
            self.result.errors.append(str(e))
        finally:
            self.db.close()

        elapsed = time.time() - start_time
        logger.info(
            "Sync completed in %.1fs - users: %d total, %d created, %d updated, "
            "%d skipped; groups: %d total; errors: %d",
            elapsed,
            self.result.users_total,
            self.result.users_created,
            self.result.users_updated,
            self.result.users_skipped,
            self.result.groups_total,
            len(self.result.errors),
        )

        return self.result

    @staticmethod
    def _build_user_dicts(users: list[UserInfo], groups: list[GroupInfo]) -> list[dict[str, str]]:
        """Build a list of user dicts for database sync.

        Combines user info from both user records and group membership data.
        Returns deduplicated user list keyed by username.
        """
        user_map: dict[str, dict[str, str]] = {}

        for user in users:
            user_map[user.name] = {
                "username": user.name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
            }

        # Ensure users referenced in groups are also included
        for group in groups:
            for member_name in group.member_names:
                if member_name not in user_map:
                    user_map[member_name] = {
                        "username": member_name,
                        "first_name": member_name,
                        "last_name": "",
                        "email": "",
                    }

        return list(user_map.values())

    def _sync_users(
        self,
        user_dicts: list[dict[str, str]],
        existing: dict[str, dict],
    ) -> None:
        """Sync users to the database."""
        try:
            created, updated = self.db.sync_users(user_dicts, existing)
            self.result.users_created = created
            self.result.users_updated = updated
            self.result.users_skipped = len(user_dicts) - created - updated
        except Exception as e:
            msg = f"Failed to sync users: {e}"
            logger.error(msg)
            self.result.errors.append(msg)

    def _handle_deactivations(
        self,
        source_users: list[UserInfo],
        existing: dict[str, dict],
    ) -> None:
        """Deactivate users that exist in DB but not in source."""
        source_usernames = {u.name for u in source_users}
        try:
            count = self.db.deactivate_removed_users(source_usernames, existing)
            if count > 0:
                logger.info("Deactivated %d users not found in source", count)
        except Exception as e:
            logger.warning("Failed to deactivate removed users: %s", e)
