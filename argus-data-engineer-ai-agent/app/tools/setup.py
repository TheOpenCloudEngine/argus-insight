"""Tool registration — creates and registers all available tools."""

from app.catalog_client.client import CatalogClient
from app.tools.registry import ToolRegistry


def create_tool_registry(catalog: CatalogClient) -> ToolRegistry:
    """Create a ToolRegistry with all available tools registered."""
    registry = ToolRegistry()

    # --- Catalog tools ---
    from app.tools.catalog.dataset import (
        GetCatalogStatsTool,
        GetDatasetDetailTool,
        GetDatasetSchemaTool,
    )
    from app.tools.catalog.lineage import GetDatasetLineageTool, RegisterLineageTool
    from app.tools.catalog.pipeline import ListPipelinesTool, RegisterPipelineTool
    from app.tools.catalog.platform import GetPlatformConfigTool, GetPlatformMetadataTool
    from app.tools.catalog.quality import (
        GetQualityProfileTool,
        GetQualityScoreTool,
        RunProfilingTool,
        RunQualityCheckTool,
    )
    from app.tools.catalog.search import SearchDatasetsTool, SearchGlossaryTool
    from app.tools.catalog.standard import (
        AnalyzeTermTool,
        AutoMapDatasetTool,
        CheckDatasetComplianceTool,
        GetDatasetTermMappingTool,
        ListStandardDictionariesTool,
        SearchStandardTermsTool,
    )

    registry.register(SearchDatasetsTool(catalog))
    registry.register(SearchGlossaryTool(catalog))
    registry.register(GetDatasetDetailTool(catalog))
    registry.register(GetDatasetSchemaTool(catalog))
    registry.register(GetCatalogStatsTool(catalog))
    registry.register(GetDatasetLineageTool(catalog))
    registry.register(RegisterLineageTool(catalog))
    registry.register(GetQualityProfileTool(catalog))
    registry.register(GetQualityScoreTool(catalog))
    registry.register(RunProfilingTool(catalog))
    registry.register(RunQualityCheckTool(catalog))
    registry.register(GetPlatformConfigTool(catalog))
    registry.register(GetPlatformMetadataTool(catalog))
    registry.register(ListPipelinesTool(catalog))
    registry.register(RegisterPipelineTool(catalog))

    # --- Standard compliance tools ---
    registry.register(ListStandardDictionariesTool(catalog))
    registry.register(SearchStandardTermsTool(catalog))
    registry.register(AnalyzeTermTool(catalog))
    registry.register(CheckDatasetComplianceTool(catalog))
    registry.register(GetDatasetTermMappingTool(catalog))
    registry.register(AutoMapDatasetTool(catalog))

    # --- Analysis tools ---
    from app.tools.analysis.impala_profile import (
        AnalyzeImpalaProfileTextTool,
        AnalyzeImpalaQueryProfileTool,
        GetImpalaQueryProfileTool,
    )

    registry.register(AnalyzeImpalaQueryProfileTool(catalog))
    registry.register(AnalyzeImpalaProfileTextTool(catalog))
    registry.register(GetImpalaQueryProfileTool(catalog))

    # --- Code generation tools ---
    from app.tools.codegen.ddl import GenerateDDLTool
    from app.tools.codegen.pipeline_config import GeneratePipelineConfigTool
    from app.tools.codegen.pyspark import GeneratePySparkTool
    from app.tools.codegen.sql import GenerateSQLTool

    registry.register(GenerateSQLTool(catalog))
    registry.register(GeneratePySparkTool(catalog))
    registry.register(GenerateDDLTool(catalog))
    registry.register(GeneratePipelineConfigTool(catalog))

    # --- Execution tools ---
    from app.tools.execution.data_preview import PreviewDataTool
    from app.tools.execution.file_writer import ListFilesTool, ReadFileTool, WriteFileTool
    from app.tools.execution.sql_executor import ExecuteSQLTool, ValidateSQLTool

    registry.register(ExecuteSQLTool(catalog))
    registry.register(ValidateSQLTool(catalog))
    registry.register(PreviewDataTool(catalog))
    registry.register(WriteFileTool())
    registry.register(ReadFileTool())
    registry.register(ListFilesTool())

    return registry
