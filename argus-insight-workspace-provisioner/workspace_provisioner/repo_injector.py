"""Repository configuration injector for K8s deployments.

Reads OS-level package repository settings from the DB and injects
ConfigMap + volumeMount into rendered K8s manifests so that containers
use the admin-configured repos instead of the image defaults.

Usage in deploy steps:
    manifests = render_manifests("airflow", variables)
    manifests = await inject_repo_config(manifests, os_key="debian-12", namespace=namespace)
    await kubectl_apply(manifests, kubeconfig=kubeconfig)
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


async def _load_repo_settings(os_key: str) -> dict | None:
    """Load repository settings for an OS key from DB."""
    from app.core.database import async_session
    from app.settings.service import get_config_by_category

    async with async_session() as session:
        cfg = await get_config_by_category(session, f"repo_{os_key}")
        raw = cfg.get("repos", "")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None


def _generate_apt_content(repos: dict) -> str:
    """Generate /etc/apt/sources.list.d/argus.list content."""
    lines = ["# Managed by Argus Insight - do not edit manually"]
    for r in repos.get("builtin", []):
        if not r.get("enabled", True):
            continue
        trusted = " [trusted=yes]" if r.get("trusted") else ""
        lines.append(f"{r['type']}{trusted} {r['url']} {r['dist']} {r['components']}")
    for r in repos.get("custom", []):
        if not r.get("enabled", True):
            continue
        trusted = " [trusted=yes]" if r.get("trusted") else ""
        lines.append(f"{r['type']}{trusted} {r['url']} {r['dist']} {r['components']}")
    return "\n".join(lines) + "\n"


def _generate_yum_content(repos: dict) -> str:
    """Generate /etc/yum.repos.d/argus.repo content."""
    lines = ["# Managed by Argus Insight - do not edit manually"]
    for r in list(repos.get("builtin", [])) + list(repos.get("custom", [])):
        if not r.get("enabled", True):
            continue
        lines.append(f"\n[{r['repo_id']}]")
        lines.append(f"name={r['name']}")
        lines.append(f"baseurl={r['baseurl']}")
        lines.append(f"gpgcheck={'1' if r.get('gpgcheck') else '0'}")
        lines.append("enabled=1")
        if r.get("gpgkey"):
            lines.append(f"gpgkey={r['gpgkey']}")
    return "\n".join(lines) + "\n"


def _generate_apk_content(repos: dict) -> str:
    """Generate /etc/apk/repositories content."""
    lines = ["# Managed by Argus Insight - do not edit manually"]
    for r in list(repos.get("builtin", [])) + list(repos.get("custom", [])):
        if not r.get("enabled", True):
            continue
        lines.append(r["url"])
    return "\n".join(lines) + "\n"


def _generate_repo_content(os_key: str, repos: dict) -> tuple[str, str, str]:
    """Generate repo file content and return (filename, content, pkg_type).

    Returns:
        (filename, content, pkg_type) where pkg_type is "apt", "yum", or "apk".
    """
    if os_key.startswith(("debian-", "ubuntu-")):
        return "argus.list", _generate_apt_content(repos), "apt"
    elif os_key.startswith(("rocky-", "centos-", "rhel-")):
        return "argus.repo", _generate_yum_content(repos), "yum"
    elif os_key.startswith("alpine-"):
        return "repositories", _generate_apk_content(repos), "apk"
    else:
        return "", "", ""


def _build_configmap_yaml(name: str, namespace: str, filename: str, content: str) -> str:
    """Build a ConfigMap YAML document."""
    # Indent content for YAML
    indented = "\n".join(f"    {line}" for line in content.splitlines())
    return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    app.kubernetes.io/part-of: argus-insight
    argus-insight/component: repo-config
data:
  {filename}: |
{indented}
"""


