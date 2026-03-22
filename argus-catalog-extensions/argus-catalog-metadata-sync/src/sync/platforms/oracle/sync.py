"""Oracle Database metadata synchronization.

Connects to Oracle via SQLAlchemy/oracledb, queries ALL_* dictionary
views to collect schema, table, column metadata including primary keys,
partition keys, tablespace, and table statistics.

Oracle has no "database" concept in the multi-DB sense — uses schemas
(owners). The qualified_name is schema.table_name.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

_ORACLE_TYPE_MAP = {
    "NUMBER": "DECIMAL",
    "FLOAT": "DOUBLE",
    "BINARY_FLOAT": "FLOAT",
    "BINARY_DOUBLE": "DOUBLE",
    "VARCHAR2": "VARCHAR",
    "NVARCHAR2": "VARCHAR",
    "CHAR": "CHAR",
    "NCHAR": "CHAR",
    "CLOB": "TEXT",
    "NCLOB": "TEXT",
    "BLOB": "BINARY",
    "RAW": "BINARY",
    "LONG": "TEXT",
    "LONG RAW": "BINARY",
    "DATE": "TIMESTAMP",
    "TIMESTAMP": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMP",
    "TIMESTAMP WITH LOCAL TIME ZONE": "TIMESTAMP",
    "INTERVAL YEAR TO MONTH": "STRING",
    "INTERVAL DAY TO SECOND": "STRING",
    "XMLTYPE": "XML",
    "SDO_GEOMETRY": "STRING",
    "ROWID": "STRING",
    "UROWID": "STRING",
    "BFILE": "STRING",
    "JSON": "JSON",
}

_PARTITION_TYPE_MAP = {
    "RANGE": "RANGE",
    "LIST": "LIST",
    "HASH": "HASH",
    "REFERENCE": "REFERENCE",
    "SYSTEM": "SYSTEM",
}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_SCHEMAS = text("""
    SELECT username FROM all_users
    WHERE oracle_maintained = 'N'
    ORDER BY username
""")

_SQL_TABLES = text("""
    SELECT t.table_name, t.tablespace_name, t.num_rows, t.blocks,
           t.avg_row_len, t.partitioned, t.temporary,
           c.comments AS table_comment
    FROM all_tables t
    LEFT JOIN all_tab_comments c
        ON c.owner = t.owner AND c.table_name = t.table_name
    WHERE t.owner = :schema
    ORDER BY t.table_name
""")

_SQL_VIEWS = text("""
    SELECT v.view_name, c.comments AS view_comment
    FROM all_views v
    LEFT JOIN all_tab_comments c
        ON c.owner = v.owner AND c.table_name = v.view_name
    WHERE v.owner = :schema
    ORDER BY v.view_name
""")

_SQL_COLUMNS = text("""
    SELECT c.column_id, c.column_name, c.data_type, c.data_length,
           c.data_precision, c.data_scale, c.nullable, c.data_default,
           cc.comments AS column_comment
    FROM all_tab_columns c
    LEFT JOIN all_col_comments cc
        ON cc.owner = c.owner AND cc.table_name = c.table_name
        AND cc.column_name = c.column_name
    WHERE c.owner = :schema AND c.table_name = :table
    ORDER BY c.column_id
""")

_SQL_PRIMARY_KEYS = text("""
    SELECT cc.column_name
    FROM all_constraints con
    JOIN all_cons_columns cc
        ON cc.owner = con.owner AND cc.constraint_name = con.constraint_name
    WHERE con.owner = :schema AND con.table_name = :table
        AND con.constraint_type = 'P'
    ORDER BY cc.position
""")

_SQL_PARTITION_KEYS = text("""
    SELECT pk.column_name
    FROM all_part_key_columns pk
    WHERE pk.owner = :schema AND pk.name = :table
        AND pk.object_type = 'TABLE'
    ORDER BY pk.column_position
""")

_SQL_PARTITION_INFO = text("""
    SELECT partitioning_type, subpartitioning_type, partition_count
    FROM all_part_tables
    WHERE owner = :schema AND table_name = :table
