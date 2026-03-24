"""Collection and document management service."""

import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection.chunker import chunk_text
from app.models.collection import (
    Collection,
    DataSource,
    Document,
    DocumentChunk,
    SyncJob,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------


async def create_collection(session: AsyncSession, data: dict) -> Collection:
    coll = Collection(**data)
    session.add(coll)
    await session.commit()
    await session.refresh(coll)
    logger.info("Collection created: %s (id=%d)", coll.name, coll.id)
    return coll


async def get_collection(session: AsyncSession, collection_id: int) -> Collection | None:
    result = await session.execute(select(Collection).where(Collection.id == collection_id))
    return result.scalars().first()


async def get_collection_by_name(session: AsyncSession, name: str) -> Collection | None:
    result = await session.execute(select(Collection).where(Collection.name == name))
    return result.scalars().first()


async def list_collections(session: AsyncSession) -> list[Collection]:
    result = await session.execute(
        select(Collection).where(Collection.status != "deleted").order_by(Collection.name)
    )
    return list(result.scalars().all())


async def update_collection(
    session: AsyncSession, collection_id: int, data: dict
) -> Collection | None:
    coll = await get_collection(session, collection_id)
    if not coll:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(coll, key, value)
    await session.commit()
    await session.refresh(coll)
    return coll


async def delete_collection(session: AsyncSession, collection_id: int) -> bool:
    coll = await get_collection(session, collection_id)
    if not coll:
        return False
    # Cascade will delete documents, chunks, sources
    await session.delete(coll)
    await session.commit()
    logger.info("Collection deleted: id=%d", collection_id)
    return True


# ---------------------------------------------------------------------------
# Document CRUD + Chunking
# ---------------------------------------------------------------------------


async def ingest_document(
    session: AsyncSession,
    collection_id: int,
    data: dict,
) -> Document:
    """Ingest a document: create/update, chunk, and prepare for embedding."""
    coll = await get_collection(session, collection_id)
    if not coll:
        raise ValueError(f"Collection {collection_id} not found")

    # Upsert by external_id within collection
    existing = await session.execute(
        select(Document).where(
            Document.collection_id == collection_id,
            Document.external_id == data["external_id"],
        )
    )
    doc = existing.scalars().first()

    if doc:
        # Update existing
        doc.title = data.get("title") or doc.title
        doc.source_text = data["source_text"]
        doc.metadata_json = data.get("metadata_json")
        doc.source_type = data.get("source_type")
        doc.source_url = data.get("source_url")
        doc.is_embedded = "false"
        # Delete old chunks
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    else:
        doc = Document(collection_id=collection_id, **data)
        session.add(doc)
        await session.flush()  # Get doc.id

    # Chunk the document
    chunks = chunk_text(
        doc.source_text,
        strategy=coll.chunk_strategy,
        max_size=coll.chunk_max_size,
        overlap=coll.chunk_overlap,
    )

    for idx, chunk_str in enumerate(chunks):
        session.add(
            DocumentChunk(
                document_id=doc.id,
                collection_id=collection_id,
                chunk_index=idx,
                chunk_text=chunk_str,
            )
        )

    doc.chunk_count = len(chunks)

    # Update collection stats
    await _update_collection_stats(session, collection_id)
    await session.commit()
    await session.refresh(doc)

    logger.info(
        "Document ingested: coll=%d, ext_id=%s, chunks=%d",
        collection_id,
        data["external_id"],
        len(chunks),
    )
    return doc


async def bulk_ingest_documents(
    session: AsyncSession,
    collection_id: int,
    documents: list[dict],
) -> dict:
    """Bulk ingest multiple documents. Returns stats."""
    ingested = 0
    errors = 0
    for doc_data in documents:
        try:
            await ingest_document(session, collection_id, doc_data)
            ingested += 1
        except Exception as e:
            errors += 1
            logger.warning("Bulk ingest error: %s", e)
    return {"ingested": ingested, "errors": errors, "total": len(documents)}


async def list_documents(
    session: AsyncSession,
    collection_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Document], int]:
    """List documents with pagination. Returns (documents, total)."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.collection_id == collection_id)
        )
    ).scalar() or 0

    result = await session.execute(
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def get_document(session: AsyncSession, document_id: int) -> Document | None:
    result = await session.execute(select(Document).where(Document.id == document_id))
    return result.scalars().first()


async def delete_document(session: AsyncSession, document_id: int) -> bool:
    doc = await get_document(session, document_id)
    if not doc:
        return False
    collection_id = doc.collection_id
    await session.delete(doc)
    await _update_collection_stats(session, collection_id)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# DataSource CRUD
# ---------------------------------------------------------------------------


async def create_data_source(session: AsyncSession, collection_id: int, data: dict) -> DataSource:
    ds = DataSource(collection_id=collection_id, **data)
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return ds


async def list_data_sources(session: AsyncSession, collection_id: int) -> list[DataSource]:
    result = await session.execute(
        select(DataSource)
        .where(DataSource.collection_id == collection_id)
        .order_by(DataSource.name)
    )
    return list(result.scalars().all())


async def delete_data_source(session: AsyncSession, source_id: int) -> bool:
    result = await session.execute(select(DataSource).where(DataSource.id == source_id))
    ds = result.scalars().first()
    if not ds:
        return False
    await session.delete(ds)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# SyncJob
# ---------------------------------------------------------------------------


async def create_sync_job(
    session: AsyncSession,
    collection_id: int,
    job_type: str,
    data_source_id: int | None = None,
) -> SyncJob:
    job = SyncJob(
        collection_id=collection_id,
        data_source_id=data_source_id,
        job_type=job_type,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def complete_sync_job(
    session: AsyncSession,
    job_id: int,
    total: int,
    processed: int,
    errors: int,
    error_msg: str | None = None,
    duration_ms: int = 0,
) -> None:
    await session.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id)
        .values(
            status="failed" if errors > 0 and processed == 0 else "completed",
            total_items=total,
            processed_items=processed,
            error_items=errors,
            error_message=error_msg,
            duration_ms=duration_ms,
            finished_at=func.now(),
        )
    )
    await session.commit()


async def list_sync_jobs(
    session: AsyncSession,
    collection_id: int,
    limit: int = 20,
) -> list[SyncJob]:
    result = await session.execute(
        select(SyncJob)
        .where(SyncJob.collection_id == collection_id)
        .order_by(SyncJob.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _update_collection_stats(session: AsyncSession, collection_id: int) -> None:
    """Recalculate denormalized counts for a collection."""
    doc_count = (
        await session.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.collection_id == collection_id)
        )
    ).scalar() or 0

    chunk_count = (
        await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.collection_id == collection_id)
        )
    ).scalar() or 0

    await session.execute(
        update(Collection)
        .where(Collection.id == collection_id)
        .values(document_count=doc_count, chunk_count=chunk_count)
    )
