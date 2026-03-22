"""Alert service layer.

Provides impact analysis, alert creation, subscription management,
and webhook notification dispatch for schema change events.
"""

import json as _json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert.models import AlertNotification, AlertSubscription, LineageAlert
from app.alert.schemas import (
    AlertResponse,
    AlertSummary,
    AlertUpdateStatus,
    PaginatedAlerts,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.catalog.models import (
    Dataset,
    DatasetColumnMapping,
    DatasetLineage,
    Owner,
    Platform,
)

logger = logging.getLogger(__name__)

# Severity ranking for comparison
_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "BREAKING": 2}


# ---------------------------------------------------------------------------
# Impact Analysis
# ---------------------------------------------------------------------------

async def analyze_and_create_alerts(
    session: AsyncSession,
    dataset_id: int,
    changes: list[dict],
) -> list[LineageAlert]:
    """Analyze schema changes against lineage column mappings and create alerts.

    Called after a SchemaSnapshot is saved with actual changes.

    Args:
        dataset_id: The dataset whose schema changed.
        changes: List of change dicts from detect_schema_changes().
                 Each: {"type": "ADD|DROP|MODIFY", "field": "col_name", ...}

    Returns:
        List of created LineageAlert objects.
    """
    if not changes:
        return []

    # Find all lineage relationships involving this dataset
    lineages = (await session.execute(
        select(DatasetLineage).where(
            or_(
                DatasetLineage.source_dataset_id == dataset_id,
                DatasetLineage.target_dataset_id == dataset_id,
            )
        )
    )).scalars().all()

    if not lineages:
        return []

    # Build change lookup: field_name -> change_info
    change_map = {c["field"]: c for c in changes}

    created_alerts: list[LineageAlert] = []

    for lineage in lineages:
        # Determine which side changed and which side is affected
        if lineage.source_dataset_id == dataset_id:
            affected_id = lineage.target_dataset_id
            mapping_field = "source_column"
        else:
            affected_id = lineage.source_dataset_id
            mapping_field = "target_column"

        # Get column mappings for this lineage
        mappings = (await session.execute(
            select(DatasetColumnMapping).where(
                DatasetColumnMapping.dataset_lineage_id == lineage.id
            )
        )).scalars().all()

        if not mappings:
            # No column mappings — create a generic INFO alert for any non-ADD change
            has_breaking = any(c["type"] in ("DROP", "MODIFY") for c in changes)
            if has_breaking:
                alert = LineageAlert(
                    alert_type="SCHEMA_CHANGE",
                    severity="INFO",
                    source_dataset_id=dataset_id,
                    affected_dataset_id=affected_id,
                    lineage_id=lineage.id,
                    change_summary=_build_generic_summary(changes),
                    change_detail=_json.dumps(changes, ensure_ascii=False),
                )
                session.add(alert)
                created_alerts.append(alert)
            continue

        # Check each mapping against changes
        impact_items = []
        for mapping in mappings:
            mapped_col = getattr(mapping, mapping_field)
            if mapped_col in change_map:
                change = change_map[mapped_col]
                other_col = (
                    mapping.target_column
                    if mapping_field == "source_column"
                    else mapping.source_column
                )
                severity = _determine_severity(change)
                impact_items.append({
                    "changed_column": mapped_col,
                    "mapped_to": other_col,
                    "change_type": change["type"],
                    "severity": severity,
                    "before": change.get("before"),
                    "after": change.get("after"),
                })

        if not impact_items:
            continue

        # Use highest severity among impacts
        max_severity = max(impact_items, key=lambda x: _SEVERITY_RANK.get(x["severity"], 0))
        overall_severity = max_severity["severity"]

        summary = _build_impact_summary(impact_items)
        alert = LineageAlert(
            alert_type="SCHEMA_CHANGE",
            severity=overall_severity,
            source_dataset_id=dataset_id,
            affected_dataset_id=affected_id,
            lineage_id=lineage.id,
            change_summary=summary,
            change_detail=_json.dumps(impact_items, ensure_ascii=False),
        )
        session.add(alert)
        created_alerts.append(alert)

    if created_alerts:
        await session.flush()

        # Dispatch notifications for each alert
        for alert in created_alerts:
            await _dispatch_notifications(session, alert)

    return created_alerts


def _determine_severity(change: dict) -> str:
    """Determine alert severity from a single schema change."""
    if change["type"] == "DROP":
        return "BREAKING"
    if change["type"] == "MODIFY":
        # Type change is WARNING, other modifications are INFO
        before = change.get("before") or {}
        after = change.get("after") or {}
        if "field_type" in before or "field_type" in after:
            return "WARNING"
        if "native_type" in before or "native_type" in after:
            return "WARNING"
        return "INFO"
    return "INFO"


