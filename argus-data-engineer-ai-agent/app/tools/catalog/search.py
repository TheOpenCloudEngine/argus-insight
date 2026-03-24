"""Catalog search tools — dataset and glossary search."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class SearchDatasetsTool(BaseTool):
    """Search datasets in the catalog using hybrid search."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "search_datasets"

    @property
    def description(self) -> str:
        return (
            "Search for datasets in the Argus Data Catalog. "
            "Uses hybrid search (keyword + semantic) to find tables, views, topics, "
            "and files across all registered platforms. Returns dataset names, IDs, "
            "platforms, and descriptions."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — dataset name, description keywords, or URN.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20).",
                    "default": 20,
                },
            },
            "required": ["query"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, query: str, limit: int = 20) -> ToolResult:
        try:
            result = await self._catalog.search_datasets(query, limit=limit)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchGlossaryTool(BaseTool):
    """Search business glossary terms."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "search_glossary"

    @property
    def description(self) -> str:
        return (
            "Search business glossary terms in the catalog. "
            "Useful for understanding business definitions of data concepts."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Glossary term to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 50).",
                    "default": 50,
                },
            },
            "required": ["search"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, search: str, limit: int = 50) -> ToolResult:
        try:
            result = await self._catalog.search_glossary(search=search, limit=limit)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
