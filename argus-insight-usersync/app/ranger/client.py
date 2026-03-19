"""Apache Ranger Admin REST API client.

Implements the UGSync REST API used by Ranger UserSync for bulk
synchronization of users, groups, and group memberships.

Bulk UGSync API endpoints (used by the real Ranger UserSync):
  - GET    /service/xusers/ugsync/groupusers       - Get existing group-user map
  - POST   /service/xusers/ugsync/users             - Bulk create/update users
  - POST   /service/xusers/ugsync/groups            - Bulk create/update groups
  - POST   /service/xusers/ugsync/groupusers        - Bulk sync group memberships
  - POST   /service/xusers/ugsync/users/visibility  - Mark deleted users invisible
  - POST   /service/xusers/ugsync/groups/visibility  - Mark deleted groups invisible
  - POST   /service/xusers/ugsync/auditinfo         - Post sync audit info

Individual XUser API endpoints (for single lookups):
  - GET    /service/xusers/users/userName/{name}    - Get user by name
  - GET    /service/xusers/groups/groupName/{name}  - Get group by name
"""

import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Ranger user source constants
USER_SOURCE_EXTERNAL = 1
GROUP_SOURCE_EXTERNAL = 1

# Ranger status / visibility
STATUS_ENABLED = 1
IS_VISIBLE = 1
IS_NOT_VISIBLE = 0