def _build_impact_summary(items: list[dict]) -> str:
    """Build a human-readable summary from impact items."""
    parts = []
    for item in items[:3]:  # max 3 in summary
        if item["change_type"] == "DROP":
            parts.append(f"'{item['changed_column']}' dropped (mapped to {item['mapped_to']})")
        elif item["change_type"] == "MODIFY":
            parts.append(f"'{item['changed_column']}' modified (mapped to {item['mapped_to']})")
        else:
            parts.append(f"'{item['changed_column']}' added")
    summary = "; ".join(parts)
    if len(items) > 3:
        summary += f" (+{len(items) - 3} more)"
    return summary


def _build_generic_summary(changes: list[dict]) -> str:
    """Build a generic summary when no column mappings exist."""
    added = sum(1 for c in changes if c["type"] == "ADD")
    dropped = sum(1 for c in changes if c["type"] == "DROP")
    modified = sum(1 for c in changes if c["type"] == "MODIFY")
    parts = []
    if dropped:
        parts.append(f"{dropped} column(s) dropped")
    if modified:
        parts.append(f"{modified} column(s) modified")
    if added:
        parts.append(f"{added} column(s) added")
    return "Schema changed: " + ", ".join(parts)


# ---------------------------------------------------------------------------
# Notification Dispatch
# ---------------------------------------------------------------------------

async def _dispatch_notifications(session: AsyncSession, alert: LineageAlert) -> None:
    """Find subscribers and dispatch notifications."""
    # Find subscribers matching this alert's scope and severity
    subs = (await session.execute(
        select(AlertSubscription).where(
            AlertSubscription.is_active == "true",
        )
    )).scalars().all()

    for sub in subs:
        # Check severity filter
        if _SEVERITY_RANK.get(alert.severity, 0) < _SEVERITY_RANK.get(sub.severity_filter, 0):
            continue

        # Check scope
        if sub.scope_type == "DATASET":
            if sub.scope_id not in (alert.source_dataset_id, alert.affected_dataset_id):
                continue
        elif sub.scope_type == "PIPELINE":
            # Check if the lineage belongs to this pipeline
            if alert.lineage_id:
                lineage = (await session.execute(
                    select(DatasetLineage.pipeline_id).where(
                        DatasetLineage.id == alert.lineage_id
                    )
                )).scalar_one_or_none()
                if lineage != sub.scope_id:
                    continue
            else:
                continue
        elif sub.scope_type == "PLATFORM":
            # Check if source or affected dataset belongs to this platform
            ds = (await session.execute(
                select(Dataset.platform_id).where(Dataset.id == alert.source_dataset_id)
            )).scalar_one_or_none()
            if ds != sub.scope_id:
                continue
        # scope_type == "ALL" matches everything

        # Send to each channel
        channels = [ch.strip() for ch in sub.channels.split(",")]
        for channel in channels:
            notification = AlertNotification(
                alert_id=alert.id,
                channel=channel,
                recipient=sub.user_id,
            )
            session.add(notification)

            if channel == "WEBHOOK":
                await _send_webhook(session, alert, sub.user_id)

    # Also notify dataset owners (IN_APP)
    owner_names = set()
    for ds_id in (alert.source_dataset_id, alert.affected_dataset_id):
        if ds_id:
            owners = (await session.execute(
                select(Owner.owner_name).where(Owner.dataset_id == ds_id)
            )).scalars().all()
            owner_names.update(owners)

    for owner in owner_names:
        notification = AlertNotification(
            alert_id=alert.id,
            channel="IN_APP",
            recipient=owner,
        )
        session.add(notification)

    await session.flush()


