"""PySpark ETL code generation tool.

Generates PySpark code that reads from source platform(s), transforms data,
and writes to a target platform. Uses catalog metadata for accurate schema
and platform connection details.
"""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult

JDBC_DRIVERS = {
    "mysql": {
        "driver_class": "com.mysql.cj.jdbc.Driver",
        "url_template": "jdbc:mysql://{host}:{port}/{database}?useSSL=false&serverTimezone=UTC",
        "default_port": 3306,
    },
    "postgresql": {
        "driver_class": "org.postgresql.Driver",
        "url_template": "jdbc:postgresql://{host}:{port}/{database}",
        "default_port": 5432,
    },
    "hive": {
        "driver_class": "org.apache.hive.jdbc.HiveDriver",
        "url_template": "jdbc:hive2://{host}:{port}/{database}",
        "default_port": 10000,
    },
    "snowflake": {
        "driver_class": "net.snowflake.client.jdbc.SnowflakeDriver",
        "url_template": "jdbc:snowflake://{host}/?db={database}&warehouse={warehouse}",
        "default_port": 443,
    },
    "redshift": {
        "driver_class": "com.amazon.redshift.jdbc42.Driver",
        "url_template": "jdbc:redshift://{host}:{port}/{database}",
        "default_port": 5439,
    },
    "trino": {
        "driver_class": "io.trino.jdbc.TrinoDriver",
        "url_template": "jdbc:trino://{host}:{port}/{catalog}/{schema}",
        "default_port": 8080,
    },
    "starrocks": {
        "driver_class": "com.mysql.cj.jdbc.Driver",
        "url_template": "jdbc:mysql://{host}:{port}/{database}",
        "default_port": 9030,
    },
}


class GeneratePySparkTool(BaseTool):
    """Generate PySpark ETL code using catalog metadata."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "generate_pyspark"

    @property
    def description(self) -> str:
        return (
            "Generate a PySpark ETL script that reads from source datasets, "
            "applies transformations, and writes to a target. Uses real schema "
            "and platform connection info from the catalog. "
            "Produces complete, runnable PySpark code with JDBC connections."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source_dataset_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Source dataset IDs to read from.",
                },
                "target_dataset_id": {
                    "type": "integer",
                    "description": "Target dataset ID to write to (optional for new targets).",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "What the ETL should do: joins, filters, aggregations, "
                        "column transformations, deduplication, etc."
                    ),
                },
                "write_mode": {
                    "type": "string",
                    "enum": ["overwrite", "append", "upsert"],
                    "description": "Write mode: overwrite, append, or upsert.",
                    "default": "overwrite",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["jdbc", "parquet", "orc", "csv", "delta"],
                    "description": "Output format (jdbc for DB, parquet for files).",
                    "default": "jdbc",
                },
            },
            "required": ["source_dataset_ids", "description"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(
        self,
        source_dataset_ids: list[int],
        description: str,
        target_dataset_id: int | None = None,
        write_mode: str = "overwrite",
        output_format: str = "jdbc",
    ) -> ToolResult:
        try:
            # Gather source dataset info
            sources = []
            for did in source_dataset_ids:
                detail = await self._catalog.get_dataset(did)
                schema = await self._catalog.get_dataset_schema(did)
                platform_type = detail.get("platform_type", "").lower()

                # Get connection info
                platform_id = detail.get("platform_id")
                conn_info = {}
                if platform_id:
                    try:
                        conn_info = await self._catalog.get_platform_config(platform_id)
                    except Exception:
                        pass

                jdbc = JDBC_DRIVERS.get(platform_type, {})

                sources.append(
                    {
                        "dataset_id": did,
                        "name": detail.get("name", ""),
                        "qualified_name": detail.get("qualified_name", ""),
                        "platform_type": platform_type,
                        "connection": conn_info,
                        "jdbc_driver": jdbc.get("driver_class", ""),
                        "jdbc_url_template": jdbc.get("url_template", ""),
                        "columns": [
                            {
                                "name": col.get("name", ""),
                                "data_type": col.get("data_type", ""),
                                "native_type": col.get("native_type", ""),
                                "nullable": col.get("nullable", True),
                                "is_primary_key": col.get("is_primary_key", False),
                            }
                            for col in (schema if isinstance(schema, list) else [])
                        ],
                    }
                )

            # Gather target info if provided
            target = None
            if target_dataset_id:
                detail = await self._catalog.get_dataset(target_dataset_id)
                schema = await self._catalog.get_dataset_schema(target_dataset_id)
                platform_type = detail.get("platform_type", "").lower()
                platform_id = detail.get("platform_id")
                conn_info = {}
                if platform_id:
                    try:
                        conn_info = await self._catalog.get_platform_config(platform_id)
                    except Exception:
                        pass
                jdbc = JDBC_DRIVERS.get(platform_type, {})
                target = {
                    "dataset_id": target_dataset_id,
                    "name": detail.get("name", ""),
                    "qualified_name": detail.get("qualified_name", ""),
                    "platform_type": platform_type,
                    "connection": conn_info,
                    "jdbc_driver": jdbc.get("driver_class", ""),
                    "jdbc_url_template": jdbc.get("url_template", ""),
                    "columns": [
                        {
                            "name": col.get("name", ""),
                            "data_type": col.get("data_type", ""),
                            "native_type": col.get("native_type", ""),
                            "nullable": col.get("nullable", True),
                            "is_primary_key": col.get("is_primary_key", False),
                        }
                        for col in (schema if isinstance(schema, list) else [])
                    ],
                }

            return ToolResult(
                success=True,
                data={
                    "sources": sources,
                    "target": target,
                    "description": description,
                    "write_mode": write_mode,
                    "output_format": output_format,
                    "instruction": (
                        "Generate a complete PySpark ETL script using the schema and connection "
                        "info above. Include: SparkSession creation, JDBC read with proper driver "
                        "and URL, transformations as described, and write with the specified mode. "
                        "Use exact column names from the schema. Add logging and error handling."
                    ),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
