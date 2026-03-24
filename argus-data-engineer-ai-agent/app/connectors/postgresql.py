"""PostgreSQL connector for read-only query execution."""

import logging

import asyncpg

from app.connectors.base import DBConnector, QueryResult

logger = logging.getLogger(__name__)


class PostgreSQLConnector(DBConnector):
    """PostgreSQL read-only connector."""

    def __init__(
        self,
        host: str,
        port: int = 5432,
        username: str = "",
        password: str = "",
        database: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._conn: asyncpg.Connection | None = None

    async def _get_conn(self) -> asyncpg.Connection:
        if self._conn is None or self._conn.is_closed():
            self._conn = await asyncpg.connect(
                host=self._host,
                port=self._port,
                user=self._username,
                password=self._password,
                database=self._database,
                timeout=10,
            )
            # Set read-only transaction
            await self._conn.execute("SET default_transaction_read_only = ON")
        return self._conn

    async def execute_query(
        self,
        sql: str,
        max_rows: int = 100,
    ) -> QueryResult:
        # Validate read-only
        error = self._validate_read_only(sql)
        if error:
            return QueryResult(columns=[], rows=[], row_count=0, error=error)

        try:
            conn = await self._get_conn()

            # Use a read-only transaction
            async with conn.transaction(readonly=True):
                stmt = await conn.prepare(sql)
                columns = [attr.name for attr in stmt.get_attributes()]
                raw_rows = await stmt.fetch(max_rows + 1)

                truncated = len(raw_rows) > max_rows
                if truncated:
                    raw_rows = raw_rows[:max_rows]

                rows = [[self._serialize(val) for val in record.values()] for record in raw_rows]

                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                )
        except Exception as e:
            logger.exception("PostgreSQL query failed")
            return QueryResult(columns=[], rows=[], row_count=0, error=str(e))

    @staticmethod
    def _serialize(val):
        """Convert PostgreSQL native types to JSON-serializable values."""
        if val is None:
            return None
        if isinstance(val, (int, float, str, bool)):
            return val
        # Convert datetime, UUID, etc. to string
        return str(val)

    async def close(self) -> None:
        if self._conn and not self._conn.is_closed():
            await self._conn.close()
            logger.debug("PostgreSQL connection closed")
