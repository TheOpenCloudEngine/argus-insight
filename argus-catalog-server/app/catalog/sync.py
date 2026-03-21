"""Platform metadata synchronization.

Connects to external data platforms and syncs table/column metadata into the catalog.
"""

import io
import json
import logging
from dataclasses import dataclass, field

import aiomysql
import asyncpg
import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import (
    Dataset,
    DatasetSchema,
    Platform,
    PlatformConfiguration,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    native_type: str
    nullable: bool
    ordinal: int
    column_key: str = ""
    column_default: str | None = None
    comment: str = ""
    is_primary_key: bool = False
    is_unique: bool = False
    is_indexed: bool = False


@dataclass
class TableInfo:
    database: str
    name: str
    table_type: str  # BASE TABLE, VIEW, SYSTEM VIEW
    engine: str | None = None
    table_comment: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)
    platform_properties: dict | None = None  # platform-specific metadata (JSON)


@dataclass
class SyncResult:
    platform_id: str
    databases_scanned: list[str] = field(default_factory=list)
    tables_created: int = 0
    tables_updated: int = 0
    tables_removed: int = 0
    tables_total: int = 0
    samples_uploaded: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MySQL / MariaDB type mapping
# ---------------------------------------------------------------------------

MYSQL_TYPE_MAP = {
    "tinyint": "NUMBER", "smallint": "NUMBER", "mediumint": "NUMBER",
    "int": "NUMBER", "bigint": "NUMBER", "decimal": "NUMBER",
    "float": "NUMBER", "double": "NUMBER",
    "char": "STRING", "varchar": "STRING",
    "tinytext": "STRING", "text": "STRING", "mediumtext": "STRING", "longtext": "STRING",
    "binary": "BYTES", "varbinary": "BYTES",
    "tinyblob": "BYTES", "blob": "BYTES", "mediumblob": "BYTES", "longblob": "BYTES",
    "date": "DATE", "datetime": "DATE", "timestamp": "DATE", "time": "DATE", "year": "DATE",
    "json": "MAP", "enum": "ENUM", "set": "ARRAY",
    "geometry": "STRING", "point": "STRING", "linestring": "STRING", "polygon": "STRING",
}


def _map_field_type(native_type: str) -> str:
    """Map a MySQL/MariaDB column type to a generic catalog field type."""
    base = native_type.split("(")[0].strip().lower()
    return MYSQL_TYPE_MAP.get(base, "STRING")


# ---------------------------------------------------------------------------
# MariaDB / MySQL metadata reader
# ---------------------------------------------------------------------------

SYSTEM_DATABASES = {"information_schema", "performance_schema", "mysql", "sys"}


