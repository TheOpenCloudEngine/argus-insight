"""Greenplum DB metadata synchronization.

Connects to Greenplum via PostgreSQL protocol, queries system catalogs
to collect database, schema, table, and column metadata including
Greenplum-specific distribution keys, partition keys, and storage formats.

Supports both GP7 (pg_partitioned_table) and GP6 (pg_partition) for
partition detection. Each database requires a separate connection since
Greenplum does not support cross-database queries.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync.core.base import BasePlatformSync, SyncResult
from sync.core.catalog_client import CatalogClient

logger = logging.getLogger(__name__)

# Greenplum native type → normalized catalog type
_GP_TYPE_MAP = {
    "int2": "SMALLINT",
    "int4": "INT",
    "int8": "BIGINT",
    "float4": "FLOAT",
    "float8": "DOUBLE",
    "numeric": "DECIMAL",
    "bool": "BOOLEAN",
    "varchar": "VARCHAR",
    "bpchar": "CHAR",
    "text": "TEXT",
    "timestamp": "TIMESTAMP",
    "timestamptz": "TIMESTAMP",
    "date": "DATE",
    "time": "TIME",
    "timetz": "TIME",
    "bytea": "BINARY",
    "json": "JSON",
    "jsonb": "JSON",
    "uuid": "UUID",
    "xml": "XML",
    "inet": "STRING",
    "cidr": "STRING",
    "macaddr": "STRING",
    "money": "DECIMAL",
    "interval": "STRING",
    "bit": "STRING",
    "varbit": "STRING",
    "point": "STRING",
    "line": "STRING",
    "lseg": "STRING",
    "box": "STRING",
    "path": "STRING",
    "polygon": "STRING",
    "circle": "STRING",
    "tsvector": "STRING",
    "tsquery": "STRING",
    "oid": "INT",
    # Array types (underscore-prefixed in pg_type.typname)
    "_int2": "ARRAY<SMALLINT>",
    "_int4": "ARRAY<INT>",
    "_int8": "ARRAY<BIGINT>",
    "_float4": "ARRAY<FLOAT>",
    "_float8": "ARRAY<DOUBLE>",
    "_numeric": "ARRAY<DECIMAL>",
    "_bool": "ARRAY<BOOLEAN>",
    "_varchar": "ARRAY<VARCHAR>",
    "_bpchar": "ARRAY<CHAR>",
    "_text": "ARRAY<TEXT>",
    "_timestamp": "ARRAY<TIMESTAMP>",
    "_timestamptz": "ARRAY<TIMESTAMP>",
    "_date": "ARRAY<DATE>",
    "_time": "ARRAY<TIME>",
    "_json": "ARRAY<JSON>",
    "_jsonb": "ARRAY<JSON>",
    "_uuid": "ARRAY<UUID>",
    "_bytea": "ARRAY<BINARY>",
    "_inet": "ARRAY<STRING>",
    "_money": "ARRAY<DECIMAL>",
    # Range types
    "int4range": "RANGE<INT>",
    "int8range": "RANGE<BIGINT>",
    "numrange": "RANGE<DECIMAL>",
    "tsrange": "RANGE<TIMESTAMP>",
    "tstzrange": "RANGE<TIMESTAMP>",
    "daterange": "RANGE<DATE>",
    # Multirange types (PG14+)
    "int4multirange": "MULTIRANGE<INT>",
    "int8multirange": "MULTIRANGE<BIGINT>",
    "nummultirange": "MULTIRANGE<DECIMAL>",
    "tsmultirange": "MULTIRANGE<TIMESTAMP>",
    "tstzmultirange": "MULTIRANGE<TIMESTAMP>",
    "datemultirange": "MULTIRANGE<DATE>",
}

# relkind → table_type
_RELKIND_MAP = {
    "r": "TABLE",
    "p": "PARTITIONED_TABLE",
    "v": "VIEW",
    "m": "MATERIALIZED_VIEW",
    "f": "FOREIGN_TABLE",
}

# Distribution policy type → human-readable
_DIST_POLICY_MAP = {
    "p": "HASH",
    "r": "REPLICATED",
}

# Partition strategy → human-readable
_PARTITION_STRATEGY_MAP = {
    "r": "RANGE",
    "l": "LIST",
    "h": "HASH",
}

# ── SQL Queries ──────────────────────────────────────────────────────────

_SQL_DATABASES = text("""
    SELECT datname FROM pg_database
    WHERE datistemplate = false
    ORDER BY datname
