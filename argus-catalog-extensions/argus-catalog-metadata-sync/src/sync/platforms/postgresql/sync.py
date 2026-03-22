"""PostgreSQL metadata synchronization.

Connects to PostgreSQL via SQLAlchemy/psycopg2, queries pg_catalog
to collect database, schema, table, column metadata including primary
keys, partition keys, and table statistics.

Shares query patterns with Greenplum sync but without GP-specific
features (distribution keys, AO storage).
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

_PG_TYPE_MAP = {
    "int2": "SMALLINT", "int4": "INT", "int8": "BIGINT",
    "float4": "FLOAT", "float8": "DOUBLE",
    "numeric": "DECIMAL", "bool": "BOOLEAN",
    "varchar": "VARCHAR", "bpchar": "CHAR", "text": "TEXT",
    "timestamp": "TIMESTAMP", "timestamptz": "TIMESTAMP",
    "date": "DATE", "time": "TIME", "timetz": "TIME",
    "bytea": "BINARY", "json": "JSON", "jsonb": "JSON",
    "uuid": "UUID", "xml": "XML",
    "inet": "STRING", "cidr": "STRING", "macaddr": "STRING",
    "money": "DECIMAL", "interval": "STRING",
    "bit": "STRING", "varbit": "STRING",
    "tsvector": "STRING", "tsquery": "STRING",
    "oid": "INT",
    # Array types
    "_int2": "ARRAY<SMALLINT>", "_int4": "ARRAY<INT>", "_int8": "ARRAY<BIGINT>",
    "_float4": "ARRAY<FLOAT>", "_float8": "ARRAY<DOUBLE>",
    "_numeric": "ARRAY<DECIMAL>", "_bool": "ARRAY<BOOLEAN>",
    "_varchar": "ARRAY<VARCHAR>", "_bpchar": "ARRAY<CHAR>", "_text": "ARRAY<TEXT>",
    "_timestamp": "ARRAY<TIMESTAMP>", "_timestamptz": "ARRAY<TIMESTAMP>",
    "_date": "ARRAY<DATE>", "_json": "ARRAY<JSON>", "_jsonb": "ARRAY<JSON>",
    "_uuid": "ARRAY<UUID>", "_bytea": "ARRAY<BINARY>",
    # Range types
    "int4range": "RANGE<INT>", "int8range": "RANGE<BIGINT>",
    "numrange": "RANGE<DECIMAL>",
    "tsrange": "RANGE<TIMESTAMP>", "tstzrange": "RANGE<TIMESTAMP>",
    "daterange": "RANGE<DATE>",
}

_RELKIND_MAP = {
    "r": "TABLE", "p": "PARTITIONED_TABLE", "v": "VIEW",
    "m": "MATERIALIZED_VIEW", "f": "FOREIGN_TABLE",
}

_PARTITION_STRATEGY_MAP = {"r": "RANGE", "l": "LIST", "h": "HASH"}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_DATABASES = text("""
    SELECT datname FROM pg_database
    WHERE datistemplate = false ORDER BY datname
""")

_SQL_SCHEMAS = text("""
    SELECT nspname FROM pg_namespace
    WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'
    ORDER BY nspname
""")

_SQL_TABLES = text("""
    SELECT c.oid, c.relname, c.relkind,
           pg_catalog.obj_description(c.oid, 'pg_class') AS comment,
           t.spcname AS tablespace,
           pg_catalog.pg_table_size(c.oid) AS table_size,
           c.reltuples::bigint AS estimated_rows,
           r.rolname AS owner
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_tablespace t ON t.oid = c.reltablespace
    LEFT JOIN pg_roles r ON r.oid = c.relowner
    WHERE n.nspname = :schema AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    ORDER BY c.relname
""")

_SQL_COLUMNS = text("""
    SELECT a.attnum, a.attname,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           t.typname AS native_type, a.attnotnull,
           pg_catalog.col_description(a.attrelid, a.attnum) AS comment
    FROM pg_attribute a
    JOIN pg_type t ON t.oid = a.atttypid
    WHERE a.attrelid = :oid AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum
