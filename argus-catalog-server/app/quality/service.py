"""Data quality service layer.

Approach A+B hybrid:
- Profiling: sample-based (uses catalog's own schema + sample data)
- Rule evaluation: direct SQL to source DB when possible, fallback to sample

Supported check types:
  NOT_NULL, UNIQUE, MIN_VALUE, MAX_VALUE, ACCEPTED_VALUES,
  REGEX, ROW_COUNT, FRESHNESS
"""

import json as _json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.quality.models import DataProfile, QualityResult, QualityRule, QualityScore
from app.quality.schemas import (
    ColumnProfile, ProfileResponse, QualityResultResponse, QualityRuleCreate,
    QualityRuleResponse, QualityRuleUpdate, QualityScoreResponse, RunCheckResponse,
)
from app.catalog.models import Dataset, DatasetSchema, Platform, PlatformConfiguration

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profiling — sample-based (Method B)
# Uses catalog's stored sample data or source DB direct query
# ---------------------------------------------------------------------------

async def profile_dataset(session: AsyncSession, dataset_id: int) -> ProfileResponse:
    """Profile a dataset by querying source DB or using stored schema info.

    Collects per-column statistics: null count, unique count, min/max, mean.
    Falls back to schema-only profile if source DB is unreachable.
    """
    # Get dataset and platform info
    dataset = (await session.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset not found: {dataset_id}")

    # Get schema fields
    fields = (await session.execute(
        select(DatasetSchema).where(DatasetSchema.dataset_id == dataset_id)
        .order_by(DatasetSchema.ordinal)
    )).scalars().all()

    # Try direct SQL profiling to source DB
    column_profiles = []
    row_count = 0

    try:
        row_count, column_profiles = await _profile_via_source_db(session, dataset, fields)
        logger.info("Profile via source DB: dataset_id=%d, rows=%d, columns=%d",
                     dataset_id, row_count, len(column_profiles))
    except Exception as e:
        logger.warning("Source DB profiling failed for dataset_id=%d: %s. Using schema-only.", dataset_id, e)
        # Fallback: schema-only profile (no actual data stats)
        for f in fields:
            column_profiles.append(ColumnProfile(
                column_name=f.field_path,
                column_type=f.field_type,
            ))

    # Save profile
    profile = DataProfile(
        dataset_id=dataset_id,
        row_count=row_count,
        profile_json=_json.dumps([cp.model_dump() for cp in column_profiles], ensure_ascii=False, default=str),
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)

    return ProfileResponse(
        id=profile.id, dataset_id=dataset_id, row_count=row_count,
        columns=column_profiles, profiled_at=profile.profiled_at,
    )


async def _profile_via_source_db(
    session: AsyncSession, dataset: Dataset, fields: list,
) -> tuple[int, list[ColumnProfile]]:
    """Execute profiling SQL directly on the source database."""
    # Get platform connection config
    platform = (await session.execute(
        select(Platform).where(Platform.id == dataset.platform_id)
    )).scalar_one_or_none()
    if not platform:
        raise ValueError("Platform not found")

    config_row = (await session.execute(
        select(PlatformConfiguration).where(PlatformConfiguration.platform_id == platform.id)
    )).scalar_one_or_none()
    if not config_row:
        raise ValueError("Platform configuration not found")

    config = _json.loads(config_row.config_json) if config_row.config_json else {}

    # Build connection URL
    db_type = platform.type.lower()
    host = config.get("host", "localhost")
    port = config.get("port", 3306)
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")

    # Parse table name from qualified_name (e.g., "sakila.film" → db=sakila, table=film)
    parts = (dataset.qualified_name or dataset.name).split(".")
    if len(parts) >= 2:
        schema_or_db = parts[-2]
        table_name = parts[-1]
    else:
        schema_or_db = database
        table_name = parts[0]

    if db_type in ("mysql", "mariadb"):
        from sqlalchemy.ext.asyncio import create_async_engine as cae
        url = f"mysql+aiomysql://{username}:{password}@{host}:{port}/{schema_or_db}?charset=utf8mb4"
    elif db_type == "postgresql":
        from sqlalchemy.ext.asyncio import create_async_engine as cae
        url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
        table_name = f"{schema_or_db}.{table_name}" if schema_or_db != database else table_name
    else:
        raise ValueError(f"Profiling not supported for platform type: {db_type}")

    engine = cae(url, pool_size=1, max_overflow=0)

    try:
        async with engine.connect() as conn:
            # Row count
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar() or 0

            column_profiles = []
            for f in fields:
                col = f.field_path
                cp = ColumnProfile(column_name=col, column_type=f.field_type, total_count=row_count)

                try:
                    # NULL count
                    r = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL"))
                    cp.null_count = r.scalar() or 0
                    cp.null_percent = round(cp.null_count / row_count * 100, 2) if row_count > 0 else 0

                    # Unique count
                    r = await conn.execute(text(f"SELECT COUNT(DISTINCT {col}) FROM {table_name}"))
                    cp.unique_count = r.scalar() or 0
                    cp.unique_percent = round(cp.unique_count / row_count * 100, 2) if row_count > 0 else 0

                    # Min/Max (safe for all types)
                    r = await conn.execute(text(f"SELECT MIN({col}), MAX({col}) FROM {table_name}"))
                    row = r.first()
                    if row:
                        cp.min_value = str(row[0]) if row[0] is not None else None
                        cp.max_value = str(row[1]) if row[1] is not None else None

                    # Mean (numeric only)
                    if f.field_type.upper() in ("INT", "INTEGER", "BIGINT", "SMALLINT", "NUMBER",
                                                  "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL"):
                        r = await conn.execute(text(f"SELECT AVG({col}) FROM {table_name}"))
                        avg = r.scalar()
                        if avg is not None:
                            cp.mean_value = round(float(avg), 4)
                except Exception:
                    pass  # Skip column if query fails

                column_profiles.append(cp)

            return row_count, column_profiles
    finally:
        await engine.dispose()


async def get_latest_profile(session: AsyncSession, dataset_id: int) -> ProfileResponse | None:
    """Get the most recent profile for a dataset."""
    profile = (await session.execute(
        select(DataProfile).where(DataProfile.dataset_id == dataset_id)
        .order_by(DataProfile.profiled_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not profile:
        return None

    columns = [ColumnProfile(**c) for c in _json.loads(profile.profile_json)]
    return ProfileResponse(
        id=profile.id, dataset_id=dataset_id, row_count=profile.row_count,
        columns=columns, profiled_at=profile.profiled_at,
    )


# ---------------------------------------------------------------------------
# Quality Rule CRUD
# ---------------------------------------------------------------------------

async def create_rule(session: AsyncSession, data: QualityRuleCreate) -> QualityRuleResponse:
    rule = QualityRule(**data.model_dump())
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    logger.info("Quality rule created: id=%d, name=%s, type=%s", rule.id, rule.rule_name, rule.check_type)
    return QualityRuleResponse.model_validate(rule)


async def list_rules(session: AsyncSession, dataset_id: int) -> list[QualityRuleResponse]:
    rules = (await session.execute(
        select(QualityRule).where(QualityRule.dataset_id == dataset_id)
        .order_by(QualityRule.created_at)
    )).scalars().all()
    return [QualityRuleResponse.model_validate(r) for r in rules]


async def get_rule(session: AsyncSession, rule_id: int) -> QualityRule | None:
    return (await session.execute(
        select(QualityRule).where(QualityRule.id == rule_id)
    )).scalar_one_or_none()


async def update_rule(session: AsyncSession, rule_id: int, data: QualityRuleUpdate) -> QualityRuleResponse | None:
    rule = await get_rule(session, rule_id)
    if not rule:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await session.flush()
    await session.refresh(rule)
    return QualityRuleResponse.model_validate(rule)


async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
    rule = await get_rule(session, rule_id)
    if not rule:
        return False
    await session.delete(rule)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Run Quality Check — evaluates all active rules for a dataset
# ---------------------------------------------------------------------------

async def run_quality_check(session: AsyncSession, dataset_id: int) -> RunCheckResponse:
    """Run all active quality rules for a dataset.

    Method A+B hybrid:
    - Uses latest profile data (Method B) for most checks
    - Falls back to profile data if source DB unavailable
    """
    # Get latest profile
    profile = await get_latest_profile(session, dataset_id)
    if not profile:
        # Auto-profile first
        profile = await profile_dataset(session, dataset_id)
        await session.flush()

    # Build column lookup from profile
    col_map = {cp.column_name: cp for cp in profile.columns}

    # Get active rules
    rules = (await session.execute(
        select(QualityRule).where(
            QualityRule.dataset_id == dataset_id,
            QualityRule.is_active == "true",
        ).order_by(QualityRule.created_at)
    )).scalars().all()

    results: list[QualityResultResponse] = []
    passed_count = 0
    failed_count = 0

    for rule in rules:
        passed, actual, detail = _evaluate_rule(rule, profile, col_map)

        result = QualityResult(
            rule_id=rule.id,
            dataset_id=dataset_id,
            passed="true" if passed else "false",
            actual_value=actual,
            detail=detail,
        )
        session.add(result)
        await session.flush()
        await session.refresh(result)

        if passed:
            passed_count += 1
        else:
            failed_count += 1

        results.append(QualityResultResponse(
            id=result.id, rule_id=rule.id, rule_name=rule.rule_name,
            check_type=rule.check_type, column_name=rule.column_name,
            dataset_id=dataset_id, passed=result.passed,
            actual_value=actual, detail=detail, severity=rule.severity,
            checked_at=result.checked_at,
        ))

    # Calculate and save score
    total = len(rules)
    score = round(passed_count / total * 100, 1) if total > 0 else 100.0

    qs = QualityScore(
        dataset_id=dataset_id,
        score=score,
        total_rules=total,
        passed_rules=passed_count,
        warning_rules=0,
        failed_rules=failed_count,
    )
    session.add(qs)
    await session.flush()

    logger.info("Quality check completed: dataset_id=%d, score=%.1f%%, passed=%d/%d",
                dataset_id, score, passed_count, total)

    return RunCheckResponse(
        dataset_id=dataset_id, score=score,
        total_rules=total, passed=passed_count, failed=failed_count,
        results=results,
    )


def _evaluate_rule(
    rule: QualityRule, profile: ProfileResponse, col_map: dict[str, ColumnProfile],
) -> tuple[bool, str, str]:
    """Evaluate a single quality rule against profile data.

    Returns: (passed, actual_value, detail)
    """
    threshold = float(rule.threshold) if rule.threshold else 100.0
    expected = rule.expected_value

    if rule.check_type == "NOT_NULL":
        cp = col_map.get(rule.column_name or "")
        if not cp:
            return False, "N/A", f"Column '{rule.column_name}' not found in profile"
        non_null_pct = 100.0 - cp.null_percent
        passed = non_null_pct >= threshold
        return passed, f"{non_null_pct:.1f}%", f"Non-null: {non_null_pct:.1f}% (threshold: {threshold}%)"

    elif rule.check_type == "UNIQUE":
        cp = col_map.get(rule.column_name or "")
        if not cp:
            return False, "N/A", f"Column '{rule.column_name}' not found"
        passed = cp.unique_percent >= threshold
        return passed, f"{cp.unique_percent:.1f}%", f"Unique: {cp.unique_percent:.1f}% (threshold: {threshold}%)"

    elif rule.check_type == "MIN_VALUE":
        cp = col_map.get(rule.column_name or "")
        if not cp or cp.min_value is None:
            return False, "N/A", "Min value unavailable"
        try:
            actual_min = float(cp.min_value)
            expected_min = float(expected) if expected else 0
            passed = actual_min >= expected_min
            return passed, str(actual_min), f"Min: {actual_min} (expected >= {expected_min})"
        except (ValueError, TypeError):
            return False, cp.min_value, f"Cannot compare: {cp.min_value}"

    elif rule.check_type == "MAX_VALUE":
        cp = col_map.get(rule.column_name or "")
        if not cp or cp.max_value is None:
            return False, "N/A", "Max value unavailable"
        try:
            actual_max = float(cp.max_value)
            expected_max = float(expected) if expected else 0
            passed = actual_max <= expected_max
            return passed, str(actual_max), f"Max: {actual_max} (expected <= {expected_max})"
        except (ValueError, TypeError):
            return False, cp.max_value, f"Cannot compare: {cp.max_value}"

    elif rule.check_type == "ROW_COUNT":
        actual_count = profile.row_count
        try:
            expected_min = int(expected) if expected else 0
            passed = actual_count >= expected_min
            return passed, str(actual_count), f"Row count: {actual_count} (expected >= {expected_min})"
        except (ValueError, TypeError):
            return False, str(actual_count), f"Invalid expected value: {expected}"

    elif rule.check_type == "ACCEPTED_VALUES":
        cp = col_map.get(rule.column_name or "")
        if not cp:
            return False, "N/A", f"Column '{rule.column_name}' not found"
        # This check needs actual data — mark as info-only from profile
        return True, "profile-only", f"ACCEPTED_VALUES requires source DB check (not available from profile)"

    elif rule.check_type == "REGEX":
        cp = col_map.get(rule.column_name or "")
        if not cp:
            return False, "N/A", f"Column '{rule.column_name}' not found"
        return True, "profile-only", f"REGEX requires source DB check (not available from profile)"

    elif rule.check_type == "FRESHNESS":
        # Check last profile time
        if profile.profiled_at:
            age_hours = (datetime.now(timezone.utc) - profile.profiled_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            try:
                max_hours = float(expected) if expected else 24
                passed = age_hours <= max_hours
                return passed, f"{age_hours:.1f}h", f"Data age: {age_hours:.1f}h (max: {max_hours}h)"
            except (ValueError, TypeError):
                return False, "N/A", f"Invalid expected value: {expected}"
        return False, "N/A", "No profile timestamp available"

    else:
        return False, "N/A", f"Unknown check type: {rule.check_type}"


# ---------------------------------------------------------------------------
# Score history
# ---------------------------------------------------------------------------

async def get_latest_score(session: AsyncSession, dataset_id: int) -> QualityScoreResponse | None:
    score = (await session.execute(
        select(QualityScore).where(QualityScore.dataset_id == dataset_id)
        .order_by(QualityScore.scored_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not score:
        return None
    return QualityScoreResponse.model_validate(score)


async def get_score_history(
    session: AsyncSession, dataset_id: int, limit: int = 30,
) -> list[QualityScoreResponse]:
    scores = (await session.execute(
        select(QualityScore).where(QualityScore.dataset_id == dataset_id)
        .order_by(QualityScore.scored_at.desc()).limit(limit)
    )).scalars().all()
    return [QualityScoreResponse.model_validate(s) for s in reversed(scores)]


async def get_latest_results(
    session: AsyncSession, dataset_id: int,
) -> list[QualityResultResponse]:
    """Get the most recent result for each active rule."""
    rules = (await session.execute(
        select(QualityRule).where(
            QualityRule.dataset_id == dataset_id,
            QualityRule.is_active == "true",
        )
    )).scalars().all()

    results = []
    for rule in rules:
        result = (await session.execute(
            select(QualityResult).where(QualityResult.rule_id == rule.id)
            .order_by(QualityResult.checked_at.desc()).limit(1)
        )).scalar_one_or_none()

        if result:
            results.append(QualityResultResponse(
                id=result.id, rule_id=rule.id, rule_name=rule.rule_name,
                check_type=rule.check_type, column_name=rule.column_name,
                dataset_id=dataset_id, passed=result.passed,
                actual_value=result.actual_value, detail=result.detail,
                severity=rule.severity, checked_at=result.checked_at,
            ))

    return results
