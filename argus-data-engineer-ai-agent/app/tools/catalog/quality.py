"""Data quality tools — profiling, rules, and checks."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class GetQualityProfileTool(BaseTool):
    """Get the latest quality profile for a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_quality_profile"

    @property
    def description(self) -> str:
        return (
            "Get the latest data quality profile for a dataset. Shows column-level "
            "statistics: null rate, unique count, min/max values, average, etc."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to get profile for.",
                },
            },
            "required": ["dataset_id"],
        }

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_quality_profile(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetQualityScoreTool(BaseTool):
    """Get quality score for a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_quality_score"

    @property
    def description(self) -> str:
        return (
            "Get the aggregated quality score for a dataset. "
            "Shows overall score and per-rule pass/fail results."
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
            result = await self._catalog.get_quality_score(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RunProfilingTool(BaseTool):
    """Trigger data profiling on a dataset's source database."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "run_profiling"

    @property
    def description(self) -> str:
        return (
            "Trigger data profiling on a dataset by querying its source database directly. "
            "Collects column-level statistics: null counts, distinct counts, min/max, avg, etc."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to profile.",
                },
            },
            "required": ["dataset_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.run_profiling(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RunQualityCheckTool(BaseTool):
    """Execute quality rules on a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "run_quality_check"

    @property
    def description(self) -> str:
        return "Execute all quality rules defined for a dataset and return pass/fail results."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to check.",
                },
            },
            "required": ["dataset_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE

    async def execute(self, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.run_quality_check(dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
