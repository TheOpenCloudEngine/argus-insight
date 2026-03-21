"""Hive Metastore metadata synchronization."""

import logging
import os
import subprocess
from datetime import datetime

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

# Hive storage format input class → human-readable name
_INPUT_FORMAT_MAP = {
    "org.apache.hadoop.hive.ql.io.orc.OrcInputFormat": "ORC",
    "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat": "PARQUET",
    "org.apache.hadoop.mapred.TextInputFormat": "TEXTFILE",
    "org.apache.hadoop.mapred.SequenceFileInputFormat": "SEQUENCEFILE",
    "org.apache.hadoop.hive.ql.io.avro.AvroContainerInputFormat": "AVRO",
    "org.apache.hadoop.hive.ql.io.RCFileInputFormat": "RCFILE",
    "org.apache.hive.hcatalog.data.JsonSerDe": "JSONFILE",
}

# Hive table type → Argus table type
_TABLE_TYPE_MAP = {
    "MANAGED_TABLE": "MANAGED_TABLE",
    "EXTERNAL_TABLE": "EXTERNAL_TABLE",
    "VIRTUAL_VIEW": "VIRTUAL_VIEW",
    "MATERIALIZED_VIEW": "MATERIALIZED_VIEW",
    "INDEX_TABLE": "MANAGED_TABLE",
}


class HiveMetastoreSync(BasePlatformSync):
    """Synchronize metadata from Hive Metastore via Thrift."""

    platform_name = "hive"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._hms_client = None

    def _init_kerberos(self) -> None:
        """Initialize Kerberos authentication if configured."""
        if not self.settings.hive_kerberos_enabled:
            return

        keytab = self.settings.hive_kerberos_keytab
        principal = self.settings.hive_kerberos_principal

        if not os.path.isfile(keytab):
            raise FileNotFoundError(f"Keytab file not found: {keytab}")

        logger.info("Initializing Kerberos: principal=%s, keytab=%s", principal, keytab)
        result = subprocess.run(
            ["kinit", "-kt", keytab, principal],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"kinit failed: {result.stderr.strip()}")
        logger.info("Kerberos authentication successful")

    def connect(self) -> bool:
        """Connect to Hive Metastore via Thrift."""
        try:
            self._init_kerberos()

            from hmsclient import HMSClient

            self._hms_client = HMSClient(
                host=self.settings.hive_metastore_host,
                port=self.settings.hive_metastore_port,
            )
            self._hms_client.open()
            # Test connection by listing databases
            self._hms_client.get_all_databases()
            logger.info(
                "Connected to Hive Metastore at %s:%d",
                self.settings.hive_metastore_host,
                self.settings.hive_metastore_port,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to Hive Metastore: %s", e)
            return False

    def disconnect(self) -> None:
        """Close the Hive Metastore connection."""
        if self._hms_client:
            try:
                self._hms_client.close()
            except Exception:
                pass
            self._hms_client = None

    def _get_databases(self) -> list[str]:
        """Get list of databases to sync."""
        all_dbs = self._hms_client.get_all_databases()

        if self.settings.hive_databases:
            # Only sync specified databases
            return [db for db in all_dbs if db in self.settings.hive_databases]

        # Sync all except excluded
        return [db for db in all_dbs if db not in self.settings.hive_exclude_databases]

    def _map_hive_type(self, hive_type: str) -> str:
        """Map Hive column type to a normalized type name."""
        # Strip parameters like DECIMAL(10,2) → DECIMAL
        base_type = hive_type.upper().split("(")[0].split("<")[0].strip()
        return base_type

    def _resolve_storage_format(self, table) -> str | None:
        """Resolve storage format from Hive table's inputFormat."""
        input_format = getattr(table.sd, "inputFormat", None)
        if input_format:
            return _INPUT_FORMAT_MAP.get(input_format)
        return None

    def _resolve_table_type(self, table) -> str:
        """Map Hive tableType to Argus table type."""
        return _TABLE_TYPE_MAP.get(table.tableType, "MANAGED_TABLE")

    def discover(self) -> list[dict]:
        """Discover databases and tables from Hive Metastore."""
        result = []
        databases = self._get_databases()
        for db_name in databases:
            tables = self._hms_client.get_all_tables(db_name)
            for table_name in tables:
                try:
                    table = self._hms_client.get_table(db_name, table_name)
                    cols = table.sd.cols if table.sd else []
                    partition_keys = table.partitionKeys or []
                    result.append({
                        "database": db_name,
                        "table": table_name,
                        "qualified_name": f"{db_name}.{table_name}",
                        "table_type": table.tableType,
                        "columns_count": len(cols) + len(partition_keys),
                        "owner": table.owner or "",
                        "location": table.sd.location if table.sd else "",
                    })
                except Exception as e:
                    logger.warning("Failed to discover %s.%s: %s", db_name, table_name, e)
        return result

    def sync(self) -> SyncResult:
        """Synchronize all Hive metadata to Argus Catalog."""
        result = SyncResult(platform=self.platform_name)

        # Resolve platform ID
        platform = self.client.get_platform_by_name(self.platform_name)
        if not platform:
            result.errors.append(f"Platform '{self.platform_name}' not found in Argus Catalog")
            result.finished_at = datetime.now()
            return result

        platform_id = platform["id"]
        databases = self._get_databases()
        logger.info("Syncing %d databases from Hive Metastore", len(databases))

        for db_name in databases:
            try:
                tables = self._hms_client.get_all_tables(db_name)
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
        logger.info(
            "Hive sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    def _sync_table(
        self,
        platform_id: int,
        db_name: str,
        table_name: str,
        result: SyncResult,
    ) -> None:
        """Sync a single Hive table to Argus Catalog."""
        table = self._hms_client.get_table(db_name, table_name)
        qualified_name = f"{db_name}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.hive_origin)

        # Build schema fields from columns + partition keys
        schema_fields = []
        ordinal = 0

        if table.sd and table.sd.cols:
            for col in table.sd.cols:
                schema_fields.append({
                    "field_path": col.name,
                    "field_type": self._map_hive_type(col.type),
                    "native_type": col.type,
                    "description": col.comment or "",
                    "nullable": "true",
                    "ordinal": ordinal,
                })
                ordinal += 1

        for pk in (table.partitionKeys or []):
            schema_fields.append({
                "field_path": pk.name,
                "field_type": self._map_hive_type(pk.type),
                "native_type": pk.type,
                "description": (pk.comment or "") + " [partition key]",
                "nullable": "false",
                "ordinal": ordinal,
            })
            ordinal += 1

        # Build properties
        properties = {}
        if table.sd and table.sd.location:
            properties["location"] = table.sd.location
        storage_format = self._resolve_storage_format(table)
        if storage_format:
            properties["storage_format"] = storage_format
        table_type = self._resolve_table_type(table)
        if table.parameters:
            for key in ("numRows", "totalSize", "rawDataSize", "transient_lastDdlTime"):
                if key in table.parameters:
                    properties[key] = table.parameters[key]

        # Build description
        description = ""
        if table.parameters and "comment" in table.parameters:
            description = table.parameters["comment"]

        # Check if dataset already exists
        existing = self.client.get_dataset_by_urn(urn)

        if existing:
            # Update existing dataset
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
            })
            # Update schema
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s", qualified_name)
        else:
            # Create new dataset
            owners = []
            if table.owner:
                owners.append({
                    "owner_name": table.owner,
                    "owner_type": "TECHNICAL_OWNER",
                })

            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.hive_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_format,
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)
