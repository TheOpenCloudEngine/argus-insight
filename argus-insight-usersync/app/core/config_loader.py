"""Configuration loader with properties variable resolution.

Loads config.properties (Java-style key=value) and config.yml,
resolving ${variable} placeholders in YAML values using properties.
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")

DEFAULT_CONFIG_DIR = Path("/etc/argus-insight-usersync")


def load_properties(path: Path) -> dict[str, str]:
    """Load a Java-style .properties file into a dict."""
    props: dict[str, str] = {}

    if not path.is_file():
        logger.debug("Properties file not found: %s", path)
        return props

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue

            for sep in ("=", ":"):
                idx = line.find(sep)
                if idx >= 0:
                    key = line[:idx].strip()
                    value = line[idx + 1 :].strip()
                    props[key] = value
                    break

    return props


def _resolve_value(value: str, props: dict[str, str]) -> str:
    """Replace ${variable} or ${variable:default} placeholders."""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default_value = match.group(2)

        if var_name in props:
            return props[var_name]

        if default_value is not None:
            return default_value

        logger.warning("Unresolved variable: ${%s}", var_name)
        return match.group(0)

    return _VAR_PATTERN.sub(replacer, value)


def _resolve_dict(data: dict[str, Any], props: dict[str, str]) -> dict[str, Any]:
    """Recursively resolve ${variable} placeholders in a dict."""
    resolved = {}
    for key, value in data.items():
        if isinstance(value, str):
            resolved[key] = _resolve_value(value, props)
        elif isinstance(value, dict):
            resolved[key] = _resolve_dict(value, props)
        elif isinstance(value, list):
            resolved[key] = [
                _resolve_value(item, props) if isinstance(item, str) else item for item in value
            ]
        else:
            resolved[key] = value
    return resolved


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return as dict."""
    if not path.is_file():
        logger.debug("YAML config file not found: %s", path)
        return {}

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, dict) else {}


def load_config(
    config_dir: Path | None = None,
    yaml_file: str = "config.yml",
    properties_file: str = "config.properties",
    yaml_path: Path | str | None = None,
    properties_path: Path | str | None = None,
) -> dict[str, Any]:
    """Load configuration by resolving YAML with properties variables."""
    base_dir = config_dir or DEFAULT_CONFIG_DIR

    props_file = Path(properties_path) if properties_path else base_dir / properties_file
    yaml_config_file = Path(yaml_path) if yaml_path else base_dir / yaml_file

    props = load_properties(props_file)
    raw_config = load_yaml(yaml_config_file)

    if not raw_config:
        return {}

    return _resolve_dict(raw_config, props)
