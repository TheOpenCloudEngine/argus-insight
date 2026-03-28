"""Kubernetes operations via kubectl subprocess.

Provides an async wrapper around kubectl for applying, deleting, and
querying Kubernetes resources. Manifest templates use ${VAR} placeholders
that are substituted at render time.
"""

import asyncio
import logging
import string
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a YAML template by substituting ${VAR} placeholders."""
    logger.debug("[template] Rendering %s", template_path.name)
    raw = template_path.read_text()
    tmpl = string.Template(raw)
    rendered = tmpl.safe_substitute(variables)
    logger.debug("[template] Rendered %s (%d bytes)", template_path.name, len(rendered))
    return rendered


def render_manifests(component: str, variables: dict[str, str]) -> str:
    """Render all YAML templates for a component (e.g., "minio", "vscode").

    Reads all .yaml files from templates/<component>/ in a deterministic
    order (secret, pvc, statefulset/deployment, service) and concatenates
    them with YAML document separators.
    """
    template_dir = TEMPLATES_DIR / component
    if not template_dir.is_dir():
        logger.error("[manifests] Template directory not found: %s", template_dir)
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    order = ["secret", "pvc", "statefulset", "deployment", "service"]
    yaml_files = sorted(
        template_dir.glob("*.yaml"),
        key=lambda p: next((i for i, o in enumerate(order) if o in p.stem), 99),
    )

    logger.info("[manifests] Rendering %d templates from '%s': %s",
                len(yaml_files), component, [f.name for f in yaml_files])

    parts = []
    for f in yaml_files:
        rendered = render_template(f, variables)
        parts.append(rendered)

    combined = "\n---\n".join(parts)
    logger.info("[manifests] Combined manifest: %d bytes from %d files", len(combined), len(parts))
    return combined


async def kubectl_apply(manifest_yaml: str, kubeconfig: str | None = None) -> str:
    """Apply a YAML manifest via kubectl."""
    cmd = ["kubectl", "apply", "-f", "-"]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    logger.info("[kubectl] apply: executing (%d bytes manifest)", len(manifest_yaml))
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
        logger.error("[kubectl] apply failed (rc=%d): %s", proc.returncode, stderr_str)
        raise RuntimeError(f"kubectl apply failed (rc={proc.returncode}): {stderr_str}")

    logger.info("[kubectl] apply success: %s", stdout_str)
    return stdout_str


async def kubectl_delete(manifest_yaml: str, kubeconfig: str | None = None) -> str:
    """Delete resources described by a YAML manifest via kubectl."""
    cmd = ["kubectl", "delete", "-f", "-", "--ignore-not-found"]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    logger.info("[kubectl] delete: executing (%d bytes manifest)", len(manifest_yaml))
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
        logger.warning("[kubectl] delete warning (rc=%d): %s", proc.returncode, stderr_str)
    else:
        logger.info("[kubectl] delete success: %s", stdout_str)

    return stdout_str


async def kubectl_wait(
    resource: str,
    namespace: str,
    condition: str = "condition=ready",
    timeout: int = 300,
    kubeconfig: str | None = None,
) -> bool:
    """Wait for a K8s resource to meet a condition."""
    cmd = [
        "kubectl", "wait", resource,
        f"--namespace={namespace}",
        f"--for={condition}",
        f"--timeout={timeout}s",
    ]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    logger.info("[kubectl] wait: %s --for=%s --namespace=%s (timeout=%ds)",
                resource, condition, namespace, timeout)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning("[kubectl] wait failed for %s (rc=%d): %s",
                       resource, proc.returncode, stderr.decode().strip())
        return False

    logger.info("[kubectl] wait: %s met %s", resource, condition)
    return True


async def kubectl_rollout_status(
    resource: str,
    namespace: str,
    timeout: int = 300,
    kubeconfig: str | None = None,
) -> bool:
    """Wait for a rollout to complete."""
    cmd = [
        "kubectl", "rollout", "status", resource,
        f"--namespace={namespace}",
        f"--timeout={timeout}s",
    ]
    if kubeconfig:
        cmd.insert(1, f"--kubeconfig={kubeconfig}")

    logger.info("[kubectl] rollout status: %s --namespace=%s (timeout=%ds)",
                resource, namespace, timeout)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning("[kubectl] rollout failed for %s (rc=%d): %s",
                       resource, proc.returncode, stderr.decode().strip())
        return False

    logger.info("[kubectl] rollout completed: %s", resource)
    return True
