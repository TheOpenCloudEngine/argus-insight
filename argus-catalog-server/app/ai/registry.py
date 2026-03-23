"""LLM provider registry — singleton manager.

Manages the active LLM provider lifecycle. Loads configuration from the
catalog_configuration DB table and creates the appropriate provider instance.
"""

import logging

from app.ai.base import LLMProvider

logger = logging.getLogger(__name__)

_current_provider: LLMProvider | None = None


async def get_provider() -> LLMProvider | None:
    """Return the current LLM provider, or None if not initialized."""
    return _current_provider


async def initialize_provider(config: dict[str, str]) -> LLMProvider:
    """Create and set the active LLM provider from DB configuration.

    Closes any existing provider before creating a new one.
    """
    global _current_provider

    if _current_provider is not None:
        await _current_provider.close()
        _current_provider = None

    provider_type = config.get("llm_provider", "openai")
    model_id = config.get("llm_model", "gpt-4o-mini")

    if provider_type == "openai":
        from app.ai.providers.openai import OpenAILLMProvider
        _current_provider = OpenAILLMProvider(
            api_key=config.get("llm_api_key", ""),
            model_id=model_id,
            base_url=config.get("llm_api_url", "") or "https://api.openai.com/v1",
        )

    elif provider_type == "ollama":
        from app.ai.providers.ollama import OllamaLLMProvider
        _current_provider = OllamaLLMProvider(
            base_url=config.get("llm_api_url", "") or "http://localhost:11434",
            model_id=model_id,
        )

    elif provider_type == "anthropic":
        from app.ai.providers.anthropic import AnthropicLLMProvider
        _current_provider = AnthropicLLMProvider(
            api_key=config.get("llm_api_key", ""),
            model_id=model_id,
            base_url=config.get("llm_api_url", "") or "https://api.anthropic.com",
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")

    logger.info(
        "LLM provider initialized: %s (model=%s)",
        provider_type, _current_provider.model_name(),
    )
    return _current_provider


async def shutdown_provider() -> None:
    """Close and release the current provider."""
    global _current_provider
    if _current_provider:
        await _current_provider.close()
        _current_provider = None
        logger.info("LLM provider shut down")
