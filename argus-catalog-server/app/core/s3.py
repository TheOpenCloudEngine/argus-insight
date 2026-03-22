"""S3-compatible object storage client for Catalog Server.

Provides async S3 operations via aioboto3, compatible with AWS S3 and MinIO.
Configuration is loaded from the catalog_configuration DB table at startup
and stored in the global settings object.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aioboto3

from app.core.config import settings

logger = logging.getLogger(__name__)

_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    """Get or create the shared aioboto3 session (lazily initialized)."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator:
    """Yield an async S3 client configured from settings.

    Usage::
        async with get_s3_client() as s3:
            await s3.list_objects_v2(Bucket="my-bucket")
    """
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
    """Create the bucket if it does not exist.

    Checks for bucket existence via head_bucket, and creates it if missing.
    Logs warnings on creation failure instead of raising.
    """
    bucket = bucket or settings.os_bucket
    async with get_s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=bucket)
            logger.info("Bucket '%s' exists", bucket)
        except Exception:
            try:
                logger.info("Bucket '%s' not found, creating...", bucket)
                await s3.create_bucket(Bucket=bucket)
                logger.info("Bucket '%s' created successfully", bucket)
            except Exception as create_err:
                logger.warning("Failed to create bucket '%s': %s", bucket, create_err)
