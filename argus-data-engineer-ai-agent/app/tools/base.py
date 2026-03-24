"""Base tool interface for the agent.

All tools implement this interface. The ToolRegistry collects tools and
provides their JSON Schema definitions to the LLM.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Tool safety classification. Higher levels require user approval."""

    AUTO = 0  # Read-only catalog queries — always auto-approved
    AUTO_READ = 1  # Data preview (LIMIT 10) — auto-approved
    APPROVE = 2  # Profiling, quality checks — requires approval
    APPROVE_WRITE = 3  # File writes, pipeline registration — requires approval
    APPROVE_EXEC = 4  # SQL execution (SELECT only) — requires approval
    BLOCKED = 5  # DDL/DML execution — never allowed


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: dict | list | str | None = None
    error: str | None = None

    def to_str(self) -> str:
        """Serialize to a string for the LLM to consume."""
        if self.error:
            return json.dumps({"error": self.error}, ensure_ascii=False)
        if isinstance(self.data, str):
            return self.data
        return json.dumps(self.data, ensure_ascii=False, default=str)


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema for the tool's input parameters."""
        ...

    @property
    def safety_level(self) -> SafetyLevel:
        """Safety classification — defaults to AUTO (read-only)."""
        return SafetyLevel.AUTO

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    def to_schema(self) -> dict:
        """Convert to the internal tool definition format for LLMs."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
