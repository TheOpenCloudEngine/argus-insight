"""Settings service — load/save configuration from catalog_configuration table."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings.models import CatalogConfiguration

logger = logging.getLogger(__name__)

# Default Object Storage settings (used for seeding)
_OS_DEFAULTS: list[tuple[str, str, str]] = [
    ("object_storage_endpoint", "http://localhost:9000", "S3-compatible endpoint URL"),
    ("object_storage_access_key", "minioadmin", "S3 access key"),
    ("object_storage_secret_key", "minioadmin", "S3 secret key"),
    ("object_storage_region", "us-east-1", "S3 region"),
    ("object_storage_use_ssl", "false", "Use SSL for S3 connection"),
    ("object_storage_bucket", "model-artifacts", "S3 bucket for model artifacts"),
    ("object_storage_presigned_url_expiry", "3600", "Presigned URL expiry in seconds"),
]


async def seed_configuration(session: AsyncSession) -> None:
    """Insert default configuration rows if they don't exist."""
    for key, value, desc in _OS_DEFAULTS:
        existing = await session.execute(
            select(CatalogConfiguration).where(CatalogConfiguration.config_key == key)
        )
        if not existing.scalars().first():
            session.add(CatalogConfiguration(
                category="object_storage",
                config_key=key,
                config_value=value,
                description=desc,
            ))
            logger.info("Seeded configuration: %s = %s", key, value if "secret" not in key else "****")
    await session.commit()


async def get_config_by_category(session: AsyncSession, category: str) -> dict[str, str]:
    """Load all configuration items for a category."""
    result = await session.execute(
        select(CatalogConfiguration).where(CatalogConfiguration.category == category)
    )
    return {row.config_key: row.config_value for row in result.scalars().all()}


async def update_config(session: AsyncSession, category: str, items: dict[str, str]) -> None:
    """Update or insert configuration items for a category."""
    for key, value in items.items():
        result = await session.execute(
            select(CatalogConfiguration).where(CatalogConfiguration.config_key == key)
        )
        row = result.scalars().first()
        if row:
            row.config_value = value
        else:
            session.add(CatalogConfiguration(
                category=category,
                config_key=key,
                config_value=value,
            ))
    await session.commit()


async def load_os_settings(session: AsyncSession) -> dict[str, str]:
    """Load Object Storage settings and update the global settings object."""
    from app.core.config import settings

    cfg = await get_config_by_category(session, "object_storage")

    settings.os_endpoint = cfg.get("object_storage_endpoint", "http://localhost:9000")
    settings.os_access_key = cfg.get("object_storage_access_key", "minioadmin")
    settings.os_secret_key = cfg.get("object_storage_secret_key", "minioadmin")
    settings.os_region = cfg.get("object_storage_region", "us-east-1")
    settings.os_use_ssl = cfg.get("object_storage_use_ssl", "false").lower() in ("true", "1", "yes")
    settings.os_bucket = cfg.get("object_storage_bucket", "model-artifacts")
    settings.os_presigned_url_expiry = int(cfg.get("object_storage_presigned_url_expiry", "3600"))

    logger.info("Object Storage settings loaded from DB: endpoint=%s, bucket=%s",
                settings.os_endpoint, settings.os_bucket)
    return cfg
