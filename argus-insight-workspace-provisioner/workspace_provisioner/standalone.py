"""Standalone database setup for independent testing.

Provides a self-contained SQLAlchemy async engine and session factory
that replaces the `app.core.database` dependency when running outside
of argus-insight-server.

Usage:
    from workspace_provisioner.standalone import init_db, get_standalone_session, Base

    await init_db()
    async with get_standalone_session() as session:
        ...

The database URL is resolved in the following order:
    1. Explicit `db_url` argument passed to `init_db()`
    2. PROVISIONER_DB_URL environment variable
    3. argus-insight-server config (config.yml + config.properties)
    4. Fallback: sqlite+aiosqlite:///provisioner.db

Environment variables (used by CLI):
    PROVISIONER_DB_URL: Database URL (overrides server config)
    GITLAB_URL: GitLab server URL
    GITLAB_TOKEN: GitLab private token
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Standalone declarative base for ORM models."""
    pass


logger = logging.getLogger(__name__)

_engine = None
_async_session: async_sessionmaker | None = None


def _build_db_url_from_server_config() -> str | None:
    """Attempt to build a database URL from argus-insight-server config.

    Returns:
        Database URL string if server config is available, None otherwise.
    """
    try:
        from app.core.config import settings

        db_type = settings.db_type.lower()
        host = settings.db_host
        port = settings.db_port
        name = settings.db_name
        user = settings.db_username
        password = settings.db_password

        if db_type == "postgresql":
            url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
        elif db_type in ("mariadb", "mysql"):
            url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
        else:
            logger.warning("Unsupported db_type '%s' in server config, skipping", db_type)
            return None

        logger.info("Using database config from argus-insight-server: %s@%s:%d/%s", user, host, port, name)
        return url
    except Exception:
        logger.info("argus-insight-server config not available, skipping server config")
        return None


async def init_db(db_url: str | None = None) -> None:
    """Initialize the standalone database engine and create all tables.

    Args:
        db_url: SQLAlchemy async database URL. If not provided, resolved from
                env PROVISIONER_DB_URL → server config → SQLite fallback.
    """
    global _engine, _async_session

    if db_url is None:
        db_url = os.environ.get("PROVISIONER_DB_URL")

    if db_url is None:
        db_url = _build_db_url_from_server_config()

    if db_url is None:
        db_url = "sqlite+aiosqlite:///provisioner.db"
        logger.info("No database configuration found, using SQLite fallback")

    # Mask password in log
    masked = db_url
    at_idx = db_url.find("@")
    if at_idx > 0:
        colon_idx = db_url.find("://")
        if colon_idx > 0:
            prefix_end = db_url.find(":", colon_idx + 3)
            if 0 < prefix_end < at_idx:
                masked = db_url[:prefix_end + 1] + "****" + db_url[at_idx:]

    logger.info("Initializing standalone database: %s", masked)
    _engine = create_async_engine(db_url, echo=False)
    _async_session = async_sessionmaker(_engine, expire_on_commit=False)

    # Import models to register them with Base.metadata
    _register_models()

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Standalone database initialized, tables created")


def _register_models() -> None:
    """Re-register ORM models with the standalone Base.

    The workspace_provisioner models import Base from app.core.database
    when running inside argus-insight-server. For standalone mode, we
    need them to use this module's Base. This function patches the
    table metadata so create_all works correctly.
    """
    from workspace_provisioner.models import (
        ArgusWorkspace,
        ArgusWorkspaceCredential,
        ArgusWorkspaceMember,
    )
    from workspace_provisioner.workflow.models import (
        ArgusWorkflowExecution,
        ArgusWorkflowStepExecution,
    )

    for model in [
        ArgusWorkspace,
        ArgusWorkspaceMember,
        ArgusWorkspaceCredential,
        ArgusWorkflowExecution,
        ArgusWorkflowStepExecution,
    ]:
        table = model.__table__
        # Remove FK constraints that reference external tables (argus_users)
        # for standalone mode where those tables don't exist
        fks_to_remove = [
            fk for fk in table.foreign_key_constraints
            if any("argus_users" in str(col) for col in fk.columns)
        ]
        for fk in fks_to_remove:
            table.foreign_key_constraints.discard(fk)
            logger.info("Removed external FK constraint on table '%s' for standalone mode", table.name)

        if table.name not in Base.metadata.tables:
            Base.metadata._add_table(table.name, table.schema, table)
            logger.info("Registered model table: %s", table.name)


@asynccontextmanager
async def get_standalone_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session from the standalone session factory."""
    if _async_session is None:
        logger.error("Attempted to get session before init_db() was called")
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _async_session() as session:
        yield session


def get_session_factory() -> async_sessionmaker:
    """Get the standalone session factory (for patching into service.py)."""
    if _async_session is None:
        logger.error("Attempted to get session factory before init_db() was called")
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session