class RangerClient:
    """HTTP client for Apache Ranger Admin UGSync REST API."""

    def __init__(self) -> None:
        self._base_url = settings.ranger_url.rstrip("/")
        self._auth = (settings.ranger_username, settings.ranger_password)
        self._timeout = settings.ranger_timeout
        self._verify = settings.ranger_ssl_verify
        self._client: httpx.Client | None = None

        # Cache of existing Ranger group-user mappings: group_name -> set of usernames
        self._existing_group_users: dict[str, set[str]] = {}

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- Connection check ---

    def check_connection(self) -> bool:
        """Verify connectivity to Ranger Admin."""
        client = self._get_client()
        try:
            resp = client.get("/service/public/v2/api/service")
            return resp.status_code == 200
        except httpx.HTTPError as e:
            logger.error(
                "Failed to connect to Ranger Admin at %s: %s",
                self._base_url,
                e,
            )
            return False

    # --- Build existing state cache ---

    def load_existing_group_users(self) -> dict[str, set[str]]:
        """Fetch existing group-user mappings from Ranger.

        GET /service/xusers/ugsync/groupusers
        Returns: {group_name: set of usernames}
        """
        client = self._get_client()
        resp = client.get("/service/xusers/ugsync/groupusers")
        resp.raise_for_status()
        data = resp.json()

        self._existing_group_users = {}
        for group_name, members in data.items():
            if isinstance(members, list):
                self._existing_group_users[group_name] = set(members)
            elif isinstance(members, set):
                self._existing_group_users[group_name] = members

        logger.info(
            "Loaded %d existing groups with memberships from Ranger",
            len(self._existing_group_users),
        )
        return self._existing_group_users

    # --- Bulk UGSync API ---

    def bulk_sync_users(self, users: list[dict[str, Any]], sync_source: str = "Unix") -> int:
        """Bulk create/update users via UGSync API.

        POST /service/xusers/ugsync/users
        Payload: {"vXUsers": [...]}
        Returns: number of users processed
        """
        if not users:
            return 0

        payload = {"vXUsers": users}
        client = self._get_client()
        resp = client.post("/service/xusers/ugsync/users", json=payload)
        resp.raise_for_status()

        try:
            count = int(resp.text)
        except (ValueError, TypeError):
            count = len(users)

        logger.info("Bulk synced %d users to Ranger (source=%s)", count, sync_source)
        return count

    def bulk_sync_groups(self, groups: list[dict[str, Any]], sync_source: str = "Unix") -> int:
        """Bulk create/update groups via UGSync API.

        POST /service/xusers/ugsync/groups
        Payload: {"vXGroups": [...]}
        Returns: number of groups processed
        """
        if not groups:
            return 0

        payload = {"vXGroups": groups}
        client = self._get_client()
        resp = client.post("/service/xusers/ugsync/groups", json=payload)
        resp.raise_for_status()

        try:
            count = int(resp.text)
        except (ValueError, TypeError):
            count = len(groups)

        logger.info("Bulk synced %d groups to Ranger (source=%s)", count, sync_source)
        return count

    def bulk_sync_group_users(self, group_user_infos: list[dict[str, Any]]) -> int:
        """Bulk sync group-user memberships via UGSync API.

        POST /service/xusers/ugsync/groupusers
        Payload: [{"groupName": "...", "addUsers": [...], "delUsers": [...]}]
        Returns: number of memberships processed
        """
        if not group_user_infos:
            return 0

        client = self._get_client()
        resp = client.post("/service/xusers/ugsync/groupusers", json=group_user_infos)
        resp.raise_for_status()

        try:
            count = int(resp.text)
        except (ValueError, TypeError):
            count = len(group_user_infos)

        logger.info("Bulk synced %d group-user mappings to Ranger", count)
        return count

    # --- Visibility (soft-delete) ---

    def mark_users_invisible(self, usernames: list[str]) -> None:
        """Mark users as not-visible in Ranger (soft-delete for removed users).

        POST /service/xusers/ugsync/users/visibility
        """
        if not usernames:
            return

        payload = {name: IS_NOT_VISIBLE for name in usernames}
        client = self._get_client()
        resp = client.post("/service/xusers/ugsync/users/visibility", json=payload)
        resp.raise_for_status()
        logger.info("Marked %d users as not-visible in Ranger", len(usernames))

    def mark_groups_invisible(self, group_names: list[str]) -> None:
        """Mark groups as not-visible in Ranger (soft-delete for removed groups).

        POST /service/xusers/ugsync/groups/visibility
        """
        if not group_names:
            return

        payload = {name: IS_NOT_VISIBLE for name in group_names}
        client = self._get_client()
        resp = client.post("/service/xusers/ugsync/groups/visibility", json=payload)
        resp.raise_for_status()
        logger.info("Marked %d groups as not-visible in Ranger", len(group_names))

    # --- Audit ---

    def post_audit_info(self, audit_info: dict[str, Any]) -> None:
        """Post sync audit information to Ranger.

        POST /service/xusers/ugsync/auditinfo
        """
        client = self._get_client()
        try:
            resp = client.post("/service/xusers/ugsync/auditinfo", json=audit_info)
            resp.raise_for_status()
            logger.debug("Posted audit info to Ranger")
        except httpx.HTTPError as e:
            logger.warning("Failed to post audit info: %s", e)

    # --- Helper to build VXUser / VXGroup payloads ---

    @staticmethod
    def build_vx_user(
        name: str,
        first_name: str = "",
        last_name: str = "",
        email: str = "",
        description: str = "",
        group_names: list[str] | None = None,
        sync_source: str = "Unix",
    ) -> dict[str, Any]:
        """Build a VXUser payload dict for the bulk ugsync API."""
        return {
            "name": name,
            "firstName": first_name or name,
            "lastName": last_name,
            "emailAddress": email,
            "description": description,
            "status": STATUS_ENABLED,
            "isVisible": IS_VISIBLE,
            "userSource": USER_SOURCE_EXTERNAL,
            "userRoleList": ["ROLE_USER"],
            "groupNameList": group_names or [],
            "syncSource": sync_source,
        }

    @staticmethod
    def build_vx_group(
        name: str,
        description: str = "",
        sync_source: str = "Unix",
    ) -> dict[str, Any]:
        """Build a VXGroup payload dict for the bulk ugsync API."""
        return {
            "name": name,
            "description": description,
            "groupType": 1,
            "groupSource": GROUP_SOURCE_EXTERNAL,
            "isVisible": IS_VISIBLE,
            "syncSource": sync_source,
        }

    @staticmethod
    def build_audit_info(
        sync_source: str,
        num_new_users: int = 0,
        num_modified_users: int = 0,
        num_new_groups: int = 0,
        num_modified_groups: int = 0,
    ) -> dict[str, Any]:
        """Build a VXUgsyncAuditInfo payload."""
        return {
            "eventTime": int(time.time() * 1000),
            "userName": "rangerusersync",
            "noOfNewUsers": num_new_users,
            "noOfModifiedUsers": num_modified_users,
            "noOfNewGroups": num_new_groups,
            "noOfModifiedGroups": num_modified_groups,
            "syncSource": sync_source,
        }
