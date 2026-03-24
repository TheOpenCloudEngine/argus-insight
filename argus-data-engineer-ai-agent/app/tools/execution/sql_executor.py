"""SQL execution tool — runs read-only queries against source databases.

Connects to the actual source database using catalog platform configuration,
executes SELECT/EXPLAIN queries, and returns results. Write operations are blocked.
"""

import logging

from app.catalog_client.client import CatalogClient
from app.connectors.factory import create_connector, is_supported
from app.tools.base import BaseTool, SafetyLevel, ToolResult

logger = logging.getLogger(__name__)


class ExecuteSQLTool(BaseTool):
    """Execute a read-only SQL query against a source database."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "execute_sql"

    @property
    def description(self) -> str:
        return (
            "Execute a read-only SQL query (SELECT, EXPLAIN, SHOW, DESCRIBE) against "
            "a source database. Connects to the actual database using the platform's "
            "connection configuration from the catalog. "
            "DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER) are blocked. "
            "Results are limited to 100 rows by default."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform_id": {
                    "type": "integer",
                    "description": "Platform ID to connect to.",
                },
                "sql": {
                    "type": "string",
                    "description": "SQL query to execute (SELECT only).",
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum rows to return (default 100, max 500).",
                    "default": 100,
                },
            },
            "required": ["platform_id", "sql"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE_EXEC

    async def execute(
        self,
        platform_id: int,
        sql: str,
        max_rows: int = 100,
    ) -> ToolResult:
        # Enforce max_rows cap
        max_rows = min(max_rows, 500)

        try:
            # Get platform info
            config = await self._catalog.get_platform_config(platform_id)
            platform_type = config.get("platform_type", "")

            if not is_supported(platform_type):
                return ToolResult(
                    success=False,
                    error=(
                        f"SQL execution not supported for platform '{platform_type}'. "
                        "Supported: mysql, postgresql."
                    ),
                )

            connector = create_connector(platform_type, config)
            try:
                result = await connector.execute_query(sql, max_rows=max_rows)
                if result.error:
                    return ToolResult(success=False, error=result.error)
                return ToolResult(
                    success=True,
                    data={
                        "columns": result.columns,
                        "rows": result.rows,
                        "row_count": result.row_count,
                        "truncated": result.truncated,
                        "table": result.to_table_str(),
                    },
                )
            finally:
                await connector.close()

        except Exception as e:
            logger.exception("SQL execution failed")
            return ToolResult(success=False, error=str(e))


class ValidateSQLTool(BaseTool):
    """Validate SQL syntax by running EXPLAIN."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "validate_sql"

    @property
    def description(self) -> str:
        return (
            "Validate a SQL query by running EXPLAIN against the source database. "
            "Returns the execution plan if valid, or an error message if the SQL is invalid."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform_id": {
                    "type": "integer",
                    "description": "Platform ID to validate against.",
                },
                "sql": {
                    "type": "string",
                    "description": "SQL query to validate.",
                },
            },
            "required": ["platform_id", "sql"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE

    async def execute(self, platform_id: int, sql: str) -> ToolResult:
        try:
            config = await self._catalog.get_platform_config(platform_id)
            platform_type = config.get("platform_type", "")

            if not is_supported(platform_type):
                return ToolResult(
                    success=False,
                    error=f"EXPLAIN not supported for '{platform_type}'.",
                )

            explain_sql = f"EXPLAIN {sql}"
            connector = create_connector(platform_type, config)
            try:
                result = await connector.execute_query(explain_sql, max_rows=50)
                if result.error:
                    return ToolResult(
                        success=False,
                        data={"valid": False, "error": result.error},
                    )
                return ToolResult(
                    success=True,
                    data={
                        "valid": True,
                        "explain_plan": result.to_table_str(),
                    },
                )
            finally:
                await connector.close()

        except Exception as e:
            return ToolResult(success=False, error=str(e))
