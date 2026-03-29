"""Plugin architecture for workspace provisioning.

Provides a metadata-driven, version-aware plugin system where:
- Each plugin is a self-contained directory with plugin.yaml metadata.
- Each plugin can have multiple versions with different deployment strategies.
- The PluginRegistry discovers, validates, and manages plugins.
- Admins configure plugin order and versions via the UI/API.
"""
