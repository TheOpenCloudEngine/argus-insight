"""Workflow step: Deploy H2O AutoML to Kubernetes for a workspace."""

import logging
import socket

from workspace_provisioner.config import H2OAutoMLConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class H2OAutoMLDeployStep(WorkflowStep):
    """Deploy H2O AutoML (Flow WebUI) to Kubernetes."""

    @property
    def name(self) -> str:
        return "argus-h2o"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: H2OAutoMLConfig = ctx.get("argus_h2o_config", H2OAutoMLConfig())

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        hostname = f"argus-h2o-{workspace_name}.argus-insight.{domain}"
        variables = {
            "H2O_IMAGE": config.image,
            "H2O_CPU_REQUEST": config.cpu_request,
            "H2O_CPU_LIMIT": config.cpu_limit,
            "H2O_MEMORY_REQUEST": config.memory_request,
            "H2O_MEMORY_LIMIT": config.memory_limit,
            "H2O_JAVA_MAX_HEAP": config.java_max_heap,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("h2o", variables)
        logger.info("Deploying H2O AutoML for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-h2o-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"H2O rollout timed out: {resource} in {namespace}")

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-h2o-{workspace_name}.{namespace}.svc.cluster.local:54321"

        ctx.set("h2o_endpoint", external_endpoint)
        ctx.set("h2o_manifests", manifests)

        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-h2o",
            display_name="H2O AutoML",
            version="3.46",
            endpoint=external_endpoint,
            metadata={
                "display": {"Image": config.image, "JVM Heap": config.java_max_heap},
                "internal": {"endpoint": internal_endpoint, "namespace": namespace},
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"endpoint": external_endpoint}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: H2OAutoMLConfig = ctx.get("argus_h2o_config", H2OAutoMLConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get("h2o_endpoint", f"argus-h2o-teardown.argus-insight.{ctx.domain}").replace("http://", "")
        return render_manifests("h2o", {
            "H2O_IMAGE": config.image, "H2O_CPU_REQUEST": config.cpu_request,
            "H2O_CPU_LIMIT": config.cpu_limit, "H2O_MEMORY_REQUEST": config.memory_request,
            "H2O_MEMORY_LIMIT": config.memory_limit, "H2O_JAVA_MAX_HEAP": config.java_max_heap,
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "HOSTNAME": hostname, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("h2o_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("h2o_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        endpoint = ctx.get("h2o_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for H2O: %s", e)
        return {"k8s_deleted": True}
