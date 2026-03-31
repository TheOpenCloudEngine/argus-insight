"""Data standard compliance tools — term search, compliance check, and auto-mapping."""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class ListStandardDictionariesTool(BaseTool):
    """List all standard dictionaries available in the catalog."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "list_standard_dictionaries"

    @property
    def description(self) -> str:
        return (
            "List all data standard dictionaries registered in the catalog. "
            "A dictionary contains standard words, domains, terms, and code groups "
            "that define naming conventions and data type rules for an organization. "
            "Use this first to find the dictionary_id needed by other standard tools."
        )

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        try:
            result = await self._catalog.list_standard_dictionaries()
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchStandardTermsTool(BaseTool):
    """Search standard terms in a dictionary."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "search_standard_terms"

    @property
    def description(self) -> str:
        return (
            "Search standard terms defined in a data standard dictionary. "
            "Each term has a Korean name, English name, abbreviation, physical column name, "
            "and associated data domain (data type and length). "
            "Use this to look up the official column naming conventions for a given concept."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dictionary_id": {
                    "type": "integer",
                    "description": "The standard dictionary ID.",
                },
                "search": {
                    "type": "string",
                    "description": "Search keyword to filter terms by name (Korean or English).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 100).",
                    "default": 100,
                },
            },
            "required": ["dictionary_id"],
        }

    async def execute(
        self, dictionary_id: int, search: str | None = None, limit: int = 100
    ) -> ToolResult:
        try:
            result = await self._catalog.search_standard_terms(
                dictionary_id, search=search, limit=limit
            )
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class AnalyzeTermTool(BaseTool):
    """Analyze a term name by decomposing it into standard morphemes."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "analyze_standard_term"

    @property
    def description(self) -> str:
        return (
            "Analyze a Korean term name by decomposing it into standard morphemes (words). "
            "Returns the matched words, auto-generated English name, abbreviation, "
            "recommended physical column name, suggested data domain, and any unmatched parts. "
            "Use this to check whether a proposed column name follows the organization's "
            "naming standard, or to generate a compliant physical name from a business term."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dictionary_id": {
                    "type": "integer",
                    "description": "The standard dictionary ID.",
                },
                "term_name": {
                    "type": "string",
                    "description": "Korean term name to analyze (e.g. '고객번호', '주문일자').",
                },
            },
            "required": ["dictionary_id", "term_name"],
        }

    async def execute(self, dictionary_id: int, term_name: str) -> ToolResult:
        try:
            result = await self._catalog.analyze_term(dictionary_id, term_name)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CheckDatasetComplianceTool(BaseTool):
    """Check a dataset's compliance against a standard dictionary."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "check_dataset_compliance"

    @property
    def description(self) -> str:
        return (
            "Check how well a dataset's columns comply with a data standard dictionary. "
            "Returns compliance statistics: total columns, matched (fully compliant), "
            "similar (partial match), violation (type mismatch), unmapped (no match), "
            "and the overall compliance rate as a percentage. "
            "Use this to audit whether a table follows the organization's naming and "
            "data type standards."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dictionary_id": {
                    "type": "integer",
                    "description": "The standard dictionary ID to check against.",
                },
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to check.",
                },
            },
            "required": ["dictionary_id", "dataset_id"],
        }

    async def execute(self, dictionary_id: int, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_dataset_compliance(dictionary_id, dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetDatasetTermMappingTool(BaseTool):
    """Get detailed term mapping status for every column in a dataset."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "get_dataset_term_mapping"

    @property
    def description(self) -> str:
        return (
            "Get the full column-by-column term mapping status for a dataset. "
            "For each column, shows whether it is mapped to a standard term (MATCHED), "
            "partially matched (SIMILAR), has a type mismatch (VIOLATION), or is unmapped. "
            "Also includes the expected standard physical name and data type for each mapping. "
            "Use this after check_dataset_compliance to see exactly which columns need attention."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dictionary_id": {
                    "type": "integer",
                    "description": "The standard dictionary ID.",
                },
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID.",
                },
            },
            "required": ["dictionary_id", "dataset_id"],
        }

    async def execute(self, dictionary_id: int, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.get_dataset_term_mapping(dictionary_id, dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class AutoMapDatasetTool(BaseTool):
    """Auto-map dataset columns to standard terms."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "auto_map_dataset"

    @property
    def description(self) -> str:
        return (
            "Automatically map a dataset's columns to standard terms by matching "
            "physical column names against the standard dictionary's term physical names. "
            "Checks data type compatibility and classifies each column as MATCHED, "
            "SIMILAR (name match but type mismatch), or VIOLATION. "
            "Returns counts of created/updated mappings. "
            "Use this to initialize or refresh the term mapping for a dataset before "
            "running compliance checks."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dictionary_id": {
                    "type": "integer",
                    "description": "The standard dictionary ID.",
                },
                "dataset_id": {
                    "type": "integer",
                    "description": "The dataset ID to auto-map.",
                },
            },
            "required": ["dictionary_id", "dataset_id"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE_WRITE

    async def execute(self, dictionary_id: int, dataset_id: int) -> ToolResult:
        try:
            result = await self._catalog.auto_map_dataset(dictionary_id, dataset_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
