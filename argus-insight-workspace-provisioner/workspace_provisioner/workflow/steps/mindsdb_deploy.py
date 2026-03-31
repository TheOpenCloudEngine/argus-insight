"""Workflow step: Deploy MindsDB to Kubernetes for a workspace.

This step:
1. Deploys MindsDB as a Deployment with persistent storage.
2. Exposes HTTP API/Web UI (47334), MySQL (47335), MongoDB (47336) protocols.
3. The Web UI provides a SQL editor for creating models and querying predictions.

Architecture:
    MindsDB (Deployment)
        ├── HTTP API + Web UI (47334) → Ingress (external)
        ├── MySQL Protocol (47335)    → ClusterIP (internal)
        ├── MongoDB Protocol (47336)  → ClusterIP (internal)
        └── PVC (/root/mindsdb)
"""

import logging

from workspace_provisioner.config import MindsdbConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class MindsdbDeployStep(WorkflowStep):
    """Deploy MindsDB AI-in-Database platform to Kubernetes.

    Reads from context:
        - workspace_name, domain, k8s_namespace, k8s_kubeconfig
        - argus_mindsdb_config (optional MindsdbConfig)

    Writes to context:
        - mindsdb_endpoint, mindsdb_manifests
    """

    @property
    def name(self) -> str:
        return "argus-mindsdb"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: MindsdbConfig = ctx.get("argus_mindsdb_config", MindsdbConfig())

        # Generate unique service ID for hostname
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-mindsdb-{svc_id}.argus-insight.{domain}"

        variables = {
            "MINDSDB_IMAGE": config.image,
            "MINDSDB_STORAGE_SIZE": config.storage_size,
            "MINDSDB_CPU_REQUEST": config.resources.cpu_request,
            "MINDSDB_CPU_LIMIT": config.resources.cpu_limit,
            "MINDSDB_MEMORY_REQUEST": config.resources.memory_request,
            "MINDSDB_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("mindsdb", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="debian-13", namespace=namespace, instance_id=svc_id)
        logger.info(
            "Deploying MindsDB for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for MindsDB rollout...")
        ready = await kubectl_rollout_status(
            f"deployment/argus-mindsdb-{workspace_name}",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"MindsDB rollout timed out: argus-mindsdb-{workspace_name} in {namespace}"
            )

        ctx.set("mindsdb_endpoint", hostname)
        ctx.set("mindsdb_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        # Register service
        svc_base = f"argus-mindsdb-{workspace_name}.{namespace}.svc.cluster.local"
        internal_http = f"http://{svc_base}:47334"
        internal_mysql = f"{svc_base}:47335"
        internal_mongodb = f"{svc_base}:47336"

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-mindsdb",
            display_name="MindsDB",
            version="1.0",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "MySQL Port": "47335",
                    "MongoDB Port": "47336",
                },
                "internal": {
                    "http": internal_http,
                    "mysql": internal_mysql,
                    "mongodb": internal_mongodb,
                    "http_port": 47334,
                    "mysql_port": 47335,
                    "mongodb_port": 47336,
                    "namespace": namespace,
                },
            },
        )

        return {
            "endpoint": hostname,
            "internal_http": internal_http,
            "internal_mysql": internal_mysql,
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: MindsdbConfig = ctx.get("argus_mindsdb_config", MindsdbConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get(
            "mindsdb_endpoint",
            f"argus-mindsdb-teardown.argus-insight.{ctx.domain}",
        )
        return render_manifests("mindsdb", {
            "MINDSDB_IMAGE": config.image,
            "MINDSDB_STORAGE_SIZE": config.storage_size,
            "MINDSDB_CPU_REQUEST": config.resources.cpu_request,
            "MINDSDB_CPU_LIMIT": config.resources.cpu_limit,
            "MINDSDB_MEMORY_REQUEST": config.resources.memory_request,
            "MINDSDB_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("mindsdb_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back MindsDB for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete all MindsDB K8s resources and DNS record."""
        manifests = ctx.get("mindsdb_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("mindsdb_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(
                    endpoint.replace("http://", "").replace("https://", "")
                )
            except Exception as e:
                logger.warning("DNS deletion failed for MindsDB: %s", e)
        logger.info("Teardown MindsDB for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
