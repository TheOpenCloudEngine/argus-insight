"""Sync API router — trigger sync operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import OptionalUser
from app.core.database import get_session
from app.models.collection import DataSource
from app.source.sync_service import sync_data_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/sources/{source_id}")
async def trigger_sync(
    source_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a full sync from a data source (fetch → ingest → embed)."""
    result = await session.execute(select(DataSource).where(DataSource.id == source_id))
    ds = result.scalars().first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    sync_result = await sync_data_source(session, ds)
    if "error" in sync_result:
        raise HTTPException(status_code=500, detail=sync_result["error"])
    return sync_result


@router.post("/collections/{collection_id}")
async def trigger_collection_sync(
    collection_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger sync for all data sources in a collection."""
    result = await session.execute(
        select(DataSource).where(
            DataSource.collection_id == collection_id,
            DataSource.status == "active",
        )
    )
    sources = list(result.scalars().all())
    if not sources:
        raise HTTPException(status_code=404, detail="No active data sources")

    results = []
    for ds in sources:
        r = await sync_data_source(session, ds)
        results.append({"source_id": ds.id, "source_name": ds.name, **r})
    return {"syncs": results}
