"""PostgreSQL engine adapter."""

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

POSTGRESQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL",
    "CROSS", "NATURAL", "ON", "USING", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
    "OFFSET", "UNION", "UNION ALL", "INTERSECT", "EXCEPT", "WITH", "RECURSIVE",
    "AS", "INSERT INTO", "VALUES", "ON CONFLICT", "DO NOTHING", "DO UPDATE",
    "CREATE TABLE", "CREATE VIEW", "CREATE INDEX", "CREATE SCHEMA",
    "CREATE FUNCTION", "CREATE TRIGGER", "CREATE TYPE", "CREATE EXTENSION",
    "DROP TABLE", "DROP VIEW", "DROP INDEX", "DROP SCHEMA", "DROP FUNCTION",
    "ALTER TABLE", "ALTER INDEX", "ALTER SCHEMA", "ADD COLUMN", "DROP COLUMN",
    "RENAME TO", "SET DEFAULT", "DELETE FROM", "UPDATE", "SET", "RETURNING",
    "CASE", "WHEN", "THEN", "ELSE", "END", "AND", "OR", "NOT", "IN", "EXISTS",
    "BETWEEN", "LIKE", "ILIKE", "SIMILAR TO", "IS NULL", "IS NOT NULL",
    "IS DISTINCT FROM", "DISTINCT", "ALL", "ANY", "SOME", "ASC", "DESC",
    "NULLS FIRST", "NULLS LAST", "FETCH FIRST", "ROWS ONLY", "FOR UPDATE",
    "FOR SHARE", "LATERAL", "EXPLAIN", "EXPLAIN ANALYZE", "VACUUM", "ANALYZE",
    "COPY", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "GRANT", "REVOKE",
    "LISTEN", "NOTIFY", "PREPARE", "EXECUTE", "DEALLOCATE",
    "PARTITION BY", "RANGE", "LIST", "HASH", "GENERATED ALWAYS AS",
    "MATERIALIZED VIEW", "REFRESH MATERIALIZED VIEW", "CONCURRENTLY",
    "TABLESAMPLE", "BERNOULLI", "SYSTEM",
]

POSTGRESQL_FUNCTIONS = [
    # Aggregate
    "count", "sum", "avg", "min", "max", "array_agg", "string_agg",
    "bool_and", "bool_or", "every", "json_agg", "jsonb_agg",
    "json_object_agg", "jsonb_object_agg", "xmlagg",
    "corr", "covar_pop", "covar_samp", "regr_avgx", "regr_avgy",
    "regr_count", "regr_intercept", "regr_r2", "regr_slope",
    "regr_sxx", "regr_sxy", "regr_syy",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp",
    "percentile_cont", "percentile_disc", "mode",
    # String
    "concat", "concat_ws", "length", "char_length", "lower", "upper",
    "initcap", "trim", "ltrim", "rtrim", "lpad", "rpad",
    "replace", "reverse", "split_part", "strpos", "position",
    "substr", "substring", "left", "right", "repeat", "translate",
    "encode", "decode", "md5", "chr", "ascii", "format",
    "regexp_match", "regexp_matches", "regexp_replace", "regexp_split_to_array",
    "regexp_split_to_table", "regexp_count", "regexp_instr", "regexp_like",
    "starts_with", "string_to_array", "array_to_string",
    "quote_ident", "quote_literal", "quote_nullable",
    # Date/Time
    "now", "current_date", "current_time", "current_timestamp",
    "clock_timestamp", "statement_timestamp", "transaction_timestamp",
    "date_trunc", "date_part", "extract", "age",
    "make_date", "make_time", "make_timestamp", "make_timestamptz",
    "make_interval", "to_timestamp", "to_date", "to_char",
    "generate_series", "date_bin",
    # Math
    "abs", "ceil", "ceiling", "floor", "round", "trunc", "mod", "power",
    "sqrt", "cbrt", "exp", "ln", "log", "log10", "sign", "pi",
    "degrees", "radians", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "random", "setseed", "greatest", "least", "width_bucket",
    "factorial", "gcd", "lcm", "div",
    # JSON/JSONB
    "json_build_object", "json_build_array", "jsonb_build_object",
    "jsonb_build_array", "json_extract_path", "json_extract_path_text",
    "jsonb_extract_path", "jsonb_extract_path_text",
    "json_array_length", "jsonb_array_length", "json_each", "jsonb_each",
    "json_each_text", "jsonb_each_text", "json_object_keys", "jsonb_object_keys",
    "json_populate_record", "jsonb_populate_record",
    "json_to_record", "jsonb_to_record", "jsonb_set", "jsonb_insert",
    "jsonb_pretty", "jsonb_typeof", "jsonb_path_query",
    "jsonb_path_query_array", "jsonb_path_exists", "to_json", "to_jsonb",
    # Array
    "array_append", "array_cat", "array_dims", "array_fill",
    "array_length", "array_lower", "array_upper", "array_ndims",
    "array_position", "array_positions", "array_prepend",
    "array_remove", "array_replace", "cardinality", "unnest",
    # Conditional
    "coalesce", "nullif", "greatest", "least",
    # Type cast
    "cast", "pg_typeof",
    # Window
    "row_number", "rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "lag", "lead", "first_value", "last_value", "nth_value",
    # System
    "pg_table_size", "pg_total_relation_size", "pg_database_size",
    "pg_size_pretty", "pg_relation_filepath", "current_database",
    "current_schema", "current_user", "session_user", "version",
]

