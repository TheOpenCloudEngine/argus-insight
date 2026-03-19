"""Application configuration.

Configuration is loaded from two files in the config directory:

1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}

Variable resolution order:
  1. Lookup variable in config.properties
  2. If not found, use the default value specified after ':'
  3. If no default, the placeholder is left as-is

Default config directory: /etc/argus-insight-server
Override with ARGUS_SERVER_CONFIG_DIR environment variable.
Override individual files with --config-yaml / --config-properties CLI arguments.
"""

import os
from pathlib import Path

from app.core.config_loader import load_config

_CONFIG_DIR = Path(os.environ.get("ARGUS_SERVER_CONFIG_DIR", "/etc/argus-insight-server"))
_yaml_path: Path = _CONFIG_DIR / "config.yml"
_properties_path: Path = _CONFIG_DIR / "config.properties"
_raw: dict = load_config(config_dir=_CONFIG_DIR)


def _get(section: str, key: str, default=None):
    """Get a value from the loaded config dict."""
    return _raw.get(section, {}).get(key, default)


def _get_nested(section: str, subsection: str, key: str, default=None):
    """Get a nested value from the loaded config dict."""
    return _raw.get(section, {}).get(subsection, {}).get(key, default)


def _to_bool(value) -> bool:
    """Convert a value to bool (handles string 'true'/'false')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


class Settings:
    """Global application settings loaded from config.yml + config.properties."""

    def __init__(self) -> None:
        # App
        self.app_name: str = _get("app", "name", "argus-insight-server")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        # Server
        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 4500))

        # Logging
        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "server.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

        # Data
        self.data_dir: Path = Path(_get("data", "dir", "/var/lib/argus-insight-server"))

        # Config
        self.config_dir: Path = _CONFIG_DIR
        self.config_yaml_path: Path = _yaml_path
        self.config_properties_path: Path = _properties_path

        # CORS (for React UI)
        self.cors_origins: list[str] = _get("cors", "origins", ["*"])

        # Agent communication
        self.agent_timeout: int = int(_get("agent", "timeout", 30))
        self.agent_health_interval: int = int(_get("agent", "health_interval", 60))
        self.agent_heartbeat_check_interval: int = int(
            _get("agent", "heartbeat_check_interval", 60)
        )
        self.agent_heartbeat_disconnect_timeout: int = int(
            _get("agent", "heartbeat_disconnect_timeout", 180)
        )

        # Database
        self.db_type: str = _get("database", "type", "postgresql")
        self.db_host: str = _get("database", "host", "localhost")
        self.db_port: int = int(_get("database", "port", 5432))
        self.db_name: str = _get("database", "name", "argus")
        self.db_username: str = _get("database", "username", "argus")
        self.db_password: str = _get("database", "password", "argus")
        self.db_pool_size: int = int(_get_nested("database", "pool", "size", 5))
        self.db_pool_max_overflow: int = int(_get_nested("database", "pool", "max_overflow", 10))
        self.db_pool_recycle: int = int(_get_nested("database", "pool", "recycle", 3600))
        self.db_echo: bool = _to_bool(_get("database", "echo", False))

        # GitLab (Workspace Provisioner)
        self.gitlab_url: str = _get("gitlab", "url", "")
        self.gitlab_token: str = _get("gitlab", "token", "")

        # Object Storage (S3/MinIO)
        self.s3_endpoint_url: str = _get("object_storage", "endpoint_url", "http://localhost:9000")
        self.s3_access_key: str = _get("object_storage", "access_key", "minioadmin")
        self.s3_secret_key: str = _get("object_storage", "secret_key", "minioadmin")
        self.s3_region: str = _get("object_storage", "region", "us-east-1")
        self.s3_default_bucket: str = _get("object_storage", "default_bucket", "argus-data")
        self.s3_use_ssl: bool = _to_bool(_get("object_storage", "use_ssl", False))
        self.s3_multipart_threshold: int = int(
            _get("object_storage", "multipart_threshold", 8388608)
        )
        self.s3_multipart_chunksize: int = int(
            _get("object_storage", "multipart_chunksize", 8388608)
        )
        self.s3_presigned_url_expiry: int = int(
            _get("object_storage", "presigned_url_expiry", 3600)
        )


def init_settings(
    yaml_path: str | None = None,
    properties_path: str | None = None,
) -> None:
    """Re-initialize settings with custom config file paths.

    Call this before the application starts to override default config locations.
    If not called, settings are loaded from the default config directory.

    Args:
        yaml_path: Absolute path to YAML config file.
        properties_path: Absolute path to properties file.
    """
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
