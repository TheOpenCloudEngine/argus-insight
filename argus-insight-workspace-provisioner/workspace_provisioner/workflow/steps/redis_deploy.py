"""Workflow step: Deploy Redis to Kubernetes for a workspace."""

import logging
import socket

from workspace_provisioner.config import RedisConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply, kubectl_delete, kubectl_rollout_status, render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class RedisDeployStep(WorkflowStep):
    """Deploy Redis to Kubernetes (internal only, no ingress)."""

    @property
    def name(self) -> str:
        return "argus-redis"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: RedisConfig = ctx.get("argus_redis_config", RedisConfig())

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        variables = {
            "REDIS_IMAGE": config.image,
            "REDIS_CPU_REQUEST": config.cpu_request,
            "REDIS_CPU_LIMIT": config.cpu_limit,
            "REDIS_MEMORY_REQUEST": config.memory_request,
            "REDIS_MEMORY_LIMIT": config.memory_limit,
            "REDIS_STORAGE_SIZE": config.storage_size,
            "REDIS_MAXMEMORY": config.maxmemory,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("redis", variables)
        logger.info("Deploying Redis for workspace '%s'", workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"statefulset/argus-redis-{workspace_name}"
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Redis rollout timed out: {resource} in {namespace}")

        hostname = f"argus-redis-{workspace_name}.{namespace}.svc.cluster.local"
        internal_endpoint = f"redis://{hostname}:6379"

        ctx.set("redis_endpoint", internal_endpoint)
        ctx.set("redis_manifests", manifests)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-redis",
            display_name="Redis",
            version="7.4",
            endpoint=None,
            metadata={
                "display": {
                    "Hostname": hostname,
                    "Port": "6379",
                    "Storage": config.storage_size,
                    "Max Memory": config.maxmemory,
                },
                "internal": {
                    "endpoint": internal_endpoint,
                    "hostname": hostname,
                    "port": 6379,
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_request": config.cpu_request, "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request, "memory_limit": config.memory_limit,
                },
            },
        )
        return {"hostname": hostname, "port": 6379}

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: RedisConfig = ctx.get("argus_redis_config", RedisConfig())
        ns = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        return render_manifests("redis", {
            "REDIS_IMAGE": config.image,
            "REDIS_CPU_REQUEST": config.cpu_request, "REDIS_CPU_LIMIT": config.cpu_limit,
            "REDIS_MEMORY_REQUEST": config.memory_request, "REDIS_MEMORY_LIMIT": config.memory_limit,
            "REDIS_STORAGE_SIZE": config.storage_size, "REDIS_MAXMEMORY": config.maxmemory,
            "WORKSPACE_NAME": ctx.workspace_name, "K8S_NAMESPACE": ns,
            "DOMAIN": ctx.domain, "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("redis_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("redis_manifests") or self._render_manifests(ctx)
        await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        return {"k8s_deleted": True}
