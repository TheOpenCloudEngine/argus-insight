"""MySQL metadata synchronization.

Connects to MySQL via SQLAlchemy/PyMySQL, queries information_schema
to collect database, table, column metadata including primary keys,
indexes, partitions, and engine type.

MySQL has no separate schema concept — database = schema.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

_MYSQL_TYPE_MAP = {
    "tinyint": "TINYINT",
    "smallint": "SMALLINT",
    "mediumint": "INT",
    "int": "INT",
    "integer": "INT",
    "bigint": "BIGINT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL",
    "numeric": "DECIMAL",
    "bit": "BOOLEAN",
    "char": "CHAR",
    "varchar": "VARCHAR",
    "tinytext": "TEXT",
    "text": "TEXT",
    "mediumtext": "TEXT",
    "longtext": "TEXT",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "tinyblob": "BINARY",
    "blob": "BINARY",
    "mediumblob": "BINARY",
    "longblob": "BINARY",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "time": "TIME",
    "year": "INT",
    "enum": "STRING",
    "set": "STRING",
    "json": "JSON",
    "geometry": "STRING",
    "point": "STRING",
    "linestring": "STRING",
    "polygon": "STRING",
    "multipoint": "STRING",
    "multilinestring": "STRING",
    "multipolygon": "STRING",
    "geometrycollection": "STRING",
}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_DATABASES = text("""
    SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
    ORDER BY SCHEMA_NAME
""")

_SQL_TABLES = text("""
    SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COMMENT,
           TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH, AUTO_INCREMENT,
           TABLE_COLLATION, CREATE_OPTIONS, ROW_FORMAT
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = :db
      AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
    ORDER BY TABLE_NAME
""")

_SQL_COLUMNS = text("""
    SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
           IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT, COLUMN_KEY, EXTRA
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :table
    ORDER BY ORDINAL_POSITION
""")

_SQL_PRIMARY_KEYS = text("""
    SELECT COLUMN_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :table
      AND CONSTRAINT_NAME = 'PRIMARY'
    ORDER BY ORDINAL_POSITION
""")

_SQL_PARTITIONS = text("""
    SELECT PARTITION_METHOD, PARTITION_EXPRESSION
    FROM information_schema.PARTITIONS
    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :table
      AND PARTITION_NAME IS NOT NULL
    LIMIT 1
""")


class MysqlMetadataSync(BasePlatformSync):
    """Synchronize metadata from MySQL to Argus Catalog."""

    platform_name = "mysql"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engine: Engine | None = None

    def connect(self) -> bool:
        try:
            s = self.settings
            url = (
                f"mysql+pymysql://{s.mysql_username}:{s.mysql_password}"
                f"@{s.mysql_host}:{s.mysql_port}/"
            )
            self._engine = create_engine(
                url, pool_size=2, max_overflow=3, pool_recycle=3600,
            )
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected to MySQL at %s:%d", s.mysql_host, s.mysql_port)
            return True
        except Exception as e:
            logger.error("Failed to connect to MySQL: %s", e)
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
                            "columns_count": 0,
                            "owner": "",
                        })
                except Exception as e:
                    logger.warning("Failed to discover tables in %s: %s", db_name, e)
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
            logger.info("Syncing %d databases from MySQL", len(databases))

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
            "MySQL sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_databases(self, conn) -> list[str]:
        rows = conn.execute(_SQL_DATABASES).fetchall()
        all_dbs = [row.SCHEMA_NAME for row in rows]
        if self.settings.mysql_databases:
            return [db for db in all_dbs if db in self.settings.mysql_databases]
        return [
            db for db in all_dbs
            if db not in self.settings.mysql_exclude_databases
        ]

    def _map_mysql_type(self, data_type: str) -> str:
        return _MYSQL_TYPE_MAP.get(data_type.lower(), data_type.upper())

    def _sync_table(
        self, platform_id: int, db_name: str, table_info, conn, result: SyncResult,
    ) -> None:
        table_name = table_info.TABLE_NAME
        qualified_name = f"{db_name}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.mysql_origin)

        table_type = "VIEW" if table_info.TABLE_TYPE == "VIEW" else "TABLE"
        description = table_info.TABLE_COMMENT or ""
        engine = table_info.ENGINE or ""

        # Columns
        col_rows = conn.execute(
            _SQL_COLUMNS, {"db": db_name, "table": table_name}
        ).fetchall()
        pk_rows = conn.execute(
            _SQL_PRIMARY_KEYS, {"db": db_name, "table": table_name}
        ).fetchall()
        pk_columns = {row.COLUMN_NAME for row in pk_rows}

        # Partition info
        part_info = self._get_partition_info(conn, db_name, table_name)

        schema_fields = []
        for col in col_rows:
            schema_fields.append({
                "field_path": col.COLUMN_NAME,
                "field_type": self._map_mysql_type(col.DATA_TYPE),
                "native_type": col.COLUMN_TYPE,
                "description": col.COLUMN_COMMENT or "",
                "nullable": str(col.IS_NULLABLE == "YES").lower(),
                "ordinal": col.ORDINAL_POSITION - 1,
                "is_primary_key": str(col.COLUMN_NAME in pk_columns).lower(),
            })

        # Properties
        properties = {
            "mysql.database": db_name,
        }
        if engine:
            properties["mysql.engine"] = engine
        if table_info.ROW_FORMAT:
            properties["mysql.row_format"] = table_info.ROW_FORMAT
        if table_info.TABLE_COLLATION:
            properties["mysql.collation"] = table_info.TABLE_COLLATION
        if table_info.TABLE_ROWS is not None:
            properties["mysql.table_rows"] = str(table_info.TABLE_ROWS)
        if table_info.DATA_LENGTH is not None:
            properties["mysql.data_length"] = str(table_info.DATA_LENGTH)
        if table_info.INDEX_LENGTH is not None:
            properties["mysql.index_length"] = str(table_info.INDEX_LENGTH)
        if table_info.AUTO_INCREMENT is not None:
            properties["mysql.auto_increment"] = str(table_info.AUTO_INCREMENT)
        if table_info.CREATE_OPTIONS:
            properties["mysql.create_options"] = table_info.CREATE_OPTIONS
        if part_info:
            properties["mysql.partition_method"] = part_info["method"]
            properties["mysql.partition_expression"] = part_info["expression"]

        storage_format = engine.upper() if engine else None

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
                "origin": self.settings.mysql_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_format,
                "schema_fields": schema_fields,
                "owners": [],
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)

    def _get_partition_info(self, conn, db_name: str, table_name: str) -> dict | None:
        try:
            rows = conn.execute(
                _SQL_PARTITIONS, {"db": db_name, "table": table_name}
            ).fetchall()
            if rows:
                return {
                    "method": rows[0].PARTITION_METHOD or "",
                    "expression": rows[0].PARTITION_EXPRESSION or "",
                }
        except Exception:
            pass
        return None
