"""Dataset detail and schema tools."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, ToolResult


class GetDatasetDetailTool(BaseTool):
    """Get full details of a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_dataset_detail"

    @property
    def description(self) -> str:
        return (
            "Get detailed information about a dataset including name, description, "
            "platform, tags, owners, row count, and properties. "
            "Use this after search_datasets to get full details by dataset ID."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID from search results.",
                },
            },
            "required": ["dataset_id"],
        }

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_dataset(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetDatasetSchemaTool(BaseTool):
    """Get column-level schema for a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_dataset_schema"

    @property
    def description(self) -> str:
        return (
            "Get the column/field schema of a dataset. Returns column names, data types, "
            "descriptions, nullable, primary key, unique, indexed flags, and PII classification. "
            "Essential for generating accurate SQL and ETL code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID.",
                },
            },
            "required": ["dataset_id"],
        }

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_dataset_schema(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetCatalogStatsTool(BaseTool):
    """Get catalog dashboard statistics."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_catalog_stats"

    @property
    def description(self) -> str:
        return (
            "Get overall catalog statistics: total dataset count, platform count, "
            "tag count, etc. Useful for understanding the data landscape."
        )

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        try:
            result = await self._catalog.get_catalog_stats()
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
