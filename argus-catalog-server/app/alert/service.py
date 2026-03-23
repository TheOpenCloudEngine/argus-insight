"""리니지 변경 알림 서비스 레이어.

Alert Rule Engine을 포함한 핵심 비즈니스 로직:
1. Rule 평가: 스키마 변경 시 활성 Rule을 순회하며 scope/trigger 매칭
2. 영향 분석: 변경 컬럼과 리니지 컬럼 매핑을 교차 확인
3. 알림 생성: 매칭된 Rule에 따라 LineageAlert 생성
4. 알림 전달: 구독자 + Owner에게 IN_APP/WEBHOOK 발송
"""

import json as _json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert.models import AlertNotification, AlertRule, LineageAlert
from app.alert.schemas import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSummary,
    AlertUpdateStatus,
    PaginatedAlerts,
)
from app.catalog.models import (
    Dataset,
    DatasetColumnMapping,
    DatasetLineage,
    DatasetTag,
    Owner,
    Platform,
    Tag,
)

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "BREAKING": 2}


# ---------------------------------------------------------------------------
# Rule Engine — evaluate active rules on schema changes
# ---------------------------------------------------------------------------

async def evaluate_rules_and_create_alerts(
    session: AsyncSession,
    dataset_id: int,
    changes: list[dict],
) -> list[LineageAlert]:
    """Evaluate all active rules against schema changes and create alerts.

    Called from save_schema_snapshot() when changes are detected.

    Flow:
    1. Fetch all active rules
    2. For each rule: scope matching → trigger evaluation → alert creation
    3. Dispatch notifications to subscribers/owners for created alerts
    """
    if not changes:
        return []

    rules = (await session.execute(
        select(AlertRule).where(AlertRule.is_active == "true")
    )).scalars().all()

    if not rules:
        return []

    # Fetch changed dataset info
    dataset = (await session.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )).scalar_one_or_none()
    if not dataset:
        return []

    # Tag IDs attached to this dataset
    tag_ids = set((await session.execute(
        select(DatasetTag.tag_id).where(DatasetTag.dataset_id == dataset_id)
    )).scalars().all())

    # Lineage relationships involving this dataset
    lineages = (await session.execute(
        select(DatasetLineage).where(
            or_(
                DatasetLineage.source_dataset_id == dataset_id,
                DatasetLineage.target_dataset_id == dataset_id,
            )
        )
    )).scalars().all()
    lineage_ids = {l.id for l in lineages}

    change_map = {c["field"]: c for c in changes}
    created_alerts: list[LineageAlert] = []

    for rule in rules:
        # ── 1. Scope matching ──
        if not _match_scope(rule, dataset_id, dataset.platform_id, tag_ids, lineage_ids):
            continue

        # ── 2. Trigger evaluation + alert creation ──
        alerts = await _evaluate_trigger(
            session, rule, dataset_id, changes, change_map, lineages,
        )
        created_alerts.extend(alerts)

    if created_alerts:
        for alert in created_alerts:
            session.add(alert)
        await session.flush()

        for alert in created_alerts:
            await _dispatch_notifications(session, alert)

    if created_alerts:
        logger.info("Rule evaluation completed: dataset_id=%d, alerts_created=%d", dataset_id, len(created_alerts))
    return created_alerts


def _match_scope(
    rule: AlertRule,
    dataset_id: int,
    platform_id: int,
    tag_ids: set[int],
    lineage_ids: set[int],
) -> bool:
    """Check if rule scope matches the changed dataset."""
    if rule.scope_type == "ALL":
        return True
    if rule.scope_type == "DATASET":
        return rule.scope_id == dataset_id
    if rule.scope_type == "TAG":
        return rule.scope_id in tag_ids
    if rule.scope_type == "LINEAGE":
        return rule.scope_id in lineage_ids
    if rule.scope_type == "PLATFORM":
        return rule.scope_id == platform_id
    return False


