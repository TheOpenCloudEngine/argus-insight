"""Model download logging and usage statistics.

Records model download events and provides aggregated statistics
for daily, weekly, and monthly usage reporting.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ModelDownloadLog, ModelVersion

logger = logging.getLogger(__name__)


async def log_download(
    session: AsyncSession,
    model_name: str,
    version: int,
    download_type: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record a model download event.

    Truncates user_agent to 500 chars. Commit failures are logged
    but do not propagate — download logging should not break the main request.
    """
    try:
        entry = ModelDownloadLog(
            model_name=model_name,
            version=version,
            download_type=download_type,
            client_ip=client_ip,
            user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
        )
        session.add(entry)
        await session.commit()
        logger.info("Download logged: %s v%d (%s) from %s", model_name, version, download_type, client_ip)
    except Exception as e:
        logger.warning("Failed to log download for %s v%d: %s", model_name, version, e)


async def get_total_download_count(session: AsyncSession) -> int:
    """Get total download count for all models."""
    result = await session.execute(select(func.count()).select_from(ModelDownloadLog))
    return result.scalar() or 0


async def get_download_count_by_model(session: AsyncSession) -> dict[str, int]:
    """Get total download count per model."""
    result = await session.execute(
        select(ModelDownloadLog.model_name, func.count())
        .group_by(ModelDownloadLog.model_name)
        .order_by(func.count().desc())
    )
    return {name: count for name, count in result.all()}


async def get_hourly_download(
    session: AsyncSession, hours: int = 24,
) -> list[dict]:
    """Get hourly download counts for the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await session.execute(
        select(
            func.date_trunc("hour", ModelDownloadLog.downloaded_at).label("hour"),
            func.count().label("count"),
        )
        .where(ModelDownloadLog.downloaded_at >= since)
        .group_by(text("hour"))
        .order_by(text("hour"))
    )
    return [
        {"date": row.hour.strftime("%H:%M") if row.hour else "", "count": row.count}
        for row in result.all()
    ]


async def get_daily_download(
    session: AsyncSession, days: int = 30,
) -> list[dict]:
    """Get daily download counts for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date(ModelDownloadLog.downloaded_at).label("day"),
            func.count().label("count"),
        )
        .where(ModelDownloadLog.downloaded_at >= since)
        .group_by(func.date(ModelDownloadLog.downloaded_at))
        .order_by(text("day"))
    )
    return [{"date": str(row.day), "count": row.count} for row in result.all()]


async def get_weekly_download(
    session: AsyncSession, weeks: int = 12,
) -> list[dict]:
    """Get weekly download counts for the last N weeks."""
    since = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    result = await session.execute(
        select(
            func.date_trunc("week", ModelDownloadLog.downloaded_at).label("week"),
            func.count().label("count"),
        )
        .where(ModelDownloadLog.downloaded_at >= since)
        .group_by(text("week"))
        .order_by(text("week"))
    )
    return [{"date": str(row.week)[:10], "count": row.count} for row in result.all()]


async def get_monthly_download(
    session: AsyncSession, months: int = 12,
) -> list[dict]:
    """Get monthly download counts for the last N months."""
    since = datetime.now(timezone.utc) - timedelta(days=months * 30)
    result = await session.execute(
        select(
            func.date_trunc("month", ModelDownloadLog.downloaded_at).label("month"),
            func.count().label("count"),
        )
        .where(ModelDownloadLog.downloaded_at >= since)
        .group_by(text("month"))
        .order_by(text("month"))
    )
    return [{"date": str(row.month)[:7], "count": row.count} for row in result.all()]


# ---------------------------------------------------------------------------
# Publish statistics (from catalog_model_versions.finished_at where status=READY)
# ---------------------------------------------------------------------------


async def get_total_publish_count(session: AsyncSession) -> int:
    """Get total number of READY model versions (published)."""
    result = await session.execute(
        select(func.count()).where(
            ModelVersion.status == "READY",
            ModelVersion.finished_at.is_not(None),
        )
    )
    return result.scalar() or 0


async def get_hourly_publish(
    session: AsyncSession, hours: int = 24,
) -> list[dict]:
    """Get hourly publish counts for the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await session.execute(
        select(
            func.date_trunc("hour", ModelVersion.finished_at).label("hour"),
            func.count().label("count"),
        )
        .where(ModelVersion.status == "READY", ModelVersion.finished_at >= since)
        .group_by(text("hour"))
        .order_by(text("hour"))
    )
    return [
        {"date": row.hour.strftime("%H:%M") if row.hour else "", "count": row.count}
        for row in result.all()
    ]


async def get_daily_publish(
    session: AsyncSession, days: int = 30,
) -> list[dict]:
    """Get daily publish counts for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date(ModelVersion.finished_at).label("day"),
            func.count().label("count"),
        )
        .where(ModelVersion.status == "READY", ModelVersion.finished_at >= since)
        .group_by(func.date(ModelVersion.finished_at))
        .order_by(text("day"))
    )
    return [{"date": str(row.day), "count": row.count} for row in result.all()]
