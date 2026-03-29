"""Infrastructure configuration service."""

import asyncio
import logging
from collections import defaultdict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import ArgusAgent
from app.core.config import settings
from app.settings.models import ArgusConfiguration
from app.settings.schemas import InfraCategoryResponse, InfraConfigResponse

logger = logging.getLogger(__name__)

# Default agent port (agents register via heartbeat, port not stored in DB)
_AGENT_PORT = 4501

# Prometheus config keys in the argus category
_PROMETHEUS_KEYS = {
    "prometheus_enable_push",
    "prometheus_push_cron",
    "prometheus_pushgateway_host",
    "prometheus_pushgateway_port",
}


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


async def get_infra_category_items(
    session: AsyncSession, category: str,
) -> dict[str, str]:
    """Get all items for a specific infrastructure category."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == category)
    )
    rows = result.scalars().all()
    return {row.config_key: row.config_value for row in rows}


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


async def initialize_object_storage(
    endpoint: str, access_key: str, secret_key: str, region: str,
) -> dict[str, object]:
    """Initialize Object Storage by ensuring the 'global' bucket exists."""
    import aioboto3

    endpoint_url = endpoint.rstrip("/")
    bucket_name = "global"

    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "us-east-1",
            verify=False,
        ) as client:
            resp = await client.list_buckets()
            buckets = [b["Name"] for b in resp.get("Buckets", [])]

            if bucket_name in buckets:
                return {
                    "success": True,
                    "message": f"Bucket '{bucket_name}' already exists. No action needed.",
                }

            await client.create_bucket(Bucket=bucket_name)
            return {
                "success": True,
                "message": f"Bucket '{bucket_name}' created successfully.",
            }
    except Exception as exc:
        msg = str(exc)
        if "InvalidAccessKeyId" in msg or "SignatureDoesNotMatch" in msg:
            return {
                "success": False,
                "message": "Authentication failed. Please check your Access Key and Secret Key.",
            }
        return {"success": False, "message": msg}


async def test_object_storage(
    endpoint: str, access_key: str, secret_key: str, region: str,
) -> dict[str, object]:
    """Test Object Storage connectivity by listing buckets."""
    import aioboto3

    endpoint_url = endpoint.rstrip("/")

    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "us-east-1",
            verify=False,
        ) as client:
            resp = await client.list_buckets()
            buckets = resp.get("Buckets", [])
            names = [b["Name"] for b in buckets]
            return {
                "success": True,
                "message": f"Connection successful. Found {len(names)} bucket(s): {', '.join(names)}"
                if names
                else "Connection successful. No buckets found.",
            }
    except Exception as exc:
        msg = str(exc)
        if "ConnectError" in type(exc).__name__ or "ConnectionError" in type(exc).__name__:
            return {"success": False, "message": f"Cannot connect to {endpoint_url}"}
        if "InvalidAccessKeyId" in msg or "SignatureDoesNotMatch" in msg:
            return {
                "success": False,
                "message": "Authentication failed. Please check your Access Key and Secret Key.",
            }
        return {"success": False, "message": msg}


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


async def test_prometheus(host: str, port: int) -> dict[str, object]:
    """Test connectivity to Prometheus Push Gateway."""
    base_url = f"http://{host}:{port}"

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(f"{base_url}/metrics")
            if resp.status_code == 200:
                return {"success": True, "message": "Push Gateway connection successful"}
            return {
                "success": False,
                "message": f"Push Gateway returned status {resp.status_code}",
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


async def push_prometheus_config_to_agents(
    session: AsyncSession, items: dict[str, str],
) -> None:
    """Push Prometheus configuration to all REGISTERED agents."""
    result = await session.execute(
        select(ArgusAgent).where(ArgusAgent.status == "REGISTERED")
    )
    agents = result.scalars().all()

    if not agents:
        logger.info("No REGISTERED agents to push Prometheus config to")
        return

    hostnames = [a.hostname for a in agents]
    logger.info(
        "Pushing Prometheus config to %d REGISTERED agent(s): %s", len(agents), hostnames,
    )

    payload = {
        "prometheus_enable_push": items.get("prometheus_enable_push", "true"),
        "prometheus_push_cron": items.get("prometheus_push_cron", "* * * * *"),
        "prometheus_pushgateway_host": items.get("prometheus_pushgateway_host", "localhost"),
        "prometheus_pushgateway_port": items.get("prometheus_pushgateway_port", "9091"),
    }

    async def _push_to_agent(agent: ArgusAgent) -> None:
        url = f"http://{agent.ip_address}:{_AGENT_PORT}/api/v1/metrics/config"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(url, json=payload)
                if resp.status_code == 200:
                    logger.info(
                        "Pushed Prometheus config to agent %s (%s)",
                        agent.hostname, agent.ip_address,
                    )
                else:
                    logger.warning(
                        "Failed to push Prometheus config to agent %s: status=%d",
                        agent.hostname, resp.status_code,
                    )
        except Exception as exc:
            logger.warning(
                "Failed to push Prometheus config to agent %s (%s): %s",
                agent.hostname, agent.ip_address, exc,
            )

    await asyncio.gather(*[_push_to_agent(agent) for agent in agents])


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
        # Auth (Keycloak OIDC) — defaults from config file
        ("auth", "auth_type", settings.auth_type, "Authentication type (local or keycloak)"),
        ("auth", "auth_keycloak_server_url", settings.auth_keycloak_server_url, "Keycloak server URL"),
        ("auth", "auth_keycloak_realm", settings.auth_keycloak_realm, "Keycloak realm"),
        ("auth", "auth_keycloak_client_id", settings.auth_keycloak_client_id, "Keycloak client ID"),
        ("auth", "auth_keycloak_client_secret", settings.auth_keycloak_client_secret, "Keycloak client secret"),
        ("auth", "auth_keycloak_admin_role", settings.auth_keycloak_admin_role, "Admin role name"),
        ("auth", "auth_keycloak_superuser_role", settings.auth_keycloak_superuser_role, "Superuser role name"),
        ("auth", "auth_keycloak_user_role", settings.auth_keycloak_user_role, "User role name"),
        # Kubernetes
        ("k8s", "k8s_kubeconfig_path", "/etc/rancher/k3s/k3s.yaml", "Path to kubeconfig file"),
        ("k8s", "k8s_namespace_prefix", "argus-ws-", "Workspace namespace prefix"),
        ("k8s", "k8s_context", "", "Kubeconfig context (empty = default)"),
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


async def get_config_by_category(
    session: AsyncSession, category: str,
) -> dict[str, str]:
    """Get all config items for a specific category as a dict."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == category)
    )
    rows = result.scalars().all()
    return {row.config_key: row.config_value for row in rows}


