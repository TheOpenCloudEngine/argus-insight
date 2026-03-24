"""Sync service — orchestrates data source sync + embedding."""

import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.collection.service import (
    complete_sync_job,
    create_sync_job,
    ingest_document,
)
from app.embedding.service import embed_collection
from app.models.collection import DataSource
from app.source.catalog_connector import CatalogConnector

logger = logging.getLogger(__name__)


async def sync_data_source(
    session: AsyncSession,
    data_source: DataSource,
) -> dict:
    """Run a full sync from a data source: fetch → ingest → embed."""
    collection_id = data_source.collection_id
    job = await create_sync_job(session, collection_id, "sync", data_source.id)
    start = time.monotonic()

    try:
        # Create connector based on source type
        config = json.loads(data_source.config_json or "{}")
        connector = _create_connector(data_source.source_type, config)

        # Fetch all items
        items = await connector.fetch_all()
        await connector.close()

        # Ingest into collection
        processed = 0
        errors = 0
        for item in items:
            try:
                await ingest_document(
                    session,
                    collection_id,
                    {
                        "external_id": item.external_id,
                        "title": item.title,
                        "source_text": item.source_text,
                        "metadata_json": item.metadata_json,
                        "source_type": item.source_type,
                        "source_url": item.source_url,
                    },
                )
                processed += 1
            except Exception as e:
                errors += 1
                logger.warning("Sync ingest error: %s", e)

        # Generate embeddings for new chunks
        embed_result = await embed_collection(session, collection_id)

        duration = int((time.monotonic() - start) * 1000)
        await complete_sync_job(
            session, job.id, len(items), processed, errors, duration_ms=duration
        )

        # Update last_sync_at on the data source
        from sqlalchemy import func, update

        from app.models.collection import DataSource as DSModel

        await session.execute(
            update(DSModel).where(DSModel.id == data_source.id).values(last_sync_at=func.now())
        )
        await session.commit()

        return {
            "job_id": job.id,
            "total": len(items),
            "processed": processed,
            "errors": errors,
            "embed": embed_result,
            "duration_ms": duration,
        }

    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        await complete_sync_job(session, job.id, 0, 0, 1, error_msg=str(e), duration_ms=duration)
        logger.exception("Sync failed for source %d", data_source.id)
        return {"error": str(e), "job_id": job.id}


def _create_connector(source_type: str, config: dict):
    """Factory for data source connectors."""
    if source_type == "catalog_api":
        return CatalogConnector(config)
    if source_type == "db_query":
        from app.source.db_query_connector import DBQueryConnector

        return DBQueryConnector(config)
    raise ValueError(f"Unsupported source type: {source_type}")
