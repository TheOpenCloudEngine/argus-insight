"""Data preview tool — samples rows from a dataset's source table.

Uses the catalog to find the platform and table name, then executes
a SELECT * LIMIT query to preview actual data.
"""

import logging

from app.catalog_client.client import CatalogClient
from app.connectors.factory import create_connector, is_supported
from app.tools.base import BaseTool, SafetyLevel, ToolResult

logger = logging.getLogger(__name__)


class PreviewDataTool(BaseTool):
    """Preview actual data from a dataset by querying its source database."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "preview_data"

    @property
    def description(self) -> str:
        return (
            "Preview actual data from a dataset by querying its source database. "
            "Executes a SELECT * with LIMIT to show sample rows. "
            "Useful for understanding data content, checking values, and verifying "
            "column meanings before generating ETL code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "Dataset ID to preview.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of rows to preview (default 10, max 50).",
                    "default": 10,
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific columns to include (optional, default all).",
                },
                "where_clause": {
                    "type": "string",
                    "description": "Optional WHERE clause filter (without the WHERE keyword).",
                },
                "order_by": {
                    "type": "string",
                    "description": "Optional ORDER BY clause (without the ORDER BY keyword).",
                },
            },
            "required": ["dataset_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO_READ

    async def execute(
        self,
        dataset_id: int,
        limit: int = 10,
        columns: list[str] | None = None,
        where_clause: str | None = None,
        order_by: str | None = None,
    ) -> ToolResult:
        limit = min(limit, 50)

        try:
            # Get dataset and platform info
            detail = await self._catalog.get_dataset(dataset_id)
            platform_type = detail.get("platform_type", "").lower()
            platform_id = detail.get("platform_id")

            if not platform_id:
                return ToolResult(success=False, error="Dataset has no associated platform.")

            if not is_supported(platform_type):
                return ToolResult(
                    success=False,
                    error=(
                        f"Preview not supported for '{platform_type}'. "
                        "Supported: mysql, postgresql."
                    ),
                )

            config = await self._catalog.get_platform_config(platform_id)

            # Build the table reference from dataset name
            # Dataset name format: "database.table" (MySQL) or "schema.table" (PostgreSQL)
            table_name = detail.get("name", "")
            if not table_name:
                return ToolResult(success=False, error="Dataset has no table name.")

            # Build SELECT query
            col_list = ", ".join(columns) if columns else "*"

            # Platform-specific quoting
            if platform_type in ("mysql", "mariadb"):
                # MySQL: backtick quoting
                parts = table_name.split(".")
                quoted = ".".join(f"`{p}`" for p in parts)
            else:
                # PostgreSQL: double-quote
                parts = table_name.split(".")
                quoted = ".".join(f'"{p}"' for p in parts)

            sql = f"SELECT {col_list} FROM {quoted}"
            if where_clause:
                sql += f" WHERE {where_clause}"
            if order_by:
                sql += f" ORDER BY {order_by}"
            sql += f" LIMIT {limit}"

            connector = create_connector(platform_type, config)
            try:
                result = await connector.execute_query(sql, max_rows=limit)
                if result.error:
                    return ToolResult(success=False, error=result.error)
                return ToolResult(
                    success=True,
                    data={
                        "dataset": table_name,
                        "platform": platform_type,
                        "columns": result.columns,
                        "rows": result.rows,
                        "row_count": result.row_count,
                        "sql": sql,
                        "table": result.to_table_str(),
                    },
                )
            finally:
                await connector.close()

        except Exception as e:
            logger.exception("Data preview failed")
            return ToolResult(success=False, error=str(e))