async def _send_webhook(session: AsyncSession, alert: LineageAlert, webhook_url: str) -> None:
    """Send alert payload to a webhook URL."""
    # Build source/affected dataset names
    src_name = ""
    src_platform = ""
    if alert.source_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.source_dataset_id)
        )).first()
        if row:
            src_name, src_platform = row

    aff_name = ""
    aff_platform = ""
    if alert.affected_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.affected_dataset_id)
        )).first()
        if row:
            aff_name, aff_platform = row

    payload = {
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "source": {"dataset": src_name, "platform": src_platform},
        "affected": {"dataset": aff_name, "platform": aff_platform},
        "change_summary": alert.change_summary,
        "changes": _json.loads(alert.change_detail) if alert.change_detail else [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            logger.info("Webhook sent to %s: %d", webhook_url, resp.status_code)
    except Exception as e:
        logger.warning("Webhook failed for %s: %s", webhook_url, e)


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

async def list_alerts(
    session: AsyncSession,
    status: str | None = None,
    severity: str | None = None,
    dataset_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedAlerts:
    base = select(LineageAlert)
    count_base = select(func.count(LineageAlert.id))

    if status:
        base = base.where(LineageAlert.status == status)
        count_base = count_base.where(LineageAlert.status == status)
    if severity:
        base = base.where(LineageAlert.severity == severity)
        count_base = count_base.where(LineageAlert.severity == severity)
    if dataset_id:
        base = base.where(
            or_(
                LineageAlert.source_dataset_id == dataset_id,
                LineageAlert.affected_dataset_id == dataset_id,
            )
        )
        count_base = count_base.where(
            or_(
                LineageAlert.source_dataset_id == dataset_id,
                LineageAlert.affected_dataset_id == dataset_id,
            )
        )

    total = (await session.execute(count_base)).scalar() or 0

    offset = (page - 1) * page_size
    alerts = (await session.execute(
        base.order_by(LineageAlert.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    items = [await _build_alert_response(session, a) for a in alerts]
    return PaginatedAlerts(items=items, total=total, page=page, page_size=page_size)


async def get_alert(session: AsyncSession, alert_id: int) -> LineageAlert | None:
    result = await session.execute(
        select(LineageAlert).where(LineageAlert.id == alert_id)
    )
    return result.scalar_one_or_none()


async def update_alert_status(
    session: AsyncSession, alert_id: int, data: AlertUpdateStatus,
) -> AlertResponse | None:
    alert = await get_alert(session, alert_id)
    if not alert:
        return None
    alert.status = data.status.value
    if data.status.value in ("RESOLVED", "DISMISSED"):
        alert.resolved_by = data.resolved_by
        alert.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(alert)
    return await _build_alert_response(session, alert)


async def get_alert_summary(session: AsyncSession) -> AlertSummary:
    """Get open alert counts by severity for the bell badge."""
    rows = (await session.execute(
        select(LineageAlert.severity, func.count(LineageAlert.id))
        .where(LineageAlert.status == "OPEN")
        .group_by(LineageAlert.severity)
    )).all()

    summary = AlertSummary()
    for severity, count in rows:
        summary.total_open += count
        if severity == "BREAKING":
            summary.breaking_count = count
        elif severity == "WARNING":
            summary.warning_count = count
        elif severity == "INFO":
            summary.info_count = count
    return summary


async def _build_alert_response(session: AsyncSession, alert: LineageAlert) -> AlertResponse:
    src_name = None
    src_platform = None
    if alert.source_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.source_dataset_id)
        )).first()
        if row:
            src_name, src_platform = row

    aff_name = None
    aff_platform = None
    if alert.affected_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.affected_dataset_id)
        )).first()
        if row:
            aff_name, aff_platform = row

    return AlertResponse(
        id=alert.id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        source_dataset_id=alert.source_dataset_id,
        source_dataset_name=src_name,
        source_platform_type=src_platform,
        affected_dataset_id=alert.affected_dataset_id,
        affected_dataset_name=aff_name,
        affected_platform_type=aff_platform,
        lineage_id=alert.lineage_id,
        change_summary=alert.change_summary,
        change_detail=alert.change_detail,
        status=alert.status,
        resolved_by=alert.resolved_by,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
    )


# ---------------------------------------------------------------------------
# Subscription CRUD
# ---------------------------------------------------------------------------

async def create_subscription(
    session: AsyncSession, data: SubscriptionCreate,
) -> SubscriptionResponse:
    sub = AlertSubscription(
        user_id=data.user_id,
        scope_type=data.scope_type.value,
        scope_id=data.scope_id,
        channels=data.channels,
        severity_filter=data.severity_filter.value,
    )
    session.add(sub)
    await session.flush()
    await session.refresh(sub)
    return SubscriptionResponse.model_validate(sub)


async def list_subscriptions(
    session: AsyncSession, user_id: str | None = None,
) -> list[SubscriptionResponse]:
    stmt = select(AlertSubscription)
    if user_id:
        stmt = stmt.where(AlertSubscription.user_id == user_id)
    stmt = stmt.order_by(AlertSubscription.created_at.desc())
    result = await session.execute(stmt)
    return [SubscriptionResponse.model_validate(s) for s in result.scalars().all()]


async def delete_subscription(session: AsyncSession, sub_id: int) -> bool:
    sub = (await session.execute(
        select(AlertSubscription).where(AlertSubscription.id == sub_id)
    )).scalar_one_or_none()
    if not sub:
        return False
    await session.delete(sub)
    await session.flush()
    return True
