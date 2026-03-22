"""StarRocks metadata synchronization.

Connects to StarRocks via MySQL protocol (pymysql), queries
information_schema to collect database, table, column metadata.
Joins with tables_config to get StarRocks-specific properties:
table model, distribution key, partition key, sort key, bucket count.

StarRocks has four table models: DUP_KEYS, AGG_KEYS, UNQ_KEYS, PRI_KEYS.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

# StarRocks type map (extends MySQL types)
_SR_TYPE_MAP = {
    "tinyint": "TINYINT",
    "smallint": "SMALLINT",
    "int": "INT",
    "integer": "INT",
    "bigint": "BIGINT",
    "largeint": "BIGINT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL",
    "decimalv2": "DECIMAL",
    "decimal32": "DECIMAL",
    "decimal64": "DECIMAL",
    "decimal128": "DECIMAL",
    "char": "CHAR",
    "varchar": "VARCHAR",
    "string": "STRING",
    "text": "TEXT",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "boolean": "BOOLEAN",
    "json": "JSON",
    "bitmap": "STRING",
    "hll": "STRING",
    "percentile": "STRING",
    "object": "STRING",
}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_DATABASES = text("""
    SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
    ORDER BY SCHEMA_NAME
""")

_SQL_TABLES = text("""
    SELECT t.TABLE_NAME, t.TABLE_TYPE, t.ENGINE, t.TABLE_COMMENT,
           t.TABLE_ROWS, t.DATA_LENGTH, t.CREATE_TIME, t.UPDATE_TIME,
           tc.TABLE_MODEL, tc.PRIMARY_KEY, tc.PARTITION_KEY,
           tc.DISTRIBUTE_KEY, tc.DISTRIBUTE_TYPE, tc.DISTRIBUTE_BUCKET,
           tc.SORT_KEY
    FROM information_schema.TABLES t
    LEFT JOIN information_schema.tables_config tc
        ON tc.TABLE_SCHEMA = t.TABLE_SCHEMA AND tc.TABLE_NAME = t.TABLE_NAME
    WHERE t.TABLE_SCHEMA = :db
      AND t.TABLE_TYPE IN ('BASE TABLE', 'VIEW', 'SYSTEM VIEW')
    ORDER BY t.TABLE_NAME
""")

_SQL_COLUMNS = text("""
    SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
           IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT, COLUMN_KEY
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :table
    ORDER BY ORDINAL_POSITION
