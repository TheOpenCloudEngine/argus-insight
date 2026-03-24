"""Lineage tools — data flow tracking and impact analysis."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class GetDatasetLineageTool(BaseTool):
    """Get lineage graph for a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_dataset_lineage"

    @property
    def description(self) -> str:
        return (
            "Get the lineage (data flow) graph for a dataset. Shows upstream sources "
            "and downstream consumers, including cross-platform relationships and "
            "column-level mappings with transform expressions."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to get lineage for.",
                },
            },
            "required": ["dataset_id"],
        }

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_dataset_lineage(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RegisterLineageTool(BaseTool):
    """Register a new lineage relationship in the catalog."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "register_lineage"

    @property
    def description(self) -> str:
        return (
            "Register a new data lineage relationship between datasets. "
            "Specifies source and target datasets, pipeline, and column mappings."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source_dataset_id": {
                    "type": "integer",
                    "description": "Source dataset ID.",
                },
                "target_dataset_id": {
                    "type": "integer",
                    "description": "Target dataset ID.",
                },
                "pipeline_id": {
                    "type": "integer",
                    "description": "Pipeline ID (optional).",
                },
                "column_mappings": {
                    "type": "array",
                    "description": "Column-level mappings.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_column": {"type": "string"},
                            "target_column": {"type": "string"},
                            "transform_expression": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["source_dataset_id", "target_dataset_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE_WRITE

    async def execute(
        self,
        source_dataset_id: int,
        target_dataset_id: int,
        pipeline_id: int | None = None,
        column_mappings: list | None = None,
    ) -> ToolResult:
        try:
            data: dict = {
                "source_dataset_id": source_dataset_id,
                "target_dataset_id": target_dataset_id,
            }
            if pipeline_id:
                data["pipeline_id"] = pipeline_id
            if column_mappings:
                data["column_mappings"] = column_mappings
            result = await self._catalog.register_lineage(data)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