async def _read_mysql_metadata(
    host: str, port: int, user: str, password: str, database: str | None = None,
) -> list[TableInfo]:
    """Connect to MySQL/MariaDB and read table + column metadata from INFORMATION_SCHEMA."""

    logger.info("[MySQL] Connecting to %s:%d", host, port)
    conn = await aiomysql.connect(
        host=host, port=port, user=user, password=password,
        db="information_schema", charset="utf8mb4",
    )
    logger.info("[MySQL] Connected successfully")
    tables: list[TableInfo] = []

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Determine target databases
            if database:
                target_dbs = [database]
            else:
                await cur.execute("SELECT SCHEMA_NAME FROM SCHEMATA")
                rows = await cur.fetchall()
                target_dbs = [
                    r["SCHEMA_NAME"] for r in rows
                    if r["SCHEMA_NAME"].lower() not in SYSTEM_DATABASES
                ]
            logger.info("[MySQL] Target databases: %s", target_dbs)

            for db in target_dbs:
                # Fetch tables with extended metadata
                await cur.execute(
                    "SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COMMENT, "
                    "ROW_FORMAT, TABLE_ROWS, AVG_ROW_LENGTH, DATA_LENGTH, "
                    "INDEX_LENGTH, AUTO_INCREMENT, TABLE_COLLATION, "
                    "CREATE_TIME, UPDATE_TIME, CREATE_OPTIONS "
                    "FROM TABLES WHERE TABLE_SCHEMA = %s",
                    (db,),
                )
                table_rows = await cur.fetchall()
                logger.info("[MySQL] Database '%s': found %d table(s)", db, len(table_rows))

                for tr in table_rows:
                    # Build platform-specific properties
                    props: dict = {"table": {}, "columns": {}}
                    tbl_props = props["table"]
                    if tr.get("ENGINE"):
                        tbl_props["engine"] = tr["ENGINE"]
                    if tr.get("ROW_FORMAT"):
                        tbl_props["row_format"] = tr["ROW_FORMAT"]
                    if tr.get("TABLE_ROWS") is not None:
                        tbl_props["estimated_rows"] = tr["TABLE_ROWS"]
                    if tr.get("AVG_ROW_LENGTH") is not None:
                        tbl_props["avg_row_length"] = tr["AVG_ROW_LENGTH"]
                    if tr.get("DATA_LENGTH") is not None:
                        tbl_props["data_size"] = tr["DATA_LENGTH"]
                    if tr.get("INDEX_LENGTH") is not None:
                        tbl_props["index_size"] = tr["INDEX_LENGTH"]
                    if tr.get("AUTO_INCREMENT") is not None:
                        tbl_props["auto_increment"] = tr["AUTO_INCREMENT"]
                    if tr.get("TABLE_COLLATION"):
                        tbl_props["collation"] = tr["TABLE_COLLATION"]
                    if tr.get("CREATE_TIME"):
                        tbl_props["create_time"] = str(tr["CREATE_TIME"])
                    if tr.get("UPDATE_TIME"):
                        tbl_props["update_time"] = str(tr["UPDATE_TIME"])
                    if tr.get("CREATE_OPTIONS"):
                        tbl_props["create_options"] = tr["CREATE_OPTIONS"]

                    table = TableInfo(
                        database=db,
                        name=tr["TABLE_NAME"],
                        table_type=tr["TABLE_TYPE"],
                        engine=tr.get("ENGINE"),
                        table_comment=tr.get("TABLE_COMMENT") or "",
                        platform_properties=props,
                    )

                    # Fetch columns with extended metadata
                    await cur.execute(
                        "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, "
                        "ORDINAL_POSITION, COLUMN_KEY, COLUMN_DEFAULT, COLUMN_COMMENT, "
                        "EXTRA, CHARACTER_SET_NAME, COLLATION_NAME "
                        "FROM COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "ORDER BY ORDINAL_POSITION",
                        (db, table.name),
                    )
                    col_rows = await cur.fetchall()

                    for cr in col_rows:
                        col_key = cr.get("COLUMN_KEY") or ""
                        table.columns.append(ColumnInfo(
                            name=cr["COLUMN_NAME"],
                            data_type=_map_field_type(cr["DATA_TYPE"]),
                            native_type=cr["COLUMN_TYPE"],
                            nullable=cr["IS_NULLABLE"] == "YES",
                            ordinal=cr["ORDINAL_POSITION"],
                            column_key=col_key,
                            column_default=cr.get("COLUMN_DEFAULT"),
                            comment=cr.get("COLUMN_COMMENT") or "",
                            is_primary_key=col_key == "PRI",
                            is_unique=col_key in ("PRI", "UNI"),
                            is_indexed=col_key in ("PRI", "MUL", "UNI"),
                        ))

                        # Column-level properties
                        col_props: dict = {}
                        if cr.get("COLUMN_KEY"):
                            col_props["key"] = cr["COLUMN_KEY"]
                        if cr.get("EXTRA"):
                            col_props["extra"] = cr["EXTRA"]
                        if cr.get("COLUMN_DEFAULT") is not None:
                            col_props["default"] = str(cr["COLUMN_DEFAULT"])
                        if cr.get("CHARACTER_SET_NAME"):
                            col_props["charset"] = cr["CHARACTER_SET_NAME"]
                        if cr.get("COLLATION_NAME"):
                            col_props["collation"] = cr["COLLATION_NAME"]
                        if col_props:
                            props["columns"][cr["COLUMN_NAME"]] = col_props

                    # Collect CREATE TABLE DDL
                    try:
                        await cur.execute(
                            f"SHOW CREATE TABLE `{db}`.`{table.name}`"
                        )
                        ddl_row = await cur.fetchone()
                        if ddl_row:
                            # SHOW CREATE TABLE returns (table_name, create_sql)
                            # For views it's (view_name, create_sql, charset, collation)
                            ddl_key = "Create Table" if "Create Table" in ddl_row else "Create View"
                            props["ddl"] = ddl_row.get(ddl_key, "")
                    except Exception as e:
                        logger.info("[MySQL] DDL collection skipped for %s.%s: %s", db, table.name, e)

                    logger.info("[MySQL] %s.%s: type=%s, engine=%s, cols=%d, ddl=%s",
                                db, table.name, table.table_type,
                                table.engine, len(table.columns), bool(props.get("ddl")))
                    tables.append(table)

    finally:
        conn.close()
        logger.info("[MySQL] Connection closed. Total tables collected: %d", len(tables))

    return tables


