"""Microsoft SQL Server metadata synchronization.

Connects to MSSQL via SQLAlchemy/pymssql, queries sys.* and
INFORMATION_SCHEMA to collect database, schema, table, column metadata
including primary keys, partition info, and filegroups.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

_MSSQL_TYPE_MAP = {
    "tinyint": "TINYINT",
    "smallint": "SMALLINT",
    "int": "INT",
    "bigint": "BIGINT",
    "float": "DOUBLE",
    "real": "FLOAT",
    "decimal": "DECIMAL",
    "numeric": "DECIMAL",
    "money": "DECIMAL",
    "smallmoney": "DECIMAL",
    "bit": "BOOLEAN",
    "char": "CHAR",
    "varchar": "VARCHAR",
    "nchar": "CHAR",
    "nvarchar": "VARCHAR",
    "text": "TEXT",
    "ntext": "TEXT",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "image": "BINARY",
    "date": "DATE",
    "time": "TIME",
    "datetime": "TIMESTAMP",
    "datetime2": "TIMESTAMP",
    "smalldatetime": "TIMESTAMP",
    "datetimeoffset": "TIMESTAMP",
    "uniqueidentifier": "UUID",
    "xml": "XML",
    "sql_variant": "STRING",
    "hierarchyid": "STRING",
    "geometry": "STRING",
    "geography": "STRING",
    "timestamp": "BINARY",
    "rowversion": "BINARY",
}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_DATABASES = text("""
    SELECT name FROM sys.databases
    WHERE state_desc = 'ONLINE' AND name NOT IN ('master', 'tempdb', 'model', 'msdb')
    ORDER BY name
""")

_SQL_SCHEMAS = text("""
    SELECT s.name
    FROM sys.schemas s
    JOIN sys.database_principals p ON p.principal_id = s.principal_id
    WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner',
          'db_accessadmin', 'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
          'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter')
    ORDER BY s.name
""")

_SQL_TABLES = text("""
    SELECT t.object_id, t.name AS table_name, t.type_desc,
           p2.rows AS row_count,
           SUM(a.total_pages) * 8 * 1024 AS total_size_bytes,
           ep.value AS table_comment,
           fg.name AS filegroup_name,
           s2.name AS schema_name
    FROM sys.tables t
    JOIN sys.schemas s2 ON s2.schema_id = t.schema_id
    JOIN sys.indexes i ON i.object_id = t.object_id AND i.index_id <= 1
    JOIN sys.partitions p2 ON p2.object_id = t.object_id AND p2.index_id <= 1
    JOIN sys.allocation_units a ON a.container_id = p2.partition_id
    LEFT JOIN sys.filegroups fg ON fg.data_space_id = i.data_space_id
    LEFT JOIN sys.extended_properties ep
        ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
    WHERE s2.name = :schema
    GROUP BY t.object_id, t.name, t.type_desc, p2.rows, ep.value, fg.name, s2.name
    ORDER BY t.name
""")

_SQL_VIEWS = text("""
    SELECT v.object_id, v.name AS view_name,
           ep.value AS view_comment,
           s2.name AS schema_name
    FROM sys.views v
    JOIN sys.schemas s2 ON s2.schema_id = v.schema_id
    LEFT JOIN sys.extended_properties ep
        ON ep.major_id = v.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
    WHERE s2.name = :schema
    ORDER BY v.name
""")

_SQL_COLUMNS = text("""
    SELECT c.column_id, c.name AS column_name,
           TYPE_NAME(c.user_type_id) AS data_type,
           c.max_length, c.precision, c.scale, c.is_nullable, c.is_identity,
           ep.value AS column_comment
    FROM sys.columns c
    LEFT JOIN sys.extended_properties ep
        ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
        AND ep.name = 'MS_Description'
    WHERE c.object_id = :oid
    ORDER BY c.column_id
""")

_SQL_PRIMARY_KEYS = text("""
    SELECT col.name AS column_name
    FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
    WHERE i.object_id = :oid AND i.is_primary_key = 1
    ORDER BY ic.key_ordinal
