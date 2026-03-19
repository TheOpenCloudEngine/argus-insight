"""Infrastructure configuration service."""

import logging
from collections import defaultdict

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
        ("domain", "pdns_server_id", "", "PowerDNS server ID"),
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
