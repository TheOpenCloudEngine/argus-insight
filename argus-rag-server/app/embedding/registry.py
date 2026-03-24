"""Embedding provider registry — singleton manager."""

import logging

from app.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)
_current_provider: EmbeddingProvider | None = None


async def get_provider() -> EmbeddingProvider | None:
    return _current_provider


async def initialize_provider(
    provider_type: str = "local",
    model_id: str = "paraphrase-multilingual-MiniLM-L12-v2",
    api_key: str = "",
    api_url: str = "",
) -> EmbeddingProvider:
    global _current_provider
    if _current_provider is not None:
        await _current_provider.close()
        _current_provider = None

    if provider_type == "local":
        from app.embedding.providers.local import LocalEmbeddingProvider

        _current_provider = LocalEmbeddingProvider(model_id=model_id)
    elif provider_type == "openai":
        from app.embedding.providers.openai import OpenAIEmbeddingProvider

        _current_provider = OpenAIEmbeddingProvider(
            api_key=api_key,
            model_id=model_id,
            base_url=api_url or "https://api.openai.com/v1",
        )
    elif provider_type == "ollama":
        from app.embedding.providers.ollama import OllamaEmbeddingProvider

        _current_provider = OllamaEmbeddingProvider(
            base_url=api_url or "http://localhost:11434",
            model_id=model_id,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider_type}")

    logger.info("Embedding provider initialized: %s (%s)", provider_type, model_id)
    return _current_provider


async def initialize_from_settings() -> EmbeddingProvider:
    from app.core.config import settings

    return await initialize_provider(
        provider_type=settings.embedding_provider,
        model_id=settings.embedding_model,
        api_key=settings.embedding_api_key,
        api_url=settings.embedding_api_url,
    )


async def shutdown_provider() -> None:
    global _current_provider
    if _current_provider:
        await _current_provider.close()
        _current_provider = None
        logger.info("Embedding provider shut down")
