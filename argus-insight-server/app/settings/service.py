"""Infrastructure configuration service."""

import logging
from collections import defaultdict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings.models import ArgusConfiguration
from app.settings.schemas import InfraCategoryResponse, InfraConfigResponse

logger = logging.getLogger(__name__)


async def get_infra_config(session: AsyncSession) -> InfraConfigResponse:
    """Load all infrastructure configuration from the database."""
    result = await session.execute(select(ArgusConfiguration))
    rows = result.scalars().all()

    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        grouped[row.category][row.config_key] = row.config_value

    categories = [
        InfraCategoryResponse(category=cat, items=items)
        for cat, items in sorted(grouped.items())
    ]

    logger.info("InfraConfig: categories=%d total_keys=%d", len(categories), len(rows))
    return InfraConfigResponse(categories=categories)


async def update_infra_category(
    session: AsyncSession,
    category: str,
    items: dict[str, str],
) -> None:
    """Update settings within a single infrastructure category."""
    for key, value in items.items():
        result = await session.execute(
            select(ArgusConfiguration).where(
                ArgusConfiguration.config_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.config_value = value
        else:
            session.add(ArgusConfiguration(
                category=category, config_key=key, config_value=value,
            ))
    await session.commit()
    logger.info("UpdateInfraCategory: category=%s keys=%s", category, list(items.keys()))


async def test_docker_registry(url: str, username: str, password: str) -> dict[str, object]:
    """Test connectivity to a Docker Registry by calling /v2/ and /v2/_catalog."""
    base_url = url.rstrip("/")

    auth = httpx.BasicAuth(username, password) if username and password else None

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0, auth=auth) as client:
            # Step 1: Verify connectivity and authentication via /v2/
            v2_resp = await client.get(f"{base_url}/v2/")
            if v2_resp.status_code == 401:
                return {
                    "success": False,
                    "message": "Authentication failed. Please check your username and password.",
                }
            if v2_resp.status_code != 200:
                return {
                    "success": False,
                    "message": f"Registry returned status {v2_resp.status_code}",
                }

            # Step 2: Verify catalog access via /v2/_catalog
            catalog_resp = await client.get(f"{base_url}/v2/_catalog")
            if catalog_resp.status_code == 200:
                return {"success": True, "message": "Zot Docker Registry connection successful"}
            return {
                "success": False,
                "message": f"Registry /v2/_catalog returned status {catalog_resp.status_code}",
            }
    except httpx.ConnectError:
        return {"success": False, "message": f"Cannot connect to {base_url}"}
    except httpx.TimeoutException:
        return {"success": False, "message": f"Connection to {base_url} timed out"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


async def test_unity_catalog(url: str, access_token: str) -> dict[str, object]:
    """Test connectivity to a Unity Catalog server."""
    base_url = url.rstrip("/")

    headers: dict[str, str] = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(base_url, headers=headers)
    except httpx.ConnectError:
        return {"success": False, "message": f"Cannot connect to {base_url}"}
    except httpx.TimeoutException:
        return {"success": False, "message": f"Connection to {base_url} timed out"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    if resp.status_code == 200:
        return {"success": True, "message": "Unity Catalog connection successful"}
    if resp.status_code == 401:
        return {
            "success": False,
            "message": "Authentication failed. Please check your access token.",
        }
    return {"success": False, "message": f"Unity Catalog returned status {resp.status_code}"}


async def initialize_unity_catalog(url: str, access_token: str) -> dict[str, object]:
    """Initialize Unity Catalog with 'global' catalog and 'default' schema."""
    base_url = url.rstrip("/")
    api_base = f"{base_url}/api/2.1/unity-catalog"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    steps: list[str] = []

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            # Step 1: List catalogs and check for "global"
            resp = await client.get(f"{api_base}/catalogs", headers=headers)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to list catalogs: {resp.status_code}",
                }

            catalogs = resp.json().get("catalogs", [])
            global_exists = any(c.get("name") == "global" for c in catalogs)

            # Step 2: Create "global" catalog if missing
            if not global_exists:
                create_resp = await client.post(
                    f"{api_base}/catalogs",
                    headers=headers,
                    json={"name": "global", "comment": "Global metastore"},
                )
                if create_resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "message": f"Failed to create 'global' catalog: {create_resp.status_code}",
                    }
                steps.append("Created catalog 'global'")
            else:
                steps.append("Catalog 'global' already exists")

            # Step 3: List schemas under "global" and check for "default"
            resp = await client.get(
                f"{api_base}/schemas", headers=headers, params={"catalog_name": "global"},
            )
            if resp.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to list schemas: {resp.status_code}",
                }

            schemas = resp.json().get("schemas", [])
            default_exists = any(s.get("name") == "default" for s in schemas)

            # Step 4: Create "default" schema if missing
            if not default_exists:
                create_resp = await client.post(
                    f"{api_base}/schemas",
                    headers=headers,
                    json={
                        "catalog_name": "global",
                        "name": "default",
                        "comment": "Default catalog",
                    },
                )
                if create_resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "message": f"Failed to create 'default' schema: {create_resp.status_code}",
                    }
                steps.append("Created schema 'default' under 'global'")
            else:
                steps.append("Schema 'default' already exists under 'global'")

    except httpx.ConnectError:
        return {"success": False, "message": f"Cannot connect to {base_url}"}
    except httpx.TimeoutException:
        return {"success": False, "message": f"Connection to {base_url} timed out"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    return {"success": True, "message": ". ".join(steps)}


async def seed_infra_config(session: AsyncSession) -> None:
    """Seed default infrastructure configuration if not present."""
    defaults = [
        # Domain
        ("domain", "domain_name", "", "Domain name for this infrastructure"),
        ("domain", "dns_server_1", "", "Primary DNS server"),
        ("domain", "dns_server_2", "", "Secondary DNS server"),
        ("domain", "dns_server_3", "", "Tertiary DNS server"),
        ("domain", "pdns_ip", "", "PowerDNS server IP address"),
        ("domain", "pdns_port", "", "PowerDNS server port"),
        ("domain", "pdns_api_key", "Argus", "PowerDNS API key"),
        ("domain", "pdns_admin_url", "", "PowerDNS Admin web UI URL"),
        # LDAP
        ("ldap", "enable_ldap_auth", "false", "Enable LDAP authentication"),
        ("ldap", "ldap_url", "ldap://<SERVER>:389", "LDAP/AD server URL"),
        ("ldap", "enable_ldap_tls", "false", "Enable LDAP TLS"),
        ("ldap", "ad_domain", "", "Active Directory domain"),
        ("ldap", "ldap_bind_user", "", "LDAP bind user DN"),
        ("ldap", "ldap_bind_password", "", "LDAP bind password"),
        ("ldap", "user_search_base", "", "User search base DN"),
        ("ldap", "user_object_class", "person", "User object class"),
        ("ldap", "user_search_filter", "", "User search filter"),
        ("ldap", "user_name_attribute", "uid", "User name attribute"),
        ("ldap", "group_search_base", "", "Group search base DN"),
        ("ldap", "group_object_class", "posixGroup", "Group object class"),
        ("ldap", "group_search_filter", "", "Group search filter"),
        ("ldap", "group_name_attribute", "cn", "Group name attribute"),
        ("ldap", "group_member_attribute", "memberUid", "Group member attribute"),
        # Command
        ("command", "openssl_path", "/usr/bin/openssl", "Path to OpenSSL binary"),
        # Security
        ("security", "ca_cert_dir", "/opt/argus-insight-server/certs", "CA certificate directory"),
    ]
    for category, key, value, description in defaults:
        result = await session.execute(
            select(ArgusConfiguration).where(
                ArgusConfiguration.config_key == key
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(ArgusConfiguration(
                category=category,
                config_key=key,
                config_value=value,
                description=description,
            ))
    await session.commit()
