"""Workflow step: Deploy Trino to Kubernetes for a workspace.

Automatically detects existing DB services (PostgreSQL, MariaDB, StarRocks)
in the same workspace and creates Trino catalog configurations for them.
Supports tier-based deployment: development, standard, performance.
"""

import json
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

# Mapping: workspace plugin_name → Trino catalog config
_CATALOG_MAP = {
    "argus-postgresql": {
        "connector": "postgresql",
        "port": 5432,
        "url_template": "jdbc:postgresql://{host}:{port}/{db}",
    },
    "argus-mariadb": {
        "connector": "mysql",
        "port": 3306,
        "url_template": "jdbc:mysql://{host}:{port}",
    },
    "argus-starrocks": {
        "connector": "mysql",
        "port": 9030,
        "url_template": "jdbc:mysql://{host}:{port}",
    },
}


async def _build_catalog_configmap(workspace_id: int, workspace_name: str, namespace: str) -> str:
    """Build a K8s ConfigMap YAML with Trino catalog properties.

    Scans existing DB services in the workspace and generates
    JDBC connector configurations for each.
    """
    from app.core.database import async_session
    from sqlalchemy import text

    catalogs: dict[str, str] = {}

    async with async_session() as session:
        rows = await session.execute(
            text("""
                SELECT plugin_name, metadata
                FROM argus_workspace_services
                WHERE workspace_id = :ws_id AND status = 'running'
                  AND plugin_name IN :plugins
            """),
            {"ws_id": workspace_id, "plugins": tuple(_CATALOG_MAP.keys())},
        )

        for plugin_name, meta_raw in rows.fetchall():
            cfg = _CATALOG_MAP.get(plugin_name)
            if not cfg:
                continue

            meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw) if isinstance(meta_raw, str) else {}
            display = meta.get("display", {})
            internal = meta.get("internal", {})

            host = internal.get("host", "")
            db_name = display.get("DB Name", "")
            db_user = display.get("DB User", "")
            db_pass = display.get("DB Password", "")

            if not host:
                logger.warning("Skipping catalog for %s: no internal host", plugin_name)
                continue

            catalog_name = plugin_name.replace("argus-", "")  # "postgresql", "mariadb"
            url = cfg["url_template"].format(host=host, port=cfg["port"], db=db_name)

            props = [
                f"connector.name={cfg['connector']}",
                f"connection-url={url}",
                f"connection-user={db_user}",
                f"connection-password={db_pass}",
            ]
            catalogs[catalog_name] = "\n".join(props)
            logger.info("Trino catalog '%s' → %s@%s:%d", catalog_name, db_user, host, cfg["port"])

    # Always add memory catalog for testing
    catalogs["memory"] = "connector.name=memory"

    # Build ConfigMap YAML
    data_entries = ""
    for name, content in catalogs.items():
        # Indent content for YAML
        indented = "\n".join(f"    {line}" for line in content.split("\n"))
        data_entries += f"  {name}.properties: |\n{indented}\n"

    return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: argus-trino-{workspace_name}-catalogs
  namespace: {namespace}
  labels:
    app.kubernetes.io/name: trino
    app.kubernetes.io/instance: {workspace_name}
    app.kubernetes.io/part-of: argus-insight
data:
{data_entries}"""


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

        # Load config — supports tier-based presets
        tier = ctx.get("argus_trino_tier", "development")
        config: TrinoConfig = ctx.get("argus_trino_config", TrinoConfig.from_tier(tier))

        # Development tier: coordinator also acts as worker (single-node)
        include_coordinator = "true" if config.worker_replicas == 0 else "false"

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
            "TRINO_INCLUDE_COORDINATOR": include_coordinator,
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

        # 1. Build catalog ConfigMap from existing DB services
        logger.info("Building Trino catalogs for workspace '%s'...", workspace_name)
        catalog_cm_yaml = await _build_catalog_configmap(ctx.workspace_id, workspace_name, namespace)
        logger.debug("Catalog ConfigMap:\n%s", catalog_cm_yaml)

        # Apply catalog ConfigMap first (kubectl_apply accepts raw YAML string)
        await kubectl_apply(catalog_cm_yaml, kubeconfig=kubeconfig)

        # 2. Render and apply Trino manifests (config + deployment + service)
        manifests = render_manifests("trino", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="rhel-10", namespace=namespace, instance_id=svc_id)

        logger.info("Deploying Trino (%s tier, %d workers) for workspace '%s'",
                     config.tier, config.worker_replicas, workspace_name)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # 3. Wait for coordinator readiness
        logger.info("Waiting for Trino coordinator rollout...")
        ready = await kubectl_rollout_status(
            f"deployment/argus-trino-{workspace_name}",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"Trino coordinator rollout timed out in {namespace}")

        ctx.set("trino_endpoint", hostname)
        ctx.set("trino_manifests", manifests)
        ctx.set("trino_catalog_cm", catalog_cm_yaml)

        # 4. Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        # 5. Register workspace service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-trino",
            display_name="Trino Query Engine",
            version="480",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "Tier": config.tier.capitalize(),
                    "Workers": str(config.worker_replicas),
                    "Trino UI": f"http://{hostname}",
                },
                "internal": {
                    "endpoint": f"http://argus-trino-{workspace_name}.{namespace}.svc.cluster.local:8080",
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_request": config.coordinator_resources.cpu_request,
                    "cpu_limit": config.coordinator_resources.cpu_limit,
                    "memory_request": config.coordinator_resources.memory_request,
                    "memory_limit": config.coordinator_resources.memory_limit,
                    "worker_cpu_limit": config.worker_resources.cpu_limit,
                    "worker_memory_limit": config.worker_resources.memory_limit,
                },
            },
        )

        logger.info("Trino deployed: %s (tier=%s, workers=%d)", hostname, config.tier, config.worker_replicas)
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