""")

_SQL_SCHEMAS = text("""
    SELECT nspname FROM pg_namespace
    WHERE nspname NOT LIKE 'pg_%'
      AND nspname NOT IN ('information_schema', 'gp_toolkit')
    ORDER BY nspname
""")

_SQL_TABLES = text("""
    SELECT c.oid, c.relname, c.relkind, c.reloptions,
           pg_catalog.obj_description(c.oid, 'pg_class') AS comment,
           t.spcname AS tablespace,
           pg_catalog.pg_table_size(c.oid) AS table_size,
           c.reltuples::bigint AS estimated_rows,
           r.rolname AS owner
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_tablespace t ON t.oid = c.reltablespace
    LEFT JOIN pg_roles r ON r.oid = c.relowner
    WHERE n.nspname = :schema
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    ORDER BY c.relname
""")

_SQL_COLUMNS = text("""
    SELECT a.attnum, a.attname,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           t.typname AS native_type,
           a.attnotnull,
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

_SQL_DISTRIBUTION = text("""
    SELECT dp.policytype, dp.numsegments,
           array_agg(a.attname ORDER BY k.n) AS dist_columns
    FROM gp_distribution_policy dp
    LEFT JOIN LATERAL unnest(dp.distkey) WITH ORDINALITY AS k(attnum, n) ON true
    LEFT JOIN pg_attribute a ON a.attrelid = dp.localoid AND a.attnum = k.attnum
    WHERE dp.localoid = :oid
    GROUP BY dp.policytype, dp.numsegments
""")

_SQL_PARTITION_GP7 = text("""
    SELECT pt.partstrat,
           array_agg(a.attname ORDER BY k.n) AS partition_columns
    FROM pg_partitioned_table pt
    CROSS JOIN LATERAL unnest(pt.partattrs::int[]) WITH ORDINALITY AS k(attnum, n)
    JOIN pg_attribute a ON a.attrelid = pt.partrelid AND a.attnum = k.attnum
    WHERE pt.partrelid = :oid
    GROUP BY pt.partstrat
""")

_SQL_PARTITION_GP6 = text("""
    SELECT pp.parkind,
           array_agg(a.attname ORDER BY a.attnum) AS partition_columns
    FROM pg_partition pp
    JOIN pg_attribute a ON a.attrelid = pp.parrelid AND a.attnum = ANY(pp.paratts)
    WHERE pp.parrelid = :oid AND pp.parlevel = 0
    GROUP BY pp.parkind
""")

_SQL_CHECK_TABLE = text("""
    SELECT to_regclass(:table_name) IS NOT NULL AS exists
""")


