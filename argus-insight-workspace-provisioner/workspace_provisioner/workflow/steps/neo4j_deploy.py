"""Workflow step: Deploy Neo4j Graph Database to Kubernetes for a workspace.

This step:
1. Deploys a Neo4j Community Edition instance as a StatefulSet.
2. Creates a persistent volume for graph data storage.
3. Exposes the Neo4j Browser UI via Ingress and Bolt protocol via ClusterIP.

Architecture:
    Neo4j (StatefulSet)
        ├── HTTP Browser (7474) → Ingress (external)
        ├── Bolt Protocol (7687) → ClusterIP (internal)
        └── PVC (/data)
"""

import logging
import secrets
import string

from workspace_provisioner.config import Neo4jConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Neo4jDeployStep(WorkflowStep):
    """Deploy Neo4j Graph Database to Kubernetes for a workspace.

    Reads from context:
        - workspace_name, domain, k8s_namespace, k8s_kubeconfig
        - argus_neo4j_config (optional Neo4jConfig)

    Writes to context:
        - neo4j_endpoint, neo4j_manifests
    """

    @property
    def name(self) -> str:
        return "argus-neo4j"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: Neo4jConfig = ctx.get("argus_neo4j_config", Neo4jConfig())
        password = _generate_password()

        # Generate unique service ID for hostname
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-neo4j-{svc_id}.argus-insight.{domain}"

        variables = {
            "NEO4J_IMAGE": config.image,
            "NEO4J_STORAGE_SIZE": config.storage_size,
            "NEO4J_CPU_REQUEST": config.resources.cpu_request,
            "NEO4J_CPU_LIMIT": config.resources.cpu_limit,
            "NEO4J_MEMORY_REQUEST": config.resources.memory_request,
            "NEO4J_MEMORY_LIMIT": config.resources.memory_limit,
            "NEO4J_PASSWORD": password,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("neo4j", variables)
        logger.info(
            "Deploying Neo4j for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for Neo4j rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-neo4j-{workspace_name}",
            namespace=namespace,
            timeout=300,
            kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"Neo4j rollout timed out: argus-neo4j-{workspace_name} in {namespace}"
            )

        ctx.set("neo4j_endpoint", hostname)
        ctx.set("neo4j_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        # Register service
        internal_bolt = f"bolt://argus-neo4j-{workspace_name}.{namespace}.svc.cluster.local:7687"
        internal_http = f"http://argus-neo4j-{workspace_name}.{namespace}.svc.cluster.local:7474"
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-neo4j",
            display_name="Neo4j Graph Database",
            version="1.0",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            username="neo4j",
            password=password,
            metadata={
                "internal_bolt": internal_bolt,
                "internal_http": internal_http,
                "bolt_port": 7687,
                "http_port": 7474,
                "namespace": namespace,
            },
        )

        return {
            "endpoint": hostname,
            "internal_bolt": internal_bolt,
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: Neo4jConfig = ctx.get("argus_neo4j_config", Neo4jConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        hostname = ctx.get("neo4j_endpoint", f"argus-neo4j-teardown.argus-insight.{ctx.domain}")
        return render_manifests("neo4j", {
            "NEO4J_IMAGE": config.image,
            "NEO4J_STORAGE_SIZE": config.storage_size,
            "NEO4J_CPU_REQUEST": config.resources.cpu_request,
            "NEO4J_CPU_LIMIT": config.resources.cpu_limit,
            "NEO4J_MEMORY_REQUEST": config.resources.memory_request,
            "NEO4J_MEMORY_LIMIT": config.resources.memory_limit,
            "NEO4J_PASSWORD": "",
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("neo4j_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back Neo4j for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete all Neo4j K8s resources and DNS record."""
        manifests = ctx.get("neo4j_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("neo4j_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for Neo4j: %s", e)
        logger.info("Teardown Neo4j for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
