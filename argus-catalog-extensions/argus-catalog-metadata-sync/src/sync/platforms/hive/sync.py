"""Hive Metastore metadata synchronization.

Supports two backends (configurable via hive.sync_mode):
- "thrift": Connects to HMS via Thrift RPC (port 9083, requires hmsclient)
- "sql": Queries HMS backend RDBMS directly (MySQL/PostgreSQL, no Kerberos)

Both backends produce identical HiveTableMetadata objects, which are then
transformed into Catalog Server dataset payloads.
"""

import logging
from datetime import datetime

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient
from sync.platforms.hive.backend_base import HiveBackend, HiveTableMetadata
from sync.platforms.hive.format_detector import (
    detect_file_format,
    detect_storage_location,
    detect_table_format,
    detect_table_type,
)

logger = logging.getLogger(__name__)

# TABLE_PARAMS keys to collect as dataset properties
_PROPERTY_KEYS = [
    "numRows", "totalSize", "rawDataSize", "transient_lastDdlTime",
    "COLUMN_STATS_ACCURATE", "bucketing_version",
    "spark.sql.sources.provider", "spark.sql.sources.schema",
    "write.format.default", "current-snapshot-id", "uuid",
    "metadata_location", "previous_metadata_location",
]


class HiveMetastoreSync(BasePlatformSync):
    """Synchronize metadata from Hive Metastore to Argus Catalog.

    Uses a pluggable backend (Thrift or SQL) selected by configuration.
    """

    platform_name = "hive"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._backend: HiveBackend = self._create_backend()

    def _create_backend(self) -> HiveBackend:
        """Create the appropriate backend based on sync_mode config."""
        mode = self.settings.hive_sync_mode
        if mode == "sql":
            from sync.platforms.hive.backend_sql import HiveSqlBackend
            logger.info("Using SQL backend for Hive Metastore")
            return HiveSqlBackend(self.settings)
        else:
            from sync.platforms.hive.backend_thrift import HiveThriftBackend
            logger.info("Using Thrift backend for Hive Metastore")
            return HiveThriftBackend(self.settings)

    def connect(self) -> bool:
        return self._backend.connect()

    def disconnect(self) -> None:
        self._backend.disconnect()

    def discover(self) -> list[dict]:
        """Discover databases and tables from Hive Metastore."""
        result = []
        for db_name in self._get_databases():
            try:
                tables = self._backend.get_tables(db_name)
            except Exception as e:
                logger.warning("Failed to list tables in %s: %s", db_name, e)
                continue
            for table_name in tables:
                try:
                    meta = self._backend.get_table_metadata(db_name, table_name)
                    result.append({
                        "database": db_name,
                        "table": table_name,
                        "qualified_name": f"{db_name}.{table_name}",
                        "table_type": meta.table_type,
                        "table_format": detect_table_format(meta.parameters),
                        "columns_count": len(meta.columns) + len(meta.partition_keys),
                        "owner": meta.owner,
                        "location": meta.location or "",
                    })
                except Exception as e:
                    logger.warning("Failed to discover %s.%s: %s", db_name, table_name, e)
        return result

    def sync(self) -> SyncResult:
        """Synchronize all Hive metadata to Argus Catalog."""
        result = SyncResult(platform=self.platform_name)
        platform = self.client.get_platform_by_name(self.platform_name)
        if not platform:
            result.errors.append(f"Platform '{self.platform_name}' not found in Argus Catalog")
            result.finished_at = datetime.now()
            return result

        platform_id = platform["id"]
        databases = self._get_databases()
        logger.info("Syncing %d databases from Hive Metastore (mode=%s)",
                     len(databases), self.settings.hive_sync_mode)

        for db_name in databases:
            try:
                tables = self._backend.get_tables(db_name)
            except Exception as e:
                logger.error("Failed to list tables in %s: %s", db_name, e)
                result.errors.append(f"Failed to list tables in {db_name}: {e}")
                continue
            for table_name in tables:
                try:
                    self._sync_table(platform_id, db_name, table_name, result)
                except Exception as e:
                    logger.error("Failed to sync %s.%s: %s", db_name, table_name, e)
                    result.failed += 1
                    result.errors.append(f"{db_name}.{table_name}: {e}")

        result.finished_at = datetime.now()
        logger.info("Hive sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
                     result.created, result.updated, result.skipped, result.failed)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_databases(self) -> list[str]:
        """Get filtered list of databases to sync."""
        all_dbs = self._backend.get_databases()
        if self.settings.hive_databases:
            return [db for db in all_dbs if db in self.settings.hive_databases]
        return [db for db in all_dbs if db not in self.settings.hive_exclude_databases]

    def _map_hive_type(self, hive_type: str) -> str:
        """Map Hive column type to a normalized type name."""
        return hive_type.upper().split("(")[0].split("<")[0].strip()

    def _sync_table(self, platform_id: int, db_name: str, table_name: str, result: SyncResult) -> None:
        """Sync a single table to Argus Catalog."""
        meta: HiveTableMetadata = self._backend.get_table_metadata(db_name, table_name)
        qualified_name = f"{db_name}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.hive_origin)

        # Detect formats
        table_format = detect_table_format(meta.parameters)
        file_format = detect_file_format(meta.input_format, meta.parameters, table_format)
        location = detect_storage_location(meta.location, meta.parameters, table_format)
        table_type = detect_table_type(meta.table_type)

        # Build schema fields
        schema_fields = []
        ordinal = 0
        for col in meta.columns:
            schema_fields.append({
                "field_path": col["name"],
                "field_type": self._map_hive_type(col["type"]),
                "native_type": col["type"],
                "description": col.get("comment", ""),
                "nullable": "true",
                "ordinal": ordinal,
            })
            ordinal += 1
        for pk in meta.partition_keys:
            schema_fields.append({
                "field_path": pk["name"],
                "field_type": self._map_hive_type(pk["type"]),
                "native_type": pk["type"],
                "description": pk.get("comment", ""),\n                "is_partition_key": "true",
                "nullable": "false",
                "ordinal": ordinal,
            })
            ordinal += 1

        # Build properties with hive. prefix
        properties = {}
        if table_format != "HIVE":
            properties["hive.table_format"] = table_format
        if location:
            properties["hive.location"] = location
        if meta.input_format:
            properties["hive.input_format"] = meta.input_format
        if meta.partition_keys:
            properties["hive.partition_keys"] = ",".join(pk["name"] for pk in meta.partition_keys)
        for key in _PROPERTY_KEYS:
            if key in meta.parameters:
                properties[f"hive.{key}"] = meta.parameters[key]

        description = meta.comment or ""
        existing = self.client.get_dataset_by_urn(urn)

        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": file_format,
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s (format=%s)", qualified_name, table_format)
        else:
            owners = []
            if meta.owner:
                owners.append({"owner_name": meta.owner, "owner_type": "TECHNICAL_OWNER"})
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.hive_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": file_format,
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s (format=%s)", qualified_name, table_format)