""")


class StarrocksMetadataSync(BasePlatformSync):
    """Synchronize metadata from StarRocks to Argus Catalog."""

    platform_name = "starrocks"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engine: Engine | None = None

    def connect(self) -> bool:
        try:
            s = self.settings
            url = (
                f"mysql+pymysql://{s.starrocks_username}:{s.starrocks_password}"
                f"@{s.starrocks_host}:{s.starrocks_port}/"
            )
            self._engine = create_engine(
                url, pool_size=2, max_overflow=3, pool_recycle=3600,
            )
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(
                "Connected to StarRocks at %s:%d",
                s.starrocks_host, s.starrocks_port,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to StarRocks: %s", e)
            return False

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def discover(self) -> list[dict]:
        result = []
        with self._engine.connect() as conn:
            for db_name in self._get_databases(conn):
                try:
                    rows = conn.execute(_SQL_TABLES, {"db": db_name}).fetchall()
                    for row in rows:
                        result.append({
                            "database": db_name,
                            "table": row.TABLE_NAME,
                            "qualified_name": f"{db_name}.{row.TABLE_NAME}",
                            "table_type": "VIEW" if row.TABLE_TYPE == "VIEW" else "TABLE",
                            "table_model": row.TABLE_MODEL or "",
                            "columns_count": 0,
                            "owner": "",
                        })
                except Exception as e:
                    logger.warning("Failed to discover in %s: %s", db_name, e)
        return result

    def sync(self) -> SyncResult:
        result = SyncResult(platform=self.platform_name)
        platform = self.client.get_platform_by_name(self.platform_name)
        if not platform:
            result.errors.append(
                f"Platform '{self.platform_name}' not found in Argus Catalog"
            )
            result.finished_at = datetime.now()
            return result

        platform_id = platform["id"]
        with self._engine.connect() as conn:
            databases = self._get_databases(conn)
            logger.info("Syncing %d databases from StarRocks", len(databases))

            for db_name in databases:
                try:
                    rows = conn.execute(_SQL_TABLES, {"db": db_name}).fetchall()
                except Exception as e:
                    logger.error("Failed to list tables in %s: %s", db_name, e)
                    result.errors.append(f"Database {db_name}: {e}")
                    continue

                for row in rows:
                    try:
                        self._sync_table(
                            platform_id, db_name, row, conn, result,
                        )
                    except Exception as e:
                        qname = f"{db_name}.{row.TABLE_NAME}"
                        logger.error("Failed to sync %s: %s", qname, e)
                        result.failed += 1
                        result.errors.append(f"{qname}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "StarRocks sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_databases(self, conn) -> list[str]:
        rows = conn.execute(_SQL_DATABASES).fetchall()
        all_dbs = [row.SCHEMA_NAME for row in rows]
        if self.settings.starrocks_databases:
            return [db for db in all_dbs if db in self.settings.starrocks_databases]
        return [
            db for db in all_dbs
            if db not in self.settings.starrocks_exclude_databases
        ]

    def _map_sr_type(self, data_type: str, column_type: str) -> str:
        """Map StarRocks type to normalized catalog type.

        Handles complex types:
        - array<varchar(65533)> → ARRAY<VARCHAR>
        - map<varchar,int>      → MAP<VARCHAR,INT>
        - struct<a int, b varchar> → STRUCT<a:INT,b:VARCHAR>
        """
        t = column_type.strip() if column_type else data_type.strip()
        lower = t.lower()

        # Complex types (StarRocks uses angle bracket syntax like Hive)
        if lower.startswith("array<") and t.endswith(">"):
            inner = t[6:-1]
            return f"ARRAY<{self._map_sr_type(inner, inner)}>"
        if lower.startswith("map<") and t.endswith(">"):
            inner = t[4:-1]
            key, value = self._split_top_level(inner, ",")
            return f"MAP<{self._map_sr_type(key, key)},{self._map_sr_type(value, value)}>"
        if lower.startswith("struct<") and t.endswith(">"):
            inner = t[7:-1]
            fields = self._split_top_level_all(inner, ",")
            mapped = []
            for field in fields:
                field = field.strip()
                parts = field.split(None, 1)
                if len(parts) == 2:
                    fname, ftype = parts
                    mapped.append(
                        f"{fname}:{self._map_sr_type(ftype, ftype)}"
                    )
                else:
                    mapped.append(self._map_sr_type(field, field))
            return f"STRUCT<{','.join(mapped)}>"

        # Simple type: strip precision
        base = data_type.lower().split("(")[0].strip() if data_type else lower.split("(")[0].strip()
        return _SR_TYPE_MAP.get(base, base.upper())

    @staticmethod
    def _split_top_level(s: str, sep: str) -> tuple[str, str]:
        depth = 0
        for i, ch in enumerate(s):
            if ch in ("(", "<"):
                depth += 1
            elif ch in (")", ">"):
                depth -= 1
            elif ch == sep and depth == 0:
                return s[:i].strip(), s[i + 1:].strip()
        return s.strip(), ""

    @staticmethod
    def _split_top_level_all(s: str, sep: str) -> list[str]:
        parts = []
        depth = 0
        start = 0
        for i, ch in enumerate(s):
            if ch in ("(", "<"):
                depth += 1
            elif ch in (")", ">"):
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append(s[start:i].strip())
                start = i + 1
        parts.append(s[start:].strip())
        return parts

    @staticmethod
    def _parse_key_columns(key_str: str | None) -> set[str]:
        """Parse comma-separated column names from tables_config fields."""
        if not key_str:
            return set()
        return {c.strip() for c in key_str.split(",") if c.strip()}

    def _sync_table(
        self, platform_id, db_name, table_info, conn, result,
    ):
        table_name = table_info.TABLE_NAME
        qualified_name = f"{db_name}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.starrocks_origin)

        table_type = "VIEW" if table_info.TABLE_TYPE == "VIEW" else "TABLE"
        description = table_info.TABLE_COMMENT or ""

        # Parse key columns from tables_config
        pk_columns = self._parse_key_columns(table_info.PRIMARY_KEY)
        dist_columns = self._parse_key_columns(table_info.DISTRIBUTE_KEY)
        part_columns = self._parse_key_columns(table_info.PARTITION_KEY)

        # Columns
        col_rows = conn.execute(
            _SQL_COLUMNS, {"db": db_name, "table": table_name},
        ).fetchall()

        schema_fields = []
        for col in col_rows:
            schema_fields.append({
                "field_path": col.COLUMN_NAME,
                "field_type": self._map_sr_type(col.DATA_TYPE, col.COLUMN_TYPE),
                "native_type": col.COLUMN_TYPE or col.DATA_TYPE,
                "description": col.COLUMN_COMMENT or "",
                "nullable": str(col.IS_NULLABLE == "YES").lower(),
                "ordinal": col.ORDINAL_POSITION - 1,
                "is_primary_key": str(col.COLUMN_NAME in pk_columns).lower(),
                "is_distribution_key": str(col.COLUMN_NAME in dist_columns).lower(),
                "is_partition_key": str(col.COLUMN_NAME in part_columns).lower(),
            })

        # Properties
        properties = {"starrocks.database": db_name}
        if table_info.TABLE_MODEL:
            properties["starrocks.table_model"] = table_info.TABLE_MODEL
        if table_info.PRIMARY_KEY:
            properties["starrocks.primary_key"] = table_info.PRIMARY_KEY
        if table_info.PARTITION_KEY:
            properties["starrocks.partition_key"] = table_info.PARTITION_KEY
        if table_info.DISTRIBUTE_KEY:
            properties["starrocks.distribute_key"] = table_info.DISTRIBUTE_KEY
        if table_info.DISTRIBUTE_TYPE:
            properties["starrocks.distribute_type"] = table_info.DISTRIBUTE_TYPE
        if table_info.DISTRIBUTE_BUCKET is not None:
            properties["starrocks.distribute_bucket"] = str(
                table_info.DISTRIBUTE_BUCKET
            )
        if table_info.SORT_KEY:
            properties["starrocks.sort_key"] = table_info.SORT_KEY
        if table_info.TABLE_ROWS is not None:
            properties["starrocks.table_rows"] = str(table_info.TABLE_ROWS)
        if table_info.DATA_LENGTH is not None:
            properties["starrocks.data_length"] = str(table_info.DATA_LENGTH)

        storage_format = table_info.ENGINE or None

        existing = self.client.get_dataset_by_urn(urn)
        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_format,
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s", qualified_name)
        else:
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.starrocks_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_format,
                "schema_fields": schema_fields,
                "owners": [],
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)
