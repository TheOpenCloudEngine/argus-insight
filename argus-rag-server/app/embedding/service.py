"""Embedding service — generate and store embeddings for document chunks."""

import logging
import time

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection.service import complete_sync_job, create_sync_job
from app.embedding.registry import get_provider
from app.models.collection import Collection, Document, DocumentChunk

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


async def embed_collection(session: AsyncSession, collection_id: int) -> dict:
    """Generate embeddings for all un-embedded chunks in a collection."""
    provider = await get_provider()
    if provider is None:
        return {"error": "Embedding provider not initialized"}

    coll = await session.execute(select(Collection).where(Collection.id == collection_id))
    coll = coll.scalars().first()
    if not coll:
        return {"error": "Collection not found"}

    # Create sync job
    job = await create_sync_job(session, collection_id, "embed")
    start = time.monotonic()

    # Get un-embedded chunks
    result = await session.execute(
        select(DocumentChunk.id, DocumentChunk.chunk_text)
        .where(
            DocumentChunk.collection_id == collection_id,
            DocumentChunk.embedding.is_(None),
        )
        .order_by(DocumentChunk.id)
    )
    rows = result.all()
    total = len(rows)
    processed = 0
    errors = 0

    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        texts = [r.chunk_text for r in batch]
        ids = [r.id for r in batch]

        try:
            vectors = await provider.embed(texts)
            for chunk_id, vector in zip(ids, vectors):
                await session.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk_id)
                    .values(
                        embedding=vector,
                        model_name=provider.model_name(),
                    )
                )
            processed += len(batch)
        except Exception as e:
            errors += len(batch)
            logger.warning("Embedding batch failed: %s", e)

        await session.commit()

    # Mark documents as embedded
    await session.execute(
        update(Document)
        .where(
            Document.collection_id == collection_id,
            Document.is_embedded == "false",
        )
        .values(is_embedded="true")
    )
    await session.commit()

    duration = int((time.monotonic() - start) * 1000)
    await complete_sync_job(session, job.id, total, processed, errors, duration_ms=duration)

    logger.info(
        "Embedding complete: coll=%d, total=%d, processed=%d, errors=%d, %dms",
        collection_id,
        total,
        processed,
        errors,
        duration,
    )
    return {
        "total": total,
        "processed": processed,
        "errors": errors,
        "duration_ms": duration,
    }


async def clear_embeddings(session: AsyncSession, collection_id: int) -> int:
    """Clear all embeddings for a collection (for re-embedding after model change)."""
    result = await session.execute(
        update(DocumentChunk)
        .where(DocumentChunk.collection_id == collection_id)
        .values(embedding=None, model_name=None)
    )
    await session.execute(
        update(Document).where(Document.collection_id == collection_id).values(is_embedded="false")
    )
    await session.commit()
    count = result.rowcount
    logger.info("Cleared embeddings for collection %d: %d chunks", collection_id, count)
    return count


async def get_embedding_stats(session: AsyncSession, collection_id: int) -> dict:
    """Get embedding coverage stats for a collection."""
    total_chunks = (
        await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.collection_id == collection_id)
        )
    ).scalar() or 0

    embedded_chunks = (
        await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.collection_id == collection_id,
                DocumentChunk.embedding.isnot(None),
            )
        )
    ).scalar() or 0

    provider = await get_provider()
    return {
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "coverage_pct": round(embedded_chunks / total_chunks * 100, 1) if total_chunks > 0 else 0,
        "provider": provider.provider_name() if provider else None,
        "model": provider.model_name() if provider else None,
    }
