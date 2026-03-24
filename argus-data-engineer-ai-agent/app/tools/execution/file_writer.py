"""File writer tool — saves generated code to files.

Writes generated code (SQL, Python, YAML, etc.) to a specified directory.
Uses a configurable workspace directory for safety.
"""

import logging
from pathlib import Path

from app.tools.base import BaseTool, SafetyLevel, ToolResult

logger = logging.getLogger(__name__)

# Default workspace for generated files
DEFAULT_WORKSPACE = "/tmp/argus-de-agent/workspace"


class WriteFileTool(BaseTool):
    """Write generated code to a file."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write generated code or configuration to a file. "
            "Files are saved to the agent's workspace directory. "
            "Use this after generating SQL, PySpark, Airflow DAG, or other code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": (
                        "Filename with extension (e.g., 'etl_pipeline.py', "
                        "'create_table.sql', 'dag_pipeline.py')."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "File content to write.",
                },
                "subdirectory": {
                    "type": "string",
                    "description": (
                        "Optional subdirectory within the workspace "
                        "(e.g., 'sql', 'pyspark', 'dags')."
                    ),
                },
            },
            "required": ["filename", "content"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.APPROVE_WRITE

    async def execute(
        self,
        filename: str,
        content: str,
        subdirectory: str = "",
    ) -> ToolResult:
        try:
            # Determine workspace directory
            workspace = Path(DEFAULT_WORKSPACE)

            if subdirectory:
                workspace = workspace / subdirectory

            # Security: prevent path traversal
            safe_filename = Path(filename).name
            if not safe_filename:
                return ToolResult(success=False, error="Invalid filename.")

            filepath = workspace / safe_filename
            resolved = filepath.resolve()
            workspace_resolved = Path(DEFAULT_WORKSPACE).resolve()

            if not str(resolved).startswith(str(workspace_resolved)):
                return ToolResult(
                    success=False,
                    error="Path traversal detected. File must be within workspace.",
                )

            # Create directory and write file
            workspace.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")

            logger.info("File written: %s (%d bytes)", filepath, len(content))
            return ToolResult(
                success=True,
                data={
                    "filepath": str(filepath),
                    "filename": safe_filename,
                    "size_bytes": len(content),
                    "lines": content.count("\n") + 1,
                },
            )
        except Exception as e:
            logger.exception("File write failed")
            return ToolResult(success=False, error=str(e))


class ReadFileTool(BaseTool):
    """Read a previously generated file from the workspace."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read a file from the agent's workspace directory. "
            "Useful for reviewing or modifying previously generated code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename to read.",
                },
                "subdirectory": {
                    "type": "string",
                    "description": "Subdirectory within workspace.",
                },
            },
            "required": ["filename"],
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(
        self,
        filename: str,
        subdirectory: str = "",
    ) -> ToolResult:
        try:
            workspace = Path(DEFAULT_WORKSPACE)
            if subdirectory:
                workspace = workspace / subdirectory

            filepath = workspace / Path(filename).name
            resolved = filepath.resolve()
            workspace_resolved = Path(DEFAULT_WORKSPACE).resolve()

            if not str(resolved).startswith(str(workspace_resolved)):
                return ToolResult(success=False, error="Path traversal detected.")

            if not filepath.is_file():
                return ToolResult(success=False, error=f"File not found: {filepath}")

            content = filepath.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                data={
                    "filepath": str(filepath),
                    "content": content,
                    "size_bytes": len(content),
                    "lines": content.count("\n") + 1,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ListFilesTool(BaseTool):
    """List files in the agent's workspace directory."""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List all files in the agent's workspace directory."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "subdirectory": {
                    "type": "string",
                    "description": "Subdirectory to list (optional).",
                },
            },
        }

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.AUTO

    async def execute(self, subdirectory: str = "") -> ToolResult:
        try:
            workspace = Path(DEFAULT_WORKSPACE)
            if subdirectory:
                workspace = workspace / subdirectory

            if not workspace.is_dir():
                return ToolResult(
                    success=True,
                    data={"files": [], "message": "Workspace is empty."},
                )

            files = []
            for f in sorted(workspace.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(Path(DEFAULT_WORKSPACE))
                    files.append(
                        {
                            "path": str(rel),
                            "size_bytes": f.stat().st_size,
                        }
                    )

            return ToolResult(success=True, data={"files": files})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
