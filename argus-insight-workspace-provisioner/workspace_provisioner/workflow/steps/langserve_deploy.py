"""Workflow step: Deploy LangServe Agent to Kubernetes for a workspace.

This step:
1. Ensures the workspace namespace exists.
2. Renders LangServe K8s manifests with workspace-specific variables.
3. Applies manifests (Deployment with s3fs sidecar, Service, Ingress).
4. Waits for rollout to complete.
5. Registers the service with endpoint info.
"""

import logging
import socket

from workspace_provisioner.config import LangServeConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class LangServeDeployStep(WorkflowStep):
    """Deploy LangServe Agent API to Kubernetes.

    Multi-instance: each deploy gets a unique service ID for hostname isolation.

    Reads from context:
        - workspace_name, workspace_id, domain
        - k8s_namespace (default: argus-ws-{workspace_name})
        - creator_username
        - minio_workspace_bucket (optional)

    Writes to context:
        - langserve_endpoint, langserve_manifests
    """

    @property
    def name(self) -> str:
        return "argus-langserve"

    async def _get_s3_settings(self) -> dict:
        from app.core.database import async_session
        from app.settings.service import get_config_by_category
        async with async_session() as session:
            cfg = await get_config_by_category(session, "argus")
            return {
                "endpoint": cfg.get("object_storage_endpoint", ""),
                "access_key": cfg.get("object_storage_access_key", ""),
                "secret_key": cfg.get("object_storage_secret_key", ""),
                "use_ssl": cfg.get("object_storage_use_ssl", "false"),
            }

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")
        kubeconfig = ctx.get("k8s_kubeconfig")
        username = ctx.get("creator_username", "default")

        await ensure_namespace(namespace)

        config: LangServeConfig = ctx.get("argus_langserve_config", LangServeConfig())
        s3 = await self._get_s3_settings()

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        # Generate unique service ID for hostname security
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()

        workspace_bucket = ctx.get("minio_workspace_bucket", f"workspace-{workspace_name}")
        hostname = f"argus-langserve-{svc_id}.argus-insight.{domain}"

        variables = {
            "LANGSERVE_IMAGE": config.image,
            "LANGSERVE_CPU_REQUEST": config.cpu_request,
            "LANGSERVE_CPU_LIMIT": config.cpu_limit,
            "LANGSERVE_MEMORY_REQUEST": config.memory_request,
            "LANGSERVE_MEMORY_LIMIT": config.memory_limit,
            "S3FS_IMAGE": config.s3fs_image,
            "INSTANCE_ID": svc_id,
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": domain,
            "HOSTNAME": hostname,
            "S3_ENDPOINT": s3["endpoint"],
            "S3_ACCESS_KEY": s3["access_key"],
            "S3_SECRET_KEY": s3["secret_key"],
            "S3_USE_SSL": s3["use_ssl"],
            "WORKSPACE_BUCKET": workspace_bucket,
            "ARGUS_SERVER_HOST": server_ip,
            "AGENT_PATH": config.agent_path,
            "PIP_INDEX_URL": config.pip_index_url,
            "AUTH_ANNOTATION": (
                f'nginx.ingress.kubernetes.io/auth-url: "http://{server_ip}:4500'
                f'/api/v1/workspace/workspaces/auth-verify?service_id={svc_id}"'
                if not config.disable_auth
                else "# auth disabled"
            ),
        }

        manifests = render_manifests("langserve", variables)
        logger.info(
            "Deploying LangServe Agent for workspace '%s' (agent_path=%s, auth=%s)",
            workspace_name, config.agent_path, "disabled" if config.disable_auth else "enabled",
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-langserve-{svc_id}"
        logger.info("Waiting for %s rollout in %s...", resource, namespace)
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"LangServe rollout timed out: {resource} in {namespace}"
            )

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-langserve-{svc_id}.{namespace}.svc.cluster.local:8000"

        ctx.set("langserve_endpoint", external_endpoint)
        ctx.set("langserve_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-langserve",
            display_name="LangServe Agent",
            version="0.3",
            endpoint=external_endpoint,
            service_id=svc_id,
            username=username,
            metadata={
                "display": {
                    "Image": config.image,
                    "Agent Path": config.agent_path,
                    "Workspace Bucket": workspace_bucket,
                },
                "internal": {
                    "endpoint": internal_endpoint,
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_limit": config.cpu_limit,
                    "memory_limit": config.memory_limit,
                },
            },
        )

        return {
            "endpoint": external_endpoint,
            "internal_endpoint": internal_endpoint,
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        config: LangServeConfig = ctx.get("argus_langserve_config", LangServeConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        instance_id = ctx.get("teardown_service_id", ctx.workspace_name)
        hostname = ctx.get(
            "langserve_endpoint",
            f"argus-langserve-teardown.argus-insight.{ctx.domain}",
        ).replace("http://", "")
        return render_manifests("langserve", {
            "LANGSERVE_IMAGE": config.image,
            "LANGSERVE_CPU_REQUEST": config.cpu_request,
            "LANGSERVE_CPU_LIMIT": config.cpu_limit,
            "LANGSERVE_MEMORY_REQUEST": config.memory_request,
            "LANGSERVE_MEMORY_LIMIT": config.memory_limit,
            "S3FS_IMAGE": config.s3fs_image,
            "INSTANCE_ID": instance_id,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
            "S3_ENDPOINT": "", "S3_ACCESS_KEY": "", "S3_SECRET_KEY": "",
            "S3_USE_SSL": "false",
            "WORKSPACE_BUCKET": "",
            "ARGUS_SERVER_HOST": "127.0.0.1",
            "AGENT_PATH": config.agent_path,
            "PIP_INDEX_URL": config.pip_index_url,
            "AUTH_ANNOTATION": "# auth disabled",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("langserve_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back LangServe for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("langserve_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("langserve_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for LangServe: %s", e)
        logger.info("Teardown LangServe for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
