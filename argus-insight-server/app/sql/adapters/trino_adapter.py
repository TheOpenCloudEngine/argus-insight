"""Trino SQL engine adapter."""

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

# ---------------------------------------------------------------------------
# Trino-specific SQL keywords / functions / types for autocomplete
# ---------------------------------------------------------------------------

TRINO_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL",
    "CROSS", "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "UNION",
    "UNION ALL", "INTERSECT", "EXCEPT", "WITH", "AS", "INSERT INTO", "VALUES",
    "CREATE TABLE", "CREATE VIEW", "CREATE SCHEMA", "DROP TABLE", "DROP VIEW",
    "ALTER TABLE", "DELETE FROM", "UPDATE", "SET", "CASE", "WHEN", "THEN", "ELSE",
    "END", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "IS NULL",
    "IS NOT NULL", "DISTINCT", "ALL", "ANY", "SOME", "ASC", "DESC", "NULLS FIRST",
    "NULLS LAST", "FETCH FIRST", "ROWS ONLY", "TABLESAMPLE", "UNNEST", "LATERAL",
    "EXPLAIN", "EXPLAIN ANALYZE", "SHOW CATALOGS", "SHOW SCHEMAS", "SHOW TABLES",
    "SHOW COLUMNS", "SHOW FUNCTIONS", "SHOW SESSION", "DESCRIBE", "USE",
    "PREPARE", "EXECUTE", "DEALLOCATE PREPARE", "GRANT", "REVOKE",
]

TRINO_FUNCTIONS = [
    # Aggregate
    "count", "sum", "avg", "min", "max", "arbitrary", "array_agg", "map_agg",
    "approx_distinct", "approx_percentile", "approx_most_frequent",
    "bool_and", "bool_or", "checksum", "corr", "covar_pop", "covar_samp",
    "every", "histogram", "kurtosis", "map_union", "multimap_agg",
    "numeric_histogram", "regr_intercept", "regr_slope", "skewness",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp",
    # String
    "concat", "length", "lower", "upper", "trim", "ltrim", "rtrim", "lpad", "rpad",
    "replace", "reverse", "split", "split_part", "strpos", "substr", "substring",
    "chr", "codepoint", "format", "from_utf8", "to_utf8", "normalize",
    "levenshtein_distance", "hamming_distance", "soundex", "translate",
    "word_stem", "starts_with", "ends_with", "regexp_extract", "regexp_like",
    "regexp_replace", "regexp_split", "regexp_count", "regexp_position",
    # Date/Time
    "current_date", "current_time", "current_timestamp", "localtime",
    "localtimestamp", "now", "date_trunc", "date_add", "date_diff",
    "date_format", "date_parse", "format_datetime", "parse_datetime",
    "from_unixtime", "to_unixtime", "from_iso8601_timestamp",
    "from_iso8601_date", "to_iso8601", "at_timezone",
    "year", "quarter", "month", "week", "day", "day_of_week", "day_of_year",
    "hour", "minute", "second", "millisecond", "timezone_hour", "timezone_minute",
    # Math
    "abs", "ceil", "ceiling", "floor", "round", "truncate", "mod", "power",
    "sqrt", "cbrt", "exp", "ln", "log2", "log10", "sign", "pi", "e",
    "degrees", "radians", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "rand", "random", "greatest", "least", "infinity", "nan", "is_finite",
    "is_infinite", "is_nan", "from_base", "to_base", "width_bucket",
    # JSON
    "json_extract", "json_extract_scalar", "json_format", "json_parse",
    "json_size", "json_array_contains", "json_array_get", "json_array_length",
    "is_json_scalar", "json_query", "json_value", "json_exists",
    # Array
    "array_distinct", "array_intersect", "array_union", "array_except",
    "array_join", "array_max", "array_min", "array_position", "array_remove",
    "array_sort", "cardinality", "contains", "element_at", "flatten",
    "repeat", "sequence", "shuffle", "slice", "transform", "zip",
    # Conditional
    "if", "coalesce", "nullif", "try", "try_cast",
    # Conversion
    "cast", "typeof", "format_number",
    # Window
    "row_number", "rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "lag", "lead", "first_value", "last_value", "nth_value",
]

TRINO_TYPES = [
    "BOOLEAN", "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "REAL", "DOUBLE",
    "DECIMAL", "VARCHAR", "CHAR", "VARBINARY", "JSON", "DATE", "TIME",
    "TIME WITH TIME ZONE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE",
    "INTERVAL YEAR TO MONTH", "INTERVAL DAY TO SECOND",
    "ARRAY", "MAP", "ROW", "IPADDRESS", "UUID", "HYPERLOGLOG",
    "P4HYPERLOGLOG", "QDIGEST", "TDIGEST",
]


