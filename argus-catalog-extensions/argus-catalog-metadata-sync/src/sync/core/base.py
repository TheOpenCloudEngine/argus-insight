"""Base class for platform sync implementations."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    platform: str
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped + self.failed

    @property
    def success(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "total": self.total,
            "success": self.success,
            "errors": self.errors[:50],
        }


class BasePlatformSync(ABC):
    """Base class for platform-specific metadata synchronization."""

    platform_name: str = ""

    def __init__(self, client: CatalogClient):
        self.client = client

    @abstractmethod
    def connect(self) -> bool:
        """Test connection to the data source. Returns True if successful."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the data source."""

    @abstractmethod
    def discover(self) -> list[dict]:
        """Discover available databases/schemas/tables without syncing.

        Returns a list of dicts with at least {database, table, columns_count}.
        """

    @abstractmethod
    def sync(self) -> SyncResult:
        """Execute full metadata synchronization."""

    def _generate_urn(self, dataset_name: str, origin: str) -> str:
        """Generate a DataHub-style URN for a dataset."""
        return (
            f"urn:li:dataset:"
            f"(urn:li:dataPlatform:{self.platform_name},{dataset_name},{origin})"
        )
