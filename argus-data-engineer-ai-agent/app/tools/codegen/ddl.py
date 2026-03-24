"""DDL generation tool — generates CREATE TABLE statements.

Produces platform-specific DDL using catalog schema metadata and
platform data type mappings.
"""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult

# Generic catalog type → platform native type mappings
TYPE_MAPPINGS = {
    "mysql": {
        "STRING": "VARCHAR(255)",
        "NUMBER": "BIGINT",
        "DATE": "DATETIME",
        "BOOLEAN": "TINYINT(1)",
        "BYTES": "BLOB",
        "MAP": "JSON",
        "ARRAY": "JSON",
        "ENUM": "VARCHAR(100)",
    },
    "postgresql": {
        "STRING": "TEXT",
        "NUMBER": "BIGINT",
        "DATE": "TIMESTAMP",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "BYTEA",
        "MAP": "JSONB",
        "ARRAY": "TEXT[]",
        "ENUM": "VARCHAR(100)",
    },
    "hive": {
        "STRING": "STRING",
        "NUMBER": "BIGINT",
        "DATE": "TIMESTAMP",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "BINARY",
        "MAP": "MAP<STRING,STRING>",
        "ARRAY": "ARRAY<STRING>",
        "ENUM": "STRING",
    },
    "snowflake": {
        "STRING": "VARCHAR",
        "NUMBER": "NUMBER",
        "DATE": "TIMESTAMP_NTZ",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "BINARY",
        "MAP": "VARIANT",
        "ARRAY": "ARRAY",
        "ENUM": "VARCHAR(100)",
    },
    "redshift": {
        "STRING": "VARCHAR(256)",
        "NUMBER": "BIGINT",
        "DATE": "TIMESTAMP",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "VARCHAR(MAX)",
        "MAP": "SUPER",
        "ARRAY": "SUPER",
        "ENUM": "VARCHAR(100)",
    },
    "starrocks": {
        "STRING": "VARCHAR(255)",
        "NUMBER": "BIGINT",
        "DATE": "DATETIME",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "VARBINARY",
        "MAP": "JSON",
        "ARRAY": "ARRAY<VARCHAR(255)>",
        "ENUM": "VARCHAR(100)",
    },
    "trino": {
        "STRING": "VARCHAR",
        "NUMBER": "BIGINT",
        "DATE": "TIMESTAMP",
        "BOOLEAN": "BOOLEAN",
        "BYTES": "VARBINARY",
        "MAP": "MAP(VARCHAR, VARCHAR)",
        "ARRAY": "ARRAY(VARCHAR)",
        "ENUM": "VARCHAR",
    },
}


class GenerateDDLTool(BaseTool):
    """Generate platform-specific CREATE TABLE DDL from catalog schema."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "generate_ddl"

    @property
    def description(self) -> str:
        return (
            "Generate a CREATE TABLE DDL statement for a target platform based on "
            "an existing dataset's schema in the catalog. Handles data type conversion "
            "between platforms (e.g., MySQL → PostgreSQL, MySQL → Hive). "
            "Can also generate DDL for a new table design."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source_dataset_id": {
                    "type": "integer",
                    "description": "Source dataset ID to base the DDL on.",
                },
                "target_platform": {
                    "type": "string",
                    "enum": [
                        "mysql",
                        "postgresql",
                        "hive",
                        "snowflake",
                        "redshift",
                        "starrocks",
                        "trino",
                    ],
                    "description": "Target platform for the DDL.",
                },
                "target_table_name": {
                    "type": "string",
                    "description": "Target table name (optional, uses source name if omitted).",
                },
                "additional_instructions": {
                    "type": "string",
                    "description": (
                        "Extra instructions: add indexes, partitioning, "
                        "distribution key, storage format, etc."
                    ),
                },
            },
            "required": ["source_dataset_id", "target_platform"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(
        self,
        source_dataset_id: int,
        target_platform: str,
        target_table_name: str | None = None,
        additional_instructions: str = "",
    ) -> ToolResult:
        try:
            detail = await self._catalog.get_dataset(source_dataset_id)
            schema = await self._catalog.get_dataset_schema(source_dataset_id)

            source_platform = detail.get("platform_type", "").lower()
            table_name = target_table_name or detail.get("name", "unknown_table")
            type_map = TYPE_MAPPINGS.get(target_platform, TYPE_MAPPINGS["postgresql"])

            columns_info = []
            for col in schema if isinstance(schema, list) else []:
                generic_type = col.get("data_type", "STRING")
                native_type = col.get("native_type", "")
                target_type = type_map.get(generic_type, type_map.get("STRING", "TEXT"))

                # Preserve precision from native type when possible
                if native_type and "(" in native_type:
                    # e.g., "decimal(10,2)" → keep precision
                    precision = native_type[native_type.index("(") :]
                    base_type = generic_type
                    if base_type == "NUMBER" and "decimal" in native_type.lower():
                        target_type = f"DECIMAL{precision}"

                columns_info.append(
                    {
                        "name": col.get("name", ""),
                        "source_native_type": native_type,
                        "source_generic_type": generic_type,
                        "suggested_target_type": target_type,
                        "nullable": col.get("nullable", True),
                        "is_primary_key": col.get("is_primary_key", False),
                        "is_unique": col.get("is_unique", False),
                        "description": col.get("description", ""),
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "source_dataset": {
                        "id": source_dataset_id,
                        "name": detail.get("name", ""),
                        "platform": source_platform,
                    },
                    "target_platform": target_platform,
                    "target_table_name": table_name,
                    "type_mappings": type_map,
                    "columns": columns_info,
                    "additional_instructions": additional_instructions,
                    "instruction": (
                        "Generate a CREATE TABLE DDL for the target platform. "
                        "Use the suggested_target_type for each column. "
                        "Add PRIMARY KEY, NOT NULL constraints as indicated. "
                        "Apply any additional instructions (partitioning, indexes, etc.)."
                    ),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
