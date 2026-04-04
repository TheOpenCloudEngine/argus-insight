"""Workflow step: Deploy Apache Kafka (KRaft mode) to Kubernetes for a workspace."""

import asyncio
import logging
import secrets
import string
import uuid

from workspace_provisioner.config import KafkaConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _generate_cluster_id() -> str:
    """Generate a KRaft cluster ID (22-char base64-like)."""
    return uuid.uuid4().hex[:22]


class KafkaDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-kafka"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        # Load config with tier support
        tier = ctx.get("argus_kafka_tier", "development")
        config: KafkaConfig = ctx.get("argus_kafka_config", KafkaConfig.from_tier(tier))

        cluster_id = _generate_cluster_id()

        # Build controller.quorum.voters string
        # Format: "node_id@host:9093,node_id@host:9093,..."
        voters = ",".join(
            f"{i}@argus-kafka-{workspace_name}-{i}.argus-kafka-{workspace_name}-headless.{namespace}.svc.cluster.local:9093"
            for i in range(config.replicas)
        )

        # Replication factor based on replicas
        repl_factor = min(config.replicas, 3)
        min_isr = max(1, repl_factor - 1) if config.replicas > 1 else 1

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()

        variables = {
            "KAFKA_IMAGE": config.image,
            "KAFKA_REPLICAS": str(config.replicas),
            "KAFKA_PROCESS_ROLES": config.process_roles,
            "KAFKA_CLUSTER_ID": cluster_id,
            "KAFKA_CONTROLLER_QUORUM_VOTERS": voters,
            "KAFKA_REPLICATION_FACTOR": str(repl_factor),
            "KAFKA_MIN_ISR": str(min_isr),
            "KAFKA_STORAGE_SIZE": config.storage_size,
            "KAFKA_CPU_REQUEST": config.resources.cpu_request,
            "KAFKA_CPU_LIMIT": config.resources.cpu_limit,
            "KAFKA_MEMORY_REQUEST": config.resources.memory_request,
            "KAFKA_MEMORY_LIMIT": config.resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
        }

        manifests = render_manifests("kafka", variables)
        logger.info("Deploying Kafka (%s tier, %d nodes) for workspace '%s'",
                     config.tier, config.replicas, workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for rollout
        logger.info("Waiting for Kafka rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-kafka-{workspace_name}",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Kafka rollout timed out in {namespace}")

        ctx.set("kafka_endpoint", f"argus-kafka-{workspace_name}.{namespace}.svc.cluster.local:9092")
        ctx.set("kafka_manifests", manifests)

        # Build bootstrap servers string
        bootstrap = ",".join(
            f"argus-kafka-{workspace_name}-{i}.argus-kafka-{workspace_name}-headless.{namespace}.svc.cluster.local:9092"
            for i in range(config.replicas)
        )

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-kafka",
            display_name="Apache Kafka",
            version="3.9",
            endpoint=f"kafka://argus-kafka-{workspace_name}.{namespace}.svc.cluster.local:9092",
            service_id=svc_id,
            metadata={
                "display": {
                    "Tier": config.tier.capitalize(),
                    "Brokers": str(config.replicas),
                    "Bootstrap Servers": bootstrap,
                    "Cluster ID": cluster_id,
                },
                "internal": {
                    "endpoint": f"argus-kafka-{workspace_name}.{namespace}.svc.cluster.local:9092",
                    "bootstrap_servers": bootstrap,
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_limit": config.resources.cpu_limit,
                    "memory_limit": config.resources.memory_limit,
                },
            },
        )

        logger.info("Kafka deployed: %d nodes, cluster_id=%s", config.replicas, cluster_id)
        return {"service_id": svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("kafka_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("kafka_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        return {"k8s_deleted": True}
