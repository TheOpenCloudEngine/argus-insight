"""Application configuration.

Configuration is loaded from two files in the config directory:
1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}
"""

import os
from pathlib import Path

from app.core.config_loader import load_config

_CONFIG_DIR = Path(os.environ.get("ARGUS_DE_AGENT_CONFIG_DIR", "/etc/argus-data-engineer-ai-agent"))
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
        self.app_name: str = _get("app", "name", "argus-data-engineer-ai-agent")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _to_bool(_get("app", "debug", False))

        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 4700))

        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "argus-de-agent.log")
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
        self.db_name: str = _get("database", "name", "argus_de_agent")
        self.db_username: str = _get("database", "username", "argus")
        self.db_password: str = _get("database", "password", "argus")
        self.db_pool_size: int = int(_get_nested("database", "pool", "size", 5))
        self.db_pool_max_overflow: int = int(_get_nested("database", "pool", "max_overflow", 10))
        self.db_pool_recycle: int = int(_get_nested("database", "pool", "recycle", 3600))
        self.db_echo: bool = _to_bool(_get("database", "echo", False))

        # Catalog Server
        self.catalog_base_url: str = _get("catalog", "base_url", "http://localhost:4600")
        self.catalog_api_prefix: str = _get("catalog", "api_prefix", "/api/v1")
        self.catalog_timeout: int = int(_get("catalog", "timeout", 30))

        # LLM
        self.llm_provider: str = _get("llm", "provider", "anthropic")
        self.llm_model: str = _get("llm", "model", "claude-sonnet-4-20250514")
        self.llm_api_key: str = _get("llm", "api_key", "")
        self.llm_api_url: str = _get("llm", "api_url", "")
        self.llm_temperature: float = float(_get("llm", "temperature", 0.3))
        self.llm_max_tokens: int = int(_get("llm", "max_tokens", 4096))

        # Agent
        self.agent_max_steps: int = int(_get("agent", "max_steps", 20))
        self.agent_auto_approve_reads: bool = _to_bool(_get("agent", "auto_approve_reads", True))
        self.agent_auto_approve_writes: bool = _to_bool(_get("agent", "auto_approve_writes", False))

        # Auth
        self.auth_type: str = _get("auth", "type", "local")
        self.auth_keycloak_server_url: str = _get_nested(
            "auth", "keycloak", "server_url", "http://localhost:8180"
        )
        self.auth_keycloak_realm: str = _get_nested("auth", "keycloak", "realm", "argus")
        self.auth_keycloak_client_id: str = _get_nested(
            "auth", "keycloak", "client_id", "argus-client"
        )
        self.auth_keycloak_client_secret: str = _get_nested(
            "auth", "keycloak", "client_secret", "argus-client-secret"
        )
        self.auth_keycloak_admin_role: str = _get_nested(
            "auth", "keycloak", "admin_role", "argus-admin"
        )
        self.auth_keycloak_superuser_role: str = _get_nested(
            "auth", "keycloak", "superuser_role", "argus-superuser"
        )
        self.auth_keycloak_user_role: str = _get_nested(
            "auth", "keycloak", "user_role", "argus-user"
        )


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
