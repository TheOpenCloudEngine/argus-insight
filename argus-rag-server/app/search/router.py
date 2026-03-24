"""Search API router — semantic, keyword, and hybrid search."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import OptionalUser
from app.core.database import get_session
from app.embedding import service as embed_svc
from app.search import service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    collection_ids: str | None = Query(None, description="Comma-separated collection IDs"),
    limit: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Semantic search using vector similarity."""
    coll_ids = _parse_collection_ids(collection_ids)
    try:
        results = await service.semantic_search(session, q, coll_ids, limit, threshold)
        return {"query": q, "results": results, "total": len(results)}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/keyword")
async def keyword_search(
    q: str = Query(..., min_length=1),
    collection_ids: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Keyword (ILIKE) search across documents."""
    coll_ids = _parse_collection_ids(collection_ids)
    results = await service.keyword_search(session, q, coll_ids, limit)
    return {"query": q, "results": results, "total": len(results)}


@router.get("/hybrid")
async def hybrid_search(
    q: str = Query(..., min_length=1),
    collection_ids: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
    keyword_weight: float = Query(0.3, ge=0.0, le=1.0),
    semantic_weight: float = Query(0.7, ge=0.0, le=1.0),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Hybrid search combining keyword and semantic results."""
    coll_ids = _parse_collection_ids(collection_ids)
    results = await service.hybrid_search(
        session,
        q,
        coll_ids,
        limit,
        threshold,
        keyword_weight,
        semantic_weight,
    )
    return {"query": q, "results": results, "total": len(results)}


# ---------------------------------------------------------------------------
# Embedding operations
# ---------------------------------------------------------------------------


@router.post("/collections/{collection_id}/embed")
async def embed_collection(
    collection_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate embeddings for all un-embedded chunks in a collection."""
    result = await embed_svc.embed_collection(session, collection_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/collections/{collection_id}/embeddings")
async def clear_embeddings(
    collection_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Clear all embeddings for a collection (for re-embedding after model change)."""
    count = await embed_svc.clear_embeddings(session, collection_id)
    return {"cleared": count}


@router.get("/collections/{collection_id}/stats")
async def embedding_stats(
    collection_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get embedding coverage stats for a collection."""
    return await embed_svc.get_embedding_stats(session, collection_id)


def _parse_collection_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        return None
