"""Workflow step: Deploy Airflow to Kubernetes for a workspace.

This step:
1. Deploys a PostgreSQL database for Airflow metadata.
2. Deploys Airflow (webserver + scheduler + git-sync sidecar) as a StatefulSet.
3. The git-sync sidecar automatically pulls DAGs from the workspace's GitLab repo.
4. An init container runs `airflow db migrate` and creates the admin user.

Architecture:
    PostgreSQL (Deployment) ← Airflow StatefulSet (webserver + scheduler + git-sync)
                                      ↓
                              GitLab workspace repo (DAGs auto-sync)
"""

import logging
import secrets
import string

from cryptography.fernet import Fernet

from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)

AIRFLOW_DEFAULTS = {
    "AIRFLOW_IMAGE": "apache/airflow:2.10.4-python3.11",
    "AIRFLOW_DAGS_STORAGE_SIZE": "10Gi",
    "AIRFLOW_LOGS_STORAGE_SIZE": "20Gi",
    "AIRFLOW_DB_STORAGE_SIZE": "10Gi",
    "AIRFLOW_WEBSERVER_CPU_REQUEST": "250m",
    "AIRFLOW_WEBSERVER_CPU_LIMIT": "2",
    "AIRFLOW_WEBSERVER_MEMORY_REQUEST": "512Mi",
    "AIRFLOW_WEBSERVER_MEMORY_LIMIT": "2Gi",
    "AIRFLOW_SCHEDULER_CPU_REQUEST": "250m",
    "AIRFLOW_SCHEDULER_CPU_LIMIT": "2",
    "AIRFLOW_SCHEDULER_MEMORY_REQUEST": "512Mi",
    "AIRFLOW_SCHEDULER_MEMORY_LIMIT": "2Gi",
}


def _generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


class AirflowDeployStep(WorkflowStep):
    """Deploy an Airflow instance to Kubernetes for a workspace.

    Reads from context:
        - workspace_name: Used to name K8s resources.
        - domain: Used for Ingress host rules.
        - k8s_namespace: Target namespace.
        - k8s_kubeconfig (optional): Path to kubeconfig.
        - gitlab_http_url (optional): GitLab repo URL for DAG sync.
        - gitlab_token (optional): GitLab access token for git-sync.

    Writes to context:
        - airflow_endpoint: External Airflow webserver URL.
        - airflow_admin_password: Admin user password.
        - airflow_manifests: Rendered YAML (for rollback).
    """

    @property
    def name(self) -> str:
        return "airflow-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        admin_password = _generate_password()
        db_password = _generate_password()
        fernet_key = _generate_fernet_key()
        secret_key = _generate_password(32)

        # Build GitLab repo URL for DAG sync
        gitlab_repo_url = ctx.get("gitlab_http_url", "")
        gitlab_token = ctx.get("gitlab_token", "")

        variables = {
            **AIRFLOW_DEFAULTS,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "AIRFLOW_ADMIN_PASSWORD": admin_password,
            "AIRFLOW_DB_PASSWORD": db_password,
            "AIRFLOW_FERNET_KEY": fernet_key,
            "AIRFLOW_SECRET_KEY": secret_key,
            "GITLAB_REPO_URL": gitlab_repo_url,
            "GITLAB_TOKEN": gitlab_token,
        }

        # Apply context overrides
        if ctx.get("airflow_image"):
            variables["AIRFLOW_IMAGE"] = ctx.get("airflow_image")

        manifests = render_manifests("airflow", variables)
        logger.info(
            "Deploying Airflow for workspace '%s' to namespace '%s'",
            workspace_name,
            namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for DB first, then Airflow
        logger.info("Waiting for Airflow DB rollout...")
        await kubectl_rollout_status(
            f"deployment/airflow-{workspace_name}-db",
            namespace=namespace,
            timeout=120,
            kubeconfig=kubeconfig,
        )

        logger.info("Waiting for Airflow rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/airflow-{workspace_name}",
            namespace=namespace,
            timeout=600,
            kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"Airflow rollout timed out: airflow-{workspace_name} in {namespace}"
            )

        external_endpoint = f"airflow-{workspace_name}.argus-insight.{domain}"

        ctx.set("airflow_endpoint", external_endpoint)
        ctx.set("airflow_admin_password", admin_password)
        ctx.set("airflow_manifests", manifests)

        return {
            "endpoint": external_endpoint,
            "admin_user": "admin",
            "namespace": namespace,
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("airflow_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back Airflow K8s resources for workspace '%s'",
                ctx.workspace_name,
            )
