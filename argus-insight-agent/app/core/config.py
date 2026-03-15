"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    app_name: str = "argus-server-agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8600

    # Logging
    log_level: str = "INFO"
    log_dir: Path = Path("/var/log/argus")

    # Data
    data_dir: Path = Path("/var/lib/argus")

    # Config
    config_dir: Path = Path("/etc/argus")

    # Command execution
    command_timeout: int = 300  # seconds
    command_max_output: int = 1024 * 1024  # 1MB

    # Monitor
    monitor_interval: int = 5  # seconds

    # Terminal
    terminal_shell: str = os.environ.get("SHELL", "/bin/bash")
    terminal_max_sessions: int = 10

    model_config = {"env_prefix": "ARGUS_", "env_file": "/etc/argus/agent.env"}


settings = Settings()
