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

from workspace_provisioner.config import AirflowConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


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
        - provisioning_config.airflow: Airflow configuration from UI settings.

    Writes to context:
        - airflow_endpoint: External Airflow webserver URL.
        - airflow_admin_password: Admin user password.
        - airflow_manifests: Rendered YAML (for rollback).
    """

    @property
    def name(self) -> str:
        return "airflow-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        # Ensure namespace exists
        await ensure_namespace(namespace)

        # Get config from context (set by service from UI request)
        config: AirflowConfig = ctx.get("airflow_config", AirflowConfig())

        admin_password = _generate_password()
        db_password = _generate_password()
        fernet_key = _generate_fernet_key()
        secret_key = _generate_password(32)

        # Build GitLab repo URL for DAG sync
        gitlab_repo_url = ctx.get("gitlab_http_url", "")
        gitlab_token = ctx.get("gitlab_token", "")

        # Generate unique service ID for hostname
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-airflow-{svc_id}.argus-insight.{domain}"

        variables = {
            "AIRFLOW_IMAGE": config.image,
            "AIRFLOW_POSTGRES_IMAGE": config.postgres_image,
            "AIRFLOW_GIT_SYNC_IMAGE": config.git_sync_image,
            "AIRFLOW_GIT_SYNC_INTERVAL": str(config.git_sync_interval),
            "AIRFLOW_DAGS_SUB_PATH": config.dags_sub_path,
            "AIRFLOW_DAGS_STORAGE_SIZE": config.dags_storage_size,
            "AIRFLOW_LOGS_STORAGE_SIZE": config.logs_storage_size,
            "AIRFLOW_DB_STORAGE_SIZE": config.db_storage_size,
            "AIRFLOW_WEBSERVER_CPU_REQUEST": config.webserver_resources.cpu_request,
            "AIRFLOW_WEBSERVER_CPU_LIMIT": config.webserver_resources.cpu_limit,
            "AIRFLOW_WEBSERVER_MEMORY_REQUEST": config.webserver_resources.memory_request,
            "AIRFLOW_WEBSERVER_MEMORY_LIMIT": config.webserver_resources.memory_limit,
            "AIRFLOW_SCHEDULER_CPU_REQUEST": config.scheduler_resources.cpu_request,
            "AIRFLOW_SCHEDULER_CPU_LIMIT": config.scheduler_resources.cpu_limit,
            "AIRFLOW_SCHEDULER_MEMORY_REQUEST": config.scheduler_resources.memory_request,
            "AIRFLOW_SCHEDULER_MEMORY_LIMIT": config.scheduler_resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
            "AIRFLOW_ADMIN_PASSWORD": admin_password,
            "AIRFLOW_DB_PASSWORD": db_password,
            "AIRFLOW_FERNET_KEY": fernet_key,
            "AIRFLOW_SECRET_KEY": secret_key,
            "GITLAB_REPO_URL": gitlab_repo_url,
            "GITLAB_TOKEN": gitlab_token,
            "ARGUS_SERVER_HOST": ctx.get("argus_server_host", "127.0.0.1"),
        }

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
            f"deployment/argus-airflow-{workspace_name}-db",
            namespace=namespace,
            timeout=120,
            kubeconfig=kubeconfig,
        )

        logger.info("Waiting for Airflow rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-airflow-{workspace_name}",
            namespace=namespace,
            timeout=600,
            kubeconfig=kubeconfig,
        )
        if not ready:
            logger.error("Airflow rollout timed out: argus-airflow-%s in %s", workspace_name, namespace)
            raise RuntimeError(
                f"Airflow rollout timed out: argus-airflow-{workspace_name} in {namespace}"
            )

        ctx.set("airflow_endpoint", hostname)
        ctx.set("airflow_admin_password", admin_password)
        ctx.set("airflow_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        # Register service
        internal_endpoint = f"http://argus-airflow-{workspace_name}.{namespace}.svc.cluster.local:8080"
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-airflow",
            display_name="Apache Airflow",
            version="1.0",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            username="admin",
            password=admin_password,
            metadata={
                "internal_endpoint": internal_endpoint,
                "namespace": namespace,
            },
        )

        return {
            "endpoint": hostname,
            "internal_endpoint": internal_endpoint,
            "admin_user": "admin",
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: AirflowConfig = ctx.get("airflow_config", AirflowConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get("airflow_endpoint", f"argus-airflow-teardown.argus-insight.{ctx.domain}")
        return render_manifests("airflow", {
            "AIRFLOW_IMAGE": config.image,
            "AIRFLOW_POSTGRES_IMAGE": config.postgres_image,
            "AIRFLOW_GIT_SYNC_IMAGE": config.git_sync_image,
            "AIRFLOW_GIT_SYNC_INTERVAL": str(config.git_sync_interval),
            "AIRFLOW_DAGS_SUB_PATH": config.dags_sub_path,
            "AIRFLOW_DAGS_STORAGE_SIZE": config.dags_storage_size,
            "AIRFLOW_LOGS_STORAGE_SIZE": config.logs_storage_size,
            "AIRFLOW_DB_STORAGE_SIZE": config.db_storage_size,
            "AIRFLOW_WEBSERVER_CPU_REQUEST": config.webserver_resources.cpu_request,
            "AIRFLOW_WEBSERVER_CPU_LIMIT": config.webserver_resources.cpu_limit,
            "AIRFLOW_WEBSERVER_MEMORY_REQUEST": config.webserver_resources.memory_request,
            "AIRFLOW_WEBSERVER_MEMORY_LIMIT": config.webserver_resources.memory_limit,
            "AIRFLOW_SCHEDULER_CPU_REQUEST": config.scheduler_resources.cpu_request,
            "AIRFLOW_SCHEDULER_CPU_LIMIT": config.scheduler_resources.cpu_limit,
            "AIRFLOW_SCHEDULER_MEMORY_REQUEST": config.scheduler_resources.memory_request,
            "AIRFLOW_SCHEDULER_MEMORY_LIMIT": config.scheduler_resources.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
            "AIRFLOW_ADMIN_PASSWORD": ctx.get("airflow_admin_password", ""),
            "AIRFLOW_DB_PASSWORD": "",
            "AIRFLOW_FERNET_KEY": "",
            "AIRFLOW_SECRET_KEY": "",
            "GITLAB_REPO_URL": ctx.get("gitlab_http_url", ""),
            "GITLAB_TOKEN": ctx.get("gitlab_token", ""),
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("airflow_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back Airflow K8s resources for workspace '%s'",
                ctx.workspace_name,
            )

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete all Airflow K8s resources and DNS record."""
        manifests = ctx.get("airflow_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("airflow_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for Airflow: %s", e)
        logger.info("Teardown Airflow for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
