"""MySQL/MariaDB connector for read-only query execution."""

import logging

import aiomysql

from app.connectors.base import DBConnector, QueryResult

logger = logging.getLogger(__name__)


class MySQLConnector(DBConnector):
    """MySQL/MariaDB read-only connector."""

    def __init__(
        self,
        host: str,
        port: int = 3306,
        username: str = "",
        password: str = "",
        database: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._conn: aiomysql.Connection | None = None

    async def _get_conn(self) -> aiomysql.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = await aiomysql.connect(
                host=self._host,
                port=self._port,
                user=self._username,
                password=self._password,
                db=self._database,
                autocommit=True,
                connect_timeout=10,
            )
            # Set read-only session
            async with self._conn.cursor() as cur:
                await cur.execute("SET SESSION TRANSACTION READ ONLY")
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
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql)
                raw_rows = await cur.fetchmany(max_rows + 1)

                truncated = len(raw_rows) > max_rows
                if truncated:
                    raw_rows = raw_rows[:max_rows]

                if not raw_rows:
                    # Get column names from description
                    columns = [desc[0] for desc in (cur.description or [])]
                    return QueryResult(
                        columns=columns,
                        rows=[],
                        row_count=0,
                    )

                columns = list(raw_rows[0].keys())
                rows = [[row.get(col) for col in columns] for row in raw_rows]

                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                )
        except Exception as e:
            logger.exception("MySQL query failed")
            return QueryResult(columns=[], rows=[], row_count=0, error=str(e))

    async def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.debug("MySQL connection closed")
