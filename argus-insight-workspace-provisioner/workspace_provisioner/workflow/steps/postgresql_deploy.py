"""Workflow step: Deploy PostgreSQL + Adminer to Kubernetes for a workspace."""

import logging
import secrets
import string

from workspace_provisioner.config import PostgresqlConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _gen_password(length: int = 24) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))


class PostgresqlDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-postgresql"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: PostgresqlConfig = ctx.get("argus_postgresql_config", PostgresqlConfig())
        password = _gen_password()

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-postgresql-{svc_id}.argus-insight.{domain}"

        variables = {
            "PG_IMAGE": config.image,
            "PG_STORAGE_SIZE": config.storage_size,
            "PG_DB_NAME": config.db_name,
            "PG_DB_USER": config.db_user,
            "PG_PASSWORD": password,
            "PG_CPU_REQUEST": config.resources.cpu_request,
            "PG_CPU_LIMIT": config.resources.cpu_limit,
            "PG_MEMORY_REQUEST": config.resources.memory_request,
            "PG_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("postgresql", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="debian-12", namespace=namespace, instance_id=svc_id)

        logger.info("Deploying PostgreSQL for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        ready = await kubectl_rollout_status(
            f"statefulset/argus-postgresql-{workspace_name}",
            namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"PostgreSQL rollout timed out in {namespace}")

        ctx.set("postgresql_endpoint", f"argus-postgresql-{workspace_name}.{namespace}.svc.cluster.local:5432")
        ctx.set("postgresql_manifests", manifests)

        # Register DNS for Adminer Web UI
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-postgresql",
            display_name="PostgreSQL",
            version="17",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "DB Name": config.db_name,
                    "DB User": config.db_user,
                    "DB Password": password,
                    "PostgreSQL Address": f"argus-postgresql-{workspace_name}.{namespace}.svc.cluster.local:5432",
                    "Encoding": "UTF-8",
                    "Adminer": f"http://{hostname}",
                },
                "internal": {
                    "host": f"argus-postgresql-{workspace_name}.{namespace}.svc.cluster.local",
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_limit": config.resources.cpu_limit,
                    "memory_limit": config.resources.memory_limit,
                },
            },
        )

        return {"endpoint": hostname, "service_id": svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("postgresql_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("postgresql_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        return {"k8s_deleted": True}
