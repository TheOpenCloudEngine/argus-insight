"""DNS zone management API endpoints."""

import logging
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.dns import service
from app.dns.schemas import (
    BindConfigResponse,
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


@router.get("/zone/bind-config", response_model=BindConfigResponse)
async def export_bind_config(
    session: AsyncSession = Depends(get_session),
) -> BindConfigResponse:
    """Export DNS zone records as BIND configuration files."""
    return await service.export_bind_config(session)


@router.get("/zone/bind-config/download")
async def download_bind_config(
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download BIND configuration files as a ZIP archive."""
    result = await service.export_bind_config(session)

    # Create ZIP in /tmp (auto-cleaned on reboot)
    tmp = tempfile.NamedTemporaryFile(
        prefix="bind-", suffix=".zip", dir="/tmp", delete=False,
    )
    tmp_path = tmp.name
    tmp.close()

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in result.files:
            zf.writestr(f.filename, f.content)

    logger.info("Created BIND config ZIP: %s (%d files)", tmp_path, len(result.files))

    return FileResponse(
        path=tmp_path,
        filename=f"bind-{result.zone}.zip",
        media_type="application/octet-stream",
        background=None,
    )


@router.patch("/zone/records", status_code=204)
async def update_zone_records(
    body: DnsRecordUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Update DNS records in the configured domain zone."""
    await service.update_zone_records(session, body.rrsets)
