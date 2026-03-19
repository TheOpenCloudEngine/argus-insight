"""DNS zone management API endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.dns import service
from app.dns.schemas import (
    DnsHealthResponse,
    DnsRecordUpdateRequest,
    DnsZoneCreateResponse,
    DnsZoneTableResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dns", tags=["dns"])


@router.get("/health", response_model=DnsHealthResponse)
async def check_health(
    session: AsyncSession = Depends(get_session),
) -> DnsHealthResponse:
    """Check PowerDNS connectivity and zone existence."""
    return await service.check_health(session)


@router.post("/zone", response_model=DnsZoneCreateResponse, status_code=201)
async def create_zone(
    session: AsyncSession = Depends(get_session),
) -> DnsZoneCreateResponse:
    """Create the configured domain zone on the PowerDNS server."""
    return await service.create_zone(session)


@router.get("/zone/records", response_model=DnsZoneTableResponse)
async def get_zone_records(
    session: AsyncSession = Depends(get_session),
) -> DnsZoneTableResponse:
    """Fetch all DNS records for the configured domain zone."""
    return await service.get_zone_records(session)


@router.patch("/zone/records", status_code=204)
async def update_zone_records(
    body: DnsRecordUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Update DNS records in the configured domain zone."""
    await service.update_zone_records(session, body.rrsets)
