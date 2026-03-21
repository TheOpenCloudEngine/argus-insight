"""Application configuration.

Configuration is loaded from two files in the config directory:
1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}
"""

import os
from pathlib import Path

from sync.core.config_loader import load_config

_CONFIG_DIR = Path(
    os.environ.get("ARGUS_CATALOG_METADATA_SYNC_CONFIG_DIR", "/etc/argus-catalog-metadata-sync")
)
_yaml_path: Path = _CONFIG_DIR / "config.yml"
_properties_path: Path = _CONFIG_DIR / "config.properties"
_raw: dict = load_config(config_dir=_CONFIG_DIR)


def _get(section: str, key: str, default=None):
    return _raw.get(section, {}).get(key, default)


def _get_nested(section: str, subsection: str, key: str, default=None):
    return _raw.get(section, {}).get(subsection, {}).get(key, default)


def _get_deep(section: str, sub1: str, sub2: str, key: str, default=None):
    return _raw.get(section, {}).get(sub1, {}).get(sub2, {}).get(key, default)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


class Settings:
    """Global application settings loaded from config.yml + config.properties."""

    def __init__(self) -> None:
        self.app_name: str = _get("app", "name", "argus-catalog-metadata-sync")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 4610))

        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "argus-catalog-metadata-sync.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

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

        # Catalog Server
        self.catalog_base_url: str = _get("catalog", "base_url",
                                          "http://localhost:4600/api/v1/catalog")
        self.catalog_timeout: int = int(_get("catalog", "timeout", 30))

        # Hive Platform
        hive_raw = _raw.get("platforms", {}).get("hive", {})
        self.hive_enabled: bool = _to_bool(hive_raw.get("enabled", True))
        self.hive_metastore_host: str = hive_raw.get("metastore_host", "localhost")
        self.hive_metastore_port: int = int(hive_raw.get("metastore_port", 9083))
        krb = hive_raw.get("kerberos", {})
        self.hive_kerberos_enabled: bool = _to_bool(krb.get("enabled", False))
        self.hive_kerberos_principal: str = krb.get("principal", "")
        self.hive_kerberos_keytab: str = krb.get("keytab", "")
        self.hive_databases: list[str] = hive_raw.get("databases", [])
        self.hive_exclude_databases: list[str] = hive_raw.get(
            "exclude_databases", ["sys", "information_schema"]
        )
        sched = hive_raw.get("schedule", {})
        self.hive_schedule_interval_minutes: int = int(sched.get("interval_minutes", 60))
        self.hive_schedule_enabled: bool = _to_bool(sched.get("enabled", True))
        self.hive_origin: str = hive_raw.get("origin", "PROD")

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy database URL from config."""
        if self.db_type == "postgresql":
            return (
                f"postgresql://{self.db_username}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        elif self.db_type == "mariadb" or self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.db_username}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        else:
            return f"sqlite:///{self.db_name}"


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
