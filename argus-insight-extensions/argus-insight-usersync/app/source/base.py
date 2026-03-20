"""Base class for sync sources."""

import abc

from app.core.models import GroupInfo, UserInfo


class SyncSource(abc.ABC):
    """Abstract base class for user/group sync sources."""

    @abc.abstractmethod
    def get_users(self) -> list[UserInfo]:
        """Fetch all users from the source."""

    @abc.abstractmethod
    def get_groups(self) -> list[GroupInfo]:
        """Fetch all groups from the source."""

    @abc.abstractmethod
    def get_source_type(self) -> str:
        """Return the source type name."""