async def load_auth_settings(session: AsyncSession) -> dict[str, str]:
    """Load Keycloak auth settings from DB and update the global settings object."""
    from app.core.config import settings as app_settings

    cfg = await get_config_by_category(session, "auth")
    if not cfg:
        logger.info("No auth settings in DB, using config file defaults")
        return {}

    app_settings.auth_type = cfg.get("auth_type", app_settings.auth_type)
    app_settings.auth_keycloak_server_url = cfg.get("auth_keycloak_server_url", app_settings.auth_keycloak_server_url)
    app_settings.auth_keycloak_realm = cfg.get("auth_keycloak_realm", app_settings.auth_keycloak_realm)
    app_settings.auth_keycloak_client_id = cfg.get("auth_keycloak_client_id", app_settings.auth_keycloak_client_id)
    app_settings.auth_keycloak_client_secret = cfg.get("auth_keycloak_client_secret", app_settings.auth_keycloak_client_secret)
    app_settings.auth_keycloak_admin_role = cfg.get("auth_keycloak_admin_role", app_settings.auth_keycloak_admin_role)
    app_settings.auth_keycloak_superuser_role = cfg.get("auth_keycloak_superuser_role", app_settings.auth_keycloak_superuser_role)
    app_settings.auth_keycloak_user_role = cfg.get("auth_keycloak_user_role", app_settings.auth_keycloak_user_role)

    # Clear JWKS cache so next request fetches keys from the (potentially new) Keycloak server
    from app.core.auth import _jwks_cache
    _jwks_cache.clear()

    logger.info("Auth settings loaded from DB: type=%s, server_url=%s, realm=%s",
                app_settings.auth_type, app_settings.auth_keycloak_server_url,
                app_settings.auth_keycloak_realm)
    return cfg


async def load_gitlab_settings(session: AsyncSession) -> dict[str, str]:
    """Load GitLab settings from DB and update the global settings object.

    Also reinitializes the GitLab client used by the workspace provisioner.
    """
    from app.core.config import settings as app_settings

    cfg = await get_config_by_category(session, "gitlab")
    if not cfg:
        logger.info("No GitLab settings in DB, using config file defaults")
        return {}

    app_settings.gitlab_url = cfg.get("gitlab_url", app_settings.gitlab_url)
    app_settings.gitlab_token = cfg.get("gitlab_token", app_settings.gitlab_token)

    # Reinitialize GitLab client if URL and token are available
    if app_settings.gitlab_url and app_settings.gitlab_token:
        try:
            from workspace_provisioner.router import init_gitlab_client
            init_gitlab_client(
                url=app_settings.gitlab_url,
                private_token=app_settings.gitlab_token,
            )
        except Exception as e:
            logger.warning("Failed to reinitialize GitLab client: %s", e)

    logger.info("GitLab settings loaded from DB: url=%s", app_settings.gitlab_url)
    return cfg
