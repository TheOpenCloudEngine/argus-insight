"""File source - reads users and groups from CSV or JSON files."""

import csv
import json
import logging
from pathlib import Path

from app.core.config import settings
from app.core.models import GroupInfo, UserInfo
from app.source.base import SyncSource

logger = logging.getLogger(__name__)


class FileSource(SyncSource):
    """Sync source that reads from CSV or JSON files.

    CSV format for users (users.csv):
        name,first_name,last_name,email,description,groups
        jdoe,John,Doe,jdoe@example.com,Developer,"dev,admin"

    CSV format for groups (groups.csv):
        name,description,members
        dev,Development team,"jdoe,jsmith"

    JSON format for users (users.json):
        [{"name": "jdoe", "first_name": "John", "last_name": "Doe",
          "email": "jdoe@example.com", "groups": ["dev", "admin"]}]

    JSON format for groups (groups.json):
        [{"name": "dev", "description": "Development team",
          "members": ["jdoe", "jsmith"]}]
    """

    def get_source_type(self) -> str:
        return "file"

    def get_users(self) -> list[UserInfo]:
        """Read users from a CSV or JSON file."""
        file_path = Path(settings.file_users_path)
        if not file_path.is_file():
            logger.warning("Users file not found: %s", file_path)
            return []

        user_filter = set(settings.sync_user_filter)
        file_format = settings.file_format.lower()

        if file_format == "json":
            users = self._read_users_json(file_path)
        else:
            users = self._read_users_csv(file_path)

        if user_filter:
            users = [u for u in users if u.name in user_filter]

        logger.info("File source: found %d users from %s", len(users), file_path)
        return users

    def get_groups(self) -> list[GroupInfo]:
        """Read groups from a CSV or JSON file."""
        file_path = Path(settings.file_groups_path)
        if not file_path.is_file():
            logger.warning("Groups file not found: %s", file_path)
            return []

        group_filter = set(settings.sync_group_filter)
        file_format = settings.file_format.lower()

        if file_format == "json":
            groups = self._read_groups_json(file_path)
        else:
            groups = self._read_groups_csv(file_path)

        if group_filter:
            groups = [g for g in groups if g.name in group_filter]

        logger.info("File source: found %d groups from %s", len(groups), file_path)
        return groups

    def _read_users_csv(self, path: Path) -> list[UserInfo]:
        """Read users from a CSV file."""
        users = []
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue
                groups_str = row.get("groups", "")
                group_names = [g.strip() for g in groups_str.split(",") if g.strip()]
                users.append(
                    UserInfo(
                        name=name,
                        first_name=row.get("first_name", "").strip(),
                        last_name=row.get("last_name", "").strip(),
                        email=row.get("email", "").strip(),
                        description=row.get("description", "").strip(),
                        group_names=group_names,
                    )
                )
        return users

    def _read_users_json(self, path: Path) -> list[UserInfo]:
        """Read users from a JSON file."""
        users = []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error("Users JSON file must contain a list")
            return []

        for item in data:
            name = item.get("name", "").strip()
            if not name:
                continue
            groups = item.get("groups", [])
            if isinstance(groups, str):
                groups = [g.strip() for g in groups.split(",") if g.strip()]
            users.append(
                UserInfo(
                    name=name,
                    first_name=item.get("first_name", ""),
                    last_name=item.get("last_name", ""),
                    email=item.get("email", ""),
                    description=item.get("description", ""),
                    group_names=groups,
                )
            )
        return users

    def _read_groups_csv(self, path: Path) -> list[GroupInfo]:
        """Read groups from a CSV file."""
        groups = []
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue
                members_str = row.get("members", "")
                member_names = [m.strip() for m in members_str.split(",") if m.strip()]
                groups.append(
                    GroupInfo(
                        name=name,
                        description=row.get("description", "").strip(),
                        member_names=member_names,
                    )
                )
        return groups

    def _read_groups_json(self, path: Path) -> list[GroupInfo]:
        """Read groups from a JSON file."""
        groups = []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error("Groups JSON file must contain a list")
            return []

        for item in data:
            name = item.get("name", "").strip()
            if not name:
                continue
            members = item.get("members", [])
            if isinstance(members, str):
                members = [m.strip() for m in members.split(",") if m.strip()]
            groups.append(
                GroupInfo(
                    name=name,
                    description=item.get("description", ""),
                    member_names=members,
                )
            )
        return groups
