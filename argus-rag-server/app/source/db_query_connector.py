"""Database Query connector — executes SQL on a source DB and ingests results.

Supports MySQL, PostgreSQL, Oracle, and MSSQL.
Runs a user-defined SELECT query and converts each row into an IngestItem.

Config example:
{
    "db_type": "mysql",          // mysql, mariadb, postgresql, oracle, mssql
    "host": "10.0.1.50",
    "port": 3306,
    "username": "reader",
    "password": "secret",
    "database": "sakila",         // database (mysql/pg/mssql) or service_name (oracle)
    "query": "SELECT film_id, title, description FROM film",
    "id_column": "film_id",       // external_id column (required)
    "title_column": "title",      // document title column (optional)
    "text_columns": ["title", "description"],  // columns to embed (optional, default all)
    "text_separator": " | "       // separator between values (default " | ")
}
"""

import json
import logging

from app.source.base import IngestItem, SourceConnector

logger = logging.getLogger(__name__)

SUPPORTED_DB_TYPES = {"mysql", "mariadb", "postgresql", "oracle", "mssql"}

DEFAULT_PORTS = {
    "mysql": 3306,
    "mariadb": 3306,
    "postgresql": 5432,
    "oracle": 1521,
    "mssql": 1433,
}


class DBQueryConnector(SourceConnector):
    """Execute a SQL query on a source DB and produce IngestItems."""

    def __init__(self, config: dict) -> None:
        self._db_type = config.get("db_type", "mysql").lower()
        self._host = config.get("host", "localhost")
        self._port = int(config.get("port", DEFAULT_PORTS.get(self._db_type, 3306)))
        self._username = config.get("username", "")
        self._password = config.get("password", "")
        self._database = config.get("database", "")
        self._query = config.get("query", "")
        self._id_column = config.get("id_column", "")
        self._title_column = config.get("title_column", "")
        self._text_columns = config.get("text_columns", [])
        self._text_separator = config.get("text_separator", " | ")

    async def fetch_all(self) -> list[IngestItem]:
        if not self._query:
            raise ValueError("No SQL query configured")
        if not self._id_column:
            raise ValueError("id_column is required")
        self._validate_select(self._query)

        rows, columns = await self._execute_query()
        items = self._rows_to_items(rows, columns)
        logger.info(
            "DB query fetched %d rows from %s://%s/%s",
            len(items),
            self._db_type,
            self._host,
            self._database,
        )
        return items

    async def preview(self, max_rows: int = 10) -> dict:
        """Execute the query and return sample rows + column names (no ingest).

        Returns: {"columns": [...], "rows": [...], "total_rows": int}
        """
        if not self._query:
            raise ValueError("No SQL query configured")
        self._validate_select(self._query)

        rows, columns = await self._execute_query(limit=max_rows)
        return {
            "columns": columns,
            "rows": rows[:max_rows],
            "total_rows": len(rows),
            "db_type": self._db_type,
            "database": self._database,
        }

    @staticmethod
    def _validate_select(query: str) -> None:
        normalized = query.strip().upper()
        if not normalized.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

    async def _execute_query(self, limit: int | None = None) -> tuple[list[dict], list[str]]:
        """Route to the appropriate DB driver."""
        if self._db_type in ("mysql", "mariadb"):
            return await self._execute_mysql(limit)
        elif self._db_type == "postgresql":
            return await self._execute_postgresql(limit)
        elif self._db_type == "oracle":
            return await self._execute_oracle(limit)
        elif self._db_type == "mssql":
            return await self._execute_mssql(limit)
        else:
            raise ValueError(
                f"Unsupported db_type: {self._db_type}. "
                f"Supported: {', '.join(sorted(SUPPORTED_DB_TYPES))}"
            )

    # ------------------------------------------------------------------
    # MySQL / MariaDB
    # ------------------------------------------------------------------

    async def _execute_mysql(self, limit: int | None = None) -> tuple[list[dict], list[str]]:
        import aiomysql

        conn = await aiomysql.connect(
            host=self._host,
            port=self._port,
            user=self._username,
            password=self._password,
            db=self._database,
            autocommit=True,
            connect_timeout=10,
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SET SESSION TRANSACTION READ ONLY")
                query = self._apply_limit(self._query, limit, "mysql")
                await cur.execute(query)
                raw_rows = await cur.fetchall()
                if not raw_rows:
                    return [], self._columns_from_cursor(cur)
                columns = list(raw_rows[0].keys())
                return [self._serialize_row(r) for r in raw_rows], columns
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------

    async def _execute_postgresql(self, limit: int | None = None) -> tuple[list[dict], list[str]]:
        import asyncpg

        conn = await asyncpg.connect(
            host=self._host,
            port=self._port,
            user=self._username,
            password=self._password,
            database=self._database,
            timeout=10,
        )
        try:
            await conn.execute("SET default_transaction_read_only = ON")
            query = self._apply_limit(self._query, limit, "postgresql")
            stmt = await conn.prepare(query)
            columns = [attr.name for attr in stmt.get_attributes()]
            raw_rows = await stmt.fetch(limit or 100000)
            rows = [
                {col: self._serialize_val(row[i]) for i, col in enumerate(columns)}
                for row in raw_rows
            ]
            return rows, columns
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Oracle
    # ------------------------------------------------------------------

    async def _execute_oracle(self, limit: int | None = None) -> tuple[list[dict], list[str]]:
        """Execute using oracledb (thin mode — no Oracle Client needed)."""
        try:
            import oracledb
        except ImportError:
            raise ValueError("oracledb package not installed. Run: pip install oracledb")

        # oracledb supports async via thin mode
        dsn = f"{self._host}:{self._port}/{self._database}"
        conn = await oracledb.connect_async(
            user=self._username,
            password=self._password,
            dsn=dsn,
        )
        try:
            cursor = conn.cursor()
            query = self._apply_limit(self._query, limit, "oracle")
            await cursor.execute(query)
            columns = [desc[0].lower() for desc in cursor.description]
            raw_rows = await cursor.fetchall()
            rows = [
                {col: self._serialize_val(val) for col, val in zip(columns, row)}
                for row in raw_rows
            ]
            return rows, columns
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # MSSQL (SQL Server)
    # ------------------------------------------------------------------

    async def _execute_mssql(self, limit: int | None = None) -> tuple[list[dict], list[str]]:
        """Execute using pymssql (synchronous, run in thread pool)."""
        try:
            import pymssql
        except ImportError:
            raise ValueError("pymssql package not installed. Run: pip install pymssql")

        import asyncio

        def _sync_execute():
            conn = pymssql.connect(
                server=self._host,
                port=self._port,
                user=self._username,
                password=self._password,
                database=self._database,
                login_timeout=10,
                as_dict=True,
            )
            try:
                cursor = conn.cursor()
                query = self._apply_limit(self._query, limit, "mssql")
                cursor.execute(query)
                raw_rows = cursor.fetchall()
                if not raw_rows:
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    return [], columns
                columns = list(raw_rows[0].keys())
                return [self._serialize_row(r) for r in raw_rows], columns
            finally:
                conn.close()

        return await asyncio.get_event_loop().run_in_executor(None, _sync_execute)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_limit(query: str, limit: int | None, db_type: str) -> str:
        """Wrap or append LIMIT/FETCH to the query for preview."""
        if limit is None:
            return query
        normalized = query.strip().rstrip(";")
        if db_type == "mssql":
            # SQL Server uses TOP
            if "TOP" not in normalized.upper():
                # Insert TOP after SELECT
                return normalized.replace("SELECT", f"SELECT TOP {limit}", 1)
            return normalized
        elif db_type == "oracle":
            # Oracle 12c+ supports FETCH FIRST
            return f"{normalized} FETCH FIRST {limit} ROWS ONLY"
        else:
            # MySQL, PostgreSQL
            if "LIMIT" not in normalized.upper():
                return f"{normalized} LIMIT {limit}"
            return normalized

    @staticmethod
    def _columns_from_cursor(cur) -> list[str]:
        if cur.description:
            return [desc[0] for desc in cur.description]
        return []

    @staticmethod
    def _serialize_val(val):
        if val is None:
            return None
        if isinstance(val, (int, float, str, bool)):
            return val
        return str(val)

    @staticmethod
    def _serialize_row(row: dict) -> dict:
        return {
            k: v if isinstance(v, (int, float, str, bool, type(None))) else str(v)
            for k, v in row.items()
        }

    def _rows_to_items(self, rows: list[dict], columns: list[str]) -> list[IngestItem]:
        """Convert query result rows to IngestItems."""
        text_cols = self._text_columns or columns
        items = []

        for row in rows:
            id_val = row.get(self._id_column, "")
            external_id = f"dbquery:{self._database}.{id_val}"
            title = str(row.get(self._title_column, "")) if self._title_column else ""

            parts = []
            for col in text_cols:
                val = row.get(col)
                if val is not None and str(val).strip():
                    parts.append(str(val))
            source_text = self._text_separator.join(parts) if parts else str(row)

            metadata = json.dumps(row, ensure_ascii=False, default=str)
            items.append(
                IngestItem(
                    external_id=external_id,
                    title=title,
                    source_text=source_text,
                    metadata_json=metadata,
                    source_type="db_query",
                    source_url=(f"{self._db_type}://{self._host}:{self._port}/{self._database}"),
                )
            )
        return items

    async def close(self) -> None:
        pass
