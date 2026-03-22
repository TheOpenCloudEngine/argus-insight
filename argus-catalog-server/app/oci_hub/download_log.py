"""OCI Model Hub download logging.

Logs download events to the OCI-specific download log table
(catalog_oci_model_download_log), separate from MLflow's
catalog_model_download_log.
"""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.oci_hub.models import OciModel, OciModelDownloadLog

logger = logging.getLogger(__name__)


async def log_oci_download(
    session: AsyncSession,
    model_name: str,
    version: int,
    download_type: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Log a download event for an OCI model.

    Only logs if the model_name exists in catalog_oci_models.
    Also increments the denormalized download_count on the model.
    """
    try:
        # Check if this is an OCI model
        result = await session.execute(
            select(OciModel.id).where(OciModel.name == model_name)
        )
        if not result.scalars().first():
            return  # Not an OCI model, skip

        # Log the download event
        entry = OciModelDownloadLog(
            model_name=model_name,
            version=version,
            download_type=download_type,
            client_ip=client_ip,
            user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
        )
        session.add(entry)

        # Increment denormalized counter
        await session.execute(
            update(OciModel)
            .where(OciModel.name == model_name)
            .values(download_count=OciModel.download_count + 1)
        )

        await session.commit()
        logger.info("OCI download logged: %s v%d (%s)", model_name, version, download_type)
    except Exception as e:
        logger.warning("Failed to log OCI download for %s v%d: %s", model_name, version, e)
