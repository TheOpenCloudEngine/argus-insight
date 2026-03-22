"""Semantic and hybrid search API endpoints.

Provides semantic search (pgvector cosine similarity), hybrid search
(keyword + semantic), and embedding management endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.embedding import service as embedding_service
from app.embedding.registry import get_provider
from app.search import service
from app.search.schemas import SemanticSearchResponse, SemanticSearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog/search", tags=["search"])


# ---------------------------------------------------------------------------
# Search endpoints
# ---------------------------------------------------------------------------

@router.get("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.3, ge=0.0, le=1.0, description="Min cosine similarity"),
    session: AsyncSession = Depends(get_session),
):
    """Semantic search across datasets using vector similarity."""
    logger.info("GET /catalog/search/semantic: q='%s', limit=%d", q, limit)
    provider = await get_provider()
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding provider not configured. Enable it in Settings > Embedding.",
        )

    try:
        results = await service.semantic_search(session, q, limit=limit, threshold=threshold)
    except Exception as e:
        logger.error("Semantic search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    items = []
    for ds_id, score in results:
        summary = await service._build_dataset_summary(session, ds_id)
        if summary:
            items.append(SemanticSearchResult(
                dataset=summary, score=round(score, 4), match_type="semantic",
            ))

    return SemanticSearchResponse(
        items=items, total=len(items), query=q,
        provider=provider.provider_name(), model=provider.model_name(),
    )


@router.get("/hybrid", response_model=SemanticSearchResponse)
async def hybrid_search(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
    keyword_weight: float = Query(0.3, ge=0.0, le=1.0),
    semantic_weight: float = Query(0.7, ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_session),
):
    """Hybrid search combining keyword matching and semantic similarity.

    Falls back to keyword-only search when embedding provider is not configured.
    """
    logger.info("GET /catalog/search/hybrid: q='%s', kw=%.1f, sem=%.1f", q, keyword_weight, semantic_weight)
    try:
        results = await service.hybrid_search(
            session, q, limit=limit, threshold=threshold,
            keyword_weight=keyword_weight, semantic_weight=semantic_weight,
        )
    except Exception as e:
        logger.error("Hybrid search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    provider = await get_provider()
    items = []
    for ds_id, score, match_type in results:
        summary = await service._build_dataset_summary(session, ds_id)
        if summary:
            items.append(SemanticSearchResult(
                dataset=summary, score=round(score, 4), match_type=match_type,
            ))

    return SemanticSearchResponse(
        items=items, total=len(items), query=q,
        provider=provider.provider_name() if provider else None,
        model=provider.model_name() if provider else None,
    )


# ---------------------------------------------------------------------------
# Embedding management endpoints
# ---------------------------------------------------------------------------

@router.get("/embeddings/stats")
async def get_embedding_stats(session: AsyncSession = Depends(get_session)):
    """Get embedding coverage statistics."""
    return await embedding_service.get_embedding_stats(session)


@router.post("/embeddings/backfill")
async def backfill_embeddings(session: AsyncSession = Depends(get_session)):
    """Re-embed all datasets. May take time for large catalogs."""
    logger.info("POST /catalog/search/embeddings/backfill")
    provider = await get_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="Embedding provider not configured")

    result = await embedding_service.embed_all_datasets(session)
    return result


@router.delete("/embeddings")
async def clear_embeddings(session: AsyncSession = Depends(get_session)):
    """Delete all embeddings (e.g. before provider switch)."""
    logger.info("DELETE /catalog/search/embeddings")
    count = await embedding_service.clear_all_embeddings(session)
    return {"deleted": count}
