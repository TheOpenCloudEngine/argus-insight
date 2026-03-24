"""LLM provider registry — singleton manager.

Manages the active LLM provider lifecycle. Loads configuration from
settings and creates the appropriate provider instance.
"""

import logging

from app.llm.base import AgentLLMProvider

logger = logging.getLogger(__name__)

_current_provider: AgentLLMProvider | None = None


async def get_provider() -> AgentLLMProvider | None:
    """Return the current LLM provider, or None if not initialized."""
    return _current_provider


async def initialize_provider(
    provider_type: str = "anthropic",
    model_id: str = "claude-sonnet-4-20250514",
    api_key: str = "",
    api_url: str = "",
) -> AgentLLMProvider:
    """Create and set the active LLM provider.

    Closes any existing provider before creating a new one.
    """
    global _current_provider

    if _current_provider is not None:
        await _current_provider.close()
        _current_provider = None

    if provider_type == "anthropic":
        from app.llm.providers.anthropic import AnthropicProvider

        _current_provider = AnthropicProvider(
            api_key=api_key,
            model_id=model_id,
            base_url=api_url or "https://api.anthropic.com",
        )

    elif provider_type == "openai":
        from app.llm.providers.openai import OpenAIProvider

        _current_provider = OpenAIProvider(
            api_key=api_key,
            model_id=model_id,
            base_url=api_url or "https://api.openai.com/v1",
        )

    elif provider_type == "ollama":
        from app.llm.providers.ollama import OllamaProvider

        _current_provider = OllamaProvider(
            base_url=api_url or "http://localhost:11434",
            model_id=model_id,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")

    logger.info(
        "LLM provider initialized: %s (model=%s)",
        provider_type,
        _current_provider.model_name(),
    )
    return _current_provider


async def initialize_from_settings() -> AgentLLMProvider:
    """Initialize the LLM provider from application settings."""
    from app.core.config import settings

    return await initialize_provider(
        provider_type=settings.llm_provider,
        model_id=settings.llm_model,
        api_key=settings.llm_api_key,
        api_url=settings.llm_api_url,
    )


async def shutdown_provider() -> None:
    """Close and release the current provider."""
    global _current_provider
    if _current_provider:
        await _current_provider.close()
        _current_provider = None
        logger.info("LLM provider shut down")