# ---------------------------------------------------------------------------
# PostgreSQL type mapping
# ---------------------------------------------------------------------------

PG_TYPE_MAP = {
    "smallint": "NUMBER", "integer": "NUMBER", "bigint": "NUMBER",
    "int2": "NUMBER", "int4": "NUMBER", "int8": "NUMBER",
    "decimal": "NUMBER", "numeric": "NUMBER",
    "real": "NUMBER", "double precision": "NUMBER", "float4": "NUMBER", "float8": "NUMBER",
    "serial": "NUMBER", "bigserial": "NUMBER",
    "character varying": "STRING", "varchar": "STRING",
    "character": "STRING", "char": "STRING",
    "text": "STRING", "name": "STRING", "citext": "STRING",
    "bytea": "BYTES",
    "date": "DATE", "timestamp without time zone": "DATE",
    "timestamp with time zone": "DATE", "time without time zone": "DATE",
    "time with time zone": "DATE", "interval": "DATE",
    "boolean": "BOOLEAN", "bool": "BOOLEAN",
    "json": "MAP", "jsonb": "MAP",
    "uuid": "STRING", "inet": "STRING", "cidr": "STRING", "macaddr": "STRING",
    "xml": "STRING", "money": "NUMBER",
    "point": "STRING", "line": "STRING", "polygon": "STRING", "geometry": "STRING",
    "ARRAY": "ARRAY", "USER-DEFINED": "STRING",
}

SYSTEM_SCHEMAS_PG = {"pg_catalog", "information_schema", "pg_toast"}


def _map_pg_field_type(udt_name: str, data_type: str) -> str:
    """Map a PostgreSQL column type to a generic catalog field type."""
    if data_type == "ARRAY":
        return "ARRAY"
    if data_type == "USER-DEFINED":
        return "STRING"
    return PG_TYPE_MAP.get(data_type, PG_TYPE_MAP.get(udt_name, "STRING"))


# ---------------------------------------------------------------------------
# PostgreSQL metadata reader
# ---------------------------------------------------------------------------

async def _safe_pg_fetch(conn, query: str, *args) -> list:
    """Execute a query, returning empty list on permission error."""
    try:
        return await conn.fetch(query, *args)
    except Exception as e:
        logger.debug("Skipped query (permission or error): %s", e)
        return []


async def _safe_pg_fetchrow(conn, query: str, *args):
    """Execute a query returning one row, or None on error."""
    try:
        return await conn.fetchrow(query, *args)
    except Exception:
        return None


