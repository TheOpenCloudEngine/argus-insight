"""Workflow step: Deploy MariaDB to Kubernetes for a workspace."""

import logging
import secrets
import string

from workspace_provisioner.config import MariadbConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _gen_password(length: int = 24) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))


class MariadbDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-mariadb"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: MariadbConfig = ctx.get("argus_mariadb_config", MariadbConfig())
        root_password = _gen_password()
        user_password = _gen_password()

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()

        variables = {
            "MARIA_IMAGE": config.image,
            "MARIA_STORAGE_SIZE": config.storage_size,
            "MARIA_DB_NAME": config.db_name,
            "MARIA_DB_USER": config.db_user,
            "MARIA_ROOT_PASSWORD": root_password,
            "MARIA_DB_PASSWORD": user_password,
            "MARIA_CPU_REQUEST": config.resources.cpu_request,
            "MARIA_CPU_LIMIT": config.resources.cpu_limit,
            "MARIA_MEMORY_REQUEST": config.resources.memory_request,
            "MARIA_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
        }

        manifests = render_manifests("mariadb", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="ubuntu-24.04", namespace=namespace, instance_id=svc_id)

        logger.info("Deploying MariaDB for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        ready = await kubectl_rollout_status(
            f"statefulset/argus-mariadb-{workspace_name}",
            namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"MariaDB rollout timed out in {namespace}")

        ctx.set("mariadb_endpoint", f"argus-mariadb-{workspace_name}.{namespace}.svc.cluster.local:3306")
        ctx.set("mariadb_manifests", manifests)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-mariadb",
            display_name="MariaDB",
            version="1.0",
            endpoint=f"mysql://{config.db_user}@argus-mariadb-{workspace_name}.{namespace}.svc.cluster.local:3306/{config.db_name}",
            service_id=svc_id,
            username=config.db_user,
            password=user_password,
            metadata={
                "display": {
                    "Database": config.db_name,
                    "Port": "3306",
                },
                "internal": {
                    "host": f"argus-mariadb-{workspace_name}.{namespace}.svc.cluster.local",
                    "root_password": root_password,
                    "namespace": namespace,
                },
            },
        )

        return {"endpoint": f"argus-mariadb-{workspace_name}", "service_id": svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("mariadb_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("mariadb_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        return {"k8s_deleted": True}
