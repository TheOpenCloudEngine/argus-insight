"""DNS zone management service.

Reads PowerDNS connection settings from the application database and communicates
with the PowerDNS Authoritative Server REST API to manage DNS zones and records.

This service layer handles all interaction with the PowerDNS HTTP API, including:
- Loading connection settings (IP, port, API key, domain) from the database
- Health checking: verifying connectivity, authentication, and zone existence
- Zone creation with automatic NS glue record setup
- Fetching zone records and flattening RRsets into individual rows for the UI
- Updating records via the PowerDNS PATCH endpoint (add, modify, delete)
- Exporting zone data as BIND-compatible configuration files

PowerDNS API reference: https://doc.powerdns.com/authoritative/http-api/
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dns.schemas import (
    BindConfigFile,
    BindConfigResponse,
    DnsHealthResponse,
    DnsRecordRow,
    DnsRRsetPatch,
    DnsZoneCreateResponse,
    DnsZoneTableResponse,
)
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

# Database config keys required to connect to PowerDNS.
# These are stored in the argus_configuration table under category='domain'.
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
    """Fetch all records for the configured domain zone from PowerDNS.

    Calls ``GET /api/v1/servers/localhost/zones/{zone}`` to retrieve all RRsets,
    then flattens them into individual record rows for the UI data table.

    PowerDNS returns records grouped by RRset (name + type), but the UI needs
    each record as a separate row. For example, if an RRset has 3 A records,
    this produces 3 rows with the same name, type, and TTL.

    Args:
        session: Database session for loading PowerDNS connection settings.

    Returns:
        DnsZoneTableResponse with the zone name and flattened record list.

    Raises:
        HTTPException(503): If PowerDNS is unreachable.
        HTTPException(404): If the configured zone does not exist.
        HTTPException(502): If PowerDNS returns an unexpected error.
    """
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
    # Each RRset may contain multiple records (e.g. round-robin A records),
    # but the UI displays each as a separate table row.
    rows: list[DnsRecordRow] = []
    for rrset in rrsets:
        name = rrset.get("name", "")
        rtype = rrset.get("type", "")
        ttl = rrset.get("ttl", 0)
        comments = rrset.get("comments", [])
        # Use only the first comment since the UI shows a single comment column per row
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
    """Update records in the configured domain zone via PowerDNS PATCH.

    Sends a PATCH request to ``/api/v1/servers/localhost/zones/{zone}`` with
    the provided RRset modifications. Each RRset in the list can either
    REPLACE (add/update) or DELETE records.

    Note: PowerDNS REPLACE is idempotent -- it sets the entire RRset to the
    provided records, so the caller must include ALL records for that name+type
    combination, not just the ones being changed.

    Args:
        session: Database session for loading PowerDNS connection settings.
        rrsets: List of RRset patches to apply to the zone.

    Raises:
        HTTPException(503): If PowerDNS is unreachable.
        HTTPException(502): If PowerDNS returns an error status.
    """
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
    """Check if PowerDNS is reachable and whether the configured zone exists.

    Performs a three-step health check:
      1. **Connectivity check** (GET /api/v1/servers): Verifies the PowerDNS API
         is reachable and the API key is valid (catches 401 Unauthorized).
      2. **Zone listing** (GET /api/v1/servers/localhost/zones): Validates that
         the server_id ('localhost') is correct and zones can be listed.
      3. **Zone existence** (GET /api/v1/servers/localhost/zones/{zone}): Checks
         whether the configured domain zone actually exists on the server.

    The UI uses the health response to determine which view to show:
    - not_configured / unreachable -> redirect to PowerDNS settings page
    - zone_missing -> show "Create Zone" button
    - ready -> show the DNS records table

    Args:
        session: Database session for loading PowerDNS connection settings.

    Returns:
        DnsHealthResponse indicating reachability, zone existence, and any errors.
        This endpoint never raises HTTP exceptions; errors are returned in the response.
    """
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
    """Create the configured domain zone on the PowerDNS server.

    Performs two steps:
      1. Creates the zone via POST /zones with kind="Native" and a single
         nameserver (ns1.{domain}).
      2. Adds a glue A record for ns1.{domain} pointing to the PowerDNS
         server IP, so the nameserver record is resolvable.

    The zone kind is set to "Native" which means PowerDNS handles replication
    internally (no AXFR/IXFR zone transfers to secondary servers).

    Args:
        session: Database session for loading PowerDNS connection settings.

    Returns:
        DnsZoneCreateResponse with the zone name and creation status.

    Raises:
        HTTPException(503): If PowerDNS is unreachable.
        HTTPException(502): If zone creation fails (e.g. zone already exists).
    """
    cfg = await _get_pdns_settings(session)
    base_url = _build_base_url(cfg)
    zone = _zone_id(cfg["domain_name"])

    # Set up the primary nameserver name (ns1.example.com.)
    ns1_name = f"ns1.{zone}"
    pdns_ip = cfg["pdns_ip"]
    headers = {"X-API-Key": cfg["pdns_api_key"]}

    body = {
        "name": zone,
        "kind": "Native",
        "nameservers": [ns1_name],
    }

    logger.info("Creating zone: POST %s/zones (name=%s, kind=Native, ns=%s)",
                base_url, zone, ns1_name)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/zones",
                json=body,
                headers=headers,
            )
    except httpx.ConnectError as exc:
        logger.info("Zone creation failed: cannot connect to %s:%s",
                     pdns_ip, cfg["pdns_port"])
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to PowerDNS at {pdns_ip}:{cfg['pdns_port']}",
        ) from exc

    logger.info("POST create zone returned status=%d", resp.status_code)

    if resp.status_code not in (200, 201):
        logger.info("Zone creation failed: %s", resp.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create zone: PowerDNS returned {resp.status_code}: "
                   f"{resp.text[:200]}",
        )

    # Add a glue A record for ns1 so the nameserver is resolvable.
    # Without this, DNS resolvers cannot find ns1.{zone} because it is
    # within the zone itself (in-bailiwick nameserver).
    glue_body = {
        "rrsets": [
            {
                "name": ns1_name,
                "type": "A",
                "ttl": 3600,
                "changetype": "REPLACE",
                "records": [{"content": pdns_ip, "disabled": False}],
            },
        ],
    }
    logger.info("Adding glue record: PATCH %s/zones/%s (ns1 A -> %s)",
                base_url, zone, pdns_ip)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            glue_resp = await client.patch(
                f"{base_url}/zones/{zone}",
                json=glue_body,
                headers=headers,
            )
        logger.info("Glue record PATCH returned status=%d", glue_resp.status_code)
    except httpx.ConnectError:
        logger.info("Failed to add glue record (connection error), zone was created")

    logger.info("Zone created successfully: %s", cfg["domain_name"])
    return DnsZoneCreateResponse(zone=cfg["domain_name"], created=True)


def _format_bind_record(name: str, ttl: int, rtype: str, content: str) -> str:
    """Format a single DNS record as a BIND zone file line."""
    return f"{name:<40s} {ttl:<8d} IN  {rtype:<8s} {content}"


async def export_bind_config(session: AsyncSession) -> BindConfigResponse:
    """Export DNS zone records as BIND-compatible configuration files.

    Generates two files that can be used to configure a Linux BIND DNS server:

    1. ``named.conf.local`` -- Zone declaration that tells BIND where to find
       the zone data file. Should be included in the main BIND configuration.
    2. ``db.{zone}`` -- Zone data file containing all enabled DNS records in
       standard BIND zone file format. Disabled records are excluded.

    Records are ordered for readability: SOA first, then grouped by record type
    following the conventional order (NS, A, AAAA, CNAME, MX, TXT, PTR, SRV),
    with any other types appended alphabetically.

    Args:
        session: Database session for loading PowerDNS connection settings.

    Returns:
        BindConfigResponse with the zone name and list of generated files.
    """
    cfg = await _get_pdns_settings(session)
    domain_name = cfg["domain_name"]
    zone_data = await get_zone_records(session)

    # --- named.conf.local ---
    # This file tells BIND to serve this zone as a master and where to find
    # the zone data file on the filesystem.
    named_conf = (
        f'zone "{domain_name}" {{\n'
        f"    type master;\n"
        f'    file "/etc/bind/zones/db.{domain_name}";\n'
        f"}};\n"
    )

    # --- db.{zone} ---
    # Only include enabled records; disabled records should not be served.
    enabled = [r for r in zone_data.records if not r.disabled]

    # Find the SOA record to extract the default TTL for the $TTL directive.
    soa_record = next((r for r in enabled if r.type == "SOA"), None)

    # The $TTL directive sets the default TTL for records that don't specify one.
    default_ttl = soa_record.ttl if soa_record else 3600

    lines: list[str] = []
    lines.append(f"; BIND zone file for {domain_name}")
    lines.append(f"; Exported from Argus Insight")
    lines.append(f"")
    lines.append(f"$TTL {default_ttl}")
    lines.append(f"")

    # SOA record must appear first in a zone file per RFC 1035.
    if soa_record:
        lines.append(
            _format_bind_record(soa_record.name, soa_record.ttl, "SOA", soa_record.content)
        )
        lines.append("")

    # Group remaining records by type for readability.
    # This ordering follows common convention in BIND zone files.
    type_order = ["NS", "A", "AAAA", "CNAME", "MX", "TXT", "PTR", "SRV"]
    other_records = [r for r in enabled if r.type != "SOA"]

    # Sort: known types first in the conventional order, then unknown types alphabetically.
    # Within each type group, records are sorted by name.
    def sort_key(r: DnsRecordRow) -> tuple[int, str, str]:
        try:
            idx = type_order.index(r.type)
        except ValueError:
            idx = len(type_order)
        return (idx, r.type, r.name)

    other_records.sort(key=sort_key)

    # Write records grouped by type with section comment headers.
    current_type = ""
    for record in other_records:
        if record.type != current_type:
            if current_type:
                lines.append("")  # Blank line between type groups
            lines.append(f"; {record.type} Records")
            current_type = record.type
        lines.append(
            _format_bind_record(record.name, record.ttl, record.type, record.content)
        )

    lines.append("")
    zone_file_content = "\n".join(lines)

    logger.info(
        "Exported BIND config for zone %s: %d enabled records",
        domain_name, len(enabled),
    )

    return BindConfigResponse(
        zone=domain_name,
        files=[
            BindConfigFile(filename="named.conf.local", content=named_conf),
            BindConfigFile(filename=f"db.{domain_name}", content=zone_file_content),
        ],
    )
