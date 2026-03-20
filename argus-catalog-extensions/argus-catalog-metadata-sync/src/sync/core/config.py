"""Configuration loader for metadata sync."""

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).resolve().parents[3] / "config" / "sync.yml"


class CatalogConfig(BaseModel):
    base_url: str = "http://localhost:4600/api/v1/catalog"
    timeout: int = 30


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 4610


class KerberosConfig(BaseModel):
    enabled: bool = False
    principal: str = ""
    keytab: str = ""


class ScheduleConfig(BaseModel):
    interval_minutes: int = 60
    enabled: bool = True


class HivePlatformConfig(BaseModel):
    enabled: bool = False
    metastore_host: str = "localhost"
    metastore_port: int = 9083
    kerberos: KerberosConfig = KerberosConfig()
    databases: list[str] = []
    exclude_databases: list[str] = ["sys", "information_schema"]
    schedule: ScheduleConfig = ScheduleConfig()
    origin: str = "PROD"


class PlatformsConfig(BaseModel):
    hive: HivePlatformConfig = HivePlatformConfig()


class SyncConfig(BaseModel):
    catalog: CatalogConfig = CatalogConfig()
    server: ServerConfig = ServerConfig()
    platforms: PlatformsConfig = PlatformsConfig()


def load_config(path: Path | None = None) -> SyncConfig:
    """Load configuration from YAML file."""
    config_path = path or CONFIG_FILE
    if config_path.is_file():
        logger.info("Loading config from %s", config_path)
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return SyncConfig(**data)
    logger.warning("Config file not found: %s, using defaults", config_path)
    return SyncConfig()


def save_config(config: SyncConfig, path: Path | None = None) -> None:
    """Save configuration to YAML file."""
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)
    logger.info("Config saved to %s", config_path)
