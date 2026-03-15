"""Application configuration.

Configuration is loaded from two files in the config directory:

1. config.properties - Java-style key=value variable definitions
2. config.yml - Main YAML config using Spring Boot style ${variable:default}

Variable resolution order:
  1. Lookup variable in config.properties
  2. If not found, use the default value specified after ':'
  3. If no default, the placeholder is left as-is

Default config directory: /etc/argus-insight-agent
Override with ARGUS_CONFIG_DIR environment variable.
"""

import os
from pathlib import Path

from app.core.config_loader import load_config

_CONFIG_DIR = Path(os.environ.get("ARGUS_CONFIG_DIR", "/etc/argus-insight-agent"))
_raw = load_config(config_dir=_CONFIG_DIR)


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
        self.app_name: str = _get("app", "name", "argus-insight-agent")
        self.app_version: str = _get("app", "version", "0.1.0")
        self.debug: bool = _get("app", "debug", False)

        # Server
        self.host: str = _get("server", "host", "0.0.0.0")
        self.port: int = int(_get("server", "port", 8600))

        # Logging
        self.log_level: str = _get("logging", "level", "INFO")
        self.log_dir: Path = Path(_get("logging", "dir", "logs"))
        self.log_filename: str = _get("logging", "filename", "agent.log")
        self.log_rolling_type: str = _get_nested("logging", "rolling", "type", "daily")
        self.log_rolling_backup_count: int = int(
            _get_nested("logging", "rolling", "backup_count", 30)
        )

        # Data
        self.data_dir: Path = Path(_get("data", "dir", "/var/lib/argus-insight-agent"))

        # Config
        self.config_dir: Path = _CONFIG_DIR

        # Backup
        self.backup_dir: Path = Path(_get("backup", "dir", "backups"))

        # Command execution
        self.command_timeout: int = int(_get("command", "timeout", 300))
        self.command_max_output: int = int(_get("command", "max_output", 1024 * 1024))

        # Monitor
        self.monitor_interval: int = int(_get("monitor", "interval", 5))

        # Terminal
        self.terminal_shell: str = _get("terminal", "shell", os.environ.get("SHELL", "/bin/bash"))
        self.terminal_max_sessions: int = int(_get("terminal", "max_sessions", 10))

        # Certificate
        self.cert_days: int = int(_get("certificate", "days", 825))
        self.cert_key_bits: int = int(_get("certificate", "key_bits", 2048))
        self.cert_base_dir: Path = Path(_get("certificate", "dir", "certificates"))

        # File manager
        self.filemgr_exec_timeout: int = int(_get("filemgr", "exec_timeout", 60))

        # Prometheus
        self.prometheus_enable_push: bool = _to_bool(_get("prometheus", "enable-push", True))
        self.prometheus_pushgateway_host: str = _get_nested(
            "prometheus", "pushgateway", "host", "localhost"
        )
        self.prometheus_pushgateway_port: int = int(
            _get_nested("prometheus", "pushgateway", "port", 9091)
        )
        self.prometheus_push_cron: str = _get("prometheus", "push-cron", "* * * * *")


settings = Settings()
