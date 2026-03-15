"""Database connection and session management.

Supports PostgreSQL and MariaDB/MySQL via SQLAlchemy async engine.
Connection pool settings are configurable through config.yml / config.properties.

Database type is determined by the 'database.type' config value:
  - 'postgresql' (default): Uses asyncpg driver
  - 'mariadb' or 'mysql': Uses aiomysql driver
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


def _build_database_url() -> str:
    """Build async database URL from settings."""
    db_type = settings.db_type.lower()
    host = settings.db_host
    port = settings.db_port
    name = settings.db_name
    user = settings.db_username
    password = settings.db_password

    if db_type == "postgresql":
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
    elif db_type in ("mariadb", "mysql"):
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
    else:
        raise ValueError(f"Unsupported database type: {db_type}. Use 'postgresql' or 'mariadb'.")


engine = create_async_engine(
    _build_database_url(),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    echo=settings.db_echo,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """FastAPI dependency that provides an async database session.

    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session() as session:
        yield session


async def init_database() -> None:
    """Initialize database connection pool and verify connectivity."""
    db_url = _build_database_url()
    # Mask password in log output
    masked = db_url
    if settings.db_password:
        masked = db_url.replace(f":{settings.db_password}@", ":****@")
    logger.info("Database connection: %s", masked)
    logger.info(
        "Database pool: size=%d, max_overflow=%d, recycle=%ds",
        settings.db_pool_size,
        settings.db_pool_max_overflow,
        settings.db_pool_recycle,
    )

    # Verify connectivity
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")


async def close_database() -> None:
    """Dispose database engine and release all pooled connections."""
    await engine.dispose()
    logger.info("Database connection pool closed")
