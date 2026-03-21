"""Hive query history collector — receives audit events and persists them immediately."""

import logging

from pydantic import BaseModel

from sync.core.database import get_session
from sync.platforms.hive.models import HiveQueryHistory

logger = logging.getLogger(__name__)


class HiveQueryEvent(BaseModel):
    """Incoming query audit event from QueryAuditHook."""

    queryId: str
    shortUsername: str | None = None
    username: str | None = None
    operationName: str | None = None
    startTime: str | None = None
    endTime: str | None = None
    durationMs: str | None = None
    query: str | None = None
    status: str
    errorMsg: str | None = None
    platformId: str | None = None     # catalog platform ID from hive-site.xml
    inputs: list[str] | None = None   # source tables from HookContext.getInputs()
    outputs: list[str] | None = None  # target tables from HookContext.getOutputs()


def save_query_event(event: HiveQueryEvent) -> HiveQueryHistory:
    """Save a single query audit event to the database immediately."""
    logger.debug("Received Hive query event: queryId=%s, status=%s, user=%s",
                 event.queryId, event.status, event.shortUsername)

    record = HiveQueryHistory(
        query_id=event.queryId,
        short_username=event.shortUsername,
        username=event.username,
        operation_name=event.operationName,
        start_time=_parse_bigint(event.startTime),
        end_time=_parse_bigint(event.endTime),
        duration_ms=_parse_bigint(event.durationMs),
        query=event.query,
        status=event.status,
        error_msg=event.errorMsg,
        platform_id=event.platformId,
    )

    session = get_session()
    try:
        session.add(record)
        session.commit()
        session.refresh(record)
        logger.debug("Saved Hive query history: id=%d, queryId=%s, status=%s",
                     record.id, record.query_id, record.status)
        return record
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _parse_bigint(value: str | None) -> int | None:
    """Parse a string to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
