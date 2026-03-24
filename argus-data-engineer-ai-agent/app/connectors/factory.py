"""Connector factory — creates DB connectors from catalog platform config.

Given a platform type and connection configuration from the catalog,
creates the appropriate async database connector.
"""

import logging

from app.connectors.base import DBConnector

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = {"mysql", "mariadb", "postgresql"}


def is_supported(platform_type: str) -> bool:
    """Check if direct SQL execution is supported for this platform."""
    return platform_type.lower() in SUPPORTED_PLATFORMS


def create_connector(platform_type: str, config: dict) -> DBConnector:
    """Create a database connector from platform type and config.

    Args:
        platform_type: Platform type string (mysql, postgresql, etc.)
        config: Connection configuration dict with host, port, username, password, database.

    Returns:
        A DBConnector instance.

    Raises:
        ValueError: If the platform type is not supported.
    """
    ptype = platform_type.lower()

    host = config.get("host", "localhost")
    port = int(config.get("port", 0))
    username = config.get("username", "")
    password = config.get("password", "")
    database = config.get("database", "")

    if ptype in ("mysql", "mariadb"):
        from app.connectors.mysql import MySQLConnector

        return MySQLConnector(
            host=host,
            port=port or 3306,
            username=username,
            password=password,
            database=database,
        )

    elif ptype == "postgresql":
        from app.connectors.postgresql import PostgreSQLConnector

        return PostgreSQLConnector(
            host=host,
            port=port or 5432,
            username=username,
            password=password,
            database=database,
        )

    else:
        raise ValueError(
            f"Unsupported platform for SQL execution: {platform_type}. "
            f"Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
