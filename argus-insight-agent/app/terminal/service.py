"""Remote terminal session management."""

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
import time
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Seconds without any WebSocket activity before a session is considered stale.
SESSION_IDLE_TIMEOUT = 120


@dataclass
class TerminalSession:
    """Represents an active terminal session."""

    session_id: str
    pid: int
    fd: int
    active: bool = True
    last_activity: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.monotonic()

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_activity


class TerminalManager:
    """Manage multiple terminal sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}
        self._reaper_task: asyncio.Task | None = None

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def start_reaper(self) -> None:
        """Start background task that cleans up stale sessions."""
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(self._reap_stale_sessions())

    async def _reap_stale_sessions(self) -> None:
        """Periodically check for and close stale sessions."""
        while True:
            await asyncio.sleep(30)
            stale = [
                sid
                for sid, s in self._sessions.items()
                if s.idle_seconds > SESSION_IDLE_TIMEOUT
            ]
            for sid in stale:
                logger.warning("Closing stale terminal session: %s (idle %.0fs)", sid,
                               self._sessions[sid].idle_seconds)
                self.close_session(sid)

    def create_session(self, session_id: str) -> TerminalSession:
        """Create a new PTY-based terminal session."""
        if len(self._sessions) >= settings.terminal_max_sessions:
            raise RuntimeError(
                f"Maximum terminal sessions ({settings.terminal_max_sessions}) reached"
            )

        pid, fd = pty.openpty()
        child_pid = os.fork()

        if child_pid == 0:
            # Child process
            os.close(pid)
            os.setsid()
            os.dup2(fd, 0)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            if fd > 2:
                os.close(fd)
            os.execvp(settings.terminal_shell, [settings.terminal_shell])
        else:
            # Parent process
            os.close(fd)
            session = TerminalSession(
                session_id=session_id,
                pid=child_pid,
                fd=pid,
            )
            self._sessions[session_id] = session
            logger.info("Terminal session created: %s (pid=%d)", session_id, child_pid)
            return session

    async def read_output(self, session_id: str, size: int = 4096) -> bytes:
        """Read output from a terminal session."""
        session = self._get_session(session_id)
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, os.read, session.fd, size)
            session.touch()
            return data
        except OSError:
            session.active = False
            return b""

    def write_input(self, session_id: str, data: bytes) -> None:
        """Write input to a terminal session."""
        session = self._get_session(session_id)
        os.write(session.fd, data)
        session.touch()

    def resize(self, session_id: str, rows: int, cols: int) -> None:
        """Resize a terminal session."""
        session = self._get_session(session_id)
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(session.fd, termios.TIOCSWINSZ, winsize)
        session.touch()

    def close_session(self, session_id: str) -> None:
        """Close and clean up a terminal session."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return

        session.active = False
        try:
            os.kill(session.pid, signal.SIGTERM)
            os.waitpid(session.pid, 0)
        except (OSError, ChildProcessError):
            pass
        try:
            os.close(session.fd)
        except OSError:
            pass

        logger.info("Terminal session closed: %s", session_id)

    def close_all(self) -> None:
        """Close all terminal sessions."""
        if self._reaper_task and not self._reaper_task.done():
            self._reaper_task.cancel()
        for session_id in list(self._sessions.keys()):
            self.close_session(session_id)

    def _get_session(self, session_id: str) -> TerminalSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Terminal session not found: {session_id}")
        return session


terminal_manager = TerminalManager()
