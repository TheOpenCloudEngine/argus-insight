"""Logging configuration."""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Configure application logging."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    log_dir = settings.log_dir
    if log_dir.exists():
        file_handler = logging.FileHandler(log_dir / "agent.log")
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        handlers=handlers,
    )
