"""Workflow step: Deploy KServe (KNative Serving) to Kubernetes for a workspace.

This step:
1. Deploys KServe runtime components into the workspace namespace.
2. Configures an InferenceService default serving runtime.
3. Sets up MinIO as the model storage backend.

Architecture:
    KServe Controller → InferenceService CRD
                              ↓
                       MinIO (model storage, from MinioDeployStep)
"""

import logging

from workspace_provisioner.config import KServeConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class KServeDeployStep(WorkflowStep):
    """Deploy KServe model serving infrastructure to Kubernetes.

    Reads from context:
        - workspace_name: Used to name K8s resources.
        - domain: Used for Ingress host rules.
        - k8s_namespace: Target namespace.
        - k8s_kubeconfig (optional): Path to kubeconfig.
        - minio_endpoint: MinIO internal endpoint (from MinioDeployStep).
        - minio_ws_admin_access_key: MinIO access key (from MinioSetupStep).
        - minio_ws_admin_secret_key: MinIO secret key (from MinioSetupStep).
        - kserve_config: KServe configuration from provisioning settings.

    Writes to context:
        - kserve_endpoint: External KServe gateway URL.
        - kserve_manifests: Rendered YAML (for rollback).
    """

    @property
    def name(self) -> str:
        return "kserve-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        # Ensure namespace exists
        await ensure_namespace(namespace)

        config: KServeConfig = ctx.get("kserve_config", KServeConfig())

        # MinIO credentials for model storage
        minio_endpoint = ctx.get("minio_endpoint", "")
        minio_access_key = ctx.get(
            "minio_ws_admin_access_key", ctx.get("minio_root_user", "")
        )
        minio_secret_key = ctx.get(
            "minio_ws_admin_secret_key", ctx.get("minio_root_password", "")
        )
        model_bucket = workspace_name

        variables = {
            "KSERVE_CONTROLLER_IMAGE": config.controller_image,
            "KSERVE_DEFAULT_RUNTIME": config.default_runtime,
            "KSERVE_CPU_REQUEST": config.resources.cpu_request,
            "KSERVE_CPU_LIMIT": config.resources.cpu_limit,
            "KSERVE_MEMORY_REQUEST": config.resources.memory_request,
            "KSERVE_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "MINIO_ENDPOINT": minio_endpoint,
            "MINIO_ACCESS_KEY": minio_access_key,
            "MINIO_SECRET_KEY": minio_secret_key,
            "MODEL_BUCKET": model_bucket,
            "ARGUS_SERVER_HOST": ctx.get("argus_server_host", "127.0.0.1"),
        }

        manifests = render_manifests("kserve", variables)
        logger.info(
            "Deploying KServe for workspace '%s' to namespace '%s'",
            workspace_name,
            namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for KServe controller rollout...")
        ready = await kubectl_rollout_status(
            f"deployment/argus-kserve-{workspace_name}-controller",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            logger.error(
                "KServe rollout timed out: argus-kserve-%s-controller in %s",
                workspace_name,
                namespace,
            )
            raise RuntimeError(
                f"KServe rollout timed out: argus-kserve-{workspace_name}-controller "
                f"in {namespace}"
            )

        external_endpoint = f"argus-kserve-{workspace_name}.argus-insight.{domain}"

        ctx.set("kserve_endpoint", external_endpoint)
        ctx.set("kserve_manifests", manifests)

        # Register service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-kserve",
            display_name="KServe Model Serving",
            version="1.0",
            endpoint=f"http://{external_endpoint}",
            metadata={
                "internal_endpoint": f"http://argus-kserve-{workspace_name}.{namespace}.svc.cluster.local:8080",
                "default_runtime": config.default_runtime,
                "namespace": namespace,
            },
        )

        return {
            "endpoint": external_endpoint,
            "default_runtime": config.default_runtime,
            "namespace": namespace,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: KServeConfig = ctx.get("kserve_config", KServeConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        return render_manifests("kserve", {
            "KSERVE_CONTROLLER_IMAGE": config.controller_image,
            "KSERVE_DEFAULT_RUNTIME": config.default_runtime,
            "KSERVE_CPU_REQUEST": config.resources.cpu_request,
            "KSERVE_CPU_LIMIT": config.resources.cpu_limit,
            "KSERVE_MEMORY_REQUEST": config.resources.memory_request,
            "KSERVE_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "MINIO_ENDPOINT": ctx.get("minio_endpoint", ""),
            "MINIO_ACCESS_KEY": ctx.get("minio_ws_admin_access_key", ""),
            "MINIO_SECRET_KEY": ctx.get("minio_ws_admin_secret_key", ""),
            "MODEL_BUCKET": ctx.workspace_name,
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("kserve_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back KServe K8s resources for workspace '%s'",
                ctx.workspace_name,
            )

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete all KServe K8s resources (re-rendering manifests from context)."""
        manifests = ctx.get("kserve_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        logger.info("Teardown KServe K8s resources for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
