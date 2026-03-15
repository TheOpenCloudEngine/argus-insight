"""Background task that marks agents as DISCONNECTED when heartbeats stop.

Runs every 60 seconds. If an agent's last heartbeat is older than 3 minutes,
its status in argus_agents is set to DISCONNECTED.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.agent.models import ArgusAgent, ArgusAgentHeartbeat
from app.core.config import settings
from app.core.database import async_session

logger = logging.getLogger(__name__)


class DisconnectChecker:
    """Periodically checks for timed-out agents and marks them DISCONNECTED."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the disconnect checker background task."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Disconnect checker started (interval=%ds, timeout=%ds)",
            settings.agent_heartbeat_check_interval,
            settings.agent_heartbeat_disconnect_timeout,
        )

    async def stop(self) -> None:
        """Stop the disconnect checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Disconnect checker stopped")

    async def _run(self) -> None:
        """Main loop: check for timed-out agents every 60 seconds."""
        while self._running:
            try:
                await self._check_disconnected()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in disconnect checker loop")
            try:
                await asyncio.sleep(settings.agent_heartbeat_check_interval)
            except asyncio.CancelledError:
                break

    async def _check_disconnected(self) -> None:
        """Find agents whose last heartbeat exceeds the timeout and mark DISCONNECTED."""
        timeout = timedelta(seconds=settings.agent_heartbeat_disconnect_timeout)
        threshold = datetime.now(timezone.utc) - timeout

        async with async_session() as session:
            # Find hostnames with stale heartbeats
            result = await session.execute(
                select(ArgusAgentHeartbeat.hostname).where(
                    ArgusAgentHeartbeat.last_heartbeat_at < threshold
                )
            )
            stale_hostnames = [row[0] for row in result.all()]

            if not stale_hostnames:
                return

            # Update status to DISCONNECTED (skip already DISCONNECTED ones)
            stmt = (
                update(ArgusAgent)
                .where(
                    ArgusAgent.hostname.in_(stale_hostnames),
                    ArgusAgent.status != "DISCONNECTED",
                )
                .values(status="DISCONNECTED", updated_at=datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                logger.warning(
                    "Marked %d agent(s) as DISCONNECTED (no heartbeat for %ds): %s",
                    result.rowcount,
                    settings.agent_heartbeat_disconnect_timeout,
                    stale_hostnames,
                )


disconnect_checker = DisconnectChecker()
