"""Data models for user/group synchronization to Argus platform database."""

from dataclasses import dataclass, field


@dataclass
class UserInfo:
    """Represents a user to be synced to the Argus database."""

    name: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    description: str = ""
    group_names: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserInfo):
            return NotImplemented
        return self.name == other.name


@dataclass
class GroupInfo:
    """Represents a group from the sync source."""

    name: str
    description: str = ""
    member_names: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GroupInfo):
            return NotImplemented
        return self.name == other.name


@dataclass
class SyncResult:
    """Result of a user/group sync operation."""

    source_type: str = ""
    users_total: int = 0
    users_created: int = 0
    users_updated: int = 0
    users_skipped: int = 0
    groups_total: int = 0
    groups_created: int = 0
    groups_updated: int = 0
    groups_skipped: int = 0
    group_memberships_updated: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
