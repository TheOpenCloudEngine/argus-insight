"""Workflow step: Deploy ChromaDB to Kubernetes for a workspace."""

import logging
import socket

from workspace_provisioner.config import ChromaDBConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class ChromaDBDeployStep(WorkflowStep):
    """Deploy ChromaDB vector database to Kubernetes (internal only, no ingress)."""

    @property
    def name(self) -> str:
        return "argus-chromadb"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: ChromaDBConfig = ctx.get("argus_chromadb_config", ChromaDBConfig())

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        variables = {
            "CHROMADB_IMAGE": config.image,
            "CHROMADB_CPU_REQUEST": config.cpu_request,
            "CHROMADB_CPU_LIMIT": config.cpu_limit,
            "CHROMADB_MEMORY_REQUEST": config.memory_request,
            "CHROMADB_MEMORY_LIMIT": config.memory_limit,
            "CHROMADB_STORAGE_SIZE": config.storage_size,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("chromadb", variables)
        logger.info("Deploying ChromaDB for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-chromadb-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"ChromaDB rollout timed out: {resource} in {namespace}")

        internal_endpoint = f"http://argus-chromadb-{workspace_name}.{namespace}.svc.cluster.local:8000"

        ctx.set("chromadb_endpoint", internal_endpoint)
        ctx.set("chromadb_manifests", manifests)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-chromadb",
            display_name="ChromaDB",
            version="0.5",
            endpoint=internal_endpoint,
            metadata={
                "display": {
                    "Image": config.image,
                    "Storage": config.storage_size,
                },
                "internal": {"endpoint": internal_endpoint, "namespace": namespace},
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"endpoint": internal_endpoint}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: ChromaDBConfig = ctx.get("argus_chromadb_config", ChromaDBConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        return render_manifests("chromadb", {
            "CHROMADB_IMAGE": config.image,
            "CHROMADB_CPU_REQUEST": config.cpu_request, "CHROMADB_CPU_LIMIT": config.cpu_limit,
            "CHROMADB_MEMORY_REQUEST": config.memory_request, "CHROMADB_MEMORY_LIMIT": config.memory_limit,
            "CHROMADB_STORAGE_SIZE": config.storage_size,
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("chromadb_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("chromadb_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        return {"k8s_deleted": True}
