"""Workflow step: Deploy RStudio Server to Kubernetes for a workspace.

This step:
1. Ensures the workspace namespace exists.
2. Renders RStudio K8s manifests with workspace-specific variables.
3. Applies manifests (Secret, Deployment with dual s3fs sidecars, Service, Ingress).
4. Waits for rollout to complete.
5. Registers the service with endpoint info.
"""

import logging
import socket

from workspace_provisioner.config import RStudioServerConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class RStudioServerDeployStep(WorkflowStep):
    """Deploy RStudio Server to Kubernetes for a workspace.

    Reads from context:
        - workspace_name, workspace_id, domain
        - k8s_namespace (default: argus-ws-{workspace_name})
        - creator_username
        - minio_workspace_bucket (optional)

    Writes to context:
        - rstudio_endpoint, rstudio_manifests
    """

    @property
    def name(self) -> str:
        return "argus-rstudio"

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

        config: RStudioServerConfig = ctx.get(
            "argus_rstudio_config", RStudioServerConfig(),
        )
        s3 = await self._get_s3_settings()

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()

        workspace_bucket = ctx.get(
            "minio_workspace_bucket", f"workspace-{workspace_name}",
        )
        user_bucket = f"user-{username}"
        hostname = f"argus-rstudio-{svc_id}.argus-insight.{domain}"

        variables = {
            "RSTUDIO_IMAGE": config.image,
            "RSTUDIO_CPU_REQUEST": config.cpu_request,
            "RSTUDIO_CPU_LIMIT": config.cpu_limit,
            "RSTUDIO_MEMORY_REQUEST": config.memory_request,
            "RSTUDIO_MEMORY_LIMIT": config.memory_limit,
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
            "USER_BUCKET": user_bucket,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("rstudio", variables)

        from workspace_provisioner.repo_injector import inject_repo_config
        manifests = await inject_repo_config(
            manifests, os_key="ubuntu-24.04",
            namespace=namespace, instance_id=svc_id,
        )

        logger.info(
            "Deploying RStudio Server for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-rstudio-{svc_id}"
        logger.info("Waiting for %s rollout in %s...", resource, namespace)
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"RStudio Server rollout timed out: {resource} in {namespace}"
            )

        external_endpoint = f"http://{hostname}"
        internal_endpoint = (
            f"http://argus-rstudio-{svc_id}.{namespace}.svc.cluster.local:8787"
        )

        ctx.set("rstudio_endpoint", external_endpoint)
        ctx.set("rstudio_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import (
            register_workspace_dns,
        )
        await register_workspace_dns(hostname)

        # Register service in DB
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-rstudio",
            display_name="RStudio Server",
            version="2024.12.0",
            endpoint=external_endpoint,
            service_id=svc_id,
            username=username,
            metadata={
                "display": {
                    "Image": config.image,
                    "Workspace": f"{config.workspace_path} (Workspace Bucket)",
                    "User": f"{config.user_data_path} (User Bucket)",
                },
                "internal": {
                    "endpoint": internal_endpoint,
                    "namespace": namespace,
                },
                "resources": {
                    "cpu_request": config.cpu_request,
                    "cpu_limit": config.cpu_limit,
                    "memory_request": config.memory_request,
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
        """Re-render manifests for teardown (when stored manifests unavailable)."""
        config: RStudioServerConfig = ctx.get(
            "argus_rstudio_config", RStudioServerConfig(),
        )
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        instance_id = ctx.get("teardown_service_id", ctx.workspace_name)
        hostname = ctx.get(
            "rstudio_endpoint",
            f"argus-rstudio-teardown.argus-insight.{ctx.domain}",
        ).replace("http://", "")
        return render_manifests("rstudio", {
            "RSTUDIO_IMAGE": config.image,
            "RSTUDIO_CPU_REQUEST": config.cpu_request,
            "RSTUDIO_CPU_LIMIT": config.cpu_limit,
            "RSTUDIO_MEMORY_REQUEST": config.memory_request,
            "RSTUDIO_MEMORY_LIMIT": config.memory_limit,
            "S3FS_IMAGE": config.s3fs_image,
            "INSTANCE_ID": instance_id,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
            "S3_ENDPOINT": "", "S3_ACCESS_KEY": "", "S3_SECRET_KEY": "",
            "S3_USE_SSL": "false",
            "WORKSPACE_BUCKET": "", "USER_BUCKET": "",
            "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("rstudio_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info(
                "Rolled back RStudio Server for workspace '%s'",
                ctx.workspace_name,
            )

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("rstudio_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("rstudio_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import (
                    delete_workspace_dns,
                )
                await delete_workspace_dns(
                    endpoint.replace("http://", "").replace("https://", "")
                )
            except Exception as e:
                logger.warning("DNS deletion failed for RStudio: %s", e)
        logger.info(
            "Teardown RStudio Server for workspace '%s'", ctx.workspace_name,
        )
        return {"k8s_deleted": True}
