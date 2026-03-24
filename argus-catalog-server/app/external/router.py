"""External API — cached dataset metadata and Avro schema for external systems."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, OptionalUser
from app.core.config import settings
from app.core.database import get_session
from app.external.cache import get_cache
from app.external.schemas import CacheConfigResponse, CacheConfigUpdate
from app.external.service import get_dataset_avro_schema, get_dataset_metadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/external", tags=["external"])


# ---------------------------------------------------------------------------
# Dataset Metadata
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/metadata")
async def get_metadata(
    dataset_id: int,
    no_cache: bool = Query(False, description="Bypass cache"),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get dataset metadata JSON for external systems."""
    if not settings.cache_enabled and not no_cache:
        no_cache = True

    result = await get_dataset_metadata(session, dataset_id, no_cache=no_cache)
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result


# ---------------------------------------------------------------------------
# Avro Schema
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/avro-schema")
async def get_avro_schema(
    dataset_id: int,
    no_cache: bool = Query(False, description="Bypass cache"),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get Avro schema for a dataset.

    Converts catalog schema to Apache Avro format with:
    - Native type → Avro type mapping
    - Nullable fields as union ["null", type]
    - Logical types (decimal, date, timestamp-millis, uuid)
    - PII and primary_key metadata annotations
    """
    if not settings.cache_enabled and not no_cache:
        no_cache = True

    result = await get_dataset_avro_schema(session, dataset_id, no_cache=no_cache)
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


@router.delete("/datasets/{dataset_id}/cache")
async def invalidate_cache_entry(
    dataset_id: int,
    user: OptionalUser = None,
):
    """Invalidate all cached data (metadata + avro) for a dataset."""
    cache = get_cache()
    count = await cache.invalidate(f"metadata:{dataset_id}")
    count += await cache.invalidate(f"avro:{dataset_id}")
    return {"invalidated": count, "dataset_id": dataset_id}


@router.delete("/cache")
async def clear_cache(user: OptionalUser = None):
    cache = get_cache()
    count = await cache.clear()
    return {"cleared": count}


@router.get("/cache/stats")
async def cache_stats(user: OptionalUser = None):
    cache = get_cache()
    return await cache.stats()


@router.get("/cache/config", response_model=CacheConfigResponse)
async def get_cache_config(user: OptionalUser = None):
    cache = get_cache()
    return CacheConfigResponse(
        max_size=cache.max_size,
        ttl_seconds=cache.ttl_seconds,
        enabled=settings.cache_enabled,
        current_size=(await cache.stats())["size"],
    )


@router.put("/cache/config", response_model=CacheConfigResponse)
async def update_cache_config(body: CacheConfigUpdate, user: CurrentUser = None):
    settings.cache_max_size = body.max_size
    settings.cache_ttl_seconds = body.ttl_seconds
    settings.cache_enabled = body.enabled

    cache = get_cache()
    await cache.reconfigure(max_size=body.max_size, ttl_seconds=body.ttl_seconds)

    logger.info(
        "Cache config updated: max_size=%d, ttl=%ds, enabled=%s",
        body.max_size,
        body.ttl_seconds,
        body.enabled,
    )
    return CacheConfigResponse(
        max_size=body.max_size,
        ttl_seconds=body.ttl_seconds,
        enabled=body.enabled,
        current_size=(await cache.stats())["size"],
    )
