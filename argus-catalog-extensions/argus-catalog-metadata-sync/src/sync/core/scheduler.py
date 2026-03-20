"""Sync scheduler — manages periodic sync jobs per platform.

Each platform gets its own independent timer thread so that schedule changes
for one platform never affect another.
"""

import logging
import threading
from datetime import datetime, timedelta

from sync.core.base import BasePlatformSync, SyncResult

logger = logging.getLogger(__name__)


class _PlatformJob:
    """A single repeating timer for one platform."""

    def __init__(self, name: str, run_fn, interval_minutes: int):
        self.name = name
        self._run_fn = run_fn
        self.interval_minutes = interval_minutes
        self._timer: threading.Timer | None = None
        self._stop = threading.Event()
        self.next_run: datetime | None = None

    def start(self) -> None:
        self._stop.clear()
        self._schedule_next()

    def stop(self) -> None:
        self._stop.set()
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.next_run = None

    def reschedule(self, interval_minutes: int) -> None:
        self.stop()
        self.interval_minutes = interval_minutes
        self.start()

    def _schedule_next(self) -> None:
        if self._stop.is_set() or self.interval_minutes <= 0:
            return
        delay = self.interval_minutes * 60
        self.next_run = datetime.now() + timedelta(seconds=delay)
        self._timer = threading.Timer(delay, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        if self._stop.is_set():
            return
        self._run_fn(self.name)
        self._schedule_next()


class SyncScheduler:
    """Manages periodic synchronization jobs for multiple platforms."""

    def __init__(self):
        self._syncs: dict[str, BasePlatformSync] = {}
        self._jobs: dict[str, _PlatformJob] = {}
        self._last_results: dict[str, SyncResult] = {}
        self._running: dict[str, bool] = {}
        self._lock = threading.Lock()

    # ---- registration ----

    def register(
        self,
        platform_sync: BasePlatformSync,
        interval_minutes: int,
        enabled: bool = True,
    ) -> None:
        """Register a platform sync with an optional repeating schedule."""
        name = platform_sync.platform_name

        # Stop existing job if re-registering
        if name in self._jobs:
            self._jobs[name].stop()

        self._syncs[name] = platform_sync
        self._running.setdefault(name, False)

        if enabled and interval_minutes > 0:
            job = _PlatformJob(name, self._run_sync, interval_minutes)
            self._jobs[name] = job
            job.start()
            logger.info("Scheduled %s sync every %d minutes", name, interval_minutes)
        else:
            logger.info("Platform %s registered (schedule disabled)", name)

    # ---- dynamic schedule control ----

    def update_schedule(self, platform: str, interval_minutes: int, enabled: bool) -> bool:
        """Change schedule for a running platform — takes effect immediately."""
        if platform not in self._syncs:
            return False

        if platform in self._jobs:
            self._jobs[platform].stop()
            del self._jobs[platform]

        if enabled and interval_minutes > 0:
            job = _PlatformJob(platform, self._run_sync, interval_minutes)
            self._jobs[platform] = job
            job.start()
            logger.info("Rescheduled %s sync every %d minutes", platform, interval_minutes)
        else:
            logger.info("Disabled schedule for %s", platform)

        return True

    # ---- manual trigger ----

    def run_now(self, platform: str) -> SyncResult | None:
        """Trigger an immediate sync for a platform."""
        if platform not in self._syncs:
            return None
        return self._run_sync(platform)

    # ---- internal ----

    def _run_sync(self, platform: str) -> SyncResult:
        """Execute sync for a platform with connection management."""
        sync = self._syncs[platform]

        with self._lock:
            if self._running.get(platform):
                logger.warning("Sync for %s already running, skipping", platform)
                return SyncResult(
                    platform=platform,
                    finished_at=datetime.now(),
                    errors=["Sync already in progress"],
                )
            self._running[platform] = True

        logger.info("Starting sync for %s", platform)
        try:
            if not sync.connect():
                result = SyncResult(
                    platform=platform,
                    finished_at=datetime.now(),
                    errors=["Failed to connect"],
                )
                self._last_results[platform] = result
                return result

            result = sync.sync()
            self._last_results[platform] = result
            return result
        except Exception as e:
            logger.error("Sync error for %s: %s", platform, e)
            result = SyncResult(
                platform=platform,
                finished_at=datetime.now(),
                errors=[str(e)],
            )
            self._last_results[platform] = result
            return result
        finally:
            sync.disconnect()
            with self._lock:
                self._running[platform] = False

    # ---- status ----

    def get_status(self, platform: str) -> dict:
        info: dict = {
            "platform": platform,
            "registered": platform in self._syncs,
            "scheduled": platform in self._jobs,
            "running": self._running.get(platform, False),
            "interval_minutes": None,
            "last_result": None,
            "next_run": None,
        }
        if platform in self._jobs:
            job = self._jobs[platform]
            info["interval_minutes"] = job.interval_minutes
            info["next_run"] = job.next_run.isoformat() if job.next_run else None
        if platform in self._last_results:
            info["last_result"] = self._last_results[platform].to_dict()
        return info

    def get_all_status(self) -> list[dict]:
        return [self.get_status(name) for name in self._syncs]

    # ---- lifecycle ----

    def start(self) -> None:
        """Start all registered jobs (called on app startup)."""
        for job in self._jobs.values():
            if not job._timer:
                job.start()
        logger.info("Scheduler started (%d platforms)", len(self._jobs))

    def stop(self) -> None:
        """Stop all jobs."""
        for job in self._jobs.values():
            job.stop()
        logger.info("Scheduler stopped")
