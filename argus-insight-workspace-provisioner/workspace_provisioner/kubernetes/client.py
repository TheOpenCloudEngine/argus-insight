"""Kubernetes operations via kubectl subprocess.

Provides an async wrapper around kubectl for applying, deleting, and
querying Kubernetes resources. Manifest templates use ${VAR} placeholders
that are substituted at render time.

This approach follows the existing Argus Insight pattern where K8s
resources are managed through YAML manifests and kustomize/kubectl,
rather than the kubernetes Python client.
"""

import asyncio
import logging
import string
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a YAML template by substituting ${VAR} placeholders.

    Uses string.Template with $-based substitution, which matches
    the ${VAR} syntax used in the manifest templates.

    Args:
        template_path: Path to the YAML template file.
        variables: Mapping of variable names to values.

    Returns:
        The rendered YAML string.
    """
    raw = template_path.read_text()
    tmpl = string.Template(raw)
    return tmpl.safe_substitute(variables)


def render_manifests(component: str, variables: dict[str, str]) -> str:
    """Render all YAML templates for a component (e.g., "minio").

    Reads all .yaml files from templates/<component>/ in a deterministic
    order (secret, pvc, statefulset/deployment, service) and concatenates
    them with YAML document separators.

    Args:
        component: Template subdirectory name (e.g., "minio").
        variables: Template variables to substitute.

    Returns:
        Combined YAML string with all rendered manifests.
    """
    template_dir = TEMPLATES_DIR / component
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    # Deterministic ordering: secret → pvc → statefulset → service
    order = ["secret", "pvc", "statefulset", "deployment", "service"]
    yaml_files = sorted(
        template_dir.glob("*.yaml"),
        key=lambda p: next((i for i, o in enumerate(order) if o in p.stem), 99),
    )

    parts = []
    for f in yaml_files:
        rendered = render_template(f, variables)
        parts.append(rendered)

    return "\n---\n".join(parts)


async def kubectl_apply(manifest_yaml: str, kubeconfig: str | None = None) -> str:
    """Apply a YAML manifest via kubectl.

    Args:
        manifest_yaml: The full YAML string to apply.
        kubeconfig: Optional path to kubeconfig file.

    Returns:
        stdout from kubectl.

    Raises:
        RuntimeError: If kubectl exits with non-zero code.
    """
    cmd = ["kubectl", "apply", "-f", "-"]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(manifest_yaml.encode())
    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()

    if proc.returncode != 0:
        logger.error("kubectl apply failed: %s", stderr_str)
        raise RuntimeError(f"kubectl apply failed (rc={proc.returncode}): {stderr_str}")

    logger.info("kubectl apply: %s", stdout_str)
    return stdout_str


async def kubectl_delete(manifest_yaml: str, kubeconfig: str | None = None) -> str:
    """Delete resources described by a YAML manifest via kubectl.

    Args:
        manifest_yaml: The full YAML string describing resources to delete.
        kubeconfig: Optional path to kubeconfig file.

    Returns:
        stdout from kubectl.
    """
    cmd = ["kubectl", "delete", "-f", "-", "--ignore-not-found"]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(manifest_yaml.encode())
    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()

    if proc.returncode != 0:
        logger.warning("kubectl delete warning: %s", stderr_str)

    logger.info("kubectl delete: %s", stdout_str)
    return stdout_str


async def kubectl_wait(
    resource: str,
    namespace: str,
    condition: str = "condition=ready",
    timeout: int = 300,
    kubeconfig: str | None = None,
) -> bool:
    """Wait for a K8s resource to meet a condition.

    Args:
        resource: Resource identifier (e.g., "statefulset/minio-my-ws").
        namespace: Kubernetes namespace.
        condition: Wait condition (default: "condition=ready").
        timeout: Timeout in seconds.
        kubeconfig: Optional kubeconfig path.

    Returns:
        True if the condition was met, False on timeout.
    """
    cmd = [
        "kubectl", "wait", resource,
        f"--namespace={namespace}",
        f"--for={condition}",
        f"--timeout={timeout}s",
    ]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning(
            "kubectl wait failed for %s: %s",
            resource,
            stderr.decode().strip(),
        )
        return False

    logger.info("kubectl wait: %s met %s", resource, condition)
    return True


async def kubectl_rollout_status(
    resource: str,
    namespace: str,
    timeout: int = 300,
    kubeconfig: str | None = None,
) -> bool:
    """Wait for a rollout to complete.

    Args:
        resource: Resource identifier (e.g., "statefulset/minio-my-ws").
        namespace: Kubernetes namespace.
        timeout: Timeout in seconds.
        kubeconfig: Optional kubeconfig path.

    Returns:
        True if the rollout completed successfully.
    """
    cmd = [
        "kubectl", "rollout", "status", resource,
        f"--namespace={namespace}",
        f"--timeout={timeout}s",
    ]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning(
            "kubectl rollout status failed for %s: %s",
            resource,
            stderr.decode().strip(),
        )
        return False

    logger.info("kubectl rollout: %s completed", resource)
    return True
