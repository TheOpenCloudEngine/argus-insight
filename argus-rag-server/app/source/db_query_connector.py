"""Database Query connector — executes SQL on a source DB and ingests results.

Connects to MySQL or PostgreSQL, runs a user-defined SELECT query,
and converts each row into an IngestItem for embedding.

Config example:
{
    "db_type": "mysql",
    "host": "10.0.1.50",
    "port": 3306,
    "username": "reader",
    "password": "secret",
    "database": "sakila",
    "query": "SELECT film_id, title, description, release_year FROM film",
    "id_column": "film_id",
    "title_column": "title",
    "text_columns": ["title", "description", "release_year"],
    "text_separator": " | "
}

- id_column: which column to use as external_id (required)
- title_column: which column to use as document title (optional)
- text_columns: which columns to concatenate into source_text
  (optional — if omitted, all columns are concatenated)
- text_separator: separator between column values (default " | ")
"""

import json
import logging

from app.source.base import IngestItem, SourceConnector

logger = logging.getLogger(__name__)


class DBQueryConnector(SourceConnector):
    """Execute a SQL query on a source DB and produce IngestItems."""

    def __init__(self, config: dict) -> None:
        self._db_type = config.get("db_type", "mysql").lower()
        self._host = config.get("host", "localhost")
        self._port = int(config.get("port", 3306))
        self._username = config.get("username", "")
        self._password = config.get("password", "")
        self._database = config.get("database", "")
        self._query = config.get("query", "")
        self._id_column = config.get("id_column", "")
        self._title_column = config.get("title_column", "")
        self._text_columns = config.get("text_columns", [])
        self._text_separator = config.get("text_separator", " | ")
        self._conn = None

    async def fetch_all(self) -> list[IngestItem]:
        if not self._query:
            raise ValueError("No SQL query configured for db_query source")
        if not self._id_column:
            raise ValueError("id_column is required for db_query source")

        # Validate read-only
        normalized = self._query.strip().upper()
        if not normalized.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed for db_query source")

        rows, columns = await self._execute_query()
        items = self._rows_to_items(rows, columns)
        logger.info(
            "DB query fetched %d rows from %s.%s",
            len(items),
            self._host,
            self._database,
        )
        return items

    async def _execute_query(self) -> tuple[list[dict], list[str]]:
        """Execute the query and return (rows_as_dicts, column_names)."""
        if self._db_type in ("mysql", "mariadb"):
            return await self._execute_mysql()
        elif self._db_type == "postgresql":
            return await self._execute_postgresql()
        else:
            raise ValueError(f"Unsupported db_type: {self._db_type}")

    async def _execute_mysql(self) -> tuple[list[dict], list[str]]:
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
        self._conn = conn
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SET SESSION TRANSACTION READ ONLY")
                await cur.execute(self._query)
                raw_rows = await cur.fetchall()
                if not raw_rows:
                    return [], []
                columns = list(raw_rows[0].keys())
                return [dict(r) for r in raw_rows], columns
        finally:
            conn.close()

    async def _execute_postgresql(self) -> tuple[list[dict], list[str]]:
        import asyncpg

        conn = await asyncpg.connect(
            host=self._host,
            port=self._port,
            user=self._username,
            password=self._password,
            database=self._database,
            timeout=10,
        )
        self._conn = conn
        try:
            await conn.execute("SET default_transaction_read_only = ON")
            stmt = await conn.prepare(self._query)
            columns = [attr.name for attr in stmt.get_attributes()]
            raw_rows = await stmt.fetch(100000)
            rows = [
                {col: self._serialize(row[i]) for i, col in enumerate(columns)} for row in raw_rows
            ]
            return rows, columns
        finally:
            await conn.close()

    def _rows_to_items(self, rows: list[dict], columns: list[str]) -> list[IngestItem]:
        """Convert query result rows to IngestItems."""
        text_cols = self._text_columns or columns
        items = []

        for row in rows:
            # external_id
            id_val = row.get(self._id_column, "")
            external_id = f"dbquery:{self._database}.{id_val}"

            # title
            title = str(row.get(self._title_column, "")) if self._title_column else ""

            # source_text — concatenate selected columns
            parts = []
            for col in text_cols:
                val = row.get(col)
                if val is not None and str(val).strip():
                    parts.append(str(val))
            source_text = self._text_separator.join(parts) if parts else str(row)

            # metadata — full row as JSON
            metadata = json.dumps(row, ensure_ascii=False, default=str)

            items.append(
                IngestItem(
                    external_id=external_id,
                    title=title,
                    source_text=source_text,
                    metadata_json=metadata,
                    source_type="db_query",
                    source_url=f"{self._db_type}://{self._host}:{self._port}/{self._database}",
                )
            )

        return items

    @staticmethod
    def _serialize(val):
        if val is None:
            return None
        if isinstance(val, (int, float, str, bool)):
            return val
        return str(val)

    async def close(self) -> None:
        pass  # Connections are closed in _execute_* methods
