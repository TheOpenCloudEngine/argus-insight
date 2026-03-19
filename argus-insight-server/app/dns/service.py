"""DNS zone management service.

Reads PowerDNS connection settings from the database and communicates
with the PowerDNS Authoritative Server REST API.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dns.schemas import (
    DnsRecordRow,
    DnsRRsetPatch,
    DnsZoneTableResponse,
)
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

# Keys we need from the domain category.
_REQUIRED_KEYS = ("pdns_ip", "pdns_port", "pdns_api_key", "domain_name")


async def _get_pdns_settings(session: AsyncSession) -> dict[str, str]:
    """Read PowerDNS connection settings from the database.

    Returns a dict with keys: pdns_ip, pdns_port, pdns_api_key,
    pdns_server_id, domain_name.

    Raises HTTPException(503) if required settings are not configured.
    """
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "domain")
    )
    rows = result.scalars().all()
    cfg = {row.config_key: row.config_value for row in rows}

    missing = [k for k in _REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                f"PowerDNS settings not configured: {', '.join(missing)}. "
                "Please configure them in Settings > Domain."
            ),
        )

    # Default server_id to "localhost" if not set.
    cfg.setdefault("pdns_server_id", "localhost")
    if not cfg["pdns_server_id"]:
        cfg["pdns_server_id"] = "localhost"

    return cfg


def _build_base_url(cfg: dict[str, str]) -> str:
    """Build the PowerDNS API base URL."""
    return f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/{cfg['pdns_server_id']}"


def _zone_id(domain_name: str) -> str:
    """Ensure the zone ID has a trailing dot."""
    return domain_name if domain_name.endswith(".") else f"{domain_name}."


async def get_zone_records(session: AsyncSession) -> DnsZoneTableResponse:
    """Fetch all records for the configured domain zone from PowerDNS."""
    cfg = await _get_pdns_settings(session)
    base_url = _build_base_url(cfg)
    zone = _zone_id(cfg["domain_name"])
    url = f"{base_url}/zones/{zone}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"X-API-Key": cfg["pdns_api_key"]})
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        ) from exc

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Zone '{cfg['domain_name']}' not found on PowerDNS server.",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"PowerDNS returned {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    rrsets = data.get("rrsets", [])

    # Flatten RRsets into individual record rows.
    rows: list[DnsRecordRow] = []
    for rrset in rrsets:
        name = rrset.get("name", "")
        rtype = rrset.get("type", "")
        ttl = rrset.get("ttl", 0)
        comments = rrset.get("comments", [])
        comment_text = comments[0]["content"] if comments else ""

        for record in rrset.get("records", []):
            rows.append(
                DnsRecordRow(
                    name=name,
                    type=rtype,
                    ttl=ttl,
                    content=record.get("content", ""),
                    disabled=record.get("disabled", False),
                    comment=comment_text,
                )
            )

    return DnsZoneTableResponse(zone=cfg["domain_name"], records=rows)


async def update_zone_records(
    session: AsyncSession,
    rrsets: list[DnsRRsetPatch],
) -> None:
    """Update records in the configured domain zone via PATCH."""
    cfg = await _get_pdns_settings(session)
    base_url = _build_base_url(cfg)
    zone = _zone_id(cfg["domain_name"])
    url = f"{base_url}/zones/{zone}"

    body = {"rrsets": [rrset.model_dump() for rrset in rrsets]}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                url,
                json=body,
                headers={"X-API-Key": cfg["pdns_api_key"]},
            )
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        ) from exc

    if resp.status_code not in (200, 204):
        raise HTTPException(
            status_code=502,
            detail=f"PowerDNS PATCH returned {resp.status_code}: {resp.text[:200]}",
        )
