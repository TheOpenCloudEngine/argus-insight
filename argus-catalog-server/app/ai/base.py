"""Abstract base class for LLM providers.

All LLM providers (OpenAI, Ollama, Anthropic) implement this interface.
The registry module manages the active provider as a singleton.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Pluggable LLM provider interface."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict:
        """Send a prompt and return the response with metadata.

        Returns:
            dict with keys:
                - "text": generated text (str)
                - "prompt_tokens": input token count (int or None)
                - "completion_tokens": output token count (int or None)
        """
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider type: 'openai', 'ollama', 'anthropic'."""
        ...

    async def close(self) -> None:
        """Release resources. Override if cleanup is needed."""
        pass
