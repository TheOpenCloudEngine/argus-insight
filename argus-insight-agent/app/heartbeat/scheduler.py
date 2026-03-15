"""Heartbeat scheduler that periodically sends agent status to Argus Insight Server.

Posts agent system information to the server every 60 seconds.
On failure, logs a WARNING with server.properties guidance.
"""

import asyncio
import json
import logging

import httpx

from app.core.config import settings
from app.heartbeat.system_info import get_dynamic_info, get_static_info

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 60  # seconds


class HeartbeatScheduler:
    """Async scheduler that sends heartbeat to the central server every 60 seconds."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat background task."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Heartbeat scheduler started (interval=%ds, server=%s:%s)",
            _HEARTBEAT_INTERVAL,
            settings.insight_server_ip,
            settings.insight_server_port,
        )

    async def stop(self) -> None:
        """Stop the heartbeat background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat scheduler stopped")

    async def _run(self) -> None:
        """Main loop: send heartbeat every 60 seconds."""
        while self._running:
            try:
                await self._send_heartbeat()
            except Exception:
                logger.warning(
                    "Argus Insight Server 연결 실패. "
                    "server.properties 파일의 server.ip=%s, server.port=%s 설정을 확인하세요.",
                    settings.insight_server_ip,
                    settings.insight_server_port,
                )
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                break

    async def _send_heartbeat(self) -> None:
        """Build payload and POST to server's heartbeat endpoint."""
        url = (
            f"http://{settings.insight_server_ip}:{settings.insight_server_port}"
            f"/api/v1/agent/heartbeat"
        )
        payload = {
            **get_static_info(),
            **get_dynamic_info(),
            "version": settings.app_version,
        }

        logger.debug("Heartbeat payload: %s", json.dumps(payload, ensure_ascii=False))

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()


heartbeat_scheduler = HeartbeatScheduler()
