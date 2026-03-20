"""Application configuration for Argus Insight UserSync.

Configuration is loaded from two files in the config directory:

1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}

Default config directory: /etc/argus-insight-usersync
Override with ARGUS_USERSYNC_CONFIG_DIR environment variable.
Override individual files with --config-yaml / --config-properties CLI arguments.
"""

import os
from pathlib import Path

from app.core.config_loader import load_config

_CONFIG_DIR = Path(os.environ.get("ARGUS_USERSYNC_CONFIG_DIR", "/etc/argus-insight-usersync"))
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


def _to_list(value, sep=",") -> list[str]:
    """Convert a string to a list by splitting on separator."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(sep) if item.strip()]
    return []


class Settings:
    """Global application settings loaded from config.yml + config.properties."""

    def __init__(self) -> None:
        # App
        self.app_name: str = _get("app", "name", "argus-insight-usersync")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        # Logging
        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "usersync.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

        # Sync source type: ldap, unix, file
        self.sync_source: str = _get("sync", "source", "unix")

        # Sync filters
        self.sync_user_filter: list[str] = _to_list(_get("sync", "user_filter", ""))
        self.sync_group_filter: list[str] = _to_list(_get("sync", "group_filter", ""))
        # Minimum UID/GID for unix source (skip system users)
        self.sync_min_uid: int = int(_get("sync", "min_uid", 500))
        self.sync_min_gid: int = int(_get("sync", "min_gid", 500))

        # LDAP source
        self.ldap_url: str = _get("ldap", "url", "ldap://localhost:389")
        self.ldap_bind_dn: str = _get("ldap", "bind_dn", "")
        self.ldap_bind_password: str = _get("ldap", "bind_password", "")
        self.ldap_user_search_base: str = _get("ldap", "user_search_base", "")
        self.ldap_user_search_filter: str = _get(
            "ldap", "user_search_filter", "(objectClass=person)"
        )
        self.ldap_user_name_attr: str = _get("ldap", "user_name_attribute", "uid")
        self.ldap_user_group_name_attr: str = _get("ldap", "user_group_name_attribute", "memberOf")
        self.ldap_group_search_base: str = _get("ldap", "group_search_base", "")
        self.ldap_group_search_filter: str = _get(
            "ldap", "group_search_filter", "(objectClass=groupOfNames)"
        )
        self.ldap_group_name_attr: str = _get("ldap", "group_name_attribute", "cn")
        self.ldap_group_member_attr: str = _get("ldap", "group_member_attribute", "member")
        self.ldap_page_size: int = int(_get("ldap", "page_size", 500))
        self.ldap_referral: str = _get("ldap", "referral", "ignore")
        self.ldap_use_ssl: bool = _to_bool(_get("ldap", "use_ssl", False))
        self.ldap_tls_ca_cert: str = _get("ldap", "tls_ca_cert", "")

        # File source
        self.file_users_path: str = _get("file", "users_path", "")
        self.file_groups_path: str = _get("file", "groups_path", "")
        self.file_format: str = _get("file", "format", "csv")

        # Database (Argus platform DB)
        self.db_type: str = _get("database", "type", "postgresql")
        self.db_host: str = _get("database", "host", "localhost")
        self.db_port: int = int(_get("database", "port", 5432))
        self.db_name: str = _get("database", "name", "argus")
        self.db_username: str = _get("database", "username", "argus")
        self.db_password: str = _get("database", "password", "argus")

        # Config
        self.config_dir: Path = _CONFIG_DIR
        self.config_yaml_path: Path = _yaml_path
        self.config_properties_path: Path = _properties_path


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
