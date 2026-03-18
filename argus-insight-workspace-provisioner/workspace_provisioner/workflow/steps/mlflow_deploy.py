"""Workflow step: Deploy MLflow to Kubernetes for a workspace.

This step:
1. Deploys a PostgreSQL database for MLflow backend store.
2. Deploys the MLflow tracking server configured to use:
   - PostgreSQL as the backend store (experiments, runs, metrics).
   - Workspace MinIO as the artifact store (models, data files).
3. Creates a dedicated MinIO bucket for MLflow artifacts.

Architecture:
    PostgreSQL (Deployment) ← MLflow Server (StatefulSet)
                                    ↓
                             MinIO (artifact storage, from MinioDeployStep)
"""

import logging
import secrets
import string

from workspace_provisioner.config import MlflowConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.minio.client import MinioAdminClient
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class MlflowDeployStep(WorkflowStep):
    """Deploy an MLflow tracking server to Kubernetes for a workspace.

    Reads from context:
        - workspace_name: Used to name K8s resources.
        - domain: Used for Ingress host rules.
        - k8s_namespace: Target namespace.
        - k8s_kubeconfig (optional): Path to kubeconfig.
        - minio_endpoint: MinIO internal endpoint (from MinioDeployStep).
        - minio_root_user: MinIO root user (from MinioDeployStep).
        - minio_root_password: MinIO root password (from MinioDeployStep).
        - provisioning_config.mlflow: MLflow configuration from UI settings.

    Writes to context:
        - mlflow_endpoint: External MLflow tracking server URL.
        - mlflow_artifact_bucket: MinIO bucket for MLflow artifacts.
        - mlflow_manifests: Rendered YAML (for rollback).
    """

    @property
    def name(self) -> str:
        return "mlflow-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        # Get config from context (set by service from UI request)
        config: MlflowConfig = ctx.get("mlflow_config", MlflowConfig())

        db_password = _generate_password()
        artifact_bucket = workspace_name  # Reuse workspace default bucket

        # MinIO credentials for MLflow artifact access
        minio_endpoint = ctx.get("minio_endpoint")
        minio_access_key = ctx.get("minio_ws_admin_access_key", ctx.get("minio_root_user", ""))
        minio_secret_key = ctx.get("minio_ws_admin_secret_key", ctx.get("minio_root_password", ""))

        # Create mlflow-artifacts prefix/bucket in MinIO if needed
        if minio_endpoint and ctx.get("minio_root_user"):
            try:
                minio_client = MinioAdminClient(
                    endpoint=minio_endpoint,
                    root_user=ctx.get("minio_root_user"),
                    root_password=ctx.get("minio_root_password"),
                )
                await minio_client.create_bucket(artifact_bucket)
            except Exception as e:
                logger.warning("MinIO bucket check for MLflow artifacts: %s", e)

        variables = {
            "MLFLOW_IMAGE": config.image,
            "MLFLOW_POSTGRES_IMAGE": config.postgres_image,
            "MLFLOW_DB_STORAGE_SIZE": config.db_storage_size,
            "MLFLOW_CPU_REQUEST": config.resources.cpu_request,
            "MLFLOW_CPU_LIMIT": config.resources.cpu_limit,
            "MLFLOW_MEMORY_REQUEST": config.resources.memory_request,
            "MLFLOW_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "MLFLOW_DB_PASSWORD": db_password,
            "MLFLOW_ARTIFACT_BUCKET": artifact_bucket,
            "MINIO_ACCESS_KEY": minio_access_key,
            "MINIO_SECRET_KEY": minio_secret_key,
        }

        manifests = render_manifests("mlflow", variables)
        logger.info(
            "Deploying MLflow for workspace '%s' to namespace '%s'",
            workspace_name,
            namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for DB first, then MLflow
        logger.info("Waiting for MLflow DB rollout...")
        await kubectl_rollout_status(
            f"deployment/mlflow-{workspace_name}-db",
            namespace=namespace,
            timeout=120,
            kubeconfig=kubeconfig,
        )

        logger.info("Waiting for MLflow server rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/mlflow-{workspace_name}",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            logger.error("MLflow rollout timed out: mlflow-%s in %s", workspace_name, namespace)
            raise RuntimeError(
                f"MLflow rollout timed out: mlflow-{workspace_name} in {namespace}"
            )

        external_endpoint = f"mlflow-{workspace_name}.argus-insight.{domain}"

        ctx.set("mlflow_endpoint", external_endpoint)
        ctx.set("mlflow_artifact_bucket", artifact_bucket)
        ctx.set("mlflow_manifests", manifests)

        return {
            "endpoint": external_endpoint,
            "artifact_bucket": artifact_bucket,
            "namespace": namespace,
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("mlflow_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back MLflow K8s resources for workspace '%s'",
                ctx.workspace_name,
            )
