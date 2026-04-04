"""Workflow step: Deploy Feast Feature Store to Kubernetes for a workspace."""

import logging
import socket

from workspace_provisioner.config import FeastConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class FeastDeployStep(WorkflowStep):
    """Deploy Feast Feature Server."""

    @property
    def name(self) -> str:
        return "argus-feast"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: FeastConfig = ctx.get("argus_feast_config", FeastConfig())

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        hostname = f"argus-feast-{workspace_name}.argus-insight.{domain}"
        variables = {
            "FEAST_IMAGE": config.image,
            "FEAST_CPU_REQUEST": config.cpu_request,
            "FEAST_CPU_LIMIT": config.cpu_limit,
            "FEAST_MEMORY_REQUEST": config.memory_request,
            "FEAST_MEMORY_LIMIT": config.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("feast", variables)
        logger.info("Deploying Feast for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-feast-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=120, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Feast rollout timed out: {resource} in {namespace}")

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-feast-{workspace_name}.{namespace}.svc.cluster.local:6566"

        ctx.set("feast_endpoint", external_endpoint)
        ctx.set("feast_manifests", manifests)

        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-feast",
            display_name="Feast Feature Store",
            version="0.40",
            endpoint=external_endpoint,
            metadata={
                "display": {"Image": config.image},
                "internal": {"endpoint": internal_endpoint, "namespace": namespace},
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"endpoint": external_endpoint}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: FeastConfig = ctx.get("argus_feast_config", FeastConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get("feast_endpoint", f"argus-feast-teardown.argus-insight.{ctx.domain}").replace("http://", "")
        return render_manifests("feast", {
            "FEAST_IMAGE": config.image, "FEAST_CPU_REQUEST": config.cpu_request,
            "FEAST_CPU_LIMIT": config.cpu_limit, "FEAST_MEMORY_REQUEST": config.memory_request,
            "FEAST_MEMORY_LIMIT": config.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "HOSTNAME": hostname, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("feast_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("feast_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        endpoint = ctx.get("feast_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for Feast: %s", e)
        return {"k8s_deleted": True}
