"""S3-compatible object storage client for Catalog Server.

Provides async S3 operations via aioboto3, compatible with AWS S3 and MinIO.
Configuration is loaded from config.yml (object_storage section).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aioboto3

from app.core.config import settings

logger = logging.getLogger(__name__)

_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator:
    """Yield an async S3 client configured from settings."""
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=settings.os_endpoint,
        aws_access_key_id=settings.os_access_key,
        aws_secret_access_key=settings.os_secret_key,
        region_name=settings.os_region,
        use_ssl=settings.os_use_ssl,
    ) as client:
        yield client


async def ensure_bucket(bucket: str | None = None) -> None:
    """Create the bucket if it does not exist."""
    bucket = bucket or settings.os_bucket
    async with get_s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=bucket)
        except Exception:
            logger.info("Bucket '%s' not found, creating...", bucket)
            await s3.create_bucket(Bucket=bucket)
            logger.info("Bucket '%s' created", bucket)