""")

_SQL_PRIMARY_KEYS = text("""
    SELECT a.attname
    FROM pg_constraint con
    CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, n)
    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
    WHERE con.conrelid = :oid AND con.contype = 'p'
    ORDER BY k.n
""")

_SQL_PARTITIONS = text("""
    SELECT pt.partstrat,
           array_agg(a.attname ORDER BY k.n) AS partition_columns
    FROM pg_partitioned_table pt
    CROSS JOIN LATERAL unnest(pt.partattrs::int[]) WITH ORDINALITY AS k(attnum, n)
    JOIN pg_attribute a ON a.attrelid = pt.partrelid AND a.attnum = k.attnum
    WHERE pt.partrelid = :oid
    GROUP BY pt.partstrat
""")


class PostgresqlMetadataSync(BasePlatformSync):
    """Synchronize metadata from PostgreSQL to Argus Catalog."""

    platform_name = "postgresql"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engines: dict[str, Engine] = {}

    def connect(self) -> bool:
        try:
            initial_db = self.settings.postgresql_database or "postgres"
            engine = self._create_engine(initial_db)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._engines[initial_db] = engine
            logger.info(
                "Connected to PostgreSQL at %s:%d",
                self.settings.postgresql_host, self.settings.postgresql_port,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
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
                                "table": row.relname,
                                "qualified_name": f"{db_name}.{schema}.{row.relname}",
                                "table_type": _RELKIND_MAP.get(row.relkind, "TABLE"),
                                "columns_count": 0,
                                "owner": row.owner or "",
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
        logger.info("Syncing %d databases from PostgreSQL", len(databases))

        for db_name in databases:
            try:
                self._sync_database(platform_id, db_name, result)
            except Exception as e:
                logger.error("Failed to sync database %s: %s", db_name, e)
                result.errors.append(f"Database {db_name}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "PostgreSQL sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_engine(self, database: str) -> Engine:
        s = self.settings
        url = (
            f"postgresql+psycopg2://{s.postgresql_username}:{s.postgresql_password}"
            f"@{s.postgresql_host}:{s.postgresql_port}/{database}"
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
        if self.settings.postgresql_database:
            return [self.settings.postgresql_database]
        initial_db = list(self._engines.keys())[0] if self._engines else "postgres"
        engine = self._engines.get(initial_db)
        if not engine:
            return []
        with engine.connect() as conn:
            rows = conn.execute(_SQL_DATABASES).fetchall()
            all_dbs = [row.datname for row in rows]
        if self.settings.postgresql_databases:
            return [db for db in all_dbs if db in self.settings.postgresql_databases]
        return [
            db for db in all_dbs
            if db not in self.settings.postgresql_exclude_databases
        ]

    def _get_schemas(self, conn) -> list[str]:
        rows = conn.execute(_SQL_SCHEMAS).fetchall()
        all_schemas = [row.nspname for row in rows]
        if self.settings.postgresql_schemas:
            return [s for s in all_schemas if s in self.settings.postgresql_schemas]
        return [
            s for s in all_schemas
            if s not in self.settings.postgresql_exclude_schemas
        ]

    def _map_pg_type(self, native_type: str, data_type: str) -> str:
        mapped = _PG_TYPE_MAP.get(native_type)
        if mapped:
            return mapped
        if data_type.endswith("[]"):
            base = data_type[:-2].split("(")[0].strip().lower()
            base_map = {
                "integer": "INT", "smallint": "SMALLINT", "bigint": "BIGINT",
                "real": "FLOAT", "double precision": "DOUBLE", "numeric": "DECIMAL",
                "boolean": "BOOLEAN", "character varying": "VARCHAR", "text": "TEXT",
                "timestamp without time zone": "TIMESTAMP",
                "timestamp with time zone": "TIMESTAMP", "date": "DATE",
                "json": "JSON", "jsonb": "JSON", "uuid": "UUID", "bytea": "BINARY",
            }
            inner = base_map.get(base, base.upper())
            return f"ARRAY<{inner}>"
        base = data_type.split("(")[0].strip().lower()
        fmt_map = {
            "integer": "INT", "smallint": "SMALLINT", "bigint": "BIGINT",
            "real": "FLOAT", "double precision": "DOUBLE", "numeric": "DECIMAL",
            "boolean": "BOOLEAN", "character varying": "VARCHAR", "character": "CHAR",
            "text": "TEXT", "bytea": "BINARY",
            "timestamp without time zone": "TIMESTAMP",
            "timestamp with time zone": "TIMESTAMP",
            "date": "DATE", "time without time zone": "TIME",
            "time with time zone": "TIME", "json": "JSON", "jsonb": "JSON",
            "uuid": "UUID", "xml": "XML", "money": "DECIMAL", "interval": "STRING",
        }
        return fmt_map.get(base, base.upper())

    def _sync_database(self, platform_id: int, db_name: str, result: SyncResult):
        engine = self._get_engine(db_name)
        if not engine:
            result.errors.append(f"Cannot connect to database: {db_name}")
            return
        try:
            with engine.connect() as conn:
                for schema in self._get_schemas(conn):
                    rows = conn.execute(_SQL_TABLES, {"schema": schema}).fetchall()
                    for row in rows:
                        try:
                            self._sync_table(
                                platform_id, db_name, schema, row, conn, result,
                            )
                        except Exception as e:
                            qname = f"{db_name}.{schema}.{row.relname}"
                            logger.error("Failed to sync %s: %s", qname, e)
                            result.failed += 1
                            result.errors.append(f"{qname}: {e}")
        finally:
            if db_name not in self._engines:
                engine.dispose()

    def _sync_table(
        self, platform_id, db_name, schema, table_info, conn, result,
    ):
        table_name = table_info.relname
        table_oid = table_info.oid
        qualified_name = f"{db_name}.{schema}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.postgresql_origin)

        table_type = _RELKIND_MAP.get(table_info.relkind, "TABLE")
        description = table_info.comment or ""

        col_rows = conn.execute(_SQL_COLUMNS, {"oid": table_oid}).fetchall()
        pk_rows = conn.execute(_SQL_PRIMARY_KEYS, {"oid": table_oid}).fetchall()
        pk_columns = {row.attname for row in pk_rows}
        part_info = self._get_partition_info(conn, table_oid)
        part_columns = set(part_info.get("columns", []))

        schema_fields = []
        for ordinal, col in enumerate(col_rows):
            schema_fields.append({
                "field_path": col.attname,
                "field_type": self._map_pg_type(col.native_type, col.data_type),
                "native_type": col.data_type,
                "description": col.comment or "",
                "nullable": str(not col.attnotnull).lower(),
                "ordinal": ordinal,
                "is_primary_key": str(col.attname in pk_columns).lower(),
                "is_partition_key": str(col.attname in part_columns).lower(),
            })

        properties = {"postgresql.database": db_name}
        if table_info.tablespace:
            properties["postgresql.tablespace"] = table_info.tablespace
        if table_info.table_size is not None and table_info.table_size >= 0:
            properties["postgresql.table_size"] = str(table_info.table_size)
        if table_info.estimated_rows is not None and table_info.estimated_rows >= 0:
            properties["postgresql.estimated_rows"] = str(table_info.estimated_rows)
        if part_info and part_info.get("columns"):
            properties["postgresql.partition_strategy"] = part_info.get("strategy", "")
            properties["postgresql.partition_columns"] = ",".join(part_info["columns"])

        existing = self.client.get_dataset_by_urn(urn)
        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": "HEAP",
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
        else:
            owners = []
            if table_info.owner:
                owners.append({"owner_name": table_info.owner, "owner_type": "TECHNICAL_OWNER"})
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.postgresql_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": "HEAP",
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1

    def _get_partition_info(self, conn, table_oid: int) -> dict:
        try:
            rows = conn.execute(_SQL_PARTITIONS, {"oid": table_oid}).fetchall()
            if rows:
                return {
                    "strategy": _PARTITION_STRATEGY_MAP.get(
                        rows[0].partstrat, rows[0].partstrat
                    ),
                    "columns": rows[0].partition_columns or [],
                }
        except Exception:
            pass
        return {}
