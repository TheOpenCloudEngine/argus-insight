"""Workflow step: Deploy StarRocks to Kubernetes for a workspace."""

import logging

from workspace_provisioner.config import StarRocksConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class StarRocksDeployStep(WorkflowStep):

    @property
    def name(self) -> str:
        return "argus-starrocks"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")

        await ensure_namespace(namespace)

        config: StarRocksConfig = ctx.get("argus_starrocks_config", StarRocksConfig())

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()
        hostname = f"argus-starrocks-{svc_id}.argus-insight.{domain}"

        variables = {
            "STARROCKS_FE_IMAGE": config.fe_image,
            "STARROCKS_BE_IMAGE": config.be_image,
            "STARROCKS_BE_REPLICAS": str(config.be_replicas),
            "STARROCKS_FE_STORAGE_SIZE": config.fe_storage_size,
            "STARROCKS_BE_STORAGE_SIZE": config.be_storage_size,
            "STARROCKS_FE_CPU_REQUEST": config.fe_resources.cpu_request,
            "STARROCKS_FE_CPU_LIMIT": config.fe_resources.cpu_limit,
            "STARROCKS_FE_MEMORY_REQUEST": config.fe_resources.memory_request,
            "STARROCKS_FE_MEMORY_LIMIT": config.fe_resources.memory_limit,
            "STARROCKS_BE_CPU_REQUEST": config.be_resources.cpu_request,
            "STARROCKS_BE_CPU_LIMIT": config.be_resources.cpu_limit,
            "STARROCKS_BE_MEMORY_REQUEST": config.be_resources.memory_request,
            "STARROCKS_BE_MEMORY_LIMIT": config.be_resources.memory_limit,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
        }

        manifests = render_manifests("starrocks", variables)
        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(manifests, os_key="ubuntu-22.04", namespace=namespace, instance_id=svc_id)

        logger.info("Deploying StarRocks for workspace '%s' to namespace '%s'", workspace_name, namespace)
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        logger.info("Waiting for StarRocks FE rollout...")
        ready = await kubectl_rollout_status(
            f"statefulset/argus-starrocks-{workspace_name}-fe",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(f"StarRocks FE rollout timed out in {namespace}")

        logger.info("Waiting for StarRocks BE rollout...")
        await kubectl_rollout_status(
            f"statefulset/argus-starrocks-{workspace_name}-be",
            namespace=namespace, timeout=300, kubeconfig=kubeconfig,
        )

        # Register BE nodes with FE via register-backends.sh in ConfigMap
        import asyncio
        register_cmd = [
            "kubectl", "exec",
            f"argus-starrocks-{workspace_name}-fe-0",
            f"-n", namespace,
            "--", "bash", "-c",
            f"""
            FE_HOST=argus-starrocks-{workspace_name}-fe
            for i in $(seq 0 {config.be_replicas - 1}); do
              BE_POD="argus-starrocks-{workspace_name}-be-${{i}}.argus-starrocks-{workspace_name}-be.{namespace}.svc.cluster.local"
              mysql -h "$FE_HOST" -P 9030 -u root -e "ALTER SYSTEM ADD BACKEND '${{BE_POD}}:9050';" 2>/dev/null || true
            done
            """,
        ]
        if kubeconfig:
            register_cmd.insert(1, f"--kubeconfig={kubeconfig}")
        proc = await asyncio.create_subprocess_exec(
            *register_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info("StarRocks BE registration complete")
        else:
            logger.warning("StarRocks BE registration may have issues: %s", stderr.decode())

        ctx.set("starrocks_endpoint", hostname)
        ctx.set("starrocks_manifests", manifests)

        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        internal_fe = f"http://argus-starrocks-{workspace_name}-fe.{namespace}.svc.cluster.local"
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-starrocks",
            display_name="StarRocks Analytics DB",
            version="4.0.8",
            endpoint=f"http://{hostname}",
            service_id=svc_id,
            metadata={
                "display": {
                    "MySQL Port": "9030",
                    "Backend Nodes": str(config.be_replicas),
                },
                "internal": {
                    "fe_http": f"{internal_fe}:8030",
                    "fe_mysql": f"{internal_fe}:9030",
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_limit": config.fe_resources.cpu_limit,
                    "memory_limit": config.fe_resources.memory_limit,
                },
            },
        )

        return {"endpoint": hostname, "service_id": svc_id}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("starrocks_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("starrocks_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("starrocks_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint)
            except Exception as e:
                logger.warning("DNS deletion failed for StarRocks: %s", e)
        return {"k8s_deleted": True}
