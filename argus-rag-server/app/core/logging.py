"""Logging configuration with daily rolling file handler."""

import logging
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings

LOG_FORMAT = (
    "%(levelname)s %(asctime)s.%(msecs)03d %(process)d %(programname)s"
    " %(filename)s:%(funcName)s:%(lineno)d - %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _ProgramNameFilter(logging.Filter):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.program_name = name

    def filter(self, record):
        record.programname = self.program_name
        return True


def setup_logging() -> None:
    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    handler = TimedRotatingFileHandler(
        filename=str(log_dir / settings.log_filename),
        when="midnight",
        interval=1,
        backupCount=settings.log_rolling_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(log_level)
    handler.setFormatter(formatter)
    handler.addFilter(_ProgramNameFilter(settings.app_name))

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level <= logging.DEBUG else logging.WARNING
    )
