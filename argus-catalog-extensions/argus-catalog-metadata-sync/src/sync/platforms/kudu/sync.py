"""Apache Kudu metadata synchronization.

Connects to Kudu master(s) via kudu-python client, discovers all tables,
extracts full metadata (schema, statistics, properties), and synchronizes
them to the Argus Catalog Server.

Kudu has no native database concept. Tables may follow the Impala naming
convention "impala::database.table_name", which is parsed into
(database, table_name) pairs. Tables without this prefix use the
configured default_database.
"""

import logging
from datetime import datetime

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

# Kudu native type → normalized catalog type
_KUDU_TYPE_MAP = {
    "int8": "TINYINT",
    "int16": "SMALLINT",
    "int32": "INT",
    "int64": "BIGINT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL",
    "string": "STRING",
    "binary": "BINARY",
    "bool": "BOOLEAN",
    "unixtime_micros": "TIMESTAMP",
    "varchar": "VARCHAR",
    "date": "DATE",
}


class KuduMetadataSync(BasePlatformSync):
    """Synchronize metadata from Apache Kudu to Argus Catalog.

    Uses the kudu-python client to connect to Kudu master(s) and collect
    table metadata including schema, statistics, and per-column properties.
    """

    platform_name = "kudu"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._kudu_client = None

    # ------------------------------------------------------------------
    # BasePlatformSync interface
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect to Kudu master(s)."""
        try:
            import kudu
        except ImportError:
            logger.error(
                "kudu-python is not installed. "
                "Install it with: pip install kudu-python"
            )
            return False

        try:
            host, port = self._parse_master_addresses()
            self._kudu_client = kudu.connect(host, port)
            # Validate connection
            self._kudu_client.list_tables()
            logger.info("Connected to Kudu master(s): %s:%d", host, port)
            return True
        except Exception as e:
            logger.error("Failed to connect to Kudu: %s", e)
            return False

    def disconnect(self) -> None:
        """Release Kudu client reference."""
        self._kudu_client = None

    def discover(self) -> list[dict]:
        """Discover available tables from Kudu."""
        result = []
        filter_str = self.settings.kudu_table_filter or None
        table_names = self._kudu_client.list_tables(match_substring=filter_str)

        for raw_name in table_names:
            try:
                t = self._kudu_client.table(raw_name)
                db, table = self._parse_table_name(raw_name)
                result.append({
                    "database": db,
                    "table": table,
                    "qualified_name": f"{db}.{table}",
                    "table_type": "TABLE",
                    "table_format": "KUDU",
                    "columns_count": t.num_columns,
                    "owner": t.owner or "",
                    "kudu_table_name": raw_name,
                })
            except Exception as e:
                logger.warning("Failed to discover %s: %s", raw_name, e)
        return result

    def sync(self) -> SyncResult:
        """Synchronize all Kudu metadata to Argus Catalog."""
        result = SyncResult(platform=self.platform_name)
        platform = self.client.get_platform_by_name(self.platform_name)
        if not platform:
            result.errors.append(
                f"Platform '{self.platform_name}' not found in Argus Catalog"
            )
            result.finished_at = datetime.now()
            return result

        platform_id = platform["id"]
        filter_str = self.settings.kudu_table_filter or None
        table_names = self._kudu_client.list_tables(match_substring=filter_str)
        logger.info("Syncing %d tables from Kudu", len(table_names))

        for raw_name in table_names:
            try:
                self._sync_table(platform_id, raw_name, result)
            except Exception as e:
                logger.error("Failed to sync %s: %s", raw_name, e)
                result.failed += 1
                result.errors.append(f"{raw_name}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "Kudu sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_master_addresses(self) -> tuple[str, int]:
        """Parse master_addresses config into (host, port).

        Input: "host1:7051,host2:7051,host3:7051"
        Output: ("host1,host2,host3", 7051)

        All masters must use the same port.
        """
        masters = self.settings.kudu_master_addresses
        host_parts = []
        port = 7051  # default Kudu master port
        for addr in masters.split(","):
            addr = addr.strip()
            if ":" in addr:
                h, p = addr.rsplit(":", 1)
                host_parts.append(h)
                port = int(p)
            else:
                host_parts.append(addr)
        return ",".join(host_parts), port

    def _parse_table_name(self, raw_name: str) -> tuple[str, str]:
        """Parse Kudu table name into (database, table_name).

        Handles Impala naming convention:
        - "impala::mydb.my_table" → ("mydb", "my_table")
        - "impala::my_table"      → (default_database, "my_table")
        - "my_table"              → (default_database, "my_table")
        """
        default_db = self.settings.kudu_default_database

        if self.settings.kudu_parse_impala_naming and raw_name.startswith("impala::"):
            name_part = raw_name[len("impala::"):]
            if "." in name_part:
                db, table = name_part.split(".", 1)
                return (db, table)
            return (default_db, name_part)
        return (default_db, raw_name)

    def _map_kudu_type(self, kudu_type: str) -> str:
        """Map Kudu column type to a normalized catalog type name."""
        return _KUDU_TYPE_MAP.get(kudu_type.lower(), kudu_type.upper())

    def _build_native_type(self, col) -> str:
        """Build native type string with precision/scale/length if applicable."""
        native_type = str(col.type)
        try:
            attrs = col.type_attributes
            if attrs:
                type_lower = native_type.lower()
                if type_lower == "decimal":
                    return f"DECIMAL({attrs.precision},{attrs.scale})"
                elif type_lower == "varchar":
                    return f"VARCHAR({attrs.length})"
        except Exception:
            pass
        return native_type

    def _sync_table(
        self, platform_id: int, raw_name: str, result: SyncResult,
    ) -> None:
        """Sync a single Kudu table to Argus Catalog."""
        db, table_name = self._parse_table_name(raw_name)
        qualified_name = f"{db}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.kudu_origin)

        t = self._kudu_client.table(raw_name)
        schema = t.schema

        # Collect table statistics
        on_disk_size = None
        live_row_count = None
        try:
            stats = self._kudu_client.get_table_statistics(raw_name)
            if stats.on_disk_size != -1:
                on_disk_size = stats.on_disk_size
            if stats.live_row_count != -1:
                live_row_count = stats.live_row_count
        except Exception as e:
            logger.debug("Could not get statistics for %s: %s", raw_name, e)

        pk_columns = set(schema.primary_keys())

        # Build schema fields
        schema_fields = []
        for ordinal in range(t.num_columns):
            col = schema[ordinal]
            native_type = self._build_native_type(col)

            schema_fields.append({
                "field_path": col.name,
                "field_type": self._map_kudu_type(str(col.type)),
                "native_type": native_type,
                "description": col.comment or "",
                "nullable": str(col.nullable).lower(),
                "ordinal": ordinal,
                "is_primary_key": str(col.name in pk_columns).lower(),
            })

        # Build properties with kudu. prefix
        properties = {
            "kudu.table_id": t.id,
            "kudu.num_replicas": str(t.num_replicas),
            "kudu.raw_table_name": raw_name,
        }
        if on_disk_size is not None:
            properties["kudu.on_disk_size"] = str(on_disk_size)
        if live_row_count is not None:
            properties["kudu.live_row_count"] = str(live_row_count)
        if pk_columns:
            properties["kudu.primary_keys"] = ",".join(schema.primary_keys())

        # Per-column encoding and compression
        for i in range(t.num_columns):
            col = schema[i]
            try:
                if col.encoding:
                    properties[f"kudu.encoding.{col.name}"] = str(col.encoding)
            except Exception:
                pass
            try:
                if col.compression:
                    properties[f"kudu.compression.{col.name}"] = str(col.compression)
            except Exception:
                pass

        description = t.comment or ""
        existing = self.client.get_dataset_by_urn(urn)

        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": "TABLE",
                "storage_format": "KUDU",
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s", qualified_name)
        else:
            owners = []
            if t.owner:
                owners.append({
                    "owner_name": t.owner,
                    "owner_type": "TECHNICAL_OWNER",
                })
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.kudu_origin,
                "qualified_name": qualified_name,
                "table_type": "TABLE",
                "storage_format": "KUDU",
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)
