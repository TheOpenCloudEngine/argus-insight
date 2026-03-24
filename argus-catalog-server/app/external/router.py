"""External API — cached dataset metadata and Avro schema for external systems.

Supports lookup by both dataset_id (int) and URN (string).
URN example: mysql-19d0bfe954e2cfdaa.sakila.actor.PROD.dataset
"""

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


def _no_cache(no_cache: bool) -> bool:
    if not settings.cache_enabled and not no_cache:
        return True
    return no_cache


# ---------------------------------------------------------------------------
# By URN (string) — primary external API
# ---------------------------------------------------------------------------


@router.get("/metadata")
async def get_metadata_by_urn(
    urn: str = Query(..., description="Dataset URN, e.g. mysql-xxx.sakila.actor.PROD.dataset"),
    no_cache: bool = Query(False),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get dataset metadata by URN.

    Performance: 1st call ~20ms (DB), 2nd+ call < 1ms (cache).
    URN→ID mapping is also cached.
    """
    result = await get_dataset_metadata(session, urn, no_cache=_no_cache(no_cache))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {urn}")
    return result


@router.get("/avro-schema")
async def get_avro_by_urn(
    urn: str = Query(..., description="Dataset URN"),
    no_cache: bool = Query(False),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get Avro schema by URN."""
    result = await get_dataset_avro_schema(session, urn, no_cache=_no_cache(no_cache))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {urn}")
    return result


# ---------------------------------------------------------------------------
# By dataset_id (int) — backward compatible
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/metadata")
async def get_metadata_by_id(
    dataset_id: int,
    no_cache: bool = Query(False),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get dataset metadata by internal ID."""
    result = await get_dataset_metadata(session, dataset_id, no_cache=_no_cache(no_cache))
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result


@router.get("/datasets/{dataset_id}/avro-schema")
async def get_avro_by_id(
    dataset_id: int,
    no_cache: bool = Query(False),
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Get Avro schema by internal ID."""
    result = await get_dataset_avro_schema(session, dataset_id, no_cache=_no_cache(no_cache))
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


@router.delete("/datasets/{dataset_id}/cache")
async def invalidate_by_id(dataset_id: int, user: OptionalUser = None):
    """Invalidate cached data for a dataset by ID."""
    cache = get_cache()
    count = await cache.invalidate(f"metadata:{dataset_id}")
    count += await cache.invalidate(f"avro:{dataset_id}")
    return {"invalidated": count, "dataset_id": dataset_id}


@router.delete("/cache")
async def clear_cache(user: OptionalUser = None):
    cache = get_cache()
    return {"cleared": await cache.clear()}


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
