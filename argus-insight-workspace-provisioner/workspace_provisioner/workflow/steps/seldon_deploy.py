"""Workflow step: Deploy Seldon Core to Kubernetes for a workspace."""

import logging
import socket

from workspace_provisioner.config import SeldonCoreConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class SeldonCoreDeployStep(WorkflowStep):
    """Deploy Seldon Core operator for advanced model serving."""

    @property
    def name(self) -> str:
        return "argus-seldon"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: SeldonCoreConfig = ctx.get("argus_seldon_config", SeldonCoreConfig())

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        variables = {
            "SELDON_IMAGE": config.image,
            "SELDON_CPU_REQUEST": config.cpu_request,
            "SELDON_CPU_LIMIT": config.cpu_limit,
            "SELDON_MEMORY_REQUEST": config.memory_request,
            "SELDON_MEMORY_LIMIT": config.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("seldon", variables)
        logger.info("Deploying Seldon Core for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-seldon-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Seldon Core rollout timed out: {resource} in {namespace}")

        internal_endpoint = f"http://argus-seldon-{workspace_name}.{namespace}.svc.cluster.local:8080"

        ctx.set("seldon_endpoint", internal_endpoint)
        ctx.set("seldon_manifests", manifests)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-seldon",
            display_name="Seldon Core",
            version="1.18",
            endpoint=internal_endpoint,
            metadata={
                "display": {"Image": config.image, "Mode": "Single-namespace operator"},
                "internal": {"endpoint": internal_endpoint, "namespace": namespace},
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"endpoint": internal_endpoint}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: SeldonCoreConfig = ctx.get("argus_seldon_config", SeldonCoreConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        return render_manifests("seldon", {
            "SELDON_IMAGE": config.image, "SELDON_CPU_REQUEST": config.cpu_request,
            "SELDON_CPU_LIMIT": config.cpu_limit, "SELDON_MEMORY_REQUEST": config.memory_request,
            "SELDON_MEMORY_LIMIT": config.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("seldon_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("seldon_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        logger.info("Teardown Seldon Core for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
