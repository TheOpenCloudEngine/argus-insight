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
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

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
            f"deployment/kserve-{workspace_name}-controller",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            logger.error(
                "KServe rollout timed out: kserve-%s-controller in %s",
                workspace_name,
                namespace,
            )
            raise RuntimeError(
                f"KServe rollout timed out: kserve-{workspace_name}-controller "
                f"in {namespace}"
            )

        external_endpoint = f"kserve-{workspace_name}.argus-insight.{domain}"

        ctx.set("kserve_endpoint", external_endpoint)
        ctx.set("kserve_manifests", manifests)

        return {
            "endpoint": external_endpoint,
            "default_runtime": config.default_runtime,
            "namespace": namespace,
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("kserve_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back KServe K8s resources for workspace '%s'",
                ctx.workspace_name,
            )