def _serialize_value(val: Any) -> Any:
    """Convert non-JSON-serializable values to strings."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, bytes):
        return val.hex()
    return str(val)


class TrinoAdapter(BaseAdapter):
    """Adapter for Trino query engine."""

    def _get_connection_kwargs(self) -> dict:
        kwargs: dict[str, Any] = {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.username or "argus",
        }
        catalog = self.config.extra.get("catalog") or self.config.database
        if catalog:
            kwargs["catalog"] = catalog
        schema = self.config.extra.get("schema")
        if schema:
            kwargs["schema"] = schema
        return kwargs

    async def test_connection(self) -> tuple[bool, str, float]:
        try:
            from trino.dbapi import connect  # type: ignore[import-untyped]
        except ImportError:
            return False, "trino package not installed (pip install trino)", 0.0

        start = time.monotonic()
        try:
            conn = connect(**self._get_connection_kwargs())
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()
            elapsed = (time.monotonic() - start) * 1000
            return True, "Connection successful", elapsed
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return False, str(e), elapsed

    async def execute(
        self, sql: str, max_rows: int = 1000, timeout_seconds: int = 300
    ) -> QueryResult:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        start = time.monotonic()
        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            cur.execute(sql)
            columns = [
                {"name": desc[0], "type": desc[1] or "VARCHAR"}
                for desc in (cur.description or [])
            ]
            rows_raw = cur.fetchmany(max_rows)
            rows = [[_serialize_value(v) for v in row] for row in rows_raw]
            elapsed = int((time.monotonic() - start) * 1000)
            engine_qid = getattr(cur, "stats", {}).get("queryId", None) if hasattr(cur, "stats") else None
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed_ms=elapsed,
                engine_query_id=engine_qid,
            )
        finally:
            conn.close()

    async def cancel(self, engine_query_id: str) -> bool:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        try:
            conn = connect(**self._get_connection_kwargs())
            cur = conn.cursor()
            cur.execute(f"CALL system.runtime.kill_query(query_id => '{engine_query_id}', message => 'Cancelled by user')")
            cur.fetchall()
            conn.close()
            return True
        except Exception as e:
            logger.warning("Trino cancel failed for %s: %s", engine_query_id, e)
            return False

    async def explain(self, sql: str, analyze: bool = False) -> str:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            cur.execute(f"{prefix} {sql}")
            rows = cur.fetchall()
            return "\n".join(str(row[0]) for row in rows)
        finally:
            conn.close()

    async def get_catalogs(self) -> list[MetadataCatalog]:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            cur.execute("SHOW CATALOGS")
            return [MetadataCatalog(name=row[0]) for row in cur.fetchall()]
        finally:
            conn.close()

    async def get_schemas(self, catalog: str = "") -> list[MetadataSchema]:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            sql = f'SHOW SCHEMAS FROM "{catalog}"' if catalog else "SHOW SCHEMAS"
            cur.execute(sql)
            return [MetadataSchema(name=row[0], catalog=catalog) for row in cur.fetchall()]
        finally:
            conn.close()

    async def get_tables(self, catalog: str = "", schema: str = "") -> list[MetadataTable]:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            if catalog and schema:
                cur.execute(
                    "SELECT table_name, table_type FROM "
                    f'"{catalog}".information_schema.tables '
                    f"WHERE table_schema = '{schema}'"
                )
            elif schema:
                cur.execute(
                    "SELECT table_name, table_type FROM information_schema.tables "
                    f"WHERE table_schema = '{schema}'"
                )
            else:
                cur.execute("SHOW TABLES")
                return [
                    MetadataTable(name=row[0], catalog=catalog, schema_name=schema)
                    for row in cur.fetchall()
                ]
            return [
                MetadataTable(
                    name=row[0], table_type=row[1], catalog=catalog, schema_name=schema
                )
                for row in cur.fetchall()
            ]
        finally:
            conn.close()

    async def get_columns(
        self, table: str, catalog: str = "", schema: str = ""
    ) -> list[MetadataColumn]:
        from trino.dbapi import connect  # type: ignore[import-untyped]

        conn = connect(**self._get_connection_kwargs())
        try:
            cur = conn.cursor()
            fqn = f'"{catalog}"."{schema}"."{table}"' if catalog and schema else f'"{table}"'
            cur.execute(f"DESCRIBE {fqn}")
            cols = []
            for i, row in enumerate(cur.fetchall()):
                cols.append(MetadataColumn(
                    name=row[0],
                    data_type=row[1],
                    nullable="NOT NULL" not in str(row[2] or ""),
                    comment=str(row[3] or ""),
                    ordinal_position=i + 1,
                ))
            return cols
        finally:
            conn.close()

    async def get_table_preview(
        self, table: str, catalog: str = "", schema: str = "", limit: int = 100
    ) -> QueryResult:
        fqn = f'"{catalog}"."{schema}"."{table}"' if catalog and schema else f'"{table}"'
        return await self.execute(f"SELECT * FROM {fqn} LIMIT {limit}", max_rows=limit)

    def get_keywords(self) -> list[str]:
        return TRINO_KEYWORDS

    def get_functions(self) -> list[str]:
        return TRINO_FUNCTIONS

    def get_data_types(self) -> list[str]:
        return TRINO_TYPES