async def _read_pg_metadata(
    host: str, port: int, user: str, password: str,
    database: str, schema: str | None = None,
) -> list[TableInfo]:
    """Connect to PostgreSQL and read table + column metadata."""

    logger.info("[PostgreSQL] Connecting to %s:%d/%s", host, port, database)
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=database,
    )
    logger.info("[PostgreSQL] Connected successfully")
    tables: list[TableInfo] = []

    try:
        # Determine target schemas
        if schema:
            target_schemas = [schema]
        else:
            rows = await _safe_pg_fetch(
                conn,
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
                "AND schema_name NOT LIKE 'pg_temp%'",
            )
            target_schemas = [r["schema_name"] for r in rows]
        logger.info("[PostgreSQL] Target schemas: %s", target_schemas)

        for sch in target_schemas:
            # Fetch tables and views
            table_rows = await _safe_pg_fetch(
                conn,
                "SELECT table_name, table_type "
                "FROM information_schema.tables "
                "WHERE table_schema = $1 AND table_type IN ('BASE TABLE', 'VIEW')",
                sch,
            )

            logger.info("[PostgreSQL] Schema '%s': found %d table(s)", sch, len(table_rows))

            for tr in table_rows:
                tbl_name = tr["table_name"]
                props: dict = {"table": {}, "columns": {}, "indexes": []}
                tbl_props = props["table"]

                # Table comment
                comment_row = await _safe_pg_fetchrow(
                    conn,
                    "SELECT obj_description(c.oid) AS comment "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = $1 AND c.relname = $2",
                    sch, tbl_name,
                )
                table_comment = (comment_row["comment"] or "") if comment_row else ""

                # Table-level platform properties from pg_class
                pg_row = await _safe_pg_fetchrow(
                    conn,
                    "SELECT c.reltuples::bigint AS estimated_rows, "
                    "c.relpersistence::text, c.relkind::text, c.relhasindex AS has_indexes, "
                    "c.relhastriggers AS has_triggers, "
                    "pg_total_relation_size(c.oid) AS total_size, "
                    "pg_table_size(c.oid) AS table_size, "
                    "pg_indexes_size(c.oid) AS index_size "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = $1 AND c.relname = $2",
                    sch, tbl_name,
                )
                if pg_row:
                    persistence_map = {"p": "permanent", "t": "temporary", "u": "unlogged"}
                    kind_map = {
                        "r": "table", "v": "view", "m": "materialized view",
                        "f": "foreign table", "p": "partitioned table",
                    }
                    tbl_props["estimated_rows"] = pg_row["estimated_rows"]
                    tbl_props["persistence"] = persistence_map.get(
                        pg_row["relpersistence"], pg_row["relpersistence"])
                    tbl_props["kind"] = kind_map.get(
                        pg_row["relkind"], pg_row["relkind"])
                    tbl_props["has_indexes"] = pg_row["has_indexes"]
                    tbl_props["has_triggers"] = pg_row["has_triggers"]
                    tbl_props["total_size"] = pg_row["total_size"]
                    tbl_props["table_size"] = pg_row["table_size"]
                    tbl_props["index_size"] = pg_row["index_size"]

                # Table owner
                owner_row = await _safe_pg_fetchrow(
                    conn,
                    "SELECT tableowner FROM pg_tables "
                    "WHERE schemaname = $1 AND tablename = $2",
                    sch, tbl_name,
                )
                if not owner_row:
                    owner_row = await _safe_pg_fetchrow(
                        conn,
                        "SELECT viewowner AS tableowner FROM pg_views "
                        "WHERE schemaname = $1 AND viewname = $2",
                        sch, tbl_name,
                    )
                if owner_row and owner_row["tableowner"]:
                    tbl_props["owner"] = owner_row["tableowner"]

                # Indexes
                idx_rows = await _safe_pg_fetch(
                    conn,
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = $1 AND tablename = $2",
                    sch, tbl_name,
                )
                for ir in idx_rows:
                    props["indexes"].append({
                        "name": ir["indexname"],
                        "definition": ir["indexdef"],
                    })

                # Constraints (PK, FK, UNIQUE, CHECK)
                constraint_rows = await _safe_pg_fetch(
                    conn,
                    "SELECT con.conname::text, con.contype::text, "
                    "array_agg(att.attname::text ORDER BY u.ord) AS columns, "
                    "CASE WHEN con.contype = 'f' THEN "
                    "  (SELECT nspname || '.' || relname FROM pg_class fc "
                    "   JOIN pg_namespace fn ON fn.oid = fc.relnamespace "
                    "   WHERE fc.oid = con.confrelid) "
                    "END AS ref_table "
                    "FROM pg_constraint con "
                    "JOIN pg_class c ON c.oid = con.conrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord) "
                    "JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum = u.attnum "
                    "WHERE n.nspname = $1 AND c.relname = $2 "
                    "GROUP BY con.conname, con.contype, con.confrelid",
                    sch, tbl_name,
                )
                contype_map = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "u": "UNIQUE", "c": "CHECK"}
                col_constraints: dict[str, list] = {}  # column_name -> [constraint_info]
                for cr in constraint_rows:
                    ctype = contype_map.get(cr["contype"], cr["contype"])
                    for col_name in (cr["columns"] or []):
                        entry: dict = {"type": ctype}
                        if cr["ref_table"]:
                            entry["references"] = cr["ref_table"]
                        col_constraints.setdefault(col_name, []).append(entry)

                table = TableInfo(
                    database=sch,
                    name=tbl_name,
                    table_type=tr["table_type"],
                    engine=None,
                    table_comment=table_comment,
                    platform_properties=props,
                )

                # Fetch columns
                col_rows = await _safe_pg_fetch(
                    conn,
                    "SELECT column_name, data_type, udt_name, is_nullable, "
                    "ordinal_position, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_schema = $1 AND table_name = $2 "
                    "ORDER BY ordinal_position",
                    sch, tbl_name,
                )

                for cr in col_rows:
                    col_name = cr["column_name"]

                    # Column comment
                    col_comment_row = await _safe_pg_fetchrow(
                        conn,
                        "SELECT col_description(c.oid, a.attnum) AS comment "
                        "FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "JOIN pg_attribute a ON a.attrelid = c.oid "
                        "WHERE n.nspname = $1 AND c.relname = $2 AND a.attname = $3",
                        sch, tbl_name, col_name,
                    )
                    col_comment = (col_comment_row["comment"] or "") if col_comment_row else ""

                    native_type = cr["udt_name"]
                    if cr["data_type"] == "ARRAY":
                        native_type = f"{cr['udt_name']}[]"

                    # Determine PK and index status from constraints + indexes
                    col_cons = col_constraints.get(col_name, [])
                    is_pk = any(c.get("type") == "PRIMARY KEY" for c in col_cons if isinstance(c, dict))
                    is_uniq = is_pk or any(
                        c.get("type") == "UNIQUE" for c in col_cons if isinstance(c, dict)
                    )
                    is_idx = is_uniq or any(
                        f'"{col_name}"' in (ir.get("indexdef", "") if isinstance(ir, dict) else "")
                        for ir in idx_rows
                    )

                    table.columns.append(ColumnInfo(
                        name=col_name,
                        data_type=_map_pg_field_type(cr["udt_name"], cr["data_type"]),
                        native_type=native_type,
                        nullable=cr["is_nullable"] == "YES",
                        ordinal=cr["ordinal_position"],
                        column_key="",
                        column_default=cr.get("column_default"),
                        comment=col_comment,
                        is_primary_key=is_pk,
                        is_unique=is_uniq,
                        is_indexed=is_idx,
                    ))

                    # Column-level properties
                    col_props: dict = {}
                    if cr.get("column_default") is not None:
                        col_props["default"] = str(cr["column_default"])
                    if col_name in col_constraints:
                        col_props["constraints"] = col_constraints[col_name]
                    if col_props:
                        props["columns"][col_name] = col_props

                # Collect CREATE TABLE DDL (PostgreSQL)
                try:
                    # pg_dump style: reconstruct from pg_get_tabledef or columns
                    ddl_parts = [f'CREATE TABLE "{sch}"."{tbl_name}" (']
                    col_defs = []
                    for cr in col_rows:
                        col_def = f'  "{cr["column_name"]}" {cr["udt_name"]}'
                        if cr["is_nullable"] == "NO":
                            col_def += " NOT NULL"
                        if cr.get("column_default") is not None:
                            col_def += f" DEFAULT {cr['column_default']}"
                        col_defs.append(col_def)
                    # Add primary key constraint
                    for cst in constraint_rows:
                        if cst["contype"] == "p":
                            pk_cols = ", ".join(f'"{c}"' for c in cst["columns"])
                            col_defs.append(f"  CONSTRAINT {cst['conname']} PRIMARY KEY ({pk_cols})")
                    # Add foreign key constraints
                    for cst in constraint_rows:
                        if cst["contype"] == "f" and cst.get("ref_table"):
                            fk_cols = ", ".join(f'"{c}"' for c in cst["columns"])
                            col_defs.append(
                                f"  CONSTRAINT {cst['conname']} FOREIGN KEY ({fk_cols}) "
                                f"REFERENCES {cst['ref_table']}"
                            )
                    # Add unique constraints (skip if same as index)
                    for cst in constraint_rows:
                        if cst["contype"] == "u":
                            u_cols = ", ".join(f'"{c}"' for c in cst["columns"])
                            col_defs.append(
                                f"  CONSTRAINT {cst['conname']} UNIQUE ({u_cols})"
                            )
                    ddl_parts.append(",\n".join(col_defs))
                    ddl_parts.append(");")
                    props["ddl"] = "\n".join(ddl_parts)
                except Exception as e:
                    logger.info("[PostgreSQL] DDL generation skipped for %s.%s: %s", sch, tbl_name, e)

                logger.info("[PostgreSQL] %s.%s: type=%s, owner=%s, cols=%d, indexes=%d, ddl=%s",
                            sch, tbl_name, tr["table_type"],
                            tbl_props.get("owner", "?"), len(table.columns),
                            len(props["indexes"]), bool(props.get("ddl")))
                tables.append(table)

    finally:
        await conn.close()
        logger.info("[PostgreSQL] Connection closed. Total tables collected: %d", len(tables))

    return tables