POSTGRESQL_TYPES = [
    "BOOLEAN", "BOOL", "SMALLINT", "INT2", "INTEGER", "INT", "INT4",
    "BIGINT", "INT8", "REAL", "FLOAT4", "DOUBLE PRECISION", "FLOAT8",
    "NUMERIC", "DECIMAL", "MONEY",
    "CHAR", "CHARACTER", "VARCHAR", "CHARACTER VARYING", "TEXT",
    "BYTEA", "BIT", "BIT VARYING",
    "DATE", "TIME", "TIME WITH TIME ZONE", "TIMETZ",
    "TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ",
    "INTERVAL",
    "BOOLEAN", "POINT", "LINE", "LSEG", "BOX", "PATH", "POLYGON", "CIRCLE",
    "CIDR", "INET", "MACADDR", "MACADDR8",
    "JSON", "JSONB", "XML",
    "UUID", "SERIAL", "BIGSERIAL", "SMALLSERIAL",
    "ARRAY", "INT4RANGE", "INT8RANGE", "NUMRANGE", "TSRANGE", "TSTZRANGE",
    "DATERANGE", "TSVECTOR", "TSQUERY", "OID",
]


def _serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, bytes):
        return val.hex()
    return str(val)


class PostgreSQLAdapter(BaseAdapter):
    """Adapter for PostgreSQL."""

    def _dsn(self) -> str:
        db = self.config.database or "postgres"
        return (
            f"postgresql://{self.config.username}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{db}"
        )

    async def test_connection(self) -> tuple[bool, str, float]:
        try:
            import asyncpg  # type: ignore[import-untyped]
        except ImportError:
            return False, "asyncpg package not installed (pip install asyncpg)", 0.0

        start = time.monotonic()
        try:
            conn = await asyncpg.connect(dsn=self._dsn())
            await conn.fetchval("SELECT 1")
            await conn.close()
            elapsed = (time.monotonic() - start) * 1000
            return True, "Connection successful", elapsed
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return False, str(e), elapsed

    async def execute(
        self, sql: str, max_rows: int = 1000, timeout_seconds: int = 300
    ) -> QueryResult:
        import asyncpg  # type: ignore[import-untyped]

        start = time.monotonic()
        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            pid = conn.get_server_pid()
            stmt = await conn.prepare(sql)
            records = await stmt.fetch(max_rows, timeout=timeout_seconds)
            columns = [
                {"name": attr.name, "type": attr.type.name if hasattr(attr.type, "name") else str(attr.type)}
                for attr in stmt.get_attributes()
            ]
            rows = [[_serialize_value(v) for v in record.values()] for record in records]
            elapsed = int((time.monotonic() - start) * 1000)
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed_ms=elapsed,
                engine_query_id=str(pid),
            )
        finally:
            await conn.close()

    async def cancel(self, engine_query_id: str) -> bool:
        import asyncpg  # type: ignore[import-untyped]

        try:
            conn = await asyncpg.connect(dsn=self._dsn())
            result = await conn.fetchval(
                "SELECT pg_cancel_backend($1)", int(engine_query_id)
            )
            await conn.close()
            return bool(result)
        except Exception as e:
            logger.warning("PostgreSQL cancel failed for PID %s: %s", engine_query_id, e)
            return False

    async def explain(self, sql: str, analyze: bool = False) -> str:
        import asyncpg  # type: ignore[import-untyped]

        prefix = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)" if analyze else "EXPLAIN (FORMAT TEXT)"
        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            rows = await conn.fetch(f"{prefix} {sql}")
            return "\n".join(row[0] for row in rows)
        finally:
            await conn.close()

    async def get_catalogs(self) -> list[MetadataCatalog]:
        import asyncpg  # type: ignore[import-untyped]

        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            rows = await conn.fetch(
                "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
            )
            return [MetadataCatalog(name=row["datname"]) for row in rows]
        finally:
            await conn.close()

    async def get_schemas(self, catalog: str = "") -> list[MetadataSchema]:
        import asyncpg  # type: ignore[import-untyped]

        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            rows = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
                "ORDER BY schema_name"
            )
            return [MetadataSchema(name=row["schema_name"], catalog=catalog) for row in rows]
        finally:
            await conn.close()

    async def get_tables(self, catalog: str = "", schema: str = "") -> list[MetadataTable]:
        import asyncpg  # type: ignore[import-untyped]

        schema = schema or "public"
        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            rows = await conn.fetch(
                "SELECT table_name, table_type FROM information_schema.tables "
                "WHERE table_schema = $1 ORDER BY table_name",
                schema,
            )
            return [
                MetadataTable(
                    name=row["table_name"],
                    table_type=row["table_type"],
                    catalog=catalog,
                    schema_name=schema,
                )
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_columns(
        self, table: str, catalog: str = "", schema: str = ""
    ) -> list[MetadataColumn]:
        import asyncpg  # type: ignore[import-untyped]

        schema = schema or "public"
        conn = await asyncpg.connect(dsn=self._dsn())
        try:
            rows = await conn.fetch(
                "SELECT column_name, data_type, is_nullable, ordinal_position, "
                "COALESCE(col_description((table_schema || '.' || table_name)::regclass, "
                "ordinal_position), '') AS comment "
                "FROM information_schema.columns "
                "WHERE table_schema = $1 AND table_name = $2 "
                "ORDER BY ordinal_position",
                schema,
                table,
            )
            return [
                MetadataColumn(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                    comment=row["comment"],
                    ordinal_position=row["ordinal_position"],
                )
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_table_preview(
        self, table: str, catalog: str = "", schema: str = "", limit: int = 100
    ) -> QueryResult:
        schema = schema or "public"
        return await self.execute(
            f'SELECT * FROM "{schema}"."{table}" LIMIT {limit}', max_rows=limit
        )

    def get_keywords(self) -> list[str]:
        return POSTGRESQL_KEYWORDS

    def get_functions(self) -> list[str]:
        return POSTGRESQL_FUNCTIONS

    def get_data_types(self) -> list[str]:
        return POSTGRESQL_TYPES
