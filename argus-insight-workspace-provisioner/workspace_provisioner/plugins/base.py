"""Core dataclasses and loaders for the plugin metadata system.

Defines PluginVersionMeta and PluginMeta dataclasses that are parsed from
version.yaml and plugin.yaml files respectively. Provides module-level
loader functions for reading these YAML files from disk.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PluginVersionMeta:
    """Metadata for a single plugin version, parsed from version.yaml.

    Each version directory contains a version.yaml that describes the
    deployment strategy, configuration, and compatibility constraints
    for that specific version of the plugin.
    """

    version: str
    display_name: str
    description: str
    status: str
    step_class: str
    config_class: str | None = None
    template_dir: str | None = None
    changelog: str | None = None
    upgradeable_from: list[str] = field(default_factory=list)
    release_date: str | None = None
    min_k8s_version: str | None = None
    depends_on_override: dict[str, list[str]] | None = None


@dataclass
class PluginMeta:
    """Metadata for a plugin, parsed from plugin.yaml.

    A plugin represents a deployable component (e.g., "airflow-deploy")
    that can have multiple versioned implementations. The plugin-level
    metadata defines common properties shared across all versions.
    """

    name: str
    display_name: str
    description: str
    icon: str
    category: str
    depends_on: list[str]
    provides: list[str]
    requires: list[str]
    tags: list[str]
    source: str
    plugin_dir: Path
    versions: dict[str, PluginVersionMeta]
    default_version: str

    def get_effective_depends_on(self, version: str) -> list[str]:
        """Return merged dependency list for a specific version.

        Starts with the plugin-level depends_on, then applies the version's
        depends_on_override by adding entries from 'add' and removing entries
        from 'remove'.

        Args:
            version: The version string to resolve dependencies for.

        Returns:
            The effective list of plugin dependencies.

        Raises:
            KeyError: If the specified version does not exist.
        """
        version_meta = self.versions[version]
        result = list(self.depends_on)

        if version_meta.depends_on_override is None:
            return result

        for item in version_meta.depends_on_override.get("remove", []):
            if item in result:
                result.remove(item)

        for item in version_meta.depends_on_override.get("add", []):
            if item not in result:
                result.append(item)

        return result

    def get_version(self, version: str | None = None) -> PluginVersionMeta:
        """Return the specified version or the default version.

        Args:
            version: Version string to look up. If None, returns the
                default version.

        Returns:
            The PluginVersionMeta for the requested version.

        Raises:
            KeyError: If the specified version does not exist.
        """
        key = version if version is not None else self.default_version
        return self.versions[key]


def load_version_yaml(version_dir: Path) -> PluginVersionMeta:
    """Load a single version.yaml from a version directory.

    Args:
        version_dir: Path to the version directory containing version.yaml.

    Returns:
        Parsed PluginVersionMeta instance.

    Raises:
        FileNotFoundError: If version.yaml does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    version_file = version_dir / "version.yaml"
    with open(version_file) as f:
        data = yaml.safe_load(f)

    return PluginVersionMeta(
        version=data["version"],
        display_name=data["display_name"],
        description=data["description"],
        status=data["status"],
        step_class=data["step_class"],
        config_class=data.get("config_class"),
        template_dir=data.get("template_dir"),
        changelog=data.get("changelog"),
        upgradeable_from=data.get("upgradeable_from", []),
        release_date=data.get("release_date"),
        min_k8s_version=data.get("min_k8s_version"),
        depends_on_override=data.get("depends_on_override"),
    )


def load_plugin_yaml(plugin_dir: Path) -> PluginMeta:
    """Load plugin.yaml and all version.yaml files from a plugin directory.

    Scans subdirectories for version.yaml files to build the complete
    set of available versions for this plugin.

    Args:
        plugin_dir: Path to the plugin directory containing plugin.yaml
            and version subdirectories.

    Returns:
        Parsed PluginMeta instance with all discovered versions.

    Raises:
        FileNotFoundError: If plugin.yaml does not exist.
        yaml.YAMLError: If any YAML file is malformed.
    """
    plugin_file = plugin_dir / "plugin.yaml"
    with open(plugin_file) as f:
        data = yaml.safe_load(f)

    versions: dict[str, PluginVersionMeta] = {}
    for child in sorted(plugin_dir.iterdir()):
        version_file = child / "version.yaml"
        if child.is_dir() and version_file.exists():
            version_meta = load_version_yaml(child)
            versions[version_meta.version] = version_meta

    return PluginMeta(
        name=data["name"],
        display_name=data["display_name"],
        description=data["description"],
        icon=data["icon"],
        category=data["category"],
        depends_on=data.get("depends_on", []),
        provides=data.get("provides", []),
        requires=data.get("requires", []),
        tags=data.get("tags", []),
        source=data.get("source", "builtin"),
        plugin_dir=plugin_dir,
        versions=versions,
        default_version=data["default_version"],
    )
