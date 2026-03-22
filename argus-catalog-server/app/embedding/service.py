"""Embedding service — generate, store, and manage dataset embeddings.

Handles the lifecycle of embeddings: build source text from dataset metadata,
call the active provider to generate vectors, and upsert into pgvector table.
"""

import asyncio
import logging

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Dataset, DatasetTag, Owner, Platform, Tag
from app.embedding.models import DatasetEmbedding
from app.embedding.registry import get_provider

logger = logging.getLogger(__name__)


async def build_source_text(session: AsyncSession, dataset_id: int) -> str | None:
    """Build embeddable text from dataset metadata.

    Concatenates: name | description | qualified_name | platform_name | tag names | owner names
    Returns None if the dataset does not exist.
    """
    result = await session.execute(
        select(Dataset.name, Dataset.description, Dataset.qualified_name,
               Platform.name.label("platform_name"), Platform.type.label("platform_type"))
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    if not row:
        return None

    parts = [row.name]
    if row.description:
        parts.append(row.description)
    if row.qualified_name:
        parts.append(row.qualified_name)
    parts.append(row.platform_name)
    parts.append(row.platform_type)

    # Tag names
    tag_result = await session.execute(
        select(Tag.name)
        .join(DatasetTag, DatasetTag.tag_id == Tag.id)
        .where(DatasetTag.dataset_id == dataset_id)
    )
    tag_names = [t[0] for t in tag_result.all()]
    if tag_names:
        parts.extend(tag_names)

    # Owner names
    owner_result = await session.execute(
        select(Owner.owner_name).where(Owner.dataset_id == dataset_id)
    )
    owner_names = [o[0] for o in owner_result.all()]
    if owner_names:
        parts.extend(owner_names)

    return " | ".join(parts)


async def embed_dataset(session: AsyncSession, dataset_id: int) -> bool:
    """Generate and store embedding for a single dataset.

    Returns True if embedding was created/updated, False if skipped.
    """
    provider = await get_provider()
    if provider is None:
        return False

    source_text = await build_source_text(session, dataset_id)
    if not source_text:
        logger.warning("Cannot embed dataset %d: not found", dataset_id)
        return False

    # Check if existing embedding has same source text (skip if unchanged)
    existing = await session.execute(
        select(DatasetEmbedding.source_text)
        .where(DatasetEmbedding.dataset_id == dataset_id)
    )
    existing_text = existing.scalar()
    if existing_text == source_text:
        return False  # No change

    # Generate embedding
    vectors = await provider.embed([source_text])
    vector = vectors[0]

    # Upsert
    existing_row = await session.execute(
        select(DatasetEmbedding).where(DatasetEmbedding.dataset_id == dataset_id)
    )
    row = existing_row.scalars().first()

    if row:
        row.embedding = vector
        row.source_text = source_text
        row.model_name = provider.model_name()
        row.provider = provider.provider_name()
        row.dimension = provider.dimension()
    else:
        session.add(DatasetEmbedding(
            dataset_id=dataset_id,
            embedding=vector,
            source_text=source_text,
            model_name=provider.model_name(),
            provider=provider.provider_name(),
            dimension=provider.dimension(),
        ))

    await session.commit()
    logger.info("Embedded dataset %d (%s, %d dim)", dataset_id, provider.model_name(), provider.dimension())
    return True


async def embed_dataset_background(dataset_id: int) -> None:
    """Schedule embedding as a non-blocking background task.

    Uses its own DB session. Failures are logged but do not propagate.
    """
    async def _do_embed():
        from app.core.database import async_session
        async with async_session() as session:
            try:
                await embed_dataset(session, dataset_id)
            except Exception as e:
                logger.warning("Background embedding failed for dataset %d: %s", dataset_id, e)

    asyncio.create_task(_do_embed())


async def embed_all_datasets(session: AsyncSession) -> dict:
    """Backfill embeddings for all active datasets.

    Returns: {"total": N, "embedded": M, "skipped": S, "errors": E}
    """
    provider = await get_provider()
    if provider is None:
        return {"total": 0, "embedded": 0, "skipped": 0, "errors": 0, "error": "No provider"}

    result = await session.execute(
        select(Dataset.id).where(Dataset.status != "removed").order_by(Dataset.id)
    )
    dataset_ids = [r[0] for r in result.all()]
    total = len(dataset_ids)
    embedded = 0
    skipped = 0
    errors = 0

    logger.info("Starting embedding backfill for %d datasets", total)

    for ds_id in dataset_ids:
        try:
            if await embed_dataset(session, ds_id):
                embedded += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            logger.warning("Embedding failed for dataset %d: %s", ds_id, e)

    logger.info("Embedding backfill complete: total=%d, embedded=%d, skipped=%d, errors=%d",
                total, embedded, skipped, errors)
    return {"total": total, "embedded": embedded, "skipped": skipped, "errors": errors}


async def delete_embedding(session: AsyncSession, dataset_id: int) -> None:
    """Remove embedding for a dataset."""
    await session.execute(
        delete(DatasetEmbedding).where(DatasetEmbedding.dataset_id == dataset_id)
    )
    await session.commit()


async def clear_all_embeddings(session: AsyncSession) -> int:
    """Delete all embeddings (e.g. before provider switch). Returns count deleted."""
    result = await session.execute(delete(DatasetEmbedding))
    await session.commit()
    count = result.rowcount
    logger.info("Cleared all embeddings: %d rows", count)
    return count


async def get_embedding_stats(session: AsyncSession) -> dict:
    """Return embedding coverage statistics."""
    total_datasets = (await session.execute(
        select(func.count()).select_from(Dataset).where(Dataset.status != "removed")
    )).scalar() or 0

    total_embeddings = (await session.execute(
        select(func.count()).select_from(DatasetEmbedding)
    )).scalar() or 0

    provider = await get_provider()

    # Read dimension from DB config instead of provider.dimension()
    # to avoid triggering model load on stats query
    from app.settings.service import get_config_by_category
    emb_cfg = await get_config_by_category(session, "embedding")
    dim = int(emb_cfg.get("embedding_dimension", "384")) if emb_cfg else None

    return {
        "total_datasets": total_datasets,
        "embedded_datasets": total_embeddings,
        "coverage_pct": round(total_embeddings / total_datasets * 100, 1) if total_datasets > 0 else 0,
        "provider": provider.provider_name() if provider else None,
        "model": provider.model_name() if provider else None,
        "dimension": dim,
    }