async def _fetch_pg_sample_rows(
    host: str, port: int, user: str, password: str,
    database: str, schema: str, table_name: str, limit: int = 100,
) -> bytes | None:
    """Fetch sample rows from PostgreSQL and return as parquet bytes."""
    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database=database,
        )
        try:
            rows = await conn.fetch(
                f'SELECT * FROM "{schema}"."{table_name}" LIMIT $1', limit,
            )
        finally:
            await conn.close()

        if not rows:
            return None

        # Convert to dict list, all values as STRING
        if not rows:
            return None
        col_names = list(rows[0].keys())
        columns: dict[str, list] = {k: [] for k in col_names}
        for row in rows:
            for k in col_names:
                v = row[k]
                columns[k].append(str(v) if v is not None else None)

        arrow_table = pa.table(columns)
        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        return buf.getvalue()

    except Exception as e:
        logger.warning("Failed to fetch PG sample for %s.%s: %s", schema, table_name, e)
        return None


async def _fetch_sample_rows(
    host: str, port: int, user: str, password: str,
    database: str, table_name: str, limit: int = 100,
) -> bytes | None:
    """Fetch up to `limit` rows from a table and return as parquet bytes."""
    try:
        conn = await aiomysql.connect(
            host=host, port=port, user=user, password=password,
            db=database, charset="utf8mb4",
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    f"SELECT * FROM `{table_name}` LIMIT %s", (limit,)
                )
                rows = await cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return None

        # Convert to pyarrow Table → parquet bytes (all columns as STRING)
        columns: dict[str, list] = {}
        for key in rows[0].keys():
            col_values = []
            for row in rows:
                v = row[key]
                col_values.append(str(v) if v is not None else None)
            columns[key] = col_values

        arrow_table = pa.table(columns)
        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        return buf.getvalue()

    except Exception as e:
        logger.warning("Failed to fetch sample for %s.%s: %s", database, table_name, e)
        return None


