"""Configuration loader with properties variable resolution."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)
_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")
DEFAULT_CONFIG_DIR = Path("/etc/argus-rag-server")


def load_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.is_file():
        return props
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            for sep in ("=", ":"):
                idx = line.find(sep)
                if idx >= 0:
                    props[line[:idx].strip()] = line[idx + 1 :].strip()
                    break
    return props


def _resolve_value(value: str, props: dict[str, str]) -> str:
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        if var_name in props:
            return props[var_name]
        return default if default is not None else match.group(0)

    return _VAR_PATTERN.sub(replacer, value)


def _resolve_dict(data: dict[str, Any], props: dict[str, str]) -> dict[str, Any]:
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


def load_config(
    config_dir: Path | None = None,
    yaml_path: Path | str | None = None,
    properties_path: Path | str | None = None,
) -> dict[str, Any]:
    base_dir = config_dir or DEFAULT_CONFIG_DIR
    props_file = Path(properties_path) if properties_path else base_dir / "config.properties"
    yaml_file = Path(yaml_path) if yaml_path else base_dir / "config.yml"
    props = load_properties(props_file)
    if not yaml_file.is_file():
        return {}
    with open(yaml_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        return {}
    return _resolve_dict(raw, props)