def _inject_volumes_into_manifest(manifest: str, configmap_name: str, pkg_type: str) -> str:
    """Inject initContainer, volumeMounts, and volumes into Deployment/StatefulSet manifests.

    Parses the YAML text and injects repo override configuration.
    """
    if pkg_type == "apt":
        mount_path_dir = "/etc/apt/sources.list.d"
        sources_file = "/etc/apt/sources.list"
        clear_cmd = (
            'echo "# Managed by Argus Insight" > /target-sources/sources.list'
        )
        file_key = "argus.list"
    elif pkg_type == "yum":
        mount_path_dir = "/etc/yum.repos.d"
        sources_file = None
        clear_cmd = ""
        file_key = "argus.repo"
    elif pkg_type == "apk":
        mount_path_dir = None  # We'll mount the file directly
        sources_file = "/etc/apk/repositories"
        clear_cmd = ""
        file_key = "repositories"
    else:
        return manifest

    # Volume definitions to add
    volumes_yaml = f"""
        - name: argus-repo-config
          configMap:
            name: {configmap_name}"""

    if pkg_type == "apt":
        # For APT: mount configmap as sources.list.d dir + empty sources.list
        volumes_yaml += """
        - name: argus-sources-list
          emptyDir: {}"""

    # Build volumeMounts for main containers
    if pkg_type == "apt":
        container_mounts = f"""
            - name: argus-repo-config
              mountPath: {mount_path_dir}
            - name: argus-sources-list
              mountPath: {sources_file}
              subPath: sources.list"""
    elif pkg_type == "yum":
        container_mounts = f"""
            - name: argus-repo-config
              mountPath: {mount_path_dir}"""
    elif pkg_type == "apk":
        container_mounts = f"""
            - name: argus-repo-config
              mountPath: {sources_file}
              subPath: {file_key}"""
    else:
        return manifest

    # Build initContainer for APT (to create empty sources.list)
    init_container_yaml = ""
    if pkg_type == "apt":
        # Find the image from the manifest
        image_match = re.search(r'image:\s*(\S+)', manifest)
        init_image = image_match.group(1) if image_match else "busybox:latest"
        init_container_yaml = f"""
        - name: setup-repos
          image: {init_image}
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "# Managed by Argus Insight" > /target-sources/sources.list
          volumeMounts:
            - name: argus-sources-list
              mountPath: /target-sources"""

    # Inject into manifest text
    result = manifest

    # Add volumes (find "volumes:" section and append)
    if "volumes:" in result:
        result = result.replace(
            "volumes:",
            "volumes:" + volumes_yaml,
            1,  # Only first occurrence
        )
    else:
        # No volumes section, add before the last line of spec
        result = result.rstrip() + f"\n      volumes:{volumes_yaml}\n"

    # Add initContainer for APT
    if init_container_yaml:
        if "initContainers:" in result:
            # Append to existing initContainers
            result = result.replace(
                "initContainers:",
                "initContainers:" + init_container_yaml,
                1,
            )
        else:
            # Add before "containers:"
            result = result.replace(
                "      containers:",
                f"      initContainers:{init_container_yaml}\n      containers:",
                1,
            )

    # Add volumeMounts to each container (find "volumeMounts:" and append)
    # We need to add to all containers' volumeMounts
    parts = result.split("volumeMounts:")
    if len(parts) > 1:
        result = (container_mounts + "\n            volumeMounts:").join(
            [parts[0] + "volumeMounts:"] +
            [container_mounts + "\n            volumeMounts:" + p if i < len(parts) - 2
             else p
             for i, p in enumerate(parts[1:-1])]
            + [parts[-1]]
        ) if len(parts) > 2 else parts[0] + "volumeMounts:" + container_mounts + parts[1]

    return result


async def inject_repo_config(
    manifests: str,
    os_key: str | None,
    namespace: str,
    instance_id: str = "",
) -> str:
    """Inject repository configuration into K8s manifests.

    If the OS key has enabled repo settings, generates a ConfigMap and
    modifies Deployment/StatefulSet manifests to mount the repo files.

    Args:
        manifests: Combined K8s manifest YAML string.
        os_key: OS+version key from version.yaml (e.g., "debian-12").
        namespace: K8s namespace for the ConfigMap.
        instance_id: Unique identifier for the ConfigMap name.

    Returns:
        Modified manifests with repo injection, or original if not applicable.
    """
    if not os_key:
        return manifests

    repos = await _load_repo_settings(os_key)
    if not repos or not repos.get("enabled", False):
        logger.debug("Repo injection skipped for %s (not enabled)", os_key)
        return manifests

    filename, content, pkg_type = _generate_repo_content(os_key, repos)
    if not filename:
        logger.warning("Unknown OS key format: %s", os_key)
        return manifests

    configmap_name = f"argus-repo-{instance_id or 'default'}"

    # Generate ConfigMap
    configmap_yaml = _build_configmap_yaml(configmap_name, namespace, filename, content)

    # Inject volumes into Deployment/StatefulSet documents
    docs = manifests.split("\n---\n")
    modified_docs = []
    for doc in docs:
        if "kind: Deployment" in doc or "kind: StatefulSet" in doc:
            doc = _inject_volumes_into_manifest(doc, configmap_name, pkg_type)
        modified_docs.append(doc)

    # Prepend ConfigMap to manifests
    result = configmap_yaml + "\n---\n" + "\n---\n".join(modified_docs)
    logger.info("Repo config injected for %s: configmap=%s, pkg_type=%s", os_key, configmap_name, pkg_type)
    return result
