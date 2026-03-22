"""Model access logging and usage statistics.

Records model access events and provides aggregated statistics
for daily, weekly, and monthly usage reporting.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ModelAccessLog, ModelVersion

logger = logging.getLogger(__name__)


async def log_access(
    session: AsyncSession,
    model_name: str,
    version: int,
    access_type: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record a model access event.

    Truncates user_agent to 500 chars. Commit failures are logged
    but do not propagate — access logging should not break the main request.
    """
    try:
        entry = ModelAccessLog(
            model_name=model_name,
            version=version,
            access_type=access_type,
            client_ip=client_ip,
            user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
        )
        session.add(entry)
        await session.commit()
        logger.info("Access logged: %s v%d (%s) from %s", model_name, version, access_type, client_ip)
    except Exception as e:
        logger.warning("Failed to log access for %s v%d: %s", model_name, version, e)


async def get_total_access_count(session: AsyncSession) -> int:
    """Get total access count for all models."""
    result = await session.execute(select(func.count()).select_from(ModelAccessLog))
    return result.scalar() or 0


async def get_access_count_by_model(session: AsyncSession) -> dict[str, int]:
    """Get total access count per model."""
    result = await session.execute(
        select(ModelAccessLog.model_name, func.count())
        .group_by(ModelAccessLog.model_name)
        .order_by(func.count().desc())
    )
    return {name: count for name, count in result.all()}


async def get_hourly_access(
    session: AsyncSession, hours: int = 24,
) -> list[dict]:
    """Get hourly access counts for the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await session.execute(
        select(
            func.date_trunc("hour", ModelAccessLog.accessed_at).label("hour"),
            func.count().label("count"),
        )
        .where(ModelAccessLog.accessed_at >= since)
        .group_by(text("hour"))
        .order_by(text("hour"))
    )
    return [
        {"date": row.hour.strftime("%H:%M") if row.hour else "", "count": row.count}
        for row in result.all()
    ]


async def get_daily_access(
    session: AsyncSession, days: int = 30,
) -> list[dict]:
    """Get daily access counts for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date(ModelAccessLog.accessed_at).label("day"),
            func.count().label("count"),
        )
        .where(ModelAccessLog.accessed_at >= since)
        .group_by(func.date(ModelAccessLog.accessed_at))
        .order_by(text("day"))
    )
    return [{"date": str(row.day), "count": row.count} for row in result.all()]


async def get_daily_access_by_model(
    session: AsyncSession, days: int = 30,
) -> list[dict]:
    """Get daily access counts per model for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date(ModelAccessLog.accessed_at).label("day"),
            ModelAccessLog.model_name,
            func.count().label("count"),
        )
        .where(ModelAccessLog.accessed_at >= since)
        .group_by(func.date(ModelAccessLog.accessed_at), ModelAccessLog.model_name)
        .order_by(text("day"))
    )
    return [
        {"date": str(row.day), "model_name": row.model_name, "count": row.count}
        for row in result.all()
    ]


async def get_weekly_access(
    session: AsyncSession, weeks: int = 12,
) -> list[dict]:
    """Get weekly access counts for the last N weeks."""
    since = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    result = await session.execute(
        select(
            func.date_trunc("week", ModelAccessLog.accessed_at).label("week"),
            func.count().label("count"),
        )
        .where(ModelAccessLog.accessed_at >= since)
        .group_by(text("week"))
        .order_by(text("week"))
    )
    return [{"date": str(row.week)[:10], "count": row.count} for row in result.all()]


async def get_monthly_access(
    session: AsyncSession, months: int = 12,
) -> list[dict]:
    """Get monthly access counts for the last N months."""
    since = datetime.now(timezone.utc) - timedelta(days=months * 30)
    result = await session.execute(
        select(
            func.date_trunc("month", ModelAccessLog.accessed_at).label("month"),
            func.count().label("count"),
        )
        .where(ModelAccessLog.accessed_at >= since)
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
        .where(
            ModelVersion.status == "READY",
            ModelVersion.finished_at >= since,
        )
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
        .where(
            ModelVersion.status == "READY",
            ModelVersion.finished_at >= since,
        )
        .group_by(func.date(ModelVersion.finished_at))
        .order_by(text("day"))
    )
    return [{"date": str(row.day), "count": row.count} for row in result.all()]
