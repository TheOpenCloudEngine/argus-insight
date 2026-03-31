"""Impala query profile analysis proxy.

Forwards profile analysis requests to the metadata-sync service, which holds
the Impala connection configuration, query history, and the profile analysis
engine.  This keeps the catalog server as the single gateway for the AI agent.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/impala", tags=["impala-profile"])

_TIMEOUT = 60.0  # Profile fetch + analysis can be slow


class ProfileTextRequest(BaseModel):
    profile_text: str


@router.get("/queries/{query_id}/profile")
async def get_query_profile(query_id: str):
    """Fetch the raw runtime profile for an Impala query."""
    url = f"{settings.metadata_sync_base_url}/collector/impala/queries/{query_id}/profile"
    return await _proxy_get(url)


@router.post("/queries/{query_id}/analyze")
async def analyze_query_profile(query_id: str):
    """Fetch and analyze an Impala query profile for bottlenecks."""
    url = f"{settings.metadata_sync_base_url}/collector/impala/queries/{query_id}/analyze"
    return await _proxy_post(url)


@router.post("/profile/analyze")
async def analyze_profile_text(req: ProfileTextRequest):
    """Analyze a user-submitted Impala profile text for bottlenecks."""
    url = f"{settings.metadata_sync_base_url}/collector/impala/profile/analyze"
    return await _proxy_post(url, json={"profile_text": req.profile_text})


async def _proxy_get(url: str) -> dict:
    """Forward GET to metadata-sync."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url)
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Metadata-sync service is unavailable",
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def _proxy_post(url: str, json: dict | None = None) -> dict:
    """Forward POST to metadata-sync."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=json)
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Metadata-sync service is unavailable",
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
