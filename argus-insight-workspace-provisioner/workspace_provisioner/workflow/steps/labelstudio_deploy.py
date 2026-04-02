"""Workflow step: Deploy Label Studio to Kubernetes for a workspace."""

import logging
import secrets
import socket

from workspace_provisioner.config import LabelStudioConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class LabelStudioDeployStep(WorkflowStep):
    """Deploy Label Studio for data labeling."""

    @property
    def name(self) -> str:
        return "argus-labelstudio"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")
        username = ctx.get("creator_username", "admin")

        await ensure_namespace(namespace)

        config: LabelStudioConfig = ctx.get("argus_labelstudio_config", LabelStudioConfig())
        admin_password = secrets.token_urlsafe(12)

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        hostname = f"argus-labelstudio-{workspace_name}.argus-insight.{domain}"
        variables = {
            "LABELSTUDIO_IMAGE": config.image,
            "LABELSTUDIO_CPU_REQUEST": config.cpu_request,
            "LABELSTUDIO_CPU_LIMIT": config.cpu_limit,
            "LABELSTUDIO_MEMORY_REQUEST": config.memory_request,
            "LABELSTUDIO_MEMORY_LIMIT": config.memory_limit,
            "LABELSTUDIO_STORAGE_SIZE": config.storage_size,
            "ADMIN_USERNAME": f"{username}@argus.local",
            "ADMIN_PASSWORD": admin_password,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("labelstudio", variables)
        logger.info("Deploying Label Studio for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-labelstudio-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Label Studio rollout timed out: {resource} in {namespace}")

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-labelstudio-{workspace_name}.{namespace}.svc.cluster.local:8080"

        ctx.set("labelstudio_endpoint", external_endpoint)
        ctx.set("labelstudio_manifests", manifests)

        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-labelstudio",
            display_name="Label Studio",
            version="1.14",
            endpoint=external_endpoint,
            username=f"{username}@argus.local",
            password=admin_password,
            metadata={
                "display": {"Image": config.image, "Storage": config.storage_size},
                "internal": {"endpoint": internal_endpoint, "namespace": namespace},
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"endpoint": external_endpoint}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: LabelStudioConfig = ctx.get("argus_labelstudio_config", LabelStudioConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get("labelstudio_endpoint", f"argus-labelstudio-teardown.argus-insight.{ctx.domain}").replace("http://", "")
        return render_manifests("labelstudio", {
            "LABELSTUDIO_IMAGE": config.image, "LABELSTUDIO_CPU_REQUEST": config.cpu_request,
            "LABELSTUDIO_CPU_LIMIT": config.cpu_limit, "LABELSTUDIO_MEMORY_REQUEST": config.memory_request,
            "LABELSTUDIO_MEMORY_LIMIT": config.memory_limit, "LABELSTUDIO_STORAGE_SIZE": config.storage_size,
            "ADMIN_USERNAME": "admin@argus.local", "ADMIN_PASSWORD": "",
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "HOSTNAME": hostname, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("labelstudio_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("labelstudio_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        endpoint = ctx.get("labelstudio_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for Label Studio: %s", e)
        return {"k8s_deleted": True}
