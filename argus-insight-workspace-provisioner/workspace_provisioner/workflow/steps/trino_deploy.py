"""Workflow step: Deploy Trino to Kubernetes for a workspace."""

import logging
import re

from workspace_provisioner.config import TrinoConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class TrinoDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-trino"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: TrinoConfig = ctx.get("argus_trino_config", TrinoConfig())

        def k8s_mem_to_java(mem: str) -> str:
            """Convert K8s memory (4Gi, 512Mi) to Java format (4G, 512M)."""
            m = re.match(r"^(\d+)(Gi|Mi|G|M)$", mem)
            if not m:
                return mem
            val, unit = m.group(1), m.group(2)
            return f"{val}{'G' if unit.startswith('G') else 'M'}"

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-trino-{svc_id}.argus-insight.{domain}"

        variables = {
            "TRINO_IMAGE": config.coordinator_image,
            "TRINO_WORKER_REPLICAS": str(config.worker_replicas),
            "TRINO_COORDINATOR_CPU_REQUEST": config.coordinator_resources.cpu_request,
            "TRINO_COORDINATOR_CPU_LIMIT": config.coordinator_resources.cpu_limit,
            "TRINO_COORDINATOR_MEMORY_REQUEST": config.coordinator_resources.memory_request,
            "TRINO_COORDINATOR_MEMORY_LIMIT": config.coordinator_resources.memory_limit,
            "TRINO_WORKER_CPU_REQUEST": config.worker_resources.cpu_request,
            "TRINO_WORKER_CPU_LIMIT": config.worker_resources.cpu_limit,
            "TRINO_WORKER_MEMORY_REQUEST": config.worker_resources.memory_request,
            "TRINO_WORKER_MEMORY_LIMIT": config.worker_resources.memory_limit,
            "TRINO_COORDINATOR_JVM_XMX": k8s_mem_to_java(config.coordinator_resources.memory_limit),
            "TRINO_WORKER_JVM_XMX": k8s_mem_to_java(config.worker_resources.memory_limit),
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("trino", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="rhel-10", namespace=namespace, instance_id=svc_id)

        logger.info("Deploying Trino for workspace '%s' to namespace '%s'", workspace_name, namespace)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for Trino coordinator rollout...")
        ready = await kubectl_rollout_status(
            f"deployment/argus-trino-{workspace_name}",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Trino coordinator rollout timed out in {namespace}")

        ctx.set("trino_endpoint", hostname)
        ctx.set("trino_manifests", manifests)

        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-trino",
            display_name="Trino Query Engine",
            version="latest",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "Workers": str(config.worker_replicas),
                },
                "internal": {
                    "endpoint": f"http://argus-trino-{workspace_name}.{namespace}.svc.cluster.local:8080",
                    "namespace": namespace,
                },
            },
        )

        return {"endpoint": hostname, "service_id": svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("trino_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("trino_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("trino_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint)
            except Exception as e:
                logger.warning("DNS deletion failed for Trino: %s", e)
        return {"k8s_deleted": True}
