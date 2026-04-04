"""Base adapter interface for SQL engines.

All engine-specific adapters must implement this interface.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectionConfig:
    """Engine-agnostic connection parameters."""

    host: str
    port: int
    database: str = ""
    username: str = ""
    password: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    """Unified query result returned by all adapters."""

    columns: list[dict[str, str]] = field(default_factory=list)  # [{"name": ..., "type": ...}]
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    elapsed_ms: int = 0
    engine_query_id: str | None = None


@dataclass
class MetadataCatalog:
    name: str


@dataclass
class MetadataSchema:
    name: str
    catalog: str = ""


@dataclass
class MetadataTable:
    name: str
    table_type: str = "TABLE"
    catalog: str = ""
    schema_name: str = ""


@dataclass
class MetadataColumn:
    name: str
    data_type: str
    nullable: bool = True
    comment: str = ""
    ordinal_position: int = 0


class BaseAdapter(abc.ABC):
    """Abstract base class for SQL engine adapters."""

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config

    @abc.abstractmethod
    async def test_connection(self) -> tuple[bool, str, float]:
        """Test connectivity. Returns (success, message, latency_ms)."""

    @abc.abstractmethod
    async def execute(
        self,
        sql: str,
        max_rows: int = 1000,
        timeout_seconds: int = 300,
    ) -> QueryResult:
        """Execute a SQL statement and return results."""

    @abc.abstractmethod
    async def cancel(self, engine_query_id: str) -> bool:
        """Cancel a running query. Returns True if successfully cancelled."""

    @abc.abstractmethod
    async def explain(self, sql: str, analyze: bool = False) -> str:
        """Return the execution plan as text."""

    @abc.abstractmethod
    async def get_catalogs(self) -> list[MetadataCatalog]:
        """List available catalogs (databases)."""

    @abc.abstractmethod
    async def get_schemas(self, catalog: str = "") -> list[MetadataSchema]:
        """List schemas within a catalog."""

    @abc.abstractmethod
    async def get_tables(self, catalog: str = "", schema: str = "") -> list[MetadataTable]:
        """List tables/views within a schema."""

    @abc.abstractmethod
    async def get_columns(
        self, table: str, catalog: str = "", schema: str = ""
    ) -> list[MetadataColumn]:
        """List columns of a table."""

    @abc.abstractmethod
    async def get_table_preview(
        self, table: str, catalog: str = "", schema: str = "", limit: int = 100
    ) -> QueryResult:
        """Return sample rows from a table."""

    @abc.abstractmethod
    def get_keywords(self) -> list[str]:
        """Return engine-specific SQL keywords for autocomplete."""

    @abc.abstractmethod
    def get_functions(self) -> list[str]:
        """Return engine-specific built-in functions for autocomplete."""

    @abc.abstractmethod
    def get_data_types(self) -> list[str]:
        """Return engine-specific data types for autocomplete."""
