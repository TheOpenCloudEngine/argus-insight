"""Workflow step: Deploy Milvus Vector Database to Kubernetes for a workspace.

This step:
1. Deploys Milvus Standalone (embedded etcd + local storage) as a StatefulSet.
2. Deploys Attu Web UI as a sidecar for collection management.
3. Exposes gRPC (19530) for PyMilvus/LangChain and HTTP (3000) for Attu UI.

Architecture:
    Milvus Standalone (StatefulSet)
        ├── gRPC API (19530)    → ClusterIP (internal, for PyMilvus/LangChain)
        ├── Attu Web UI (3000)  → Ingress (external)
        └── PVC (/var/lib/milvus)
"""

import logging

from workspace_provisioner.config import MilvusConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class MilvusDeployStep(WorkflowStep):
    """Deploy Milvus Vector Database to Kubernetes.

    Reads from context:
        - workspace_name, domain, k8s_namespace, k8s_kubeconfig
        - argus_milvus_config (optional MilvusConfig)

    Writes to context:
        - milvus_endpoint, milvus_manifests
    """

    @property
    def name(self) -> str:
        return "argus-milvus"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: MilvusConfig = ctx.get("argus_milvus_config", MilvusConfig())

        # Generate unique service ID for hostname
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-milvus-{svc_id}.argus-insight.{domain}"

        variables = {
            "MILVUS_IMAGE": config.image,
            "ATTU_IMAGE": config.attu_image,
            "MILVUS_STORAGE_SIZE": config.storage_size,
            "MILVUS_CPU_REQUEST": config.resources.cpu_request,
            "MILVUS_CPU_LIMIT": config.resources.cpu_limit,
            "MILVUS_MEMORY_REQUEST": config.resources.memory_request,
            "MILVUS_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("milvus", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="ubuntu-22.04", namespace=namespace, instance_id=svc_id)
        logger.info(
            "Deploying Milvus for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for Milvus rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-milvus-{workspace_name}",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"Milvus rollout timed out: argus-milvus-{workspace_name} in {namespace}"
            )

        ctx.set("milvus_endpoint", hostname)
        ctx.set("milvus_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        # Register service
        svc_base = f"argus-milvus-{workspace_name}.{namespace}.svc.cluster.local"
        internal_grpc = f"{svc_base}:19530"
        internal_attu = f"http://{svc_base}:3000"

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-milvus",
            display_name="Milvus Vector Database",
            version="1.0",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "gRPC Port": "19530",
                },
                "internal": {
                    "grpc": internal_grpc,
                    "attu": internal_attu,
                    "grpc_port": 19530,
                    "attu_port": 3000,
                    "namespace": namespace,
                },
            },
        )

        return {
            "endpoint": hostname,
            "internal_grpc": internal_grpc,
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: MilvusConfig = ctx.get("argus_milvus_config", MilvusConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get(
            "milvus_endpoint",
            f"argus-milvus-teardown.argus-insight.{ctx.domain}",
        )
        return render_manifests("milvus", {
            "MILVUS_IMAGE": config.image,
            "ATTU_IMAGE": config.attu_image,
            "MILVUS_STORAGE_SIZE": config.storage_size,
            "MILVUS_CPU_REQUEST": config.resources.cpu_request,
            "MILVUS_CPU_LIMIT": config.resources.cpu_limit,
            "MILVUS_MEMORY_REQUEST": config.resources.memory_request,
            "MILVUS_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("milvus_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back Milvus for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete all Milvus K8s resources and DNS record."""
        manifests = ctx.get("milvus_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("milvus_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(
                    endpoint.replace("http://", "").replace("https://", "")
                )
            except Exception as e:
                logger.warning("DNS deletion failed for Milvus: %s", e)
        logger.info("Teardown Milvus for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
