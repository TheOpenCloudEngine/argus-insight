"""Workflow step: Deploy MinIO to Kubernetes for a workspace.

This step:
1. Renders MinIO K8s manifest templates with workspace-specific variables.
2. Applies the manifests via kubectl (Secret, PVC, StatefulSet, Service, Ingress).
3. Waits for the StatefulSet rollout to complete.
4. Stores the MinIO endpoint and credentials in the workflow context.
"""

import logging
import secrets
import string

from workspace_provisioner.config import MinioConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _generate_password(length: int = 24) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class MinioDeployStep(WorkflowStep):
    """Deploy a MinIO instance to Kubernetes for a workspace.

    Reads from context:
        - workspace_name: Used to name all K8s resources.
        - domain: Used for Ingress host rules.
        - k8s_namespace: Target namespace (default: argus-ws-{workspace_name}).
        - k8s_kubeconfig (optional): Path to kubeconfig file.
        - provisioning_config.minio: MinIO configuration from UI settings.

    Writes to context:
        - minio_endpoint: Internal K8s service endpoint (host:port).
        - minio_external_endpoint: External endpoint via Ingress.
        - minio_console_endpoint: External console endpoint via Ingress.
        - minio_root_user: Root admin username.
        - minio_root_password: Root admin password.
        - minio_manifests: Rendered YAML (for rollback).
    """

    @property
    def name(self) -> str:
        return "minio-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        # Get config from context (set by service from UI request)
        config: MinioConfig = ctx.get("minio_config", MinioConfig())

        root_user = f"minio-{workspace_name}-admin"
        root_password = _generate_password()

        # Build template variables from config
        variables = {
            "MINIO_IMAGE": config.image,
            "MINIO_STORAGE_SIZE": config.storage_size,
            "MINIO_CPU_REQUEST": config.resources.cpu_request,
            "MINIO_CPU_LIMIT": config.resources.cpu_limit,
            "MINIO_MEMORY_REQUEST": config.resources.memory_request,
            "MINIO_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "MINIO_ROOT_USER": root_user,
            "MINIO_ROOT_PASSWORD": root_password,
        }

        # Render and apply manifests
        manifests = render_manifests("minio", variables)
        logger.info("Deploying MinIO for workspace '%s' to namespace '%s'", workspace_name, namespace)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for StatefulSet rollout
        resource = f"statefulset/minio-{workspace_name}"
        logger.info("Waiting for %s rollout in %s...", resource, namespace)
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=300, kubeconfig=kubeconfig
        )
        if not ready:
            raise RuntimeError(
                f"MinIO StatefulSet rollout timed out: {resource} in {namespace}"
            )

        # Build endpoints
        internal_endpoint = f"minio-{workspace_name}.{namespace}.svc.cluster.local:9000"
        external_endpoint = f"minio-{workspace_name}.argus-insight.{domain}"
        console_endpoint = f"minio-console-{workspace_name}.argus-insight.{domain}"

        # Store in context for subsequent steps
        ctx.set("minio_endpoint", internal_endpoint)
        ctx.set("minio_external_endpoint", external_endpoint)
        ctx.set("minio_console_endpoint", console_endpoint)
        ctx.set("minio_root_user", root_user)
        ctx.set("minio_root_password", root_password)
        ctx.set("minio_manifests", manifests)
        ctx.set("k8s_namespace", namespace)

        return {
            "endpoint": internal_endpoint,
            "external_endpoint": external_endpoint,
            "console_endpoint": console_endpoint,
            "root_user": root_user,
            "namespace": namespace,
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Delete all MinIO K8s resources."""
        manifests = ctx.get("minio_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back MinIO K8s resources for workspace '%s'", ctx.workspace_name)
