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

# Default Embedding settings
_EMBEDDING_DEFAULTS: list[tuple[str, str, str]] = [
    ("embedding_enabled", "false", "Enable semantic search embedding"),
    ("embedding_provider", "local", "Embedding provider: local, openai, ollama"),
    ("embedding_model", "all-MiniLM-L6-v2", "Embedding model identifier"),
    ("embedding_api_key", "", "API key for remote providers (OpenAI)"),
    ("embedding_api_url", "", "API URL override for remote providers"),
    ("embedding_dimension", "384", "Embedding vector dimension"),
]


def _build_auth_defaults() -> list[tuple[str, str, str]]:
    """Build auth defaults from config file values (fallback for first startup)."""
    from app.core.config import settings
    return [
        ("auth_type", settings.auth_type, "Authentication type"),
        ("auth_keycloak_server_url", settings.auth_keycloak_server_url, "Keycloak server URL"),
        ("auth_keycloak_realm", settings.auth_keycloak_realm, "Keycloak realm"),
        ("auth_keycloak_client_id", settings.auth_keycloak_client_id, "Keycloak client ID"),
        ("auth_keycloak_client_secret", settings.auth_keycloak_client_secret, "Keycloak client secret"),
        ("auth_keycloak_admin_role", settings.auth_keycloak_admin_role, "Admin role name"),
        ("auth_keycloak_superuser_role", settings.auth_keycloak_superuser_role, "Superuser role name"),
        ("auth_keycloak_user_role", settings.auth_keycloak_user_role, "User role name"),
    ]


def _build_cors_defaults() -> list[tuple[str, str, str]]:
    """Build CORS defaults from config file values."""
    from app.core.config import settings
    origins = settings.cors_origins
    origins_str = ",".join(origins) if isinstance(origins, list) else str(origins)
    return [
        ("cors_origins", origins_str, "Allowed CORS origins (comma-separated)"),
    ]


async def seed_configuration(session: AsyncSession) -> None:
    """Insert default configuration rows if they don't exist."""
    all_defaults = [
        ("object_storage", _OS_DEFAULTS),
        ("embedding", _EMBEDDING_DEFAULTS),
        ("auth", _build_auth_defaults()),
        ("cors", _build_cors_defaults()),
    ]
    for category, defaults in all_defaults:
        for key, value, desc in defaults:
            existing = await session.execute(
                select(CatalogConfiguration).where(CatalogConfiguration.config_key == key)
            )
            if not existing.scalars().first():
                session.add(CatalogConfiguration(
                    category=category,
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
    logger.info("Configuration updated: category=%s, %d item(s)", category, len(items))


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


async def load_embedding_settings(session: AsyncSession) -> dict[str, str]:
    """Load embedding settings from DB and initialize the provider if enabled."""
    cfg = await get_config_by_category(session, "embedding")
    enabled = cfg.get("embedding_enabled", "false").lower() in ("true", "1", "yes")

    if enabled:
        from app.embedding.registry import initialize_provider
        try:
            await initialize_provider(cfg)
        except Exception as e:
            logger.warning("Embedding provider initialization failed: %s", e)
    else:
        logger.info("Embedding is disabled")

    return cfg


async def load_auth_settings(session: AsyncSession) -> dict[str, str]:
    """Load Keycloak auth settings from DB and update the global settings object."""
    from app.core.config import settings

    cfg = await get_config_by_category(session, "auth")
    if not cfg:
        logger.info("No auth settings in DB, using config file defaults")
        return {}

    settings.auth_type = cfg.get("auth_type", settings.auth_type)
    settings.auth_keycloak_server_url = cfg.get("auth_keycloak_server_url", settings.auth_keycloak_server_url)
    settings.auth_keycloak_realm = cfg.get("auth_keycloak_realm", settings.auth_keycloak_realm)
    settings.auth_keycloak_client_id = cfg.get("auth_keycloak_client_id", settings.auth_keycloak_client_id)
    settings.auth_keycloak_client_secret = cfg.get("auth_keycloak_client_secret", settings.auth_keycloak_client_secret)
    settings.auth_keycloak_admin_role = cfg.get("auth_keycloak_admin_role", settings.auth_keycloak_admin_role)
    settings.auth_keycloak_superuser_role = cfg.get("auth_keycloak_superuser_role", settings.auth_keycloak_superuser_role)
    settings.auth_keycloak_user_role = cfg.get("auth_keycloak_user_role", settings.auth_keycloak_user_role)

    # Clear JWKS cache so next request fetches keys from the (potentially new) Keycloak server
    from app.core.auth import _jwks_cache
    _jwks_cache.clear()

    logger.info("Auth settings loaded from DB: server_url=%s, realm=%s",
                settings.auth_keycloak_server_url, settings.auth_keycloak_realm)
    return cfg


async def load_cors_settings(session: AsyncSession) -> dict[str, str]:
    """Load CORS settings from DB and update the global settings object."""
    from app.core.config import settings

    cfg = await get_config_by_category(session, "cors")
    if not cfg:
        logger.info("No CORS settings in DB, using config file defaults")
        return {}

    origins_str = cfg.get("cors_origins", "*")
    settings.cors_origins = [o.strip() for o in origins_str.split(",") if o.strip()]

    logger.info("CORS settings loaded from DB: origins=%s", settings.cors_origins)
    return cfg
