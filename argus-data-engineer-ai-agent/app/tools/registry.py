"""Tool registry — collects all available tools and dispatches execution.

The registry is the bridge between the agent engine and individual tools.
It provides tool schemas to the LLM and routes tool calls to the right handler.
"""

import logging

from app.core.config import settings
from app.tools.base import BaseTool, SafetyLevel, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its name."""
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_tool_definitions(self) -> list[dict]:
        """Return all tool schemas in the format expected by LLM providers."""
        return [tool.to_schema() for tool in self._tools.values()]

    def requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval before execution."""
        tool = self._tools.get(tool_name)
        if not tool:
            return True  # Unknown tools always require approval

        level = tool.safety_level

        if level == SafetyLevel.BLOCKED:
            return True  # Will be blocked regardless
        if level in (SafetyLevel.AUTO, SafetyLevel.AUTO_READ):
            return False
        if level == SafetyLevel.APPROVE and settings.agent_auto_approve_reads:
            # Profiling/quality checks auto-approved if configured
            return False
        if level in (SafetyLevel.APPROVE_WRITE, SafetyLevel.APPROVE_EXEC):
            return not settings.agent_auto_approve_writes
        return True

    def is_blocked(self, tool_name: str) -> bool:
        """Check if a tool is blocked from execution entirely."""
        tool = self._tools.get(tool_name)
        return tool is not None and tool.safety_level == SafetyLevel.BLOCKED

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        """Execute a tool by name with the given arguments."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        if tool.safety_level == SafetyLevel.BLOCKED:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' is blocked for safety. Generate code instead.",
            )

        try:
            result = await tool.execute(**arguments)
            logger.info("Tool '%s' executed: success=%s", name, result.success)
            return result
        except Exception as e:
            logger.exception("Tool '%s' execution failed", name)
            return ToolResult(success=False, error=str(e))

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)
