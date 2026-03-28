"""PowerDNS API client for DNS record management."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def get_pdns_settings(session) -> dict[str, str]:
    """Read PowerDNS settings from the argus_configuration table."""
    from sqlalchemy import select
    from app.settings.models import ArgusConfiguration

    logger.debug("Loading PowerDNS settings from DB (category=domain)")
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "domain")
    )
    cfg = {row.config_key: row.config_value for row in result.scalars().all()}
    logger.info("PowerDNS settings loaded: pdns_ip=%s, pdns_port=%s, domain=%s",
                cfg.get("pdns_ip", "N/A"), cfg.get("pdns_port", "N/A"),
                cfg.get("domain_name", "N/A"))
    return cfg


async def register_dns(
    pdns_ip: str,
    pdns_port: str,
    pdns_api_key: str,
    domain_name: str,
    hostname: str,
    target_ip: str,
) -> None:
    """Register an A record in PowerDNS."""
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{pdns_ip}:{pdns_port}/api/v1/servers/localhost"
    url = f"{base_url}/zones/{zone}"

    body = {
        "rrsets": [{
            "name": fqdn, "type": "A", "ttl": 300, "changetype": "REPLACE",
            "records": [{"content": target_ip, "disabled": False}],
        }],
    }
    logger.info("DNS register: PATCH %s — %s A %s (TTL 300)", url, fqdn, target_ip)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(url, json=body, headers={"X-API-Key": pdns_api_key})
        if resp.status_code in (200, 204):
            logger.info("DNS register: success — %s -> %s", fqdn, target_ip)
        else:
            logger.warning("DNS register: unexpected status %d — %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.error("DNS register: failed for %s -> %s", fqdn, target_ip, exc_info=True)


async def delete_dns(
    pdns_ip: str,
    pdns_port: str,
    pdns_api_key: str,
    domain_name: str,
    hostname: str,
) -> None:
    """Remove an A record from PowerDNS."""
    zone = domain_name if domain_name.endswith(".") else f"{domain_name}."
    fqdn = hostname if hostname.endswith(".") else f"{hostname}."
    base_url = f"http://{pdns_ip}:{pdns_port}/api/v1/servers/localhost"
    url = f"{base_url}/zones/{zone}"

    body = {"rrsets": [{"name": fqdn, "type": "A", "changetype": "DELETE"}]}
    logger.info("DNS delete: PATCH %s — DELETE %s A", url, fqdn)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(url, json=body, headers={"X-API-Key": pdns_api_key})
        if resp.status_code in (200, 204):
            logger.info("DNS delete: success — %s removed", fqdn)
        else:
            logger.warning("DNS delete: unexpected status %d — %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.error("DNS delete: failed for %s", fqdn, exc_info=True)
