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
    DnsHealthResponse,
    DnsRecordRow,
    DnsRRsetPatch,
    DnsZoneCreateResponse,
    DnsZoneTableResponse,
)
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

# Keys we need from the domain category.
_REQUIRED_KEYS = ("pdns_ip", "pdns_port", "pdns_api_key", "domain_name")


async def _get_pdns_settings(session: AsyncSession) -> dict[str, str]:
    """Read PowerDNS connection settings from the database.

    Returns a dict with keys: pdns_ip, pdns_port, pdns_api_key, domain_name.

    Raises HTTPException(503) if required settings are not configured.
    """
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "domain")
    )
    rows = result.scalars().all()
    cfg = {row.config_key: row.config_value for row in rows}

    logger.info(
        "Loaded PowerDNS settings: ip=%s, port=%s, domain=%s",
        cfg.get("pdns_ip"), cfg.get("pdns_port"), cfg.get("domain_name"),
    )

    missing = [k for k in _REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        logger.info("PowerDNS settings missing: %s", ", ".join(missing))
        raise HTTPException(
            status_code=503,
            detail=(
                f"PowerDNS settings not configured: {', '.join(missing)}. "
                "Please configure them in Settings > Domain."
            ),
        )

    return cfg


def _build_base_url(cfg: dict[str, str]) -> str:
    """Build the PowerDNS API base URL.

    The server_id is always 'localhost' in PowerDNS Authoritative Server.
    See: https://doc.powerdns.com/authoritative/http-api/server.html
    """
    return f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1/servers/localhost"


def _zone_id(domain_name: str) -> str:
    """Ensure the zone ID has a trailing dot."""
    return domain_name if domain_name.endswith(".") else f"{domain_name}."


async def get_zone_records(session: AsyncSession) -> DnsZoneTableResponse:
    """Fetch all records for the configured domain zone from PowerDNS."""
    cfg = await _get_pdns_settings(session)
    base_url = _build_base_url(cfg)
    zone = _zone_id(cfg["domain_name"])
    url = f"{base_url}/zones/{zone}"

    logger.info("Fetching zone records: GET %s", url)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"X-API-Key": cfg["pdns_api_key"]})
    except httpx.ConnectError as exc:
        logger.info("Connection failed to PowerDNS at %s:%s", cfg["pdns_ip"], cfg["pdns_port"])
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        ) from exc

    logger.info("GET zone records returned status=%d", resp.status_code)

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

    logger.info(
        "Flattened %d records from %d rrsets for zone %s",
        len(rows), len(rrsets), cfg["domain_name"],
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
    logger.info("Updating zone records: PATCH %s (%d rrsets)", url, len(rrsets))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                url,
                json=body,
                headers={"X-API-Key": cfg["pdns_api_key"]},
            )
    except httpx.ConnectError as exc:
        logger.info("Connection failed to PowerDNS at %s:%s", cfg["pdns_ip"], cfg["pdns_port"])
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        ) from exc

    logger.info("PATCH zone records returned status=%d", resp.status_code)

    if resp.status_code not in (200, 204):
        raise HTTPException(
            status_code=502,
            detail=f"PowerDNS PATCH returned {resp.status_code}: {resp.text[:200]}",
        )


