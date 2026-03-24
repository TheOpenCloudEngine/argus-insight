"""SQL generation tool — generates SELECT, INSERT, MERGE queries.

Uses catalog schema metadata to produce accurate, platform-specific SQL.
The LLM decides WHAT to generate; this tool provides structured context
and formatting guidelines to ensure correctness.
"""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult

# Platform-specific SQL dialect hints for the LLM
DIALECT_HINTS = {
    "mysql": {
        "quoting": "backtick (`table`)",
        "limit": "LIMIT n",
        "string_concat": "CONCAT(a, b)",
        "current_timestamp": "NOW()",
        "upsert": "INSERT ... ON DUPLICATE KEY UPDATE",
        "date_format": "DATE_FORMAT(col, '%Y-%m-%d')",
        "type_cast": "CAST(col AS type)",
        "boolean": "TINYINT(1) — 0/1",
        "auto_increment": "AUTO_INCREMENT",
        "json_extract": "JSON_EXTRACT(col, '$.key') or col->'$.key'",
    },
    "postgresql": {
        "quoting": 'double-quote ("table")',
        "limit": "LIMIT n",
        "string_concat": "a || b",
        "current_timestamp": "NOW() or CURRENT_TIMESTAMP",
        "upsert": "INSERT ... ON CONFLICT DO UPDATE",
        "date_format": "TO_CHAR(col, 'YYYY-MM-DD')",
        "type_cast": "col::type or CAST(col AS type)",
        "boolean": "BOOLEAN — true/false",
        "auto_increment": "SERIAL / GENERATED ALWAYS AS IDENTITY",
        "json_extract": "col->>'key' or jsonb_extract_path_text()",
    },
    "hive": {
        "quoting": "backtick (`table`)",
        "limit": "LIMIT n",
        "string_concat": "CONCAT(a, b)",
        "current_timestamp": "CURRENT_TIMESTAMP",
        "upsert": "INSERT OVERWRITE (no true upsert)",
        "date_format": "DATE_FORMAT(col, 'yyyy-MM-dd')",
        "type_cast": "CAST(col AS type)",
        "boolean": "BOOLEAN — true/false",
        "partitioning": "PARTITIONED BY (col type)",
        "storage": "STORED AS ORC/PARQUET/TEXTFILE",
    },
    "snowflake": {
        "quoting": 'double-quote ("TABLE")',
        "limit": "LIMIT n",
        "string_concat": "a || b or CONCAT(a, b)",
        "current_timestamp": "CURRENT_TIMESTAMP()",
        "upsert": "MERGE INTO ... USING ... WHEN MATCHED THEN UPDATE",
        "date_format": "TO_CHAR(col, 'YYYY-MM-DD')",
        "type_cast": "col::type or CAST(col AS type)",
        "boolean": "BOOLEAN — true/false",
        "variant": "VARIANT for semi-structured JSON",
    },
    "redshift": {
        "quoting": 'double-quote ("table")',
        "limit": "LIMIT n",
        "string_concat": "a || b",
        "current_timestamp": "GETDATE() or SYSDATE",
        "upsert": "DELETE+INSERT pattern (no native MERGE pre-2023)",
        "date_format": "TO_CHAR(col, 'YYYY-MM-DD')",
        "type_cast": "CAST(col AS type)",
        "sortkey": "SORTKEY(col) — for query performance",
        "distkey": "DISTKEY(col) — for distribution",
    },
    "trino": {
        "quoting": 'double-quote ("table")',
        "limit": "LIMIT n",
        "string_concat": "a || b or CONCAT(a, b)",
        "current_timestamp": "CURRENT_TIMESTAMP",
        "upsert": "MERGE INTO (Trino 380+)",
        "date_format": "FORMAT_DATETIME(col, 'yyyy-MM-dd')",
        "type_cast": "CAST(col AS type)",
        "cross_catalog": "catalog.schema.table referencing supported",
    },
    "starrocks": {
        "quoting": "backtick (`table`)",
        "limit": "LIMIT n",
        "string_concat": "CONCAT(a, b)",
        "current_timestamp": "NOW()",
        "upsert": "INSERT INTO ... ON DUPLICATE KEY UPDATE (Primary Key model)",
        "date_format": "DATE_FORMAT(col, '%Y-%m-%d')",
        "type_cast": "CAST(col AS type)",
        "model": "Duplicate/Aggregate/Unique/Primary Key table models",
    },
}


class GenerateSQLTool(BaseTool):
    """Generate platform-specific SQL queries using catalog metadata."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "generate_sql"

    @property
    def description(self) -> str:
        return (
            "Generate a SQL query (SELECT, INSERT, MERGE, aggregation, join, etc.) "
            "using the actual schema from the catalog. Provide the dataset IDs and "
            "describe what the query should do. The generated SQL uses exact column "
            "names and platform-specific dialect."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Dataset IDs involved in the query.",
                },
                "query_type": {
                    "type": "string",
                    "enum": [
                        "SELECT",
                        "INSERT_SELECT",
                        "MERGE_UPSERT",
                        "AGGREGATION",
                        "JOIN",
                        "WINDOW",
                        "CTE",
                        "CUSTOM",
                    ],
                    "description": "Type of SQL query to generate.",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Natural language description of what the query should do. "
                        "Be specific about filters, joins, aggregations, etc."
                    ),
                },
                "target_platform_type": {
                    "type": "string",
                    "description": (
                        "Target platform SQL dialect (mysql, postgresql, hive, etc.). "
                        "If omitted, uses the source dataset's platform."
                    ),
                },
            },
            "required": ["dataset_ids", "query_type", "description"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(
        self,
        dataset_ids: list[int],
        query_type: str,
        description: str,
        target_platform_type: str | None = None,
    ) -> ToolResult:
        try:
            # Gather schema info for all datasets
            datasets_info = []
            for did in dataset_ids:
                detail = await self._catalog.get_dataset(did)
                schema = await self._catalog.get_dataset_schema(did)
                datasets_info.append(
                    {
                        "dataset_id": did,
                        "name": detail.get("name", ""),
                        "qualified_name": detail.get("qualified_name", ""),
                        "platform_type": detail.get("platform_type", ""),
                        "description": detail.get("description", ""),
                        "columns": [
                            {
                                "name": col.get("name", ""),
                                "data_type": col.get("data_type", ""),
                                "native_type": col.get("native_type", ""),
                                "nullable": col.get("nullable", True),
                                "is_primary_key": col.get("is_primary_key", False),
                                "is_unique": col.get("is_unique", False),
                                "description": col.get("description", ""),
                            }
                            for col in (schema if isinstance(schema, list) else [])
                        ],
                    }
                )

            # Determine platform dialect
            platform = target_platform_type
            if not platform and datasets_info:
                platform = datasets_info[0].get("platform_type", "").lower()
            dialect = DIALECT_HINTS.get(platform, DIALECT_HINTS.get("postgresql", {}))

            return ToolResult(
                success=True,
                data={
                    "datasets": datasets_info,
                    "query_type": query_type,
                    "description": description,
                    "target_platform": platform,
                    "dialect_hints": dialect,
                    "instruction": (
                        "Generate the SQL query using the exact column names and types above. "
                        "Apply the dialect hints for the target platform. "
                        "Include comments explaining key parts of the query."
                    ),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