async def _evaluate_trigger(
    session: AsyncSession,
    rule: AlertRule,
    dataset_id: int,
    changes: list[dict],
    change_map: dict[str, dict],
    lineages: list,
) -> list[LineageAlert]:
    """Evaluate rule trigger condition and create Alert objects."""
    config = _json.loads(rule.trigger_config) if rule.trigger_config else {}
    alerts: list[LineageAlert] = []

    if rule.trigger_type == "ANY":
        # Alert on any change
        severity = rule.severity_override or _auto_severity(changes)
        alerts.append(_create_alert(
            rule, dataset_id, None, None, severity,
            _build_generic_summary(changes),
            _json.dumps(changes, ensure_ascii=False),
        ))

    elif rule.trigger_type == "SCHEMA_CHANGE":
        # Filter by change types (DROP/MODIFY/ADD)
        allowed_types = set(config.get("change_types", ["DROP", "MODIFY", "ADD"]))
        filtered = [c for c in changes if c["type"] in allowed_types]
        if filtered:
            severity = rule.severity_override or _auto_severity(filtered)
            alerts.append(_create_alert(
                rule, dataset_id, None, None, severity,
                _build_generic_summary(filtered),
                _json.dumps(filtered, ensure_ascii=False),
            ))

    elif rule.trigger_type == "COLUMN_WATCH":
        # Watch specific columns only
        watch_cols = set(config.get("columns", []))
        allowed_types = set(config.get("change_types", ["DROP", "MODIFY", "ADD"]))
        matched = [c for c in changes if c["field"] in watch_cols and c["type"] in allowed_types]
        if matched:
            severity = rule.severity_override or _auto_severity(matched)
            summary_parts = [f"'{c['field']}' {c['type'].lower()}" for c in matched[:3]]
            summary = "; ".join(summary_parts)
            if len(matched) > 3:
                summary += f" (+{len(matched) - 3} more)"
            alerts.append(_create_alert(
                rule, dataset_id, None, None, severity,
                summary,
                _json.dumps(matched, ensure_ascii=False),
            ))

    elif rule.trigger_type == "MAPPING_BROKEN":
        # Fire only when mapped columns change
        if rule.scope_type == "LINEAGE" and rule.scope_id:
            # Check only the specific lineage
            target_lineages = [l for l in lineages if l.id == rule.scope_id]
        else:
            target_lineages = lineages

        for lineage in target_lineages:
            impact_alerts = await _check_mapping_impact(
                session, rule, dataset_id, lineage, change_map,
            )
            alerts.extend(impact_alerts)

    return alerts


