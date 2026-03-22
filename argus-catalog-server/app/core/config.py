"""Application configuration.

Configuration is loaded from two files in the config directory:
1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}
"""

import os
from pathlib import Path

from app.core.config_loader import load_config

_CONFIG_DIR = Path(os.environ.get("ARGUS_CATALOG_SERVER_CONFIG_DIR", "/etc/argus-catalog-server"))
_yaml_path: Path = _CONFIG_DIR / "config.yml"
_properties_path: Path = _CONFIG_DIR / "config.properties"
_raw: dict = load_config(config_dir=_CONFIG_DIR)


def _get(section: str, key: str, default=None):
    return _raw.get(section, {}).get(key, default)


def _get_nested(section: str, subsection: str, key: str, default=None):
    return _raw.get(section, {}).get(subsection, {}).get(key, default)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


class Settings:
    """Global application settings loaded from config.yml + config.properties."""

    def __init__(self) -> None:
        self.app_name: str = _get("app", "name", "argus-catalog-server")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 4600))

        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "argus-catalog-server.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

        self.data_dir: Path = Path(_get("data", "dir", "/var/lib/argus-catalog-server"))

        self.config_dir: Path = _CONFIG_DIR
        self.config_yaml_path: Path = _yaml_path
        self.config_properties_path: Path = _properties_path

        self.cors_origins: list[str] = _get("cors", "origins", ["*"])

        # Database
        self.db_type: str = _get("database", "type", "postgresql")
        self.db_host: str = _get("database", "host", "localhost")
        self.db_port: int = int(_get("database", "port", 5432))
        self.db_name: str = _get("database", "name", "argus_catalog")
        self.db_username: str = _get("database", "username", "argus")
        self.db_password: str = _get("database", "password", "argus")
        self.db_pool_size: int = int(_get_nested("database", "pool", "size", 5))
        self.db_pool_max_overflow: int = int(_get_nested("database", "pool", "max_overflow", 10))
        self.db_pool_recycle: int = int(_get_nested("database", "pool", "recycle", 3600))
        self.db_echo: bool = _to_bool(_get("database", "echo", False))

        # Added for SSO AUTH - Keycloak OIDC configuration
        self.auth_type: str = _get("auth", "type", "keycloak")
        self.auth_keycloak_server_url: str = _get_nested("auth", "keycloak", "server_url", "http://localhost:8180")
        self.auth_keycloak_realm: str = _get_nested("auth", "keycloak", "realm", "argus-catalog")
        self.auth_keycloak_client_id: str = _get_nested("auth", "keycloak", "client_id", "argus-catalog-server")
        self.auth_keycloak_client_secret: str = _get_nested("auth", "keycloak", "client_secret", "argus-catalog-server-secret")
        self.auth_keycloak_admin_role: str = _get_nested("auth", "keycloak", "admin_role", "catalog-admin")
        self.auth_keycloak_user_role: str = _get_nested("auth", "keycloak", "user_role", "catalog-user")

        # Object Storage (MinIO / S3) — defaults, overwritten from DB at startup
        self.os_endpoint: str = "http://localhost:9000"
        self.os_access_key: str = "minioadmin"
        self.os_secret_key: str = "minioadmin"
        self.os_region: str = "us-east-1"
        self.os_use_ssl: bool = False
        self.os_bucket: str = "model-artifacts"
        self.os_presigned_url_expiry: int = 3600


def init_settings(
    yaml_path: str | None = None,
    properties_path: str | None = None,
) -> None:
    """Re-initialize settings with custom config file paths."""
    global _raw, _yaml_path, _properties_path
    if yaml_path:
        _yaml_path = Path(yaml_path)
    if properties_path:
        _properties_path = Path(properties_path)
    _raw = load_config(
        config_dir=_CONFIG_DIR,
        yaml_path=yaml_path,
        properties_path=properties_path,
    )
    settings.__init__()


settings = Settings()
