"""Apache Ranger Admin REST API client.

Implements the XUser REST API used by Ranger UserSync to create/update
users, groups, and group memberships.

Key Ranger Admin API endpoints:
  - GET/POST   /service/xusers/users          - List/create users
  - GET/PUT    /service/xusers/users/{id}      - Get/update user
  - GET        /service/xusers/users/userName/{name} - Get user by name
  - GET/POST   /service/xusers/groups          - List/create groups
  - GET/PUT    /service/xusers/groups/{id}     - Get/update group
  - GET        /service/xusers/groups/groupName/{name} - Get group by name
  - GET/POST   /service/xusers/groupusers      - List/create group-user mappings
  - GET/DELETE /service/xusers/groupusers/{id} - Get/delete group-user mapping
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Ranger user source constants
USER_SOURCE_EXTERNAL = 1  # External (synced) user
GROUP_SOURCE_EXTERNAL = 1  # External (synced) group

# Ranger user/group status
STATUS_ENABLED = 1
STATUS_DISABLED = 0

# Ranger visibility
IS_VISIBLE = 1


class RangerClient:
    """HTTP client for Apache Ranger Admin XUser REST API."""

    def __init__(self) -> None:
        self._base_url = settings.ranger_url.rstrip("/")
        self._auth = (settings.ranger_username, settings.ranger_password)
        self._timeout = settings.ranger_timeout
        self._verify = settings.ranger_ssl_verify
        self._client: httpx.Client | None = None

        # Caches for existing Ranger entities (populated during sync)
        self._user_cache: dict[str, dict] = {}
        self._group_cache: dict[str, dict] = {}

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- User operations ---

    def get_user_by_name(self, username: str) -> dict | None:
        """Get a Ranger user by username. Returns None if not found."""
        if username in self._user_cache:
            return self._user_cache[username]

        client = self._get_client()
        try:
            resp = client.get(f"/service/xusers/users/userName/{username}")
            if resp.status_code == 200:
                user = resp.json()
                self._user_cache[username] = user
                return user
            return None
        except httpx.HTTPError:
            logger.debug("User not found in Ranger: %s", username)
            return None

    def create_user(
        self,
        name: str,
        first_name: str = "",
        last_name: str = "",
        email: str = "",
        description: str = "",
        group_names: list[str] | None = None,
    ) -> dict:
        """Create a new user in Ranger."""
        payload: dict[str, Any] = {
            "name": name,
            "firstName": first_name or name,
            "lastName": last_name,
            "emailAddress": email,
            "description": description,
            "password": name,  # Ranger requires a password field
            "userSource": USER_SOURCE_EXTERNAL,
            "status": STATUS_ENABLED,
            "isVisible": IS_VISIBLE,
            "userRoleList": ["ROLE_USER"],
            "groupNameList": group_names or [],
        }

        client = self._get_client()
        resp = client.post("/service/xusers/secure/users", json=payload)
        resp.raise_for_status()
        user = resp.json()
        self._user_cache[name] = user
        logger.debug("Created Ranger user: %s (id=%s)", name, user.get("id"))
        return user

    def update_user(self, user_id: int, update_data: dict) -> dict:
        """Update an existing Ranger user."""
        client = self._get_client()
        resp = client.put(f"/service/xusers/secure/users/{user_id}", json=update_data)
        resp.raise_for_status()
        user = resp.json()
        self._user_cache[user.get("name", "")] = user
        logger.debug("Updated Ranger user: id=%s", user_id)
        return user

    def list_users(self, page_size: int = 200) -> list[dict]:
        """List all users from Ranger with pagination."""
        all_users = []
        start_index = 0
        client = self._get_client()

        while True:
            resp = client.get(
                "/service/xusers/users",
                params={"startIndex": start_index, "pageSize": page_size},
            )
            resp.raise_for_status()
            data = resp.json()
            users = data.get("vXUsers", [])
            if not users:
                break
            all_users.extend(users)
            total = data.get("totalCount", 0)
            start_index += page_size
            if start_index >= total:
                break

        # Populate cache
        for u in all_users:
            name = u.get("name", "")
            if name:
                self._user_cache[name] = u

        return all_users

    # --- Group operations ---

    def get_group_by_name(self, group_name: str) -> dict | None:
        """Get a Ranger group by name. Returns None if not found."""
        if group_name in self._group_cache:
            return self._group_cache[group_name]

        client = self._get_client()
        try:
            resp = client.get(f"/service/xusers/groups/groupName/{group_name}")
            if resp.status_code == 200:
                group = resp.json()
                self._group_cache[group_name] = group
                return group
            return None
        except httpx.HTTPError:
            logger.debug("Group not found in Ranger: %s", group_name)
            return None

    def create_group(self, name: str, description: str = "") -> dict:
        """Create a new group in Ranger."""
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "groupType": 0,
            "groupSource": GROUP_SOURCE_EXTERNAL,
            "isVisible": IS_VISIBLE,
        }

        client = self._get_client()
        resp = client.post("/service/xusers/secure/groups", json=payload)
        resp.raise_for_status()
        group = resp.json()
        self._group_cache[name] = group
        logger.debug("Created Ranger group: %s (id=%s)", name, group.get("id"))
        return group

    def update_group(self, group_id: int, update_data: dict) -> dict:
        """Update an existing Ranger group."""
        client = self._get_client()
        resp = client.put(f"/service/xusers/secure/groups/{group_id}", json=update_data)
        resp.raise_for_status()
        group = resp.json()
        self._group_cache[group.get("name", "")] = group
        logger.debug("Updated Ranger group: id=%s", group_id)
        return group

    def list_groups(self, page_size: int = 200) -> list[dict]:
        """List all groups from Ranger with pagination."""
        all_groups = []
        start_index = 0
        client = self._get_client()

        while True:
            resp = client.get(
                "/service/xusers/groups",
                params={"startIndex": start_index, "pageSize": page_size},
            )
            resp.raise_for_status()
            data = resp.json()
            groups = data.get("vXGroups", [])
            if not groups:
                break
            all_groups.extend(groups)
            total = data.get("totalCount", 0)
            start_index += page_size
            if start_index >= total:
                break

        for g in all_groups:
            name = g.get("name", "")
            if name:
                self._group_cache[name] = g

        return all_groups

    # --- Group-User membership operations ---

    def get_group_users(self, group_name: str) -> list[str]:
        """Get user names belonging to a group."""
        client = self._get_client()
        resp = client.get(
            "/service/xusers/groupusers",
            params={"name": group_name, "pageSize": 10000},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [gu.get("name", "") for gu in data.get("vXGroupUsers", [])]

    def add_user_to_group(self, user_name: str, group_name: str) -> dict | None:
        """Add a user to a group via group-user mapping."""
        group = self.get_group_by_name(group_name)
        user = self.get_user_by_name(user_name)
        if not group or not user:
            logger.warning(
                "Cannot add user '%s' to group '%s': user or group not found",
                user_name,
                group_name,
            )
            return None

        payload = {
            "name": user_name,
            "parentGroupId": group["id"],
            "userId": user["id"],
        }

        client = self._get_client()
        resp = client.post("/service/xusers/groupusers", json=payload)
        if resp.status_code in (200, 201):
            logger.debug("Added user '%s' to group '%s'", user_name, group_name)
            return resp.json()
        elif resp.status_code == 409:
            logger.debug("User '%s' already in group '%s'", user_name, group_name)
            return None
        else:
            resp.raise_for_status()
            return None

    def check_connection(self) -> bool:
        """Verify connectivity to Ranger Admin."""
        client = self._get_client()
        try:
            resp = client.get("/service/public/v2/api/service")
            return resp.status_code == 200
        except httpx.HTTPError as e:
            logger.error("Failed to connect to Ranger Admin at %s: %s", self._base_url, e)
            return False
