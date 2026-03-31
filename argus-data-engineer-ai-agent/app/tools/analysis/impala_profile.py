"""Impala query profile analysis tools.

Provides tools for the AI agent to fetch and analyze Impala query runtime
profiles, automatically detecting bottleneck nodes that cause slow queries.
"""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class AnalyzeImpalaQueryProfileTool(BaseTool):
    """Analyze an Impala query profile to detect performance bottlenecks."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "analyze_impala_query_profile"

    @property
    def description(self) -> str:
        return (
            "Analyze an Impala query's runtime profile to automatically detect "
            "performance bottlenecks. Fetches the profile from the Impala daemon "
            "or Cloudera Manager, parses the execution node tree, and applies "
            "8 detection rules: time-dominant nodes, data skew across instances, "
            "spill to disk, low scan selectivity, network wait on exchanges, "
            "join row explosion, cardinality estimation errors, and memory pressure. "
            "Returns a ranked list of bottlenecks with severity, evidence metrics, "
            "and optimization recommendations."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "description": (
                        "Impala query ID (e.g. 'f44b0e2e12c0fc5a:5b6cfc5300000000'). "
                        "Can be found in Impala web UI, Cloudera Manager, or query logs."
                    ),
                },
            },
            "required": ["query_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, query_id: str) -> ToolResult:
        try:
            result = await self._catalog.analyze_impala_query_profile(query_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class AnalyzeImpalaProfileTextTool(BaseTool):
    """Analyze a raw Impala profile text for bottlenecks."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "analyze_impala_profile_text"

    @property
    def description(self) -> str:
        return (
            "Analyze a raw Impala runtime profile text pasted by the user. "
            "Use this when the user provides profile text directly instead of "
            "a query ID. Parses the profile and runs the same 8 bottleneck "
            "detection rules as analyze_impala_query_profile."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "profile_text": {
                    "type": "string",
                    "description": "Raw Impala runtime profile text.",
                },
            },
            "required": ["profile_text"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, profile_text: str) -> ToolResult:
        try:
            result = await self._catalog.analyze_impala_profile_text(profile_text)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetImpalaQueryProfileTool(BaseTool):
    """Fetch the raw runtime profile text for an Impala query."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_impala_query_profile"

    @property
    def description(self) -> str:
        return (
            "Fetch the raw runtime profile text for an Impala query. "
            "Returns the full text-format profile from the Impala daemon "
            "or Cloudera Manager. Use this when you need to see the raw profile "
            "before or instead of running automated bottleneck analysis."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "description": "Impala query ID.",
                },
            },
            "required": ["query_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, query_id: str) -> ToolResult:
        try:
            result = await self._catalog.get_impala_query_profile(query_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
