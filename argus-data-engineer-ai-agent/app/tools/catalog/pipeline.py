"""Pipeline tools — list and register data pipelines."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class ListPipelinesTool(BaseTool):
    """List registered data pipelines."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "list_pipelines"

    @property
    def description(self) -> str:
        return (
            "List all registered data pipelines in the catalog. "
            "Shows pipeline names, types (ETL/CDC/EXPORT), sources, targets, "
            "and scheduling information."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 50).",
                    "default": 50,
                },
            },
        }

    async def execute(self, limit: int = 50) -> ToolResult:
        try:
            result = await self._catalog.list_pipelines(limit=limit)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RegisterPipelineTool(BaseTool):
    """Register a new data pipeline in the catalog."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "register_pipeline"

    @property
    def description(self) -> str:
        return (
            "Register a new data pipeline in the catalog. "
            "Records the pipeline name, type, description, scheduling, "
            "and source/target dataset relationships."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Pipeline name.",
                },
                "pipeline_type": {
                    "type": "string",
                    "enum": ["ETL", "CDC", "EXPORT", "IMPORT", "TRANSFORM"],
                    "description": "Pipeline type.",
                },
                "description": {
                    "type": "string",
                    "description": "Pipeline description.",
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression or schedule keyword (e.g., '@daily').",
                },
                "source_dataset_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Source dataset IDs.",
                },
                "target_dataset_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Target dataset IDs.",
                },
            },
            "required": ["name", "pipeline_type"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE_WRITE

    async def execute(
        self,
        name: str,
        pipeline_type: str,
        description: str = "",
        schedule: str = "",
        source_dataset_ids: list | None = None,
        target_dataset_ids: list | None = None,
    ) -> ToolResult:
        try:
            data: dict = {
                "name": name,
                "pipeline_type": pipeline_type,
                "description": description,
            }
            if schedule:
                data["schedule"] = schedule
            if source_dataset_ids:
                data["source_dataset_ids"] = source_dataset_ids
            if target_dataset_ids:
                data["target_dataset_ids"] = target_dataset_ids
            result = await self._catalog.register_pipeline(data)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
