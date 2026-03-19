"""S3-compatible object storage client.

Provides a shared aioboto3 session for async S3 operations,
compatible with both AWS S3 and MinIO.

Object Storage settings are loaded dynamically from the database
(argus_configuration table, category='argus') instead of static config files.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aioboto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

_session: aioboto3.Session | None = None


def get_session() -> aioboto3.Session:
    """Get or create the shared aioboto3 session."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


async def _load_os_settings() -> dict[str, str]:
    """Load Object Storage settings from the argus_configuration table."""
    async with async_session() as db:
        result = await db.execute(
            select(ArgusConfiguration).where(
                ArgusConfiguration.category == "argus",
                ArgusConfiguration.config_key.like("object_storage_%"),
            )
        )
        rows = result.scalars().all()

    cfg: dict[str, str] = {}
    for row in rows:
        cfg[row.config_key] = row.config_value
    return cfg


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator:
    """Yield an async S3 client configured from database settings.

    Usage::

        async with get_s3_client() as s3:
            await s3.list_objects_v2(Bucket="my-bucket")
    """
    cfg = await _load_os_settings()
    endpoint_url = cfg.get("object_storage_endpoint", "http://localhost:9000")
    access_key = cfg.get("object_storage_access_key", "minioadmin")
    secret_key = cfg.get("object_storage_secret_key", "minioadmin")
    region = cfg.get("object_storage_region", "us-east-1")
    use_ssl = cfg.get("object_storage_use_ssl", "false").lower() in ("true", "1", "yes")

    session = get_session()
    async with session.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        use_ssl=use_ssl,
    ) as client:
        yield client


async def get_s3_settings() -> dict[str, str]:
    """Return the Object Storage settings from the database.

    Useful for callers that need individual setting values
    (e.g. multipart_threshold, presigned_url_expiry).
    """
    return await _load_os_settings()


async def ensure_bucket(bucket: str) -> None:
    """Create the bucket if it does not exist."""
    async with get_s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=bucket)
        except Exception:
            logger.info("Bucket '%s' not found, creating...", bucket)
            await s3.create_bucket(Bucket=bucket)
            logger.info("Bucket '%s' created", bucket)