""")


class OracleMetadataSync(BasePlatformSync):
    """Synchronize metadata from Oracle Database to Argus Catalog."""

    platform_name = "oracle"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engine: Engine | None = None

    def connect(self) -> bool:
        try:
            s = self.settings
            if s.oracle_service_name:
                dsn = f"{s.oracle_host}:{s.oracle_port}/{s.oracle_service_name}"
            else:
                dsn = f"{s.oracle_host}:{s.oracle_port}/{s.oracle_sid}"
            url = f"oracle+oracledb://{s.oracle_username}:{s.oracle_password}@{dsn}"
            self._engine = create_engine(
                url, pool_size=2, max_overflow=3, pool_recycle=3600,
                thick_mode=None,
            )
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM DUAL"))
            logger.info("Connected to Oracle at %s:%d", s.oracle_host, s.oracle_port)
            return True
        except Exception as e:
            logger.error("Failed to connect to Oracle: %s", e)
            return False

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def discover(self) -> list[dict]:
        result = []
        with self._engine.connect() as conn:
            for schema in self._get_schemas(conn):
                try:
                    rows = conn.execute(_SQL_TABLES, {"schema": schema}).fetchall()
                    for row in rows:
                        result.append({
                            "database": schema,
                            "table": row.table_name,
                            "qualified_name": f"{schema}.{row.table_name}",
                            "table_type": "TABLE",
                            "columns_count": 0,
                            "owner": schema,
                        })
                    views = conn.execute(_SQL_VIEWS, {"schema": schema}).fetchall()
                    for v in views:
                        result.append({
                            "database": schema,
                            "table": v.view_name,
                            "qualified_name": f"{schema}.{v.view_name}",
                            "table_type": "VIEW",
                            "columns_count": 0,
                            "owner": schema,
                        })
                except Exception as e:
                    logger.warning("Failed to discover in %s: %s", schema, e)
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
            schemas = self._get_schemas(conn)
            logger.info("Syncing %d schemas from Oracle", len(schemas))

            for schema in schemas:
                # Tables
                try:
                    rows = conn.execute(_SQL_TABLES, {"schema": schema}).fetchall()
                except Exception as e:
                    logger.error("Failed to list tables in %s: %s", schema, e)
                    result.errors.append(f"Schema {schema}: {e}")
                    continue
                for row in rows:
                    try:
                        self._sync_table(
                            platform_id, schema, row, conn, result,
                        )
                    except Exception as e:
                        qname = f"{schema}.{row.table_name}"
                        logger.error("Failed to sync %s: %s", qname, e)
                        result.failed += 1
                        result.errors.append(f"{qname}: {e}")

                # Views
                try:
                    views = conn.execute(_SQL_VIEWS, {"schema": schema}).fetchall()
                except Exception as e:
                    logger.error("Failed to list views in %s: %s", schema, e)
                    continue
                for v in views:
                    try:
                        self._sync_view(
                            platform_id, schema, v, conn, result,
                        )
                    except Exception as e:
                        qname = f"{schema}.{v.view_name}"
                        logger.error("Failed to sync %s: %s", qname, e)
                        result.failed += 1
                        result.errors.append(f"{qname}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "Oracle sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_schemas(self, conn) -> list[str]:
        rows = conn.execute(_SQL_SCHEMAS).fetchall()
        all_schemas = [row.username for row in rows]
        if self.settings.oracle_schemas:
            return [s for s in all_schemas if s in self.settings.oracle_schemas]
        return [
            s for s in all_schemas
            if s not in self.settings.oracle_exclude_schemas
        ]

    def _map_oracle_type(self, data_type: str) -> str:
        return _ORACLE_TYPE_MAP.get(data_type.upper(), data_type.upper())

    def _build_native_type(self, col) -> str:
        dt = col.data_type
        if dt in ("NUMBER",) and col.data_precision is not None:
            if col.data_scale and col.data_scale > 0:
                return f"NUMBER({col.data_precision},{col.data_scale})"
            return f"NUMBER({col.data_precision})"
        if dt in ("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR", "RAW"):
            return f"{dt}({col.data_length})"
        return dt

    def _get_columns_and_fields(self, conn, schema, table_name):
        col_rows = conn.execute(
            _SQL_COLUMNS, {"schema": schema, "table": table_name}
        ).fetchall()
        pk_rows = conn.execute(
            _SQL_PRIMARY_KEYS, {"schema": schema, "table": table_name}
        ).fetchall()
        pk_columns = {row.column_name for row in pk_rows}
        part_keys = self._get_partition_keys(conn, schema, table_name)

        schema_fields = []
        for ordinal, col in enumerate(col_rows):
            schema_fields.append({
                "field_path": col.column_name,
                "field_type": self._map_oracle_type(col.data_type),
                "native_type": self._build_native_type(col),
                "description": col.column_comment or "",
                "nullable": str(col.nullable == "Y").lower(),
                "ordinal": ordinal,
                "is_primary_key": str(col.column_name in pk_columns).lower(),
                "is_partition_key": str(col.column_name in part_keys).lower(),
            })
        return schema_fields, part_keys

    def _get_partition_keys(self, conn, schema, table_name) -> set[str]:
        try:
            rows = conn.execute(
                _SQL_PARTITION_KEYS, {"schema": schema, "table": table_name}
            ).fetchall()
            return {row.column_name for row in rows}
        except Exception:
            return set()

    def _get_partition_info(self, conn, schema, table_name) -> dict:
        try:
            rows = conn.execute(
                _SQL_PARTITION_INFO, {"schema": schema, "table": table_name}
            ).fetchall()
            if rows:
                row = rows[0]
                return {
                    "type": _PARTITION_TYPE_MAP.get(
                        row.partitioning_type, row.partitioning_type
                    ),
                    "subtype": row.subpartitioning_type or "",
                    "count": row.partition_count,
                }
        except Exception:
            pass
        return {}

    def _sync_table(
        self, platform_id, schema, table_info, conn, result,
    ):
        table_name = table_info.table_name
        qualified_name = f"{schema}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.oracle_origin)

        description = table_info.table_comment or ""
        is_partitioned = table_info.partitioned == "YES"

        schema_fields, part_keys = self._get_columns_and_fields(
            conn, schema, table_name,
        )

        table_type = "PARTITIONED_TABLE" if is_partitioned else "TABLE"
        if table_info.temporary == "Y":
            table_type = "TEMPORARY_TABLE"

        properties = {"oracle.schema": schema}
        if table_info.tablespace_name:
            properties["oracle.tablespace"] = table_info.tablespace_name
        if table_info.num_rows is not None:
            properties["oracle.num_rows"] = str(table_info.num_rows)
        if table_info.avg_row_len is not None:
            properties["oracle.avg_row_len"] = str(table_info.avg_row_len)
        if table_info.blocks is not None:
            properties["oracle.blocks"] = str(table_info.blocks)

        if is_partitioned:
            part_info = self._get_partition_info(conn, schema, table_name)
            if part_info:
                properties["oracle.partition_type"] = part_info["type"]
                if part_info["subtype"] and part_info["subtype"] != "NONE":
                    properties["oracle.subpartition_type"] = part_info["subtype"]
                properties["oracle.partition_count"] = str(part_info["count"])
            if part_keys:
                properties["oracle.partition_columns"] = ",".join(sorted(part_keys))

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
            owners = [{"owner_name": schema, "owner_type": "TECHNICAL_OWNER"}]
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.oracle_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1

    def _sync_view(
        self, platform_id, schema, view_info, conn, result,
    ):
        view_name = view_info.view_name
        qualified_name = f"{schema}.{view_name}"
        urn = self._generate_urn(qualified_name, self.settings.oracle_origin)

        description = view_info.view_comment or ""
        schema_fields, _ = self._get_columns_and_fields(conn, schema, view_name)

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
            owners = [{"owner_name": schema, "owner_type": "TECHNICAL_OWNER"}]
            self.client.create_dataset({
                "name": view_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.oracle_origin,
                "qualified_name": qualified_name,
                "table_type": "VIEW",
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": {"oracle.schema": schema},
            })
            result.created += 1
