"""Abstract base class for Agent LLM providers.

Unlike the catalog server's simple generate() interface, agent providers
must support the tool_use protocol so the ReAct engine can call tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Structured response from an LLM that may contain text and/or tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop_reason: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class AgentLLMProvider(ABC):
    """Pluggable LLM provider interface with tool_use support."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send messages with optional tool definitions and return structured response.

        Args:
            messages: Conversation history in provider-native format.
            tools: Tool definitions for the LLM to choose from.
            system_prompt: System-level instructions.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with text and/or tool_calls.
        """
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider type: 'anthropic', 'openai', 'ollama'."""
        ...

    async def close(self) -> None:
        """Release resources. Override if cleanup is needed."""
        pass