""")

_SQL_PARTITION_INFO = text("""
    SELECT c.name AS column_name, pf.name AS function_name,
           pf.type_desc AS function_type, pf.fanout AS partition_count
    FROM sys.tables t
    JOIN sys.indexes i ON i.object_id = t.object_id AND i.index_id <= 1
    JOIN sys.partition_schemes ps ON ps.data_space_id = i.data_space_id
    JOIN sys.partition_functions pf ON pf.function_id = ps.function_id
    JOIN sys.index_columns ic ON ic.object_id = i.object_id
        AND ic.index_id = i.index_id AND ic.partition_ordinal > 0
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE t.object_id = :oid
    ORDER BY ic.partition_ordinal
""")


class MssqlMetadataSync(BasePlatformSync):
    """Synchronize metadata from SQL Server to Argus Catalog."""

    platform_name = "mssql"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engines: dict[str, Engine] = {}

    def connect(self) -> bool:
        try:
            initial_db = self.settings.mssql_database or "master"
            engine = self._create_engine(initial_db)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._engines[initial_db] = engine
            logger.info(
                "Connected to MSSQL at %s:%d",
                self.settings.mssql_host, self.settings.mssql_port,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to MSSQL: %s", e)
            return False

    def disconnect(self) -> None:
        for engine in self._engines.values():
            try:
                engine.dispose()
            except Exception:
                pass
        self._engines.clear()

    def discover(self) -> list[dict]:
        result = []
        for db_name in self._get_databases():
            engine = self._get_engine(db_name)
            if not engine:
                continue
            try:
                with engine.connect() as conn:
                    for schema in self._get_schemas(conn):
                        rows = conn.execute(_SQL_TABLES, {"schema": schema}).fetchall()
                        for row in rows:
                            result.append({
                                "database": db_name,
                                "schema": schema,
                                "table": row.table_name,
                                "qualified_name": f"{db_name}.{schema}.{row.table_name}",
                                "table_type": "TABLE",
                                "columns_count": 0,
                                "owner": "",
                            })
            except Exception as e:
                logger.warning("Failed to discover in %s: %s", db_name, e)
            finally:
                if db_name not in self._engines:
                    engine.dispose()
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
        databases = self._get_databases()
        logger.info("Syncing %d databases from MSSQL", len(databases))

        for db_name in databases:
            try:
                self._sync_database(platform_id, db_name, result)
            except Exception as e:
                logger.error("Failed to sync database %s: %s", db_name, e)
                result.errors.append(f"Database {db_name}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "MSSQL sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_engine(self, database: str) -> Engine:
        s = self.settings
        url = (
            f"mssql+pymssql://{s.mssql_username}:{s.mssql_password}"
            f"@{s.mssql_host}:{s.mssql_port}/{database}"
        )
        return create_engine(url, pool_size=2, max_overflow=3, pool_recycle=3600)

    def _get_engine(self, database: str) -> Engine | None:
        if database in self._engines:
            return self._engines[database]
        try:
            engine = self._create_engine(database)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            logger.warning("Cannot connect to database %s: %s", database, e)
            return None

    def _get_databases(self) -> list[str]:
        if self.settings.mssql_database:
            return [self.settings.mssql_database]
        initial_db = list(self._engines.keys())[0] if self._engines else "master"
        engine = self._engines.get(initial_db)
        if not engine:
            return []
        with engine.connect() as conn:
            rows = conn.execute(_SQL_DATABASES).fetchall()
            all_dbs = [row.name for row in rows]
        if self.settings.mssql_databases:
            return [db for db in all_dbs if db in self.settings.mssql_databases]
        return [
            db for db in all_dbs
            if db not in self.settings.mssql_exclude_databases
        ]

    def _get_schemas(self, conn) -> list[str]:
        rows = conn.execute(_SQL_SCHEMAS).fetchall()
        all_schemas = [row.name for row in rows]
        if self.settings.mssql_schemas:
            return [s for s in all_schemas if s in self.settings.mssql_schemas]
        return all_schemas

    def _map_mssql_type(self, data_type: str) -> str:
        return _MSSQL_TYPE_MAP.get(data_type.lower(), data_type.upper())

    def _build_native_type(self, col) -> str:
        dt = col.data_type
        if dt in ("decimal", "numeric") and col.precision:
            return f"{dt.upper()}({col.precision},{col.scale})"
        if dt in ("varchar", "nvarchar", "char", "nchar", "varbinary", "binary"):
            length = "MAX" if col.max_length == -1 else str(col.max_length)
            return f"{dt.upper()}({length})"
        return dt.upper()

    def _sync_database(self, platform_id, db_name, result):
        engine = self._get_engine(db_name)
        if not engine:
            result.errors.append(f"Cannot connect to database: {db_name}")
            return
        try:
            with engine.connect() as conn:
                for schema in self._get_schemas(conn):
                    # Tables
                    rows = conn.execute(_SQL_TABLES, {"schema": schema}).fetchall()
                    for row in rows:
                        try:
                            self._sync_table(
                                platform_id, db_name, schema, row, conn, result,
                            )
                        except Exception as e:
                            qname = f"{db_name}.{schema}.{row.table_name}"
                            logger.error("Failed to sync %s: %s", qname, e)
                            result.failed += 1
                            result.errors.append(f"{qname}: {e}")

                    # Views
                    views = conn.execute(_SQL_VIEWS, {"schema": schema}).fetchall()
                    for v in views:
                        try:
                            self._sync_view(
                                platform_id, db_name, schema, v, conn, result,
                            )
                        except Exception as e:
                            qname = f"{db_name}.{schema}.{v.view_name}"
                            logger.error("Failed to sync %s: %s", qname, e)
                            result.failed += 1
                            result.errors.append(f"{qname}: {e}")
        finally:
            if db_name not in self._engines:
                engine.dispose()

    def _get_columns_fields(self, conn, object_id):
        col_rows = conn.execute(_SQL_COLUMNS, {"oid": object_id}).fetchall()
        pk_rows = conn.execute(_SQL_PRIMARY_KEYS, {"oid": object_id}).fetchall()
        pk_columns = {row.column_name for row in pk_rows}

        part_rows = conn.execute(_SQL_PARTITION_INFO, {"oid": object_id}).fetchall()
        part_columns = {row.column_name for row in part_rows}
        part_info = {}
        if part_rows:
            part_info = {
                "function_type": part_rows[0].function_type,
                "partition_count": part_rows[0].partition_count,
                "columns": [row.column_name for row in part_rows],
            }

        schema_fields = []
        for ordinal, col in enumerate(col_rows):
            schema_fields.append({
                "field_path": col.column_name,
                "field_type": self._map_mssql_type(col.data_type),
                "native_type": self._build_native_type(col),
                "description": str(col.column_comment) if col.column_comment else "",
                "nullable": str(bool(col.is_nullable)).lower(),
                "ordinal": ordinal,
                "is_primary_key": str(col.column_name in pk_columns).lower(),
                "is_partition_key": str(col.column_name in part_columns).lower(),
            })
        return schema_fields, part_info

    def _sync_table(self, platform_id, db_name, schema, table_info, conn, result):
        table_name = table_info.table_name
        qualified_name = f"{db_name}.{schema}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.mssql_origin)

        description = str(table_info.table_comment) if table_info.table_comment else ""
        schema_fields, part_info = self._get_columns_fields(
            conn, table_info.object_id,
        )

        table_type = "PARTITIONED_TABLE" if part_info else "TABLE"

        properties = {"mssql.database": db_name}
        if table_info.filegroup_name:
            properties["mssql.filegroup"] = table_info.filegroup_name
        if table_info.row_count is not None:
            properties["mssql.row_count"] = str(table_info.row_count)
        if table_info.total_size_bytes is not None:
            properties["mssql.total_size"] = str(table_info.total_size_bytes)
        if part_info:
            properties["mssql.partition_function_type"] = part_info["function_type"]
            properties["mssql.partition_count"] = str(part_info["partition_count"])
            properties["mssql.partition_columns"] = ",".join(part_info["columns"])

        existing = self.client.get_dataset_by_urn(urn)
        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
        else:
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.mssql_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "schema_fields": schema_fields,
                "owners": [],
                "properties": properties,
            })
            result.created += 1

    def _sync_view(self, platform_id, db_name, schema, view_info, conn, result):
        view_name = view_info.view_name
        qualified_name = f"{db_name}.{schema}.{view_name}"
        urn = self._generate_urn(qualified_name, self.settings.mssql_origin)

        description = str(view_info.view_comment) if view_info.view_comment else ""
        schema_fields, _ = self._get_columns_fields(conn, view_info.object_id)

        existing = self.client.get_dataset_by_urn(urn)
        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": "VIEW",
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
        else:
            self.client.create_dataset({
                "name": view_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.mssql_origin,
                "qualified_name": qualified_name,
                "table_type": "VIEW",
                "schema_fields": schema_fields,
                "owners": [],
                "properties": {"mssql.database": db_name},
            })
            result.created += 1
