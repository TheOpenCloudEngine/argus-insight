"""Multi-collection semantic and hybrid search service."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding.registry import get_provider

logger = logging.getLogger(__name__)


async def semantic_search(
    session: AsyncSession,
    query: str,
    collection_ids: list[int] | None = None,
    limit: int = 20,
    threshold: float = 0.3,
) -> list[dict]:
    """Semantic search across one or more collections using pgvector.

    Returns list of dicts with: chunk_id, document_id, collection_id,
    collection_name, title, chunk_text, similarity.
    """
    provider = await get_provider()
    if provider is None:
        raise ValueError("Embedding provider not initialized")

    query_vectors = await provider.embed([query])
    query_vec = query_vectors[0]

    # Build collection filter
    coll_filter = ""
    params: dict = {
        "query_vec": str(query_vec),
        "threshold": threshold,
        "lim": limit,
    }
    if collection_ids:
        coll_filter = "AND c.collection_id = ANY(:coll_ids)"
        params["coll_ids"] = collection_ids

    sql = f"""
        SELECT c.id AS chunk_id,
               c.document_id,
               c.collection_id,
               col.name AS collection_name,
               d.title,
               d.external_id,
               c.chunk_text,
               1 - (c.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM rag_document_chunks c
        JOIN rag_documents d ON d.id = c.document_id
        JOIN rag_collections col ON col.id = c.collection_id
        WHERE c.embedding IS NOT NULL
          AND 1 - (c.embedding <=> CAST(:query_vec AS vector)) >= :threshold
          {coll_filter}
        ORDER BY c.embedding <=> CAST(:query_vec AS vector)
        LIMIT :lim
    """

    result = await session.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "collection_id": row.collection_id,
            "collection_name": row.collection_name,
            "title": row.title,
            "external_id": row.external_id,
            "chunk_text": row.chunk_text,
            "similarity": round(float(row.similarity), 4),
            "match_type": "semantic",
        }
        for row in rows
    ]


async def keyword_search(
    session: AsyncSession,
    query: str,
    collection_ids: list[int] | None = None,
    limit: int = 50,
) -> list[dict]:
    """Keyword (ILIKE) search across documents."""
    pattern = f"%{query}%"

    coll_filter = ""
    params: dict = {"pattern": pattern, "lim": limit}
    if collection_ids:
        coll_filter = "AND d.collection_id = ANY(:coll_ids)"
        params["coll_ids"] = collection_ids

    sql = f"""
        SELECT d.id AS document_id,
               d.collection_id,
               col.name AS collection_name,
               d.title,
               d.external_id,
               d.source_text
        FROM rag_documents d
        JOIN rag_collections col ON col.id = d.collection_id
        WHERE (d.title ILIKE :pattern OR d.source_text ILIKE :pattern
               OR d.external_id ILIKE :pattern)
          {coll_filter}
        LIMIT :lim
    """

    result = await session.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "document_id": row.document_id,
            "collection_id": row.collection_id,
            "collection_name": row.collection_name,
            "title": row.title,
            "external_id": row.external_id,
            "chunk_text": row.source_text[:500],
            "similarity": 1.0,
            "match_type": "keyword",
        }
        for row in rows
    ]


async def hybrid_search(
    session: AsyncSession,
    query: str,
    collection_ids: list[int] | None = None,
    limit: int = 20,
    threshold: float = 0.3,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
) -> list[dict]:
    """Combine keyword and semantic search with weighted scoring.

    Falls back to keyword-only if embedding provider is unavailable.
    """
    provider = await get_provider()

    # Semantic results
    semantic_map: dict[str, dict] = {}
    if provider is not None:
        try:
            sem_results = await semantic_search(
                session, query, collection_ids, limit=limit * 2, threshold=threshold
            )
            for r in sem_results:
                key = f"{r['collection_id']}:{r.get('chunk_id', r['document_id'])}"
                semantic_map[key] = r
        except Exception as e:
            logger.warning("Semantic search failed, keyword fallback: %s", e)

    # Keyword results
    kw_results = await keyword_search(session, query, collection_ids, limit=limit * 2)
    kw_map: dict[str, dict] = {}
    for r in kw_results:
        key = f"{r['collection_id']}:{r['document_id']}"
        kw_map[key] = r

    # Merge
    all_keys = set(semantic_map.keys()) | set(kw_map.keys())
    scored: list[dict] = []

    for key in all_keys:
        sem = semantic_map.get(key)
        kw = kw_map.get(key)

        sem_score = sem["similarity"] if sem else 0.0
        kw_score = 1.0 if kw else 0.0

        if semantic_map:
            combined = semantic_weight * sem_score + keyword_weight * kw_score
        else:
            combined = kw_score

        base = sem or kw
        if sem_score > 0 and kw_score > 0:
            match_type = "hybrid"
        elif sem_score > 0:
            match_type = "semantic"
        else:
            match_type = "keyword"

        scored.append(
            {
                **base,
                "similarity": round(combined, 4),
                "match_type": match_type,
            }
        )

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:limit]