async def check_health(session: AsyncSession) -> DnsHealthResponse:
    """Check if PowerDNS is reachable and whether the configured zone exists."""
    logger.info("Starting PowerDNS health check")
    try:
        cfg = await _get_pdns_settings(session)
    except HTTPException:
        logger.info("Health check failed: PowerDNS settings not configured")
        return DnsHealthResponse(
            reachable=False,
            zone_exists=False,
            zone="",
            error="PowerDNS settings are not configured. "
                  "Please configure them in Settings > Domain > PowerDNS.",
        )

    api_base = f"http://{cfg['pdns_ip']}:{cfg['pdns_port']}/api/v1"
    headers = {"X-API-Key": cfg["pdns_api_key"]}
    zone = _zone_id(cfg["domain_name"])

    # 1) Check basic connectivity via GET /api/v1/servers.
    logger.info("Health check step 1: GET %s/servers", api_base)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{api_base}/servers", headers=headers)
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.info("Health check step 1 failed: cannot connect to %s:%s",
                     cfg["pdns_ip"], cfg["pdns_port"])
        return DnsHealthResponse(
            reachable=False,
            zone_exists=False,
            zone=cfg["domain_name"],
            error=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        )

    logger.info("Health check step 1 result: status=%d", resp.status_code)

    if resp.status_code == 401:
        logger.info("Health check failed: API key unauthorized")
        return DnsHealthResponse(
            reachable=False,
            zone_exists=False,
            zone=cfg["domain_name"],
            error="PowerDNS API key is invalid (401 Unauthorized).",
        )

    if resp.status_code != 200:
        logger.info("Health check failed: unexpected status %d", resp.status_code)
        return DnsHealthResponse(
            reachable=False,
            zone_exists=False,
            zone=cfg["domain_name"],
            error=f"PowerDNS returned {resp.status_code} on connectivity check.",
        )

    # 2) List zones to validate configuration.
    base_url = _build_base_url(cfg)
    logger.info("Health check step 2: GET %s/zones", base_url)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            zones_resp = await client.get(f"{base_url}/zones", headers=headers)
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.info("Health check step 2 failed: connection error")
        return DnsHealthResponse(
            reachable=True,
            zone_exists=False,
            zone=cfg["domain_name"],
            error="Failed to list zones from PowerDNS.",
        )

    logger.info("Health check step 2 result: status=%d", zones_resp.status_code)

    if zones_resp.status_code == 404:
        return DnsHealthResponse(
            reachable=True,
            zone_exists=False,
            zone=cfg["domain_name"],
            error="PowerDNS zone listing failed (404). "
                  "Please check the PowerDNS configuration.",
        )

    if zones_resp.status_code != 200:
        return DnsHealthResponse(
            reachable=True,
            zone_exists=False,
            zone=cfg["domain_name"],
            error=f"PowerDNS returned {zones_resp.status_code} listing zones.",
        )

    # 3) Check if the zone exists.
    logger.info("Health check step 3: GET %s/zones/%s", base_url, zone)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            zone_resp = await client.get(f"{base_url}/zones/{zone}", headers=headers)
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.info("Health check step 3 failed: connection error")
        return DnsHealthResponse(
            reachable=True,
            zone_exists=False,
            zone=cfg["domain_name"],
        )

    zone_exists = zone_resp.status_code == 200
    logger.info(
        "Health check complete: reachable=True, zone_exists=%s, zone=%s",
        zone_exists, cfg["domain_name"],
    )
    return DnsHealthResponse(
        reachable=True,
        zone_exists=zone_exists,
        zone=cfg["domain_name"],
    )


async def create_zone(session: AsyncSession) -> DnsZoneCreateResponse:
    """Create the configured domain zone on the PowerDNS server."""
    cfg = await _get_pdns_settings(session)
    base_url = _build_base_url(cfg)
    zone = _zone_id(cfg["domain_name"])

    body = {
        "name": zone,
        "kind": "Native",
        "nameservers": [f"ns1.{zone}", f"ns2.{zone}"],
    }

    logger.info("Creating zone: POST %s/zones (name=%s, kind=Native)", base_url, zone)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/zones",
                json=body,
                headers={"X-API-Key": cfg["pdns_api_key"]},
            )
    except httpx.ConnectError as exc:
        logger.info("Zone creation failed: cannot connect to %s:%s",
                     cfg["pdns_ip"], cfg["pdns_port"])
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {cfg['pdns_ip']}:{cfg['pdns_port']}",
        ) from exc

    logger.info("POST create zone returned status=%d", resp.status_code)

    if resp.status_code not in (200, 201):
        logger.info("Zone creation failed: %s", resp.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create zone: PowerDNS returned {resp.status_code}: "
                   f"{resp.text[:200]}",
        )

    logger.info("Zone created successfully: %s", cfg["domain_name"])
    return DnsZoneCreateResponse(zone=cfg["domain_name"], created=True)
