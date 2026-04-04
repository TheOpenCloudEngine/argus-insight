"""StarRocks engine adapter.

StarRocks uses MySQL-compatible protocol, so we use PyMySQL (via aiomysql).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.sql.adapters.base import (
    BaseAdapter,
    ConnectionConfig,
    MetadataCatalog,
    MetadataColumn,
    MetadataSchema,
    MetadataTable,
    QueryResult,
)

logger = logging.getLogger(__name__)

STARROCKS_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL",
    "CROSS", "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "UNION",
    "UNION ALL", "INTERSECT", "EXCEPT", "WITH", "AS", "INSERT INTO", "VALUES",
    "INSERT OVERWRITE", "CREATE TABLE", "CREATE VIEW", "CREATE MATERIALIZED VIEW",
    "CREATE DATABASE", "CREATE INDEX", "CREATE EXTERNAL TABLE", "CREATE CATALOG",
    "DROP TABLE", "DROP VIEW", "DROP DATABASE", "DROP MATERIALIZED VIEW",
    "ALTER TABLE", "ALTER VIEW", "ALTER DATABASE", "ALTER MATERIALIZED VIEW",
    "DELETE FROM", "UPDATE", "SET", "CASE", "WHEN", "THEN", "ELSE", "END",
    "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "REGEXP", "RLIKE",
    "IS NULL", "IS NOT NULL", "DISTINCT", "ALL", "ASC", "DESC",
    "EXPLAIN", "DESCRIBE", "SHOW DATABASES", "SHOW TABLES", "SHOW COLUMNS",
    "SHOW CREATE TABLE", "SHOW PARTITIONS", "SHOW TABLET", "SHOW PROC",
    "SHOW BACKENDS", "SHOW FRONTENDS", "SHOW BROKER", "SHOW LOAD",
    "SHOW EXPORT", "SHOW DATA", "SHOW CATALOGS", "SHOW RESOURCES",
    "SUBMIT TASK", "ADMIN SHOW CONFIG", "ADMIN SET CONFIG",
    "LOAD", "BROKER LOAD", "ROUTINE LOAD", "STREAM LOAD",
    "DISTRIBUTED BY", "HASH", "RANDOM", "BUCKETS",
    "PARTITION BY", "RANGE", "LIST", "PROPERTIES",
    "DUPLICATE KEY", "AGGREGATE KEY", "UNIQUE KEY", "PRIMARY KEY",
    "ENGINE", "OLAP", "MYSQL", "ELASTICSEARCH", "HIVE", "ICEBERG", "HUDI",
]

STARROCKS_FUNCTIONS = [
    # Aggregate
    "count", "sum", "avg", "min", "max", "group_concat", "array_agg",
    "bitmap_union", "bitmap_union_count", "bitmap_intersect",
    "hll_union_agg", "hll_raw_agg", "hll_cardinality",
    "approx_count_distinct", "multi_distinct_count",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp",
    "percentile_approx", "percentile_cont", "percentile_disc",
    "corr", "covar_pop", "covar_samp",
    "retention", "window_funnel",
    # String
    "concat", "concat_ws", "length", "char_length", "lower", "upper",
    "trim", "ltrim", "rtrim", "lpad", "rpad", "replace", "reverse",
    "split", "split_part", "substr", "substring", "instr", "locate",
    "repeat", "space", "left", "right", "regexp_extract", "regexp_replace",
    "parse_url", "money_format", "hex", "unhex", "sm3", "md5",
    "starts_with", "ends_with", "strleft", "strright",
    # Date/Time
    "now", "curdate", "curtime", "current_date", "current_time",
    "current_timestamp", "unix_timestamp", "from_unixtime",
    "date_format", "str_to_date", "date_add", "date_sub", "datediff",
    "timediff", "timestampdiff", "timestampadd",
    "date_trunc", "date_floor", "date_ceil",
    "year", "quarter", "month", "week", "day", "dayofweek", "dayofyear",
    "hour", "minute", "second", "microsecond",
    "makedate", "maketime", "to_date", "to_days", "from_days",
    "last_day", "next_day", "previous_day", "months_between",
    # Math
    "abs", "ceil", "ceiling", "floor", "round", "truncate", "mod", "power",
    "sqrt", "cbrt", "exp", "ln", "log", "log2", "log10", "sign", "pi", "e",
    "degrees", "radians", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "rand", "random", "greatest", "least", "pmod", "positive", "negative",
    "conv", "bin", "hex",
    # JSON
    "parse_json", "json_query", "json_value", "json_exists",
    "json_each", "json_length", "json_keys", "json_object",
    "json_array", "get_json_double", "get_json_int", "get_json_string",
    "json_extract",
    # Bitmap
    "bitmap_count", "bitmap_empty", "bitmap_hash", "bitmap_or",
    "bitmap_and", "bitmap_xor", "bitmap_not", "bitmap_contains",
    "bitmap_to_string", "bitmap_from_string", "to_bitmap",
    # Array
    "array_append", "array_contains", "array_length", "array_position",
    "array_remove", "array_sort", "array_distinct", "array_intersect",
    "array_union", "array_except", "array_slice", "array_join",
    "array_map", "array_filter", "cardinality", "element_at",
    # Conditional
    "if", "ifnull", "nullif", "coalesce", "case_when",
    # Conversion
    "cast", "convert",
    # Window
    "row_number", "rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "lag", "lead", "first_value", "last_value", "nth_value",
]

STARROCKS_TYPES = [
    "BOOLEAN", "TINYINT", "SMALLINT", "INT", "INTEGER", "BIGINT", "LARGEINT",
    "FLOAT", "DOUBLE", "DECIMAL", "DECIMALV3",
    "CHAR", "VARCHAR", "STRING", "BINARY", "VARBINARY",
    "DATE", "DATETIME", "TIMESTAMP",
    "JSON", "ARRAY", "MAP", "STRUCT",
    "BITMAP", "HLL", "PERCENTILE",
]


def _serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


class StarRocksAdapter(BaseAdapter):
    """Adapter for StarRocks (MySQL protocol)."""

    def _conn_kwargs(self) -> dict:
        return {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.username or "root",
            "password": self.config.password or "",
            "db": self.config.database or "",
        }

    async def test_connection(self) -> tuple[bool, str, float]:
        try:
            import aiomysql  # type: ignore[import-untyped]
        except ImportError:
            return False, "aiomysql package not installed (pip install aiomysql)", 0.0

        start = time.monotonic()
        try:
            conn = await aiomysql.connect(**self._conn_kwargs())
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
            conn.close()
            elapsed = (time.monotonic() - start) * 1000
            return True, "Connection successful", elapsed
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return False, str(e), elapsed

    async def execute(
        self, sql: str, max_rows: int = 1000, timeout_seconds: int = 300
    ) -> QueryResult:
        import aiomysql  # type: ignore[import-untyped]

        start = time.monotonic()
        conn = await aiomysql.connect(**self._conn_kwargs(), connect_timeout=timeout_seconds)
        try:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                columns = [
                    {"name": desc[0], "type": _mysql_type_name(desc[1])}
                    for desc in (cur.description or [])
                ]
                rows_raw = await cur.fetchmany(max_rows)
                rows = [[_serialize_value(v) for v in row] for row in rows_raw]
                elapsed = int((time.monotonic() - start) * 1000)
                conn_id = conn.thread_id()
                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    elapsed_ms=elapsed,
                    engine_query_id=str(conn_id) if conn_id else None,
                )
        finally:
            conn.close()

    async def cancel(self, engine_query_id: str) -> bool:
        import aiomysql  # type: ignore[import-untyped]

        try:
            conn = await aiomysql.connect(**self._conn_kwargs())
            async with conn.cursor() as cur:
                await cur.execute(f"KILL QUERY {engine_query_id}")
            conn.close()
            return True
        except Exception as e:
            logger.warning("StarRocks cancel failed for %s: %s", engine_query_id, e)
            return False

    async def explain(self, sql: str, analyze: bool = False) -> str:
        import aiomysql  # type: ignore[import-untyped]

        prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
        conn = await aiomysql.connect(**self._conn_kwargs())
        try:
            async with conn.cursor() as cur:
                await cur.execute(f"{prefix} {sql}")
                rows = await cur.fetchall()
                return "\n".join(str(row[0]) if len(row) == 1 else str(row) for row in rows)
        finally:
            conn.close()

    async def get_catalogs(self) -> list[MetadataCatalog]:
        """MariaDB/MySQL has no catalog concept. Return empty so UI skips to schemas."""
        return []

    async def get_schemas(self, catalog: str = "") -> list[MetadataSchema]:
        import aiomysql  # type: ignore[import-untyped]

        conn = await aiomysql.connect(**self._conn_kwargs())
        try:
            async with conn.cursor() as cur:
                await cur.execute("SHOW DATABASES")
                rows = await cur.fetchall()
                return [MetadataSchema(name=row[0], catalog=catalog) for row in rows]
        finally:
            conn.close()

    async def get_tables(self, catalog: str = "", schema: str = "") -> list[MetadataTable]:
        import aiomysql  # type: ignore[import-untyped]

        conn = await aiomysql.connect(**self._conn_kwargs())
        try:
            async with conn.cursor() as cur:
                if schema:
                    await cur.execute(
                        "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.tables "
                        "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
                        (schema,),
                    )
                    rows = await cur.fetchall()
                    return [
                        MetadataTable(
                            name=row[0], table_type=row[1],
                            catalog=catalog, schema_name=schema,
                        )
                        for row in rows
                    ]
                else:
                    await cur.execute("SHOW TABLES")
                    rows = await cur.fetchall()
                    return [
                        MetadataTable(name=row[0], catalog=catalog, schema_name=schema)
                        for row in rows
                    ]
        finally:
            conn.close()

    async def get_columns(
        self, table: str, catalog: str = "", schema: str = ""
    ) -> list[MetadataColumn]:
        import aiomysql  # type: ignore[import-untyped]

        conn = await aiomysql.connect(**self._conn_kwargs())
        try:
            async with conn.cursor() as cur:
                if schema:
                    await cur.execute(
                        "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, "
                        "ORDINAL_POSITION, COLUMN_COMMENT "
                        "FROM information_schema.columns "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "ORDER BY ORDINAL_POSITION",
                        (schema, table),
                    )
                else:
                    await cur.execute(f"DESCRIBE `{table}`")
                    rows = await cur.fetchall()
                    return [
                        MetadataColumn(
                            name=row[0], data_type=row[1],
                            nullable=row[2] == "YES", ordinal_position=i + 1,
                        )
                        for i, row in enumerate(rows)
                    ]
                rows = await cur.fetchall()
                return [
                    MetadataColumn(
                        name=row[0], data_type=row[1],
                        nullable=row[2] == "YES",
                        ordinal_position=row[3],
                        comment=row[4] or "",
                    )
                    for row in rows
                ]
        finally:
            conn.close()

    async def get_table_preview(
        self, table: str, catalog: str = "", schema: str = "", limit: int = 100
    ) -> QueryResult:
        fqn = f"`{schema}`.`{table}`" if schema else f"`{table}`"
        return await self.execute(f"SELECT * FROM {fqn} LIMIT {limit}", max_rows=limit)

    def get_keywords(self) -> list[str]:
        return STARROCKS_KEYWORDS

    def get_functions(self) -> list[str]:
        return STARROCKS_FUNCTIONS

    def get_data_types(self) -> list[str]:
        return STARROCKS_TYPES


# MySQL field type constants → human-readable names
_MYSQL_TYPE_MAP = {
    0: "DECIMAL", 1: "TINYINT", 2: "SMALLINT", 3: "INT", 4: "FLOAT",
    5: "DOUBLE", 6: "NULL", 7: "TIMESTAMP", 8: "BIGINT", 9: "MEDIUMINT",
    10: "DATE", 11: "TIME", 12: "DATETIME", 13: "YEAR", 14: "DATE",
    15: "VARCHAR", 16: "BIT", 245: "JSON", 246: "DECIMAL",
    249: "TINYBLOB", 250: "MEDIUMBLOB", 251: "LONGBLOB", 252: "BLOB",
    253: "VARCHAR", 254: "CHAR",
}


def _mysql_type_name(type_code: int | None) -> str:
    if type_code is None:
        return "VARCHAR"
    return _MYSQL_TYPE_MAP.get(type_code, "VARCHAR")
