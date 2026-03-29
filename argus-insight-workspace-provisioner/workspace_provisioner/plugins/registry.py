"""Plugin registry for discovering, validating, and managing plugins.

The PluginRegistry is a singleton that:
- Discovers plugins from filesystem directories (builtin and external).
- Resolves dependency order using topological sort (Kahn's algorithm).
- Dynamically imports step and config classes for instantiation.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from collections import deque
from pathlib import Path

from workspace_provisioner.plugins.base import PluginMeta, load_plugin_yaml
from workspace_provisioner.workflow.engine import WorkflowStep

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton plugin registry that discovers, validates, and manages plugins."""

    _instance: PluginRegistry | None = None

    @classmethod
    def get_instance(cls) -> PluginRegistry:
        """Return the singleton registry instance, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        cls._instance = None

    def __init__(self) -> None:
        self._plugins: dict[str, PluginMeta] = {}  # name -> meta
        self._step_cache: dict[str, type[WorkflowStep]] = {}  # "name:version" -> class

    # ------------------------------------------------------------------
    # Discovery & registration
    # ------------------------------------------------------------------

    def discover(self, dirs: list[Path]) -> int:
        """Scan directories for plugin.yaml files and register them.

        Each dir is expected to contain subdirectories, each with a plugin.yaml.
        Returns number of plugins discovered.
        """
        self._discover_dirs = list(dirs)
        count = 0
        for base_dir in dirs:
            if not base_dir.is_dir():
                logger.warning("Plugin directory does not exist: %s", base_dir)
                continue
            for child in sorted(base_dir.iterdir()):
                plugin_yaml = child / "plugin.yaml"
                if child.is_dir() and plugin_yaml.exists():
                    try:
                        meta = load_plugin_yaml(child)
                        self.register(meta)
                        count += 1
                        logger.info(
                            "Discovered plugin '%s' (%s) with %d version(s) from %s",
                            meta.name,
                            meta.source,
                            len(meta.versions),
                            child,
                        )
                    except Exception:
                        logger.exception("Failed to load plugin from %s", child)
        return count

    def rescan(self) -> None:
        """Re-discover plugins from the same directories used during initial discover.

        Clears the current registry and step cache, then re-discovers.
        The discovery directories are stored during the first discover() call.
        """
        self._plugins.clear()
        self._step_cache.clear()
        if hasattr(self, "_discover_dirs"):
            self.discover(self._discover_dirs)

    def register(self, meta: PluginMeta) -> None:
        """Register a plugin. Overwrites if same name exists (external overrides builtin)."""
        if meta.name in self._plugins:
            existing = self._plugins[meta.name]
            logger.info(
                "Plugin '%s' overridden: source '%s' -> '%s'",
                meta.name,
                existing.source,
                meta.source,
            )
        self._plugins[meta.name] = meta

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_all(self) -> list[PluginMeta]:
        """Return all registered plugins sorted by name."""
        return sorted(self._plugins.values(), key=lambda p: p.name)

    def get(self, name: str) -> PluginMeta | None:
        """Get plugin by name."""
        return self._plugins.get(name)

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def resolve_order(
        self,
        selected: list[str],
        versions: dict[str, str] | None = None,
    ) -> list[str]:
        """Validate dependencies and return topologically sorted plugin names.

        Uses Kahn's algorithm (BFS-based) and tries to preserve the admin's
        preferred order where dependency constraints allow.

        Args:
            selected: Plugin names to include (order from admin).
            versions: Optional name->version mapping for version-specific deps.

        Returns:
            Sorted list of plugin names respecting dependencies.

        Raises:
            ValueError: If a dependency is missing or a cycle is detected.
        """
        versions = versions or {}
        selected_set = set(selected)

        # Build adjacency list and in-degree map
        # Edge: dep -> plugin (dep must come before plugin)
        in_degree: dict[str, int] = {name: 0 for name in selected}
        adjacency: dict[str, list[str]] = {name: [] for name in selected}

        for name in selected:
            meta = self._plugins.get(name)
            if meta is None:
                raise ValueError(f"Plugin '{name}' is not registered")

            if name in versions:
                deps = meta.get_effective_depends_on(versions[name])
            else:
                deps = list(meta.depends_on)

            for dep in deps:
                if dep not in selected_set:
                    raise ValueError(
                        f"Plugin '{name}' depends on '{dep}', "
                        f"which is not in the selected set"
                    )
                adjacency[dep].append(name)
                in_degree[name] += 1

        # Build priority map from admin's preferred order (lower index = higher priority)
        priority = {name: idx for idx, name in enumerate(selected)}

        # Kahn's algorithm with priority queue to preserve admin order
        queue: deque[str] = deque()
        # Collect all zero in-degree nodes, sorted by admin preference
        zero_degree = [name for name in selected if in_degree[name] == 0]
        zero_degree.sort(key=lambda n: priority[n])
        queue.extend(zero_degree)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)

            # Collect newly freed neighbors, then sort by admin preference
            newly_freed: list[str] = []
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    newly_freed.append(neighbor)

            if newly_freed:
                newly_freed.sort(key=lambda n: priority[n])
                # Insert into queue maintaining priority order
                # Merge newly_freed into the existing queue
                merged: deque[str] = deque()
                qi = 0
                ni = 0
                queue_list = list(queue)
                while qi < len(queue_list) and ni < len(newly_freed):
                    if priority[queue_list[qi]] <= priority[newly_freed[ni]]:
                        merged.append(queue_list[qi])
                        qi += 1
                    else:
                        merged.append(newly_freed[ni])
                        ni += 1
                while qi < len(queue_list):
                    merged.append(queue_list[qi])
                    qi += 1
                while ni < len(newly_freed):
                    merged.append(newly_freed[ni])
                    ni += 1
                queue = merged

        if len(result) != len(selected):
            # Find the cycle participants
            remaining = selected_set - set(result)
            raise ValueError(
                f"Circular dependency detected among plugins: "
                f"{', '.join(sorted(remaining))}"
            )

        return result

    def validate_order(
        self,
        ordered: list[str],
        versions: dict[str, str] | None = None,
    ) -> list[str]:
        """Check if admin-specified order respects dependencies.

        Returns list of violation messages (empty = valid).
        """
        versions = versions or {}
        violations: list[str] = []
        seen: set[str] = set()

        for name in ordered:
            meta = self._plugins.get(name)
            if meta is None:
                violations.append(f"Plugin '{name}' is not registered")
                seen.add(name)
                continue

            if name in versions:
                deps = meta.get_effective_depends_on(versions[name])
            else:
                deps = list(meta.depends_on)

            for dep in deps:
                if dep not in seen:
                    violations.append(
                        f"Plugin '{name}' depends on '{dep}', "
                        f"but '{dep}' does not appear before it"
                    )
            seen.add(name)

        return violations

    # ------------------------------------------------------------------
    # Instantiation & dynamic import
    # ------------------------------------------------------------------

    def instantiate_step(
        self,
        name: str,
        version: str | None = None,
        **kwargs,
    ) -> WorkflowStep:
        """Create a WorkflowStep instance for the given plugin and version.

        Dynamically imports the step_class from the version metadata.
        Uses cache for repeated instantiation of the same class.

        Args:
            name: Plugin name.
            version: Version string. If None, uses the plugin's default version.
            **kwargs: Arguments passed to the step class constructor.

        Returns:
            An instantiated WorkflowStep.

        Raises:
            KeyError: If the plugin or version is not found.
            ImportError: If the step class cannot be imported.
        """
        meta = self._plugins.get(name)
        if meta is None:
            raise KeyError(f"Plugin '{name}' is not registered")

        version_meta = meta.get_version(version)
        cache_key = f"{name}:{version_meta.version}"

        if cache_key not in self._step_cache:
            version_dir = meta.plugin_dir / version_meta.version
            cls = self._import_class(version_meta.step_class, base_dir=version_dir)
            if not issubclass(cls, WorkflowStep):
                raise TypeError(
                    f"Step class '{version_meta.step_class}' for plugin '{name}' "
                    f"is not a subclass of WorkflowStep"
                )
            self._step_cache[cache_key] = cls

        step_cls = self._step_cache[cache_key]
        # Pass plugin_name if the step class accepts it
        import inspect
        sig = inspect.signature(step_cls.__init__)
        if "plugin_name" in sig.parameters:
            kwargs.setdefault("plugin_name", name)
        return step_cls(**kwargs)

    def get_config_schema(self, name: str, version: str | None = None) -> dict | None:
        """Return JSON Schema for the plugin version's config class.

        Imports the Pydantic model and calls model_json_schema().
        Returns None if no config_class defined.
        """
        config_cls = self.get_config_class(name, version)
        if config_cls is None:
            return None
        return config_cls.model_json_schema()

    def get_config_class(self, name: str, version: str | None = None):
        """Return the Pydantic config model class (or None).

        Args:
            name: Plugin name.
            version: Version string. If None, uses the plugin's default version.

        Returns:
            The Pydantic model class, or None if no config_class is defined.

        Raises:
            KeyError: If the plugin or version is not found.
            ImportError: If the config class cannot be imported.
        """
        meta = self._plugins.get(name)
        if meta is None:
            raise KeyError(f"Plugin '{name}' is not registered")

        version_meta = meta.get_version(version)
        if version_meta.config_class is None:
            return None

        version_dir = meta.plugin_dir / version_meta.version
        return self._import_class(version_meta.config_class, base_dir=version_dir)

    def _import_class(self, class_path: str, base_dir: Path | None = None) -> type:
        """Import a class by its dotted path or relative path.

        If class_path contains no dots before the class name (e.g., "step.MyStep"),
        treat it as relative to base_dir using importlib.util.spec_from_file_location.
        Otherwise treat as absolute Python import path.

        Args:
            class_path: Dotted import path like "workspace_provisioner.workflow.steps.xxx.XxxStep"
                or relative like "step.XxxStep".
            base_dir: Base directory for resolving relative imports.

        Returns:
            The imported class.

        Raises:
            ImportError: If the module or class cannot be found.
        """
        module_path, _, class_name = class_path.rpartition(".")
        if not module_path:
            raise ImportError(
                f"Invalid class path '{class_path}': must be in 'module.ClassName' format"
            )

        # Determine if this is a relative or absolute import.
        # Relative: the module_path has no dots (e.g., "step" from "step.MyStep").
        # Absolute: the module_path contains dots (e.g., "workspace_provisioner.workflow.steps.xxx").
        if "." not in module_path and base_dir is not None:
            # Relative import: resolve from base_dir
            module_file = base_dir / f"{module_path}.py"
            if not module_file.exists():
                raise ImportError(
                    f"Module file not found: {module_file} "
                    f"(resolved from relative path '{class_path}')"
                )
            spec = importlib.util.spec_from_file_location(
                f"_plugin_dynamic_.{module_path}",
                module_file,
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec from {module_file}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            # Absolute import
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                raise ImportError(
                    f"Cannot import module '{module_path}' from class path '{class_path}'"
                ) from e

        cls = getattr(module, class_name, None)
        if cls is None:
            raise ImportError(
                f"Class '{class_name}' not found in module '{module_path}'"
            )

        return cls