class GreenplumMetadataSync(BasePlatformSync):
    """Synchronize metadata from Greenplum DB to Argus Catalog.

    Uses PostgreSQL protocol via SQLAlchemy/psycopg2 to query Greenplum
    system catalogs. Each database requires a separate connection.
    """

    platform_name = "greenplum"

    def __init__(self, client: CatalogClient, settings):
        super().__init__(client)
        self.settings = settings
        self._engines: dict[str, Engine] = {}
        self._has_gp7_partitions: bool = False

    # ------------------------------------------------------------------
    # BasePlatformSync interface
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect to Greenplum and validate it is a GP instance."""
        try:
            initial_db = self.settings.greenplum_database or "postgres"
            engine = self._create_engine(initial_db)
            with engine.connect() as conn:
                # Verify this is Greenplum (not vanilla PostgreSQL)
                result = conn.execute(
                    _SQL_CHECK_TABLE, {"table_name": "gp_distribution_policy"}
                )
                is_gp = result.scalar()
                if not is_gp:
                    logger.error(
                        "Target database does not appear to be Greenplum "
                        "(gp_distribution_policy not found)"
                    )
                    engine.dispose()
                    return False

                # Detect GP7 partition support
                result = conn.execute(
                    _SQL_CHECK_TABLE, {"table_name": "pg_partitioned_table"}
                )
                self._has_gp7_partitions = bool(result.scalar())

            self._engines[initial_db] = engine
            logger.info(
                "Connected to Greenplum at %s:%d/%s (GP7 partitions: %s)",
                self.settings.greenplum_host,
                self.settings.greenplum_port,
                initial_db,
                self._has_gp7_partitions,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to Greenplum: %s", e)
            return False

    def disconnect(self) -> None:
        """Dispose all database engines."""
        for engine in self._engines.values():
            try:
                engine.dispose()
            except Exception:
                pass
        self._engines.clear()

    def discover(self) -> list[dict]:
        """Discover available tables from Greenplum."""
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
                logger.warning("Failed to discover tables in %s: %s", db_name, e)
            finally:
                if db_name not in self._engines:
                    engine.dispose()
        return result

    def sync(self) -> SyncResult:
        """Synchronize all Greenplum metadata to Argus Catalog."""
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
        logger.info("Syncing %d databases from Greenplum", len(databases))

        for db_name in databases:
            try:
                self._sync_database(platform_id, db_name, result)
            except Exception as e:
                logger.error("Failed to sync database %s: %s", db_name, e)
                result.errors.append(f"Database {db_name}: {e}")

        result.finished_at = datetime.now()
        logger.info(
            "Greenplum sync completed: created=%d, updated=%d, skipped=%d, failed=%d",
            result.created, result.updated, result.skipped, result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Database / Schema helpers
    # ------------------------------------------------------------------

    def _create_engine(self, database: str) -> Engine:
        """Create a SQLAlchemy engine for a specific database."""
        s = self.settings
        url = (
            f"postgresql+psycopg2://{s.greenplum_username}:{s.greenplum_password}"
            f"@{s.greenplum_host}:{s.greenplum_port}/{database}"
        )
        return create_engine(url, pool_size=2, max_overflow=3, pool_recycle=3600)

    def _get_engine(self, database: str) -> Engine | None:
        """Get or create an engine for a database."""
        if database in self._engines:
            return self._engines[database]
        try:
            engine = self._create_engine(database)
            # Test connectivity
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            logger.warning("Cannot connect to database %s: %s", database, e)
            return None

    def _get_databases(self) -> list[str]:
        """Get filtered list of databases to sync."""
        # If a specific database is configured, use only that
        if self.settings.greenplum_database:
            return [self.settings.greenplum_database]

        # Query all databases from the initial connection
        initial_db = list(self._engines.keys())[0] if self._engines else "postgres"
        engine = self._engines.get(initial_db)
        if not engine:
            return []

        with engine.connect() as conn:
            rows = conn.execute(_SQL_DATABASES).fetchall()
            all_dbs = [row.datname for row in rows]

        if self.settings.greenplum_databases:
            return [db for db in all_dbs if db in self.settings.greenplum_databases]
        return [
            db for db in all_dbs
            if db not in self.settings.greenplum_exclude_databases
        ]

    def _get_schemas(self, conn) -> list[str]:
        """Get filtered list of schemas from a database connection."""
        rows = conn.execute(_SQL_SCHEMAS).fetchall()
        all_schemas = [row.nspname for row in rows]

        if self.settings.greenplum_schemas:
            return [s for s in all_schemas if s in self.settings.greenplum_schemas]
        return [
            s for s in all_schemas
            if s not in self.settings.greenplum_exclude_schemas
        ]

    # ------------------------------------------------------------------
    # Sync orchestration
    # ------------------------------------------------------------------

    def _sync_database(
        self, platform_id: int, db_name: str, result: SyncResult,
    ) -> None:
        """Sync all tables in a database."""
        engine = self._get_engine(db_name)
        if not engine:
            result.errors.append(f"Cannot connect to database: {db_name}")
            return

        try:
            with engine.connect() as conn:
                schemas = self._get_schemas(conn)
                logger.info(
                    "Syncing database %s: %d schemas", db_name, len(schemas),
                )
                for schema in schemas:
                    rows = conn.execute(
                        _SQL_TABLES, {"schema": schema}
                    ).fetchall()
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
            # Dispose engines that were created for this sync (not the initial one)
            if db_name not in self._engines:
                engine.dispose()

    def _sync_table(
        self,
        platform_id: int,
        db_name: str,
        schema: str,
        table_info,
        conn,
        result: SyncResult,
    ) -> None:
        """Sync a single table to Argus Catalog."""
        table_name = table_info.relname
        table_oid = table_info.oid
        qualified_name = f"{db_name}.{schema}.{table_name}"
        urn = self._generate_urn(qualified_name, self.settings.greenplum_origin)

        # Table metadata
        table_type = _RELKIND_MAP.get(table_info.relkind, "TABLE")
        description = table_info.comment or ""
        owner = table_info.owner or ""

        # Columns
        columns = self._get_columns(conn, table_oid)
        pk_columns = self._get_primary_keys(conn, table_oid)
        dist_info = self._get_distribution_info(conn, table_oid)
        part_info = self._get_partition_info(conn, table_oid)
        storage_type = self._detect_storage_type(table_info.relkind, table_info.reloptions)

        dist_columns = set(dist_info.get("columns", []))
        part_columns = set(part_info.get("columns", []))

        # Build schema fields
        schema_fields = []
        for ordinal, col in enumerate(columns):
            schema_fields.append({
                "field_path": col["name"],
                "field_type": self._map_gp_type(col["native_type"], col["data_type"]),
                "native_type": col["data_type"],
                "description": col["comment"] or "",
                "nullable": str(not col["notnull"]).lower(),
                "ordinal": ordinal,
                "is_primary_key": str(col["name"] in pk_columns).lower(),
                "is_partition_key": str(col["name"] in part_columns).lower(),
                "is_distribution_key": str(col["name"] in dist_columns).lower(),
            })

        # Build properties
        properties = {
            "greenplum.database": db_name,
        }
        if storage_type:
            properties["greenplum.storage_type"] = storage_type

        # Distribution
        if dist_info:
            policy_type = dist_info.get("policy_type", "RANDOM")
            if policy_type == "HASH" and dist_info.get("columns"):
                cols_str = ", ".join(dist_info["columns"])
                properties["greenplum.distribution_policy"] = (
                    f"DISTRIBUTED BY ({cols_str})"
                )
                properties["greenplum.distribution_columns"] = ",".join(
                    dist_info["columns"]
                )
            elif policy_type == "REPLICATED":
                properties["greenplum.distribution_policy"] = "DISTRIBUTED REPLICATED"
            else:
                properties["greenplum.distribution_policy"] = "DISTRIBUTED RANDOMLY"
            if dist_info.get("numsegments"):
                properties["greenplum.numsegments"] = str(dist_info["numsegments"])

        # Partition
        if part_info and part_info.get("columns"):
            properties["greenplum.partition_strategy"] = part_info.get("strategy", "")
            properties["greenplum.partition_columns"] = ",".join(part_info["columns"])

        # Table size and stats
        if table_info.tablespace:
            properties["greenplum.tablespace"] = table_info.tablespace
        if table_info.table_size is not None and table_info.table_size >= 0:
            properties["greenplum.table_size"] = str(table_info.table_size)
        if table_info.estimated_rows is not None and table_info.estimated_rows >= 0:
            properties["greenplum.estimated_rows"] = str(table_info.estimated_rows)

        # Create or update
        existing = self.client.get_dataset_by_urn(urn)

        if existing:
            dataset_id = existing["id"]
            self.client.update_dataset(dataset_id, {
                "description": description,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_type,
            })
            self.client.update_schema_fields(dataset_id, schema_fields)
            result.updated += 1
            logger.debug("Updated: %s", qualified_name)
        else:
            owners = []
            if owner:
                owners.append({
                    "owner_name": owner,
                    "owner_type": "TECHNICAL_OWNER",
                })
            self.client.create_dataset({
                "name": table_name,
                "platform_id": platform_id,
                "description": description,
                "origin": self.settings.greenplum_origin,
                "qualified_name": qualified_name,
                "table_type": table_type,
                "storage_format": storage_type,
                "schema_fields": schema_fields,
                "owners": owners,
                "properties": properties,
            })
            result.created += 1
            logger.debug("Created: %s", qualified_name)

    # ------------------------------------------------------------------
    # Metadata query helpers
    # ------------------------------------------------------------------

    def _get_columns(self, conn, table_oid: int) -> list[dict]:
        """Get column metadata for a table."""
        rows = conn.execute(_SQL_COLUMNS, {"oid": table_oid}).fetchall()
        return [
            {
                "name": row.attname,
                "data_type": row.data_type,
                "native_type": row.native_type,
                "notnull": row.attnotnull,
                "comment": row.comment,
            }
            for row in rows
        ]

    def _get_primary_keys(self, conn, table_oid: int) -> set[str]:
        """Get primary key column names."""
        rows = conn.execute(_SQL_PRIMARY_KEYS, {"oid": table_oid}).fetchall()
        return {row.attname for row in rows}

    def _get_distribution_info(self, conn, table_oid: int) -> dict:
        """Get Greenplum distribution policy for a table.

        Returns: {"policy_type": "HASH"|"RANDOM"|"REPLICATED",
                  "columns": [...], "numsegments": int}
        """
        try:
            rows = conn.execute(_SQL_DISTRIBUTION, {"oid": table_oid}).fetchall()
            if not rows:
                return {}
            row = rows[0]
            policy_type = _DIST_POLICY_MAP.get(row.policytype, "RANDOM")
            columns = []
            if row.dist_columns and row.dist_columns != [None]:
                columns = [c for c in row.dist_columns if c is not None]
            return {
                "policy_type": policy_type,
                "columns": columns,
                "numsegments": row.numsegments,
            }
        except Exception as e:
            logger.debug("Could not get distribution info for oid %d: %s", table_oid, e)
            return {}

    def _get_partition_info(self, conn, table_oid: int) -> dict:
        """Get partition key info. Tries GP7 first, falls back to GP6.

        Returns: {"strategy": "RANGE"|"LIST"|"HASH", "columns": [...]}
        """
        # Try GP7 (pg_partitioned_table)
        if self._has_gp7_partitions:
            try:
                rows = conn.execute(
                    _SQL_PARTITION_GP7, {"oid": table_oid}
                ).fetchall()
                if rows:
                    row = rows[0]
                    return {
                        "strategy": _PARTITION_STRATEGY_MAP.get(
                            row.partstrat, row.partstrat
                        ),
                        "columns": row.partition_columns or [],
                    }
            except Exception as e:
                logger.debug("GP7 partition query failed for oid %d: %s", table_oid, e)

        # Fallback to GP6 (pg_partition)
        try:
            rows = conn.execute(
                _SQL_PARTITION_GP6, {"oid": table_oid}
            ).fetchall()
            if rows:
                row = rows[0]
                return {
                    "strategy": _PARTITION_STRATEGY_MAP.get(
                        row.parkind, row.parkind
                    ),
                    "columns": row.partition_columns or [],
                }
        except Exception:
            pass  # pg_partition may not exist in GP7

        return {}

    # ------------------------------------------------------------------
    # Type mapping and format detection
    # ------------------------------------------------------------------

    def _map_gp_type(self, native_type: str, data_type: str) -> str:
        """Map Greenplum column type to a normalized catalog type.

        Args:
            native_type: pg_type.typname (e.g., "int4", "_int4", "numeric")
            data_type: format_type() output (e.g., "integer", "integer[]",
                       "numeric(10,2)")
        """
        # Check direct mapping first (includes array underscore prefix types)
        mapped = _GP_TYPE_MAP.get(native_type)
        if mapped:
            return mapped

        # Handle array types from format_type (e.g., "text[]", "integer[]")
        if data_type.endswith("[]"):
            base_type = data_type[:-2]
            base_mapped = self._map_gp_type_from_format(base_type)
            return f"ARRAY<{base_mapped}>"

        # Map from format_type output
        return self._map_gp_type_from_format(data_type)

    def _map_gp_type_from_format(self, format_type: str) -> str:
        """Map format_type() output to normalized type, stripping precision."""
        # Extract base type before parentheses: "numeric(10,2)" → "numeric"
        base = format_type.split("(")[0].strip().lower()

        # Common format_type names → standard names
        format_map = {
            "integer": "INT",
            "smallint": "SMALLINT",
            "bigint": "BIGINT",
            "real": "FLOAT",
            "double precision": "DOUBLE",
            "numeric": "DECIMAL",
            "boolean": "BOOLEAN",
            "character varying": "VARCHAR",
            "character": "CHAR",
            "text": "TEXT",
            "bytea": "BINARY",
            "timestamp without time zone": "TIMESTAMP",
            "timestamp with time zone": "TIMESTAMP",
            "date": "DATE",
            "time without time zone": "TIME",
            "time with time zone": "TIME",
            "interval": "STRING",
            "json": "JSON",
            "jsonb": "JSON",
            "uuid": "UUID",
            "xml": "XML",
            "money": "DECIMAL",
            "inet": "STRING",
            "cidr": "STRING",
            "macaddr": "STRING",
            "tsvector": "STRING",
            "tsquery": "STRING",
        }
        return format_map.get(base, base.upper())

    def _detect_storage_type(
        self, relkind: str, reloptions: list | None,
    ) -> str | None:
        """Detect Greenplum storage type from reloptions.

        Returns: "HEAP", "AORO", "AOCO", or None for views.
        """
        if relkind in ("v", "m"):
            return None

        if not reloptions:
            return "HEAP"

        opts = {
            kv.split("=")[0].lower(): kv.split("=")[1].lower()
            for kv in reloptions
            if "=" in kv
        }

        if opts.get("appendoptimized") == "true" or opts.get("appendonly") == "true":
            if opts.get("orientation") == "column":
                return "AOCO"
            return "AORO"
        return "HEAP"