async def _check_mapping_impact(
    session: AsyncSession,
    rule: AlertRule,
    dataset_id: int,
    lineage,
    change_map: dict[str, dict],
) -> list[LineageAlert]:
    """Check column mappings against changes for a specific lineage relationship."""
    if lineage.source_dataset_id == dataset_id:
        affected_id = lineage.target_dataset_id
        mapping_field = "source_column"
    else:
        affected_id = lineage.source_dataset_id
        mapping_field = "target_column"

    mappings = (await session.execute(
        select(DatasetColumnMapping).where(
            DatasetColumnMapping.dataset_lineage_id == lineage.id
        )
    )).scalars().all()

    if not mappings:
        return []

    impact_items = []
    for mapping in mappings:
        mapped_col = getattr(mapping, mapping_field)
        if mapped_col in change_map:
            change = change_map[mapped_col]
            other_col = (
                mapping.target_column if mapping_field == "source_column"
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
        return []

    max_sev = max(impact_items, key=lambda x: _SEVERITY_RANK.get(x["severity"], 0))
    severity = rule.severity_override or max_sev["severity"]

    parts = []
    for item in impact_items[:3]:
        if item["change_type"] == "DROP":
            parts.append(f"'{item['changed_column']}' dropped (mapped to {item['mapped_to']})")
        elif item["change_type"] == "MODIFY":
            parts.append(f"'{item['changed_column']}' modified (mapped to {item['mapped_to']})")
    summary = "; ".join(parts)
    if len(impact_items) > 3:
        summary += f" (+{len(impact_items) - 3} more)"

    return [_create_alert(
        rule, dataset_id, affected_id, lineage.id, severity,
        summary, _json.dumps(impact_items, ensure_ascii=False),
    )]


def _create_alert(
    rule: AlertRule,
    source_dataset_id: int,
    affected_dataset_id: int | None,
    lineage_id: int | None,
    severity: str,
    summary: str,
    detail: str,
) -> LineageAlert:
    return LineageAlert(
        alert_type="SCHEMA_CHANGE",
        severity=severity,
        source_dataset_id=source_dataset_id,
        affected_dataset_id=affected_dataset_id,
        lineage_id=lineage_id,
        rule_id=rule.id,
        change_summary=summary,
        change_detail=detail,
    )


def _determine_severity(change: dict) -> str:
    if change["type"] == "DROP":
        return "BREAKING"
    if change["type"] == "MODIFY":
        before = change.get("before") or {}
        after = change.get("after") or {}
        if "field_type" in before or "field_type" in after:
            return "WARNING"
        if "native_type" in before or "native_type" in after:
            return "WARNING"
        return "INFO"
    return "INFO"


def _auto_severity(changes: list[dict]) -> str:
    max_sev = "INFO"
    for c in changes:
        s = _determine_severity(c)
        if _SEVERITY_RANK.get(s, 0) > _SEVERITY_RANK.get(max_sev, 0):
            max_sev = s
    return max_sev


def _build_generic_summary(changes: list[dict]) -> str:
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
    """Dispatch notifications to rule subscribers and dataset owners."""
    rule = None
    if alert.rule_id:
        rule = (await session.execute(
            select(AlertRule).where(AlertRule.id == alert.rule_id)
        )).scalar_one_or_none()

    recipients: set[str] = set()

    # Rule subscribers
    if rule and rule.subscribers:
        for sub in rule.subscribers.split(","):
            sub = sub.strip()
            if sub:
                recipients.add(sub)

    # Owner notifications
    if not rule or rule.notify_owners == "true":
        for ds_id in (alert.source_dataset_id, alert.affected_dataset_id):
            if ds_id:
                owners = (await session.execute(
                    select(Owner.owner_name).where(Owner.dataset_id == ds_id)
                )).scalars().all()
                recipients.update(owners)

    channels = ["IN_APP"]
    if rule:
        channels = [ch.strip() for ch in rule.channels.split(",")]

    for recipient in recipients:
        for channel in channels:
            notification = AlertNotification(
                alert_id=alert.id,
                channel=channel,
                recipient=recipient,
            )
            session.add(notification)

    # Webhook dispatch
    webhook_url = rule.webhook_url if rule else None
    if webhook_url and "WEBHOOK" in channels:
        await _send_webhook(session, alert, webhook_url)

    await session.flush()


async def _send_webhook(session: AsyncSession, alert: LineageAlert, webhook_url: str) -> None:
    """Send alert payload to an external webhook URL."""
    src_name, src_platform = "", ""
    if alert.source_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.source_dataset_id)
        )).first()
        if row:
            src_name, src_platform = row

    aff_name, aff_platform = "", ""
    if alert.affected_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.affected_dataset_id)
        )).first()
        if row:
            aff_name, aff_platform = row

    # Rule name
    rule_name = None
    if alert.rule_id:
        rule = (await session.execute(
            select(AlertRule.rule_name).where(AlertRule.id == alert.rule_id)
        )).scalar_one_or_none()
        rule_name = rule

    payload = {
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "rule_name": rule_name,
        "source": {"dataset": src_name, "platform": src_platform},
        "affected": {"dataset": aff_name, "platform": aff_platform},
        "change_summary": alert.change_summary,
        "changes": _json.loads(alert.change_detail) if alert.change_detail else [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            logger.info("Webhook sent: %s (HTTP %d)", webhook_url, resp.status_code)
    except Exception as e:
        logger.warning("Webhook failed: %s - %s", webhook_url, e)


# ---------------------------------------------------------------------------
# Alert Rule CRUD
# ---------------------------------------------------------------------------

async def create_rule(session: AsyncSession, data: AlertRuleCreate) -> AlertRuleResponse:
    rule = AlertRule(
        rule_name=data.rule_name,
        description=data.description,
        scope_type=data.scope_type.value,
        scope_id=data.scope_id,
        trigger_type=data.trigger_type.value,
        trigger_config=data.trigger_config,
        severity_override=data.severity_override.value if data.severity_override else None,
        channels=data.channels,
        notify_owners=data.notify_owners,
        webhook_url=data.webhook_url,
        subscribers=data.subscribers,
        created_by=data.created_by,
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    logger.info("Alert rule created: id=%d, name=%s, scope=%s/%s", rule.id, rule.rule_name, rule.scope_type, rule.scope_id)
    return await _build_rule_response(session, rule)


async def list_rules(session: AsyncSession) -> list[AlertRuleResponse]:
    rules = (await session.execute(
        select(AlertRule).order_by(AlertRule.created_at.desc())
    )).scalars().all()
    return [await _build_rule_response(session, r) for r in rules]


async def get_rule(session: AsyncSession, rule_id: int) -> AlertRule | None:
    return (await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )).scalar_one_or_none()


async def update_rule(
    session: AsyncSession, rule_id: int, data: AlertRuleUpdate,
) -> AlertRuleResponse | None:
    rule = await get_rule(session, rule_id)
    if not rule:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "severity_override" and value is not None:
            value = value.value if hasattr(value, "value") else value
        if field == "scope_type" and value is not None:
            value = value.value if hasattr(value, "value") else value
        if field == "trigger_type" and value is not None:
            value = value.value if hasattr(value, "value") else value
        setattr(rule, field, value)
    await session.flush()
    await session.refresh(rule)
    return await _build_rule_response(session, rule)


async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
    rule = await get_rule(session, rule_id)
    if not rule:
        return False
    logger.info("Alert rule deleted: id=%d, name=%s", rule.id, rule.rule_name)
    await session.delete(rule)
    await session.flush()
    return True


async def _build_rule_response(session: AsyncSession, rule: AlertRule) -> AlertRuleResponse:
    """Build rule response with scope target name and alert count."""
    scope_name = None
    if rule.scope_type == "DATASET" and rule.scope_id:
        ds = (await session.execute(
            select(Dataset.name).where(Dataset.id == rule.scope_id)
        )).scalar_one_or_none()
        scope_name = ds
    elif rule.scope_type == "TAG" and rule.scope_id:
        tag = (await session.execute(
            select(Tag.name).where(Tag.id == rule.scope_id)
        )).scalar_one_or_none()
        scope_name = tag
    elif rule.scope_type == "LINEAGE" and rule.scope_id:
        row = (await session.execute(
            select(Dataset.name)
            .join(DatasetLineage, DatasetLineage.source_dataset_id == Dataset.id)
            .where(DatasetLineage.id == rule.scope_id)
        )).scalar_one_or_none()
        if row:
            tgt = (await session.execute(
                select(Dataset.name)
                .join(DatasetLineage, DatasetLineage.target_dataset_id == Dataset.id)
                .where(DatasetLineage.id == rule.scope_id)
            )).scalar_one_or_none()
            scope_name = f"{row} → {tgt}" if tgt else row
    elif rule.scope_type == "PLATFORM" and rule.scope_id:
        p = (await session.execute(
            select(Platform.name).where(Platform.id == rule.scope_id)
        )).scalar_one_or_none()
        scope_name = p

    # Count alerts generated by this rule
    alert_count = (await session.execute(
        select(func.count(LineageAlert.id)).where(LineageAlert.rule_id == rule.id)
    )).scalar() or 0

    return AlertRuleResponse(
        id=rule.id,
        rule_name=rule.rule_name,
        description=rule.description,
        scope_type=rule.scope_type,
        scope_id=rule.scope_id,
        scope_name=scope_name,
        trigger_type=rule.trigger_type,
        trigger_config=rule.trigger_config or "{}",
        severity_override=rule.severity_override,
        channels=rule.channels,
        notify_owners=rule.notify_owners,
        webhook_url=rule.webhook_url,
        subscribers=rule.subscribers,
        is_active=rule.is_active,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        alert_count=alert_count,
    )


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
        base = base.where(or_(
            LineageAlert.source_dataset_id == dataset_id,
            LineageAlert.affected_dataset_id == dataset_id,
        ))
        count_base = count_base.where(or_(
            LineageAlert.source_dataset_id == dataset_id,
            LineageAlert.affected_dataset_id == dataset_id,
        ))

    total = (await session.execute(count_base)).scalar() or 0
    offset = (page - 1) * page_size
    alerts = (await session.execute(
        base.order_by(LineageAlert.created_at.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    items = [await _build_alert_response(session, a) for a in alerts]
    return PaginatedAlerts(items=items, total=total, page=page, page_size=page_size)


async def get_alert(session: AsyncSession, alert_id: int) -> LineageAlert | None:
    return (await session.execute(
        select(LineageAlert).where(LineageAlert.id == alert_id)
    )).scalar_one_or_none()


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
    src_name = src_platform = None
    if alert.source_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.source_dataset_id)
        )).first()
        if row:
            src_name, src_platform = row

    aff_name = aff_platform = None
    if alert.affected_dataset_id:
        row = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == alert.affected_dataset_id)
        )).first()
        if row:
            aff_name, aff_platform = row

    rule_name = None
    if alert.rule_id:
        rule_name = (await session.execute(
            select(AlertRule.rule_name).where(AlertRule.id == alert.rule_id)
        )).scalar_one_or_none()

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
        rule_id=alert.rule_id,
        rule_name=rule_name,
        change_summary=alert.change_summary,
        change_detail=alert.change_detail,
        status=alert.status,
        resolved_by=alert.resolved_by,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
    )
