"""Workflow step: Deploy JupyterLab to Kubernetes for a workspace.

This step:
1. Ensures the workspace namespace exists.
2. Renders JupyterLab K8s manifests with workspace-specific variables.
3. Applies manifests (Secret, Deployment with dual s3fs sidecars, Service, Ingress).
4. Waits for rollout to complete.
5. Registers the service with endpoint info.
"""

import logging
import socket

from workspace_provisioner.config import JupyterLabConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


JUPYTER_PLUGIN_INFO = {
    "argus-jupyter": ("JupyterLab", "argus_jupyter_config"),
    "argus-jupyter-tensorflow": ("JupyterLab TensorFlow", "argus_jupyter_tensorflow_config"),
    "argus-jupyter-pyspark": ("JupyterLab PySpark", "argus_jupyter_pyspark_config"),
}


class JupyterLabDeployStep(WorkflowStep):
    """Deploy JupyterLab to Kubernetes for a workspace.

    Supports all Jupyter variants (base, TensorFlow, PySpark).
    The plugin_name is passed at construction to select the correct
    config key and display name.

    Reads from context:
        - workspace_name, workspace_id, domain
        - k8s_namespace (default: argus-ws-{workspace_name})
        - creator_username
        - minio_workspace_bucket (optional)

    Writes to context:
        - jupyter_endpoint, jupyter_manifests
    """

    def __init__(self, plugin_name: str = "argus-jupyter") -> None:
        self._plugin_name = plugin_name

    @property
    def name(self) -> str:
        return self._plugin_name

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

        svc_display, config_key = JUPYTER_PLUGIN_INFO.get(
            self._plugin_name, ("JupyterLab", "argus_jupyter_config")
        )
        config: JupyterLabConfig = ctx.get(config_key, JupyterLabConfig())
        s3 = await self._get_s3_settings()

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        # Generate unique service ID for hostname security
        from workspace_provisioner.service import generate_service_id
        svc_id = generate_service_id()

        workspace_bucket = ctx.get("minio_workspace_bucket", f"workspace-{workspace_name}")
        user_bucket = f"user-{username}"
        hostname = f"argus-jupyter-{svc_id}.argus-insight.{domain}"

        # Build install packages string
        install_packages = " ".join(config.install_packages) if config.install_packages else ""

        variables = {
            "JUPYTER_IMAGE": config.image,
            "JUPYTER_CPU_REQUEST": config.cpu_request,
            "JUPYTER_CPU_LIMIT": config.cpu_limit,
            "JUPYTER_MEMORY_REQUEST": config.memory_request,
            "JUPYTER_MEMORY_LIMIT": config.memory_limit,
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
            "PIP_INDEX_URL": config.pip_index_url,
            "INSTALL_PACKAGES": install_packages,
            "ARGUS_SERVER_HOST": server_ip,
        }

        manifests = render_manifests("jupyter", variables)
        logger.info(
            "Deploying JupyterLab for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        resource = f"deployment/argus-jupyter-{svc_id}"
        logger.info("Waiting for %s rollout in %s...", resource, namespace)
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"JupyterLab rollout timed out: {resource} in {namespace}"
            )

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-jupyter-{svc_id}.{namespace}.svc.cluster.local:8888"

        ctx.set("jupyter_endpoint", external_endpoint)
        ctx.set("jupyter_manifests", manifests)

        # Register DNS
        from workspace_provisioner.workflow.steps.app_deploy import register_workspace_dns
        await register_workspace_dns(hostname)

        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name=self._plugin_name,
            display_name=svc_display,
            version="1.0",
            endpoint=external_endpoint,
            service_id=svc_id,
            metadata={
                "image": config.image,
                "internal_endpoint": internal_endpoint,
                "workspace_bucket": workspace_bucket,
                "user_bucket": user_bucket,
                "namespace": namespace,
            },
        )

        return {
            "endpoint": external_endpoint,
            "internal_endpoint": internal_endpoint,
            "namespace": namespace,
            "service_id": svc_id,
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        _, config_key = JUPYTER_PLUGIN_INFO.get(
            self._plugin_name, ("JupyterLab", "argus_jupyter_config")
        )
        config: JupyterLabConfig = ctx.get(config_key, JupyterLabConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        instance_id = ctx.get("teardown_service_id", ctx.workspace_name)
        hostname = ctx.get(
            "jupyter_endpoint",
            f"argus-jupyter-teardown.argus-insight.{ctx.domain}",
        ).replace("http://", "")
        return render_manifests("jupyter", {
            "JUPYTER_IMAGE": config.image,
            "JUPYTER_CPU_REQUEST": config.cpu_request,
            "JUPYTER_CPU_LIMIT": config.cpu_limit,
            "JUPYTER_MEMORY_REQUEST": config.memory_request,
            "JUPYTER_MEMORY_LIMIT": config.memory_limit,
            "S3FS_IMAGE": config.s3fs_image,
            "INSTANCE_ID": instance_id,
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "HOSTNAME": hostname,
            "S3_ENDPOINT": "", "S3_ACCESS_KEY": "", "S3_SECRET_KEY": "",
            "S3_USE_SSL": "false",
            "WORKSPACE_BUCKET": "", "USER_BUCKET": "",
            "PIP_INDEX_URL": config.pip_index_url,
            "INSTALL_PACKAGES": "",
            "ARGUS_SERVER_HOST": "127.0.0.1",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("jupyter_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back JupyterLab for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("jupyter_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        endpoint = ctx.get("jupyter_endpoint")
        if endpoint:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import delete_workspace_dns
                await delete_workspace_dns(endpoint.replace("http://", "").replace("https://", ""))
            except Exception as e:
                logger.warning("DNS deletion failed for JupyterLab: %s", e)
        logger.info("Teardown JupyterLab for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
