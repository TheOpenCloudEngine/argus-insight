"""Semantic and hybrid search service.

Provides cosine-similarity based semantic search via pgvector,
with optional hybrid scoring that combines keyword and semantic results.
"""

import logging

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Dataset, DatasetTag, Owner, Platform
from app.catalog.schemas import DatasetSummary
from app.embedding.models import DatasetEmbedding
from app.embedding.registry import get_provider

logger = logging.getLogger(__name__)


async def semantic_search(
    session: AsyncSession,
    query: str,
    limit: int = 20,
    threshold: float = 0.3,
) -> list[tuple[int, float]]:
    """Perform semantic search using pgvector cosine similarity.

    Returns list of (dataset_id, similarity_score) ordered by relevance.
    Raises ValueError if the embedding provider is not initialized.
    """
    provider = await get_provider()
    if provider is None:
        raise ValueError("Embedding provider not initialized. Enable it in Settings.")

    # Embed the query
    query_vectors = await provider.embed([query])
    query_vec = query_vectors[0]

    # pgvector cosine distance operator: <=>
    # similarity = 1 - cosine_distance
    # Note: use CAST() instead of ::vector to avoid SQLAlchemy text() parameter conflict with ::
    result = await session.execute(text("""
        SELECT e.dataset_id,
               1 - (e.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM catalog_dataset_embeddings e
        JOIN catalog_datasets d ON d.id = e.dataset_id
        WHERE d.status != 'removed'
          AND 1 - (e.embedding <=> CAST(:query_vec AS vector)) >= :threshold
        ORDER BY e.embedding <=> CAST(:query_vec AS vector)
        LIMIT :lim
    """), {
        "query_vec": str(query_vec),
        "threshold": threshold,
        "lim": limit,
    })

    results = [(row[0], float(row[1])) for row in result.fetchall()]
    logger.info("Semantic search: q='%s', results=%d, threshold=%.2f", query, len(results), threshold)
    return results


async def keyword_search_ids(
    session: AsyncSession,
    query: str,
    limit: int = 50,
) -> set[int]:
    """Return dataset IDs matching keyword ILIKE search."""
    pattern = f"%{query}%"
    result = await session.execute(
        select(Dataset.id)
        .where(
            Dataset.status != "removed",
            or_(
                Dataset.name.ilike(pattern),
                Dataset.description.ilike(pattern),
                Dataset.urn.ilike(pattern),
                Dataset.qualified_name.ilike(pattern),
            ),
        )
        .limit(limit)
    )
    return {row[0] for row in result.fetchall()}


async def hybrid_search(
    session: AsyncSession,
    query: str,
    limit: int = 20,
    threshold: float = 0.3,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
) -> list[tuple[int, float, str]]:
    """Combine keyword and semantic search with weighted scoring.

    Returns list of (dataset_id, combined_score, match_type) ordered by relevance.
    Falls back to keyword-only search when embedding provider is not available.
    """
    provider = await get_provider()

    # Semantic results (skip if provider not available)
    semantic_map: dict[int, float] = {}
    if provider is not None:
        try:
            semantic_results = await semantic_search(session, query, limit=limit * 2, threshold=threshold)
            semantic_map = {ds_id: score for ds_id, score in semantic_results}
        except Exception as e:
            logger.warning("Semantic search unavailable, falling back to keyword: %s", e)
    else:
        logger.info("Embedding provider not available, using keyword-only search")

    # Keyword results
    keyword_ids = await keyword_search_ids(session, query, limit=limit * 2)

    # Combine scores with match_type tracking
    all_ids = set(semantic_map.keys()) | keyword_ids
    scored: list[tuple[int, float, str]] = []
    for ds_id in all_ids:
        sem_score = semantic_map.get(ds_id, 0.0)
        kw_score = 1.0 if ds_id in keyword_ids else 0.0

        if semantic_map:
            combined = semantic_weight * sem_score + keyword_weight * kw_score
        else:
            # Keyword-only fallback (no semantic available)
            combined = kw_score

        if sem_score > 0 and kw_score > 0:
            match_type = "hybrid"
        elif sem_score > 0:
            match_type = "semantic"
        else:
            match_type = "keyword"

        scored.append((ds_id, combined, match_type))

    scored.sort(key=lambda x: x[1], reverse=True)
    logger.info(
        "Hybrid search: q='%s', semantic=%d, keyword=%d, combined=%d",
        query, len(semantic_map), len(keyword_ids), len(scored),
    )
    return scored[:limit]


async def _build_dataset_summary(session: AsyncSession, dataset_id: int) -> DatasetSummary | None:
    """Build a DatasetSummary for a single dataset ID."""
    result = await session.execute(
        select(
            Dataset.id, Dataset.urn, Dataset.name,
            Platform.name.label("platform_name"), Platform.type.label("platform_type"),
            Dataset.description, Dataset.origin, Dataset.status,
            Dataset.is_synced, Dataset.created_at, Dataset.updated_at,
        )
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    if not row:
        return None

    # Counts
    tag_count = (await session.execute(
        select(func.count()).where(DatasetTag.dataset_id == dataset_id)
    )).scalar() or 0
    owner_count = (await session.execute(
        select(func.count()).where(Owner.dataset_id == dataset_id)
    )).scalar() or 0

    return DatasetSummary(
        id=row.id, urn=row.urn, name=row.name,
        platform_name=row.platform_name, platform_type=row.platform_type,
        description=row.description, origin=row.origin, status=row.status,
        is_synced=row.is_synced, tag_count=tag_count, owner_count=owner_count,
        schema_field_count=0,
        created_at=row.created_at, updated_at=row.updated_at,
    )
