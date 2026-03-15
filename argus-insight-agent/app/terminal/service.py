"""Remote terminal session management."""

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TerminalSession:
    """Represents an active terminal session."""

    session_id: str
    pid: int
    fd: int
    active: bool = True


class TerminalManager:
    """Manage multiple terminal sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    @property
    def session_count(self) -> int:
        return len(self._sessions)

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
            return data
        except OSError:
            session.active = False
            return b""

    def write_input(self, session_id: str, data: bytes) -> None:
        """Write input to a terminal session."""
        session = self._get_session(session_id)
        os.write(session.fd, data)

    def resize(self, session_id: str, rows: int, cols: int) -> None:
        """Resize a terminal session."""
        session = self._get_session(session_id)
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(session.fd, termios.TIOCSWINSZ, winsize)

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
        for session_id in list(self._sessions.keys()):
            self.close_session(session_id)

    def _get_session(self, session_id: str) -> TerminalSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Terminal session not found: {session_id}")
        return session


terminal_manager = TerminalManager()
