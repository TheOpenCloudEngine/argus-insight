"""Platform tools — connection config and capabilities."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, ToolResult


class GetPlatformConfigTool(BaseTool):
    """Get platform connection configuration."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_platform_config"

    @property
    def description(self) -> str:
        return (
            "Get the connection configuration for a data platform (host, port, database, "
            "driver, etc.). Useful for generating JDBC URLs and connection strings in ETL code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform_id": {
                    "type": "integer",
                    "description": "The platform ID.",
                },
            },
            "required": ["platform_id"],
        }

    async def execute(self, platform_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_platform_config(platform_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetPlatformMetadataTool(BaseTool):
    """Get platform capabilities and supported features."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_platform_metadata"

    @property
    def description(self) -> str:
        return (
            "Get platform capabilities: supported data types, table types, storage formats, "
            "and features (partitioning, distribution keys, etc.). "
            "Essential for generating platform-specific DDL and code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform_id": {
                    "type": "integer",
                    "description": "The platform ID.",
                },
            },
            "required": ["platform_id"],
        }

    async def execute(self, platform_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_platform_metadata(platform_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
