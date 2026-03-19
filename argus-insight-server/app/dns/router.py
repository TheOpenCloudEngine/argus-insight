"""DNS zone management API endpoints.

Defines the FastAPI router for DNS zone operations under ``/api/v1/dns``.
All endpoints delegate to the service layer for business logic and PowerDNS
API communication.

Endpoints:
    GET  /dns/health                  - Check PowerDNS connectivity and zone status
    POST /dns/zone                    - Create the configured domain zone
    GET  /dns/zone/records            - List all DNS records in the zone
    GET  /dns/zone/bind-config        - Export zone as BIND config files (JSON)
    GET  /dns/zone/bind-config/download - Download BIND config as ZIP archive
    PATCH /dns/zone/records           - Add, update, or delete DNS records
"""

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


# ------------------------------------------------------------------------------- #
# Health Check
# ------------------------------------------------------------------------------- #


@router.get("/health", response_model=DnsHealthResponse)
async def check_health(
    session: AsyncSession = Depends(get_session),
) -> DnsHealthResponse:
    """Check PowerDNS connectivity and zone existence.

    Called by the UI on page load to determine which view to render:
    settings prompt, zone creation button, or the records table.
    """
    return await service.check_health(session)


# ------------------------------------------------------------------------------- #
# Zone Management
# ------------------------------------------------------------------------------- #


@router.post("/zone", response_model=DnsZoneCreateResponse, status_code=201)
async def create_zone(
    session: AsyncSession = Depends(get_session),
) -> DnsZoneCreateResponse:
    """Create the configured domain zone on the PowerDNS server.

    Called when the health check shows the zone does not yet exist.
    Creates the zone with a default NS record and glue A record.
    """
    return await service.create_zone(session)


# ------------------------------------------------------------------------------- #
# Zone Records
# ------------------------------------------------------------------------------- #


@router.get("/zone/records", response_model=DnsZoneTableResponse)
async def get_zone_records(
    session: AsyncSession = Depends(get_session),
) -> DnsZoneTableResponse:
    """Fetch all DNS records for the configured domain zone.

    Returns records flattened from PowerDNS RRsets into individual rows
    suitable for rendering in the UI data table.
    """
    return await service.get_zone_records(session)


@router.patch("/zone/records", status_code=204)
async def update_zone_records(
    body: DnsRecordUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Update DNS records in the configured domain zone.

    Accepts a list of RRset patches with changetype REPLACE or DELETE.
    Used by the UI for adding, editing, toggling, and deleting records.
    """
    await service.update_zone_records(session, body.rrsets)


# ------------------------------------------------------------------------------- #
# BIND Configuration Export
# ------------------------------------------------------------------------------- #


@router.get("/zone/bind-config", response_model=BindConfigResponse)
async def export_bind_config(
    session: AsyncSession = Depends(get_session),
) -> BindConfigResponse:
    """Export DNS zone records as BIND configuration files (JSON response).

    Returns the file contents as JSON so the UI can display a preview
    before the user decides to download.
    """
    return await service.export_bind_config(session)


@router.get("/zone/bind-config/download")
async def download_bind_config(
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download BIND configuration files as a ZIP archive.

    Generates the same BIND config files as the JSON endpoint above,
    but packages them into a ZIP file for direct download. The ZIP is
    created in /tmp and served as an octet-stream attachment.
    """
    result = await service.export_bind_config(session)

    # Create a temporary ZIP file in /tmp (auto-cleaned on reboot).
    # delete=False is needed because FileResponse reads the file after this function returns.
    tmp = tempfile.NamedTemporaryFile(
        prefix="bind-", suffix=".zip", dir="/tmp", delete=False,
    )
    tmp_path = tmp.name
    tmp.close()

    # Write each BIND config file into the ZIP archive with deflate compression.
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
