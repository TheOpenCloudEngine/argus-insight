"""Settings API for Catalog Server.

Provides endpoints to read/update Object Storage (MinIO) configuration
and test connectivity. Settings are stored in the catalog_configuration table.
"""

import logging

import aioboto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.settings.service import get_config_by_category, load_os_settings, update_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ObjectStorageConfig(BaseModel):
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    use_ssl: bool = False
    bucket: str = "model-artifacts"
    presigned_url_expiry: int = 3600


class ObjectStorageTestRequest(BaseModel):
    endpoint: str = Field(..., description="S3-compatible endpoint URL")
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    bucket: str = "model-artifacts"


class TestResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Get / Update Object Storage config (DB-backed)
# ---------------------------------------------------------------------------

@router.get("/object-storage", response_model=ObjectStorageConfig)
async def get_object_storage_config(session: AsyncSession = Depends(get_session)):
    """Return current Object Storage configuration from database."""
    cfg = await get_config_by_category(session, "object_storage")
    return ObjectStorageConfig(
        endpoint=cfg.get("object_storage_endpoint", ""),
        access_key=cfg.get("object_storage_access_key", ""),
        secret_key=cfg.get("object_storage_secret_key", ""),
        region=cfg.get("object_storage_region", "us-east-1"),
        use_ssl=cfg.get("object_storage_use_ssl", "false").lower() in ("true", "1", "yes"),
        bucket=cfg.get("object_storage_bucket", "model-artifacts"),
        presigned_url_expiry=int(cfg.get("object_storage_presigned_url_expiry", "3600")),
    )


@router.put("/object-storage")
async def update_object_storage_config(
    body: ObjectStorageConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update Object Storage configuration in database and reload into memory."""
    items = {
        "object_storage_endpoint": body.endpoint,
        "object_storage_access_key": body.access_key,
        "object_storage_secret_key": body.secret_key,
        "object_storage_region": body.region,
        "object_storage_use_ssl": str(body.use_ssl).lower(),
        "object_storage_bucket": body.bucket,
        "object_storage_presigned_url_expiry": str(body.presigned_url_expiry),
    }
    await update_config(session, "object_storage", items)

    # Reload into memory
    await load_os_settings(session)

    # Reset S3 session so next request uses new config
    from app.core import s3
    s3._session = None

    logger.info("Object Storage config saved to DB: endpoint=%s, bucket=%s", body.endpoint, body.bucket)
    return {"status": "ok", "message": "Object Storage configuration saved"}


# ---------------------------------------------------------------------------
# Test connectivity
# ---------------------------------------------------------------------------

@router.post("/object-storage/test", response_model=TestResponse)
async def test_object_storage(body: ObjectStorageTestRequest):
    """Test S3 connectivity by checking if the configured bucket exists."""
    logger.info("Object Storage test: endpoint=%s, bucket=%s", body.endpoint, body.bucket)
    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=body.endpoint,
            aws_access_key_id=body.access_key,
            aws_secret_access_key=body.secret_key,
            region_name=body.region,
        ) as s3:
            await s3.head_bucket(Bucket=body.bucket)
            msg = f"Connection successful. Bucket '{body.bucket}' exists."
            logger.info("Object Storage test succeeded: %s", msg)
            return TestResponse(success=True, message=msg)
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NoSuchBucket" in error_msg or "Not Found" in error_msg:
            msg = f"Bucket '{body.bucket}' does not exist."
        elif "InvalidAccessKeyId" in error_msg or "SignatureDoesNotMatch" in error_msg:
            msg = f"Authentication failed: invalid access key or secret key."
        elif "ConnectTimeoutError" in error_msg or "EndpointConnectionError" in error_msg:
            msg = f"Connection failed: unable to reach {body.endpoint}."
        else:
            msg = f"Error: {error_msg}"
        logger.info("Object Storage test failed: %s", msg)
        return TestResponse(success=False, message=msg)
