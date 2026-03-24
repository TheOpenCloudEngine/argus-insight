"""Pipeline config generation tool — Airflow DAG, Kestra Flow.

Generates scheduler configuration files using catalog metadata.
"""

from app.catalog_client.client import CatalogClient
from app.tools.base import BaseTool, SafetyLevel, ToolResult


class GeneratePipelineConfigTool(BaseTool):
    """Generate pipeline orchestration config (Airflow DAG, Kestra flow)."""

    def __init__(self, catalog: CatalogClient) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "generate_pipeline_config"

    @property
    def description(self) -> str:
        return (
            "Generate a pipeline orchestration configuration file: "
            "Airflow DAG (Python), Kestra Flow (YAML), or a generic cron job. "
            "Uses catalog metadata for source/target datasets and scheduling. "
            "Produces a complete, runnable configuration file."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "orchestrator": {
                    "type": "string",
                    "enum": ["airflow", "kestra"],
                    "description": "Target orchestrator.",
                },
                "pipeline_name": {
                    "type": "string",
                    "description": "Pipeline/DAG name.",
                },
                "description": {
                    "type": "string",
                    "description": "What the pipeline does.",
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression or preset (@daily, @hourly, etc.).",
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
                "task_type": {
                    "type": "string",
                    "enum": ["spark_submit", "sql", "python", "bash"],
                    "description": "Type of task to run in the pipeline.",
                    "default": "spark_submit",
                },
                "retries": {
                    "type": "integer",
                    "description": "Number of retries on failure (default 2).",
                    "default": 2,
                },
            },
            "required": ["orchestrator", "pipeline_name", "schedule"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(
        self,
        orchestrator: str,
        pipeline_name: str,
        schedule: str,
        description: str = "",
        source_dataset_ids: list[int] | None = None,
        target_dataset_ids: list[int] | None = None,
        task_type: str = "spark_submit",
        retries: int = 2,
    ) -> ToolResult:
        try:
            # Gather source/target dataset info
            sources = []
            for did in source_dataset_ids or []:
                detail = await self._catalog.get_dataset(did)
                sources.append(
                    {
                        "dataset_id": did,
                        "name": detail.get("name", ""),
                        "platform_type": detail.get("platform_type", ""),
                        "qualified_name": detail.get("qualified_name", ""),
                    }
                )

            targets = []
            for did in target_dataset_ids or []:
                detail = await self._catalog.get_dataset(did)
                targets.append(
                    {
                        "dataset_id": did,
                        "name": detail.get("name", ""),
                        "platform_type": detail.get("platform_type", ""),
                        "qualified_name": detail.get("qualified_name", ""),
                    }
                )

            templates = {
                "airflow": {
                    "file_type": "python",
                    "file_extension": ".py",
                    "structure_hint": (
                        "Generate a complete Airflow DAG Python file with: "
                        "DAG definition (dag_id, schedule, default_args with retries), "
                        "task definitions (operator based on task_type), "
                        "task dependencies. Use Airflow 2.x TaskFlow API or classic operators."
                    ),
                },
                "kestra": {
                    "file_type": "yaml",
                    "file_extension": ".yml",
                    "structure_hint": (
                        "Generate a Kestra flow YAML with: "
                        "id, namespace, description, triggers (schedule), "
                        "tasks (type based on task_type). Use Kestra's plugin ecosystem."
                    ),
                },
            }

            template = templates.get(orchestrator, templates["airflow"])

            return ToolResult(
                success=True,
                data={
                    "orchestrator": orchestrator,
                    "pipeline_name": pipeline_name,
                    "description": description,
                    "schedule": schedule,
                    "task_type": task_type,
                    "retries": retries,
                    "sources": sources,
                    "targets": targets,
                    "template": template,
                    "instruction": (
                        f"Generate a complete {orchestrator} "
                        f"configuration ({template['file_extension']}) for the pipeline. "
                        "Include proper scheduling, task definitions, retries, "
                        "and source/target metadata as comments."
                    ),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
