"""Abstract base for data source connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IngestItem:
    """A single item fetched from a data source, ready for ingestion."""

    external_id: str
    title: str
    source_text: str
    metadata_json: str | None = None
    source_type: str = ""
    source_url: str | None = None


class SourceConnector(ABC):
    """Fetches data from an external source for ingestion into a collection."""

    @abstractmethod
    async def fetch_all(self) -> list[IngestItem]:
        """Fetch all items from the source."""
        ...

    @abstractmethod
    async def close(self) -> None: ...
