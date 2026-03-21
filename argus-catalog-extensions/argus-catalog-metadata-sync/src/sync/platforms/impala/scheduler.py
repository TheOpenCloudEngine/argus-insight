"""Impala query collection scheduler.

Runs the ImpalaQueryCollector at a configurable interval using a daemon
timer thread, independent of the metadata-sync scheduler.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from sync.platforms.impala.collector import ImpalaQueryCollector

logger = logging.getLogger(__name__)


class ImpalaCollectorScheduler:
    """Periodic scheduler for Impala query collection."""

    def __init__(
        self,
        collector: ImpalaQueryCollector,
        interval_minutes: int = 5,
    ) -> None:
        self.collector = collector
        self.interval_minutes = interval_minutes
        self._timer: threading.Timer | None = None
        self._stop = threading.Event()
        self.next_run: datetime | None = None

    def start(self) -> None:
        """Start the periodic collection."""
        self._stop.clear()
        # Run immediately on start, then schedule repeating
        self._run()
        logger.info(
            "Impala collector started (every %d minutes, platform=%s)",
            self.interval_minutes, self.collector.platform_id,
        )

    def stop(self) -> None:
        """Stop the periodic collection."""
        self._stop.set()
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.next_run = None
        logger.info("Impala collector stopped")

    def _schedule_next(self) -> None:
        if self._stop.is_set() or self.interval_minutes <= 0:
            return
        delay = self.interval_minutes * 60
        self.next_run = datetime.now() + timedelta(seconds=delay)
        self._timer = threading.Timer(delay, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self) -> None:
        if self._stop.is_set():
            return
        try:
            records = self.collector.collect()

            # Trigger lineage parsing for each collected query
            if records:
                try:
                    from sync.platforms.impala.lineage_service import (
                        process_impala_query_lineage,
                    )
                    lineage_count = 0
                    for record in records:
                        lineage_count += process_impala_query_lineage(record)
                    if lineage_count:
                        logger.info(
                            "Parsed %d lineage record(s) from %d Impala queries",
                            lineage_count, len(records),
                        )
                except Exception as e:
                    logger.warning("Impala lineage parsing failed: %s", e)

        except Exception:
            logger.exception("Impala query collection failed")
        finally:
            self._schedule_next()
