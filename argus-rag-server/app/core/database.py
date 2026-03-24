"""Database connection and session management with pgvector support."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _build_database_url() -> str:
    db_type = settings.db_type.lower()
    host, port = settings.db_host, settings.db_port
    name, user, pw = settings.db_name, settings.db_username, settings.db_password
    if db_type == "postgresql":
        return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{name}"
    elif db_type in ("mariadb", "mysql"):
        return f"mysql+aiomysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"
    raise ValueError(f"Unsupported database type: {db_type}")


engine = create_async_engine(
    _build_database_url(),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    echo=settings.db_echo,
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_database() -> None:
    db_url = _build_database_url()
    masked = db_url
    if settings.db_password:
        masked = db_url.replace(f":{settings.db_password}@", ":****@")
    logger.info("Database connection: %s", masked)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        # Enable pgvector extension
        if settings.db_type == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.commit()
    logger.info("Database connection verified (pgvector enabled)")


async def close_database() -> None:
    await engine.dispose()
    logger.info("Database connection pool closed")
