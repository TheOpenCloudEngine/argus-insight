"""Impala query collector via Cloudera Manager REST API.

Polls the Cloudera Manager ``/impalaQueries`` endpoint at a configurable
interval and persists newly finished queries to the database. Each collected
query is then passed to the lineage parser.

Cloudera Manager API reference:
  GET /api/v{ver}/clusters/{cluster}/services/{service}/impalaQueries
  - Basic Auth (username/password)
  - TLS support (with optional certificate verification skip)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
import urllib3

from sync.core.database import get_session
from sync.platforms.impala.models import ImpalaQueryHistory

logger = logging.getLogger(__name__)


class ImpalaQueryCollector:
    """Collects Impala query history from Cloudera Manager API."""

    def __init__(
        self,
        cm_host: str,
        cm_port: int,
        cm_username: str,
        cm_password: str,
        cluster_name: str,
        service_name: str,
        platform_id: str,
        tls_enabled: bool = False,
        tls_verify: bool = True,
        api_version: int = 19,
    ) -> None:
        self.platform_id = platform_id
        self.cluster_name = cluster_name
        self.service_name = service_name
        self.api_version = api_version

        scheme = "https" if tls_enabled else "http"
        self.base_url = (
            f"{scheme}://{cm_host}:{cm_port}/api/v{api_version}"
            f"/clusters/{cluster_name}/services/{service_name}/impalaQueries"
        )
        self.auth = (cm_username, cm_password)
        self.verify = tls_verify if tls_enabled else True

        # Suppress InsecureRequestWarning when TLS cert verification is off
        if tls_enabled and not tls_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._last_poll_time: datetime | None = None

    def collect(self) -> list[ImpalaQueryHistory]:
        """Poll Cloudera Manager for new Impala queries and save them.

        Returns list of newly persisted ImpalaQueryHistory records.
        """
        now = datetime.now(timezone.utc)
        from_time = self._last_poll_time or datetime(
            now.year, now.month, now.day, tzinfo=timezone.utc,
        )

        queries = self._fetch_queries(from_time, now)
        if not queries:
            self._last_poll_time = now
            return []

        records = self._save_queries(queries)
        self._last_poll_time = now

        logger.info(
            "Collected %d Impala queries (%d new) from CM %s/%s",
            len(queries), len(records), self.cluster_name, self.service_name,
        )
        return records

    def _fetch_queries(
        self, from_time: datetime, to_time: datetime,
    ) -> list[dict]:
        """Fetch Impala queries from Cloudera Manager API."""
        all_queries: list[dict] = []
        offset = 0
        limit = 100

        while True:
            params = {
                "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "to": to_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "filter": "queryState = FINISHED OR queryState = EXCEPTION",
                "limit": limit,
                "offset": offset,
            }

            try:
                resp = requests.get(
                    self.base_url,
                    params=params,
                    auth=self.auth,
                    verify=self.verify,
                    timeout=30,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error("Failed to fetch Impala queries from CM: %s", e)
                break

            data = resp.json()
            queries = data.get("queries", [])
            if not queries:
                break

            all_queries.extend(queries)

            if len(queries) < limit:
                break
            offset += limit

        return all_queries

    def _save_queries(self, queries: list[dict]) -> list[ImpalaQueryHistory]:
        """Save queries to database, skipping duplicates."""
        session = get_session()
        records: list[ImpalaQueryHistory] = []
        try:
            for q in queries:
                query_id = q.get("queryId", "")
                if not query_id:
                    continue

                # Skip if already collected
                existing = (
                    session.query(ImpalaQueryHistory.id)
                    .filter_by(query_id=query_id)
                    .first()
                )
                if existing:
                    continue

                record = ImpalaQueryHistory(
                    query_id=query_id,
                    query_type=q.get("queryType"),
                    query_state=q.get("queryState"),
                    statement=q.get("statement"),
                    database=q.get("database"),
                    username=q.get("user"),
                    coordinator_host=_extract_host(q.get("coordinator")),
                    start_time=_parse_datetime(q.get("startTime")),
                    end_time=_parse_datetime(q.get("endTime")),
                    duration_ms=q.get("durationMillis"),
                    rows_produced=q.get("rowsProduced"),
                    platform_id=self.platform_id,
                )
                session.add(record)
                records.append(record)

            if records:
                session.commit()
                for r in records:
                    session.refresh(r)

            return records
        except Exception:
            session.rollback()
            logger.exception("Failed to save Impala queries")
            raise
        finally:
            session.close()


def _extract_host(coordinator: dict | None) -> str | None:
    """Extract hostname from ApiHostRef object."""
    if coordinator and isinstance(coordinator, dict):
        return coordinator.get("hostId") or coordinator.get("hostname")
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string from Cloudera Manager API."""
    if not value:
        return None
    try:
        # CM returns: "2026-03-21T14:30:45.123Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