async def _upload_sample_parquet(
    catalog_url: str, platform_id: str, dataset_name: str, parquet_bytes: bytes,
) -> bool:
    """Upload parquet sample to catalog server via HTTP."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{catalog_url}/api/v1/catalog/samples/upload",
                content=parquet_bytes,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Platform-Id": platform_id,
                    "X-Dataset-Name": dataset_name,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                return True
            logger.warning("Sample upload failed (%d): %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Sample upload error for %s/%s: %s", platform_id, dataset_name, e)
    return False


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def _generate_urn(platform_id: str, path: str, env: str, entity_type: str = "dataset") -> str:
    return f"{platform_id}.{path}.{env}.{entity_type}"


SUPPORTED_TYPES = {"mysql", "postgresql"}


async def sync_platform_metadata(
    session: AsyncSession,
    platform_id_str: str,
    database: str | None = None,
    catalog_url: str = "http://127.0.0.1:4600",
) -> SyncResult:
    """Sync metadata from an external platform into the catalog.

    Supports: mysql (MySQL/MariaDB), postgresql (PostgreSQL).

    Args:
        session: DB session
        platform_id_str: The platform_id string (e.g. "mysql-19d0bfe954e2cfdaa")
        database: For MySQL: database name. For PostgreSQL: schema name. Optional.
        catalog_url: Base URL of the catalog server for sample upload.

    Returns:
        SyncResult with summary statistics.
    """
    result = SyncResult(platform_id=platform_id_str)

    # 1. Resolve platform
    row = await session.execute(
        select(Platform).where(Platform.platform_id == platform_id_str)
    )
    platform = row.scalars().first()
    if not platform:
        result.errors.append(f"Platform not found: {platform_id_str}")
        return result

    if platform.type not in SUPPORTED_TYPES:
        result.errors.append(f"Sync not supported for platform type: {platform.type}")
        return result

    # 2. Load connection config
    cfg_row = await session.execute(
        select(PlatformConfiguration).where(
            PlatformConfiguration.platform_id == platform.id
        )
    )
    cfg = cfg_row.scalars().first()
    if not cfg:
        result.errors.append(f"No configuration found for platform: {platform_id_str}")
        return result

    config = json.loads(cfg.config_json)
    host = config.get("host", "localhost")
    user = config.get("username", "root")
    password = config.get("password", "")

    # 3. Read metadata from the remote DB
    is_pg = platform.type == "postgresql"
    default_port = 5432 if is_pg else 3306
    port = int(config.get("port", default_port))
    logger.info("Syncing metadata from %s:%d (platform=%s, type=%s)",
                host, port, platform_id_str, platform.type)
    try:
        if is_pg:
            pg_database = config.get("database", "postgres")
            tables = await _read_pg_metadata(host, port, user, password, pg_database, database)
        else:
            tables = await _read_mysql_metadata(host, port, user, password, database)
    except Exception as e:
        result.errors.append(f"Connection failed: {e}")
        return result

    result.databases_scanned = sorted({t.database for t in tables})
    result.tables_total = len(tables)
    logger.info("Found %d table(s) across database(s): %s",
                len(tables), result.databases_scanned)

    # 4. Upsert datasets + schema fields
    for table in tables:
        path = f"{table.database}.{table.name}"
        urn = _generate_urn(platform_id_str, path, "PROD")
        qualified_name = f"{platform_id_str}.{path}"

        # Check if dataset already exists (by new URN or by platform + name)
        ds_row = await session.execute(
            select(Dataset).where(Dataset.urn == urn)
        )
        dataset = ds_row.scalars().first()
        if not dataset:
            # Fallback: find by platform_id + name (for migrating old URN format)
            ds_row = await session.execute(
                select(Dataset).where(
                    Dataset.platform_id == platform.id,
                    Dataset.name == f"{table.database}.{table.name}",
                )
            )
            dataset = ds_row.scalars().first()

        table_type = "VIEW" if "VIEW" in table.table_type.upper() else "TABLE"

        if dataset:
            # Update existing (also restore if previously removed)
            logger.info("Sync upsert [UPDATE]: %s (id=%d)", urn, dataset.id)
            dataset.urn = urn
            dataset.name = f"{table.database}.{table.name}"
            dataset.qualified_name = qualified_name
            dataset.description = table.table_comment or dataset.description
            dataset.table_type = table_type
            dataset.platform_properties = json.dumps(
                table.platform_properties, ensure_ascii=False) if table.platform_properties else None
            dataset.is_synced = "true"
            dataset.status = "active"
            result.tables_updated += 1
        else:
            # Create new
            dataset = Dataset(
                urn=urn,
                name=f"{table.database}.{table.name}",
                platform_id=platform.id,
                description=table.table_comment or None,
                origin="PROD",
                qualified_name=qualified_name,
                table_type=table_type,
                platform_properties=json.dumps(
                    table.platform_properties, ensure_ascii=False) if table.platform_properties else None,
                is_synced="true",
                status="active",
            )
            session.add(dataset)
            await session.flush()
            logger.info("Sync upsert [CREATE]: %s (id=%d)", urn, dataset.id)
            result.tables_created += 1

        # Sync schema fields: detect changes, save snapshot, then delete and re-insert
        existing_fields_result = await session.execute(
            select(DatasetSchema).where(DatasetSchema.dataset_id == dataset.id)
        )
        existing_fields = existing_fields_result.scalars().all()

        # Save schema snapshot if changes detected
        from app.catalog.service import save_schema_snapshot
        await save_schema_snapshot(
            session, dataset.id, existing_fields, table.columns, from_sync=True,
        )

        for f in existing_fields:
            await session.delete(f)

        for col in table.columns:
            session.add(DatasetSchema(
                dataset_id=dataset.id,
                field_path=col.name,
                field_type=col.data_type,
                native_type=col.native_type,
                description=col.comment or None,
                nullable="true" if col.nullable else "false",
                is_primary_key="true" if col.is_primary_key else "false",
                is_unique="true" if col.is_unique else "false",
                is_indexed="true" if col.is_indexed else "false",
                ordinal=col.ordinal,
            ))

    # 4b. Mark datasets as removed if they no longer exist in the source
    #     Only compare within the scanned database(s), not all datasets of this platform
    synced_urns = {
        _generate_urn(platform_id_str, f"{t.database}.{t.name}", "PROD")
        for t in tables
    }
    scanned_db_prefixes = [
        f"{platform_id_str}.{db}." for db in result.databases_scanned
    ]
    existing_rows = await session.execute(
        select(Dataset).where(
            Dataset.platform_id == platform.id,
            Dataset.status != "removed",
        )
    )
    for ds in existing_rows.scalars().all():
        # Only check datasets that belong to the scanned database(s)
        belongs_to_scanned_db = any(
            ds.urn.startswith(prefix) for prefix in scanned_db_prefixes
        )
        if belongs_to_scanned_db and ds.urn not in synced_urns:
            ds.status = "removed"
            result.tables_removed += 1
            logger.info("Marked as removed: %s", ds.urn)

    await session.commit()
    logger.info("Sync complete: created=%d, updated=%d, removed=%d, total=%d",
                result.tables_created, result.tables_updated,
                result.tables_removed, result.tables_total)

    # 5. Fetch sample data and upload as parquet
    logger.info("Collecting sample data for %d table(s)...", len(tables))
    for table in tables:
        # Skip views — sample data from base tables only
        if "VIEW" in table.table_type.upper():
            continue

        dataset_name = f"{table.database}.{table.name}"
        if is_pg:
            pg_database = config.get("database", "postgres")
            parquet_bytes = await _fetch_pg_sample_rows(
                host, port, user, password, pg_database, table.database, table.name,
            )
        else:
            parquet_bytes = await _fetch_sample_rows(
                host, port, user, password, table.database, table.name,
            )
        if parquet_bytes:
            logger.info("Uploading sample: %s/%s (%d bytes)",
                        platform_id_str, dataset_name, len(parquet_bytes))
            ok = await _upload_sample_parquet(
                catalog_url, platform_id_str, dataset_name, parquet_bytes,
            )
            if ok:
                result.samples_uploaded += 1
        else:
            logger.info("No sample data for %s/%s (empty table or error)",
                        platform_id_str, dataset_name)

    logger.info("Sample upload complete: %d file(s)", result.samples_uploaded)
    return result
