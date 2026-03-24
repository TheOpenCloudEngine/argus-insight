"""Settings API — embedding model and chunking configuration."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class EmbeddingSettings(BaseModel):
    provider: str
    model: str
    api_url: str
    dimension: int


class EmbeddingSettingsUpdate(BaseModel):
    provider: str = Field(..., description="local, openai, ollama")
    model: str = Field(...)
    api_key: str = ""
    api_url: str = ""


class ChunkingSettings(BaseModel):
    default_strategy: str
    max_chunk_size: int
    min_chunk_size: int
    overlap: int


class ChunkingSettingsUpdate(BaseModel):
    default_strategy: str = "paragraph"
    max_chunk_size: int = Field(512, ge=100, le=4096)
    min_chunk_size: int = Field(50, ge=10, le=500)
    overlap: int = Field(50, ge=0, le=500)


@router.get("/embedding", response_model=EmbeddingSettings)
async def get_embedding_settings(user: CurrentUser):
    return EmbeddingSettings(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        api_url=settings.embedding_api_url,
        dimension=settings.embedding_dimension,
    )


@router.put("/embedding", response_model=EmbeddingSettings)
async def update_embedding_settings(body: EmbeddingSettingsUpdate, user: CurrentUser):
    """Update embedding provider and reinitialize."""
    settings.embedding_provider = body.provider
    settings.embedding_model = body.model
    settings.embedding_api_key = body.api_key
    settings.embedding_api_url = body.api_url

    from app.embedding.registry import initialize_provider

    try:
        provider = await initialize_provider(
            provider_type=body.provider,
            model_id=body.model,
            api_key=body.api_key,
            api_url=body.api_url,
        )
        settings.embedding_dimension = provider.dimension()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed: {e}")

    logger.info("Embedding settings updated: %s / %s", body.provider, body.model)
    return EmbeddingSettings(
        provider=body.provider,
        model=body.model,
        api_url=body.api_url,
        dimension=settings.embedding_dimension,
    )


@router.get("/chunking", response_model=ChunkingSettings)
async def get_chunking_settings(user: CurrentUser):
    return ChunkingSettings(
        default_strategy=settings.chunk_default_strategy,
        max_chunk_size=settings.chunk_max_size,
        min_chunk_size=settings.chunk_min_size,
        overlap=settings.chunk_overlap,
    )


@router.put("/chunking", response_model=ChunkingSettings)
async def update_chunking_settings(body: ChunkingSettingsUpdate, user: CurrentUser):
    settings.chunk_default_strategy = body.default_strategy
    settings.chunk_max_size = body.max_chunk_size
    settings.chunk_min_size = body.min_chunk_size
    settings.chunk_overlap = body.overlap
    logger.info("Chunking settings updated: strategy=%s", body.default_strategy)
    return ChunkingSettings(
        default_strategy=body.default_strategy,
        max_chunk_size=body.max_chunk_size,
        min_chunk_size=body.min_chunk_size,
        overlap=body.overlap,
    )
