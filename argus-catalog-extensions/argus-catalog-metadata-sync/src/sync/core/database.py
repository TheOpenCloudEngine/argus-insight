"""Database connection and session management using SQLAlchemy."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def init_db(settings) -> None:
    """Initialize database engine and create all tables.

    Args:
        settings: Settings instance with database_url, db_pool_size, etc.
    """
    global _engine, _SessionLocal

    # Import models to ensure they are registered with Base.metadata
    import sync.platforms.hive.models  # noqa: F401

    engine_kwargs = {"echo": settings.db_echo}
    if settings.db_type in ("postgresql", "mariadb", "mysql"):
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_pool_max_overflow
        engine_kwargs["pool_recycle"] = settings.db_pool_recycle

    _engine = create_engine(settings.database_url, **engine_kwargs)
    _SessionLocal = sessionmaker(bind=_engine)

    Base.metadata.create_all(_engine)
    logger.info("Database initialized: %s@%s:%s/%s",
                settings.db_username, settings.db_host, settings.db_port, settings.db_name)


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()
