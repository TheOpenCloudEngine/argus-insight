"""Argus database client for user/group synchronization.

Directly connects to the Argus platform database (PostgreSQL or MariaDB/MySQL)
and synchronizes users and groups into the argus_users and argus_roles tables.

Replaces the previous Ranger Admin REST API integration with direct DB access.
"""

import hashlib
import logging
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default password hash for externally synced users (SHA-256 of empty string).
# External users authenticate via LDAP/AD, not local password.
_EXTERNAL_USER_PASSWORD_HASH = hashlib.sha256(b"").hexdigest()

# Default role for externally synced users
_DEFAULT_ROLE_NAME = "User"

metadata = MetaData()

argus_roles = Table(
    "argus_roles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(50), nullable=False, unique=True),
    Column("description", String(255)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

argus_users = Table(
    "argus_users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(100), nullable=False, unique=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("first_name", String(100), nullable=False),
    Column("last_name", String(100), nullable=False),
    Column("phone_number", String(30)),
    Column("password_hash", String(255), nullable=False),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("role_id", Integer, ForeignKey("argus_roles.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


def _build_database_url() -> str:
    """Build synchronous database URL from settings."""
    db_type = settings.db_type.lower()
    host = settings.db_host
    port = settings.db_port
    name = settings.db_name
    user = settings.db_username
    password = settings.db_password

    if db_type == "postgresql":
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    elif db_type in ("mariadb", "mysql"):
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
    else:
        raise ValueError(f"Unsupported database type: {db_type}. Use 'postgresql' or 'mariadb'.")


class DatabaseClient:
    """Synchronous database client for user/group synchronization."""

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._default_role_id: int | None = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            url = _build_database_url()
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def check_connection(self) -> bool:
        """Verify connectivity to the Argus database."""
        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Failed to connect to database: %s", e)
            return False

    def _resolve_default_role_id(self) -> int:
        """Look up the default role ID for synced users."""
        if self._default_role_id is not None:
            return self._default_role_id

        engine = self._get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                select(argus_roles.c.id).where(argus_roles.c.name == _DEFAULT_ROLE_NAME)
            ).first()
            if row is None:
                raise RuntimeError(
                    f"Default role '{_DEFAULT_ROLE_NAME}' not found in argus_roles table. "
                    "Please seed roles before running usersync."
                )
            self._default_role_id = row[0]
            return self._default_role_id

    def load_existing_users(self) -> dict[str, dict[str, Any]]:
        """Load all existing users from argus_users.

        Returns: {username: {"id": ..., "email": ..., "first_name": ..., ...}}
        """
        engine = self._get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    argus_users.c.id,
                    argus_users.c.username,
                    argus_users.c.email,
                    argus_users.c.first_name,
                    argus_users.c.last_name,
                    argus_users.c.status,
                )
            ).fetchall()

        existing: dict[str, dict[str, Any]] = {}
        for row in rows:
            existing[row.username] = {
                "id": row.id,
                "email": row.email,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "status": row.status,
            }

        logger.info("Loaded %d existing users from database", len(existing))
        return existing

    def sync_users(
        self,
        users: list[dict[str, Any]],
        existing: dict[str, dict[str, Any]],
    ) -> tuple[int, int]:
        """Sync users to argus_users table via upsert logic.

        Args:
            users: List of user dicts with keys: username, email, first_name, last_name.
            existing: Current database state from load_existing_users().

        Returns:
            Tuple of (created_count, updated_count).
        """
        if not users:
            return 0, 0

        role_id = self._resolve_default_role_id()
        engine = self._get_engine()
        created = 0
        updated = 0

        with engine.begin() as conn:
            for user in users:
                username = user["username"]
                email = user.get("email") or f"{username}@external"
                first_name = user.get("first_name") or username
                last_name = user.get("last_name") or ""

                if username in existing:
                    # Update if changed
                    ex = existing[username]
                    changes: dict[str, Any] = {}
                    if email != ex["email"]:
                        changes["email"] = email
                    if first_name != ex["first_name"]:
                        changes["first_name"] = first_name
                    if last_name != ex["last_name"]:
                        changes["last_name"] = last_name
                    if ex["status"] != "active":
                        changes["status"] = "active"

                    if changes:
                        conn.execute(
                            argus_users.update()
                            .where(argus_users.c.id == ex["id"])
                            .values(**changes)
                        )
                        updated += 1
                else:
                    # Insert new user
                    conn.execute(
                        argus_users.insert().values(
                            username=username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            password_hash=_EXTERNAL_USER_PASSWORD_HASH,
                            status="active",
                            role_id=role_id,
                        )
                    )
                    created += 1

        logger.info(
            "User sync complete: %d created, %d updated (out of %d total)",
            created,
            updated,
            len(users),
        )
        return created, updated

    def deactivate_removed_users(
        self,
        source_usernames: set[str],
        existing: dict[str, dict[str, Any]],
    ) -> int:
        """Deactivate users that exist in DB but not in source.

        Args:
            source_usernames: Set of usernames from the sync source.
            existing: Current database state from load_existing_users().

        Returns:
            Number of users deactivated.
        """
        to_deactivate = []
        for username, info in existing.items():
            if username not in source_usernames and info["status"] == "active":
                to_deactivate.append(info["id"])

        if not to_deactivate:
            return 0

        engine = self._get_engine()
        with engine.begin() as conn:
            conn.execute(
                argus_users.update()
                .where(argus_users.c.id.in_(to_deactivate))
                .values(status="inactive")
            )

        logger.info("Deactivated %d users not found in source", len(to_deactivate))
        return len(to_deactivate)
