"""Workflow step: Deploy Apache NiFi + NiFi Registry to Kubernetes.

NiFi 2.x uses K8s Lease for leader election (no ZooKeeper).
Registry is co-deployed for flow versioning and NAR management.
Ingress uses sticky session to prevent flow corruption in cluster mode.
"""

import asyncio
import logging
import re

from workspace_provisioner.config import NiFiConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class NiFiDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-nifi"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        # Load config with tier support
        tier = ctx.get("argus_nifi_tier", "development")
        config: NiFiConfig = ctx.get("argus_nifi_config", NiFiConfig.from_tier(tier))

        cluster_is_node = "true" if config.replicas > 1 else "false"

        # JVM heap = 80% of memory limit
        def mem_to_jvm(mem: str) -> str:
            m = re.match(r"^(\d+)(Gi|Mi)$", mem)
            if not m:
                return "1536m"
            val, unit = int(m.group(1)), m.group(2)
            if unit == "Gi":
                return f"{int(val * 1024 * 0.8)}m"
            return f"{int(val * 0.8)}m"

        from workspace_provisioner.service import generate_service_id
        nifi_svc_id = generate_service_id()
        registry_svc_id = generate_service_id()
        nifi_hostname = f"argus-nifi-{nifi_svc_id}.argus-insight.{domain}"
        registry_hostname = f"argus-nifi-registry-{registry_svc_id}.argus-insight.{domain}"

        variables = {
            "NIFI_IMAGE": config.nifi_image,
            "NIFI_REGISTRY_IMAGE": config.registry_image,
            "NIFI_REPLICAS": str(config.replicas),
            "NIFI_CLUSTER_IS_NODE": cluster_is_node,
            "NIFI_HOSTNAME": nifi_hostname,
            "REGISTRY_HOSTNAME": registry_hostname,
            "NIFI_CPU_REQUEST": config.resources.cpu_request,
            "NIFI_CPU_LIMIT": config.resources.cpu_limit,
            "NIFI_MEMORY_REQUEST": config.resources.memory_request,
            "NIFI_MEMORY_LIMIT": config.resources.memory_limit,
            "NIFI_JVM_XMS": "512m",
            "NIFI_JVM_XMX": mem_to_jvm(config.resources.memory_limit),
            "NIFI_CONTENT_STORAGE": config.content_storage,
            "NIFI_PROVENANCE_STORAGE": config.provenance_storage,
            "NIFI_FLOWFILE_STORAGE": config.flowfile_storage,
            "REGISTRY_CPU_REQUEST": config.registry_resources.cpu_request,
            "REGISTRY_CPU_LIMIT": config.registry_resources.cpu_limit,
            "REGISTRY_MEMORY_REQUEST": config.registry_resources.memory_request,
            "REGISTRY_MEMORY_LIMIT": config.registry_resources.memory_limit,
            "REGISTRY_DB_STORAGE": config.registry_db_storage,
            "REGISTRY_FLOW_STORAGE": config.registry_flow_storage,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
        }

        manifests = render_manifests("nifi", variables)

        logger.info("Deploying NiFi (%s tier, %d nodes) + Registry for workspace '%s'",
                     config.tier, config.replicas, workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for Registry first (NiFi depends on it for client registration)
        logger.info("Waiting for NiFi Registry rollout...")
        ready = await kubectl_rollout_status(
            f"deployment/argus-nifi-registry-{workspace_name}",
            namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"NiFi Registry rollout timed out in {namespace}")

        # Wait for NiFi
        logger.info("Waiting for NiFi rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-nifi-{workspace_name}",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"NiFi rollout timed out in {namespace}")

        # Register DNS for both NiFi and Registry
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(nifi_hostname)
        await register_workspace_dns(registry_hostname)

        # Auto-register NiFi Registry Client via NiFi REST API
        registry_internal = f"http://argus-nifi-registry-{workspace_name}.{namespace}.svc.cluster.local:18080"
        nifi_api = f"http://argus-nifi-{workspace_name}.{namespace}.svc.cluster.local:8080/nifi-api"

        # Wait a bit for NiFi API to be fully ready
        await asyncio.sleep(10)
        try:
            import json as json_mod
            import urllib.request
            payload = json_mod.dumps({
                "revision": {"version": 0},
                "component": {
                    "name": "Workspace Registry",
                    "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
                    "properties": {
                        "url": f"{registry_internal}/nifi-registry",
                    },
                },
            }).encode()
            req = urllib.request.Request(
                f"{nifi_api}/controller/registry-clients",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info("NiFi Registry Client registered: %s", registry_internal)
        except Exception as e:
            logger.warning("Failed to auto-register NiFi Registry Client (can be done manually): %s", e)

        ctx.set("nifi_endpoint", nifi_hostname)
        ctx.set("nifi_manifests", manifests)

        # Register workspace service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-nifi",
            display_name="Apache NiFi",
            version="2.4.0",
            endpoint=f"http://{nifi_hostname}/nifi",
            service_id=nifi_svc_id,
            metadata={
                "display": {
                    "Tier": config.tier.capitalize(),
                    "Nodes": str(config.replicas),
                    "Cluster Mode": "Kubernetes Lease" if config.replicas > 1 else "Standalone",
                    "Session": "Sticky (cookie-based)",
                    "NiFi (Internal)": f"http://argus-nifi-{workspace_name}.{namespace}.svc.cluster.local:8080/nifi",
                    "NiFi Registry": f"http://{registry_hostname}/nifi-registry",
                    "NiFi Registry (Internal)": registry_internal,
                    "Storage": f"Content {config.content_storage}, Provenance {config.provenance_storage}, FlowFile {config.flowfile_storage}",
                },
                "internal": {
                    "endpoint": f"http://argus-nifi-{workspace_name}.{namespace}.svc.cluster.local:8080",
                    "registry_endpoint": registry_internal,
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_limit": config.resources.cpu_limit,
                    "memory_limit": config.resources.memory_limit,
                },
            },
        )

        logger.info("NiFi deployed: %s (tier=%s, nodes=%d, registry=%s)",
                     nifi_hostname, config.tier, config.replicas, registry_hostname)
        return {"endpoint": nifi_hostname, "service_id": nifi_svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("nifi_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("nifi_manifests")
        if manifests:
            await kubectl_delete(manifests, kubeconfig=ctx.get("k8s_kubeconfig"))
        endpoint = ctx.get("nifi_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint)
            except Exception as e:
                logger.warning("DNS deletion failed for NiFi: %s", e)
        return {"k8s_deleted": True}
