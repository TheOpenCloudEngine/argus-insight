"""Workflow step: Deploy VS Code Server to Kubernetes for a workspace.

This step:
1. Ensures the workspace namespace exists.
2. Renders VS Code K8s manifests with workspace-specific variables.
3. Applies manifests (Secret, Deployment with dual s3fs sidecars, Service, Ingress).
4. Waits for rollout to complete.
5. Registers the service with endpoint info.
"""

import logging
import socket

from workspace_provisioner.config import VScodeServerConfig
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    kubectl_rollout_status,
    render_manifests,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.workflow.steps.app_deploy import ensure_namespace

logger = logging.getLogger(__name__)


class VScodeServerDeployStep(WorkflowStep):
    """Deploy VS Code Server to Kubernetes for a workspace.

    Reads from context:
        - workspace_name
        - workspace_id
        - domain
        - k8s_namespace (default: argus-ws-{workspace_name})
        - creator_username

    Writes to context:
        - vscode_endpoint
        - vscode_manifests
    """

    @property
    def name(self) -> str:
        return "argus-vscode-server"

    async def _get_s3_settings(self) -> dict:
        """Load S3 settings from DB."""
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

        # Ensure namespace exists
        await ensure_namespace(namespace)

        # Get config
        config: VScodeServerConfig = ctx.get("argus_vscode_server_config", VScodeServerConfig())

        # Get S3 settings
        s3 = await self._get_s3_settings()

        # Get server IP for auth-url
        try:
            server_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            server_ip = ctx.get("argus_server_host", "127.0.0.1")

        # Instance ID = workspace name (one per workspace)
        instance_id = workspace_name

        # Build hostname
        hostname = f"argus-vscode-{workspace_name}.argus-insight.{domain}"

        # Workspace bucket and user bucket
        workspace_bucket = ctx.get("minio_workspace_bucket", f"workspace-{workspace_name}")
        user_bucket = f"user-{username}"

        variables = {
            "INSTANCE_ID": instance_id,
            "USERNAME": username,
            "K8S_NAMESPACE": namespace,
            "HOSTNAME": hostname,
            "DOMAIN": domain,
            "S3_ENDPOINT": s3["endpoint"],
            "S3_ACCESS_KEY": s3["access_key"],
            "S3_SECRET_KEY": s3["secret_key"],
            "S3_USE_SSL": s3["use_ssl"],
            "WORKSPACE_BUCKET": workspace_bucket,
            "USER_BUCKET": user_bucket,
            "ARGUS_SERVER_HOST": server_ip,
            "APP_TYPE": "vscode",
        }

        manifests = render_manifests("vscode", variables)
        logger.info(
            "Deploying VS Code Server for workspace '%s' to namespace '%s'",
            workspace_name, namespace,
        )
        await kubectl_apply(manifests, kubeconfig=kubeconfig)

        # Wait for deployment
        resource = f"deployment/argus-vscode-{instance_id}"
        logger.info("Waiting for %s rollout in %s...", resource, namespace)
        ready = await kubectl_rollout_status(
            resource, namespace=namespace, timeout=180, kubeconfig=kubeconfig,
        )
        if not ready:
            raise RuntimeError(
                f"VS Code Server rollout timed out: {resource} in {namespace}"
            )

        external_endpoint = f"http://{hostname}"
        internal_endpoint = f"http://argus-vscode-{instance_id}.{namespace}.svc.cluster.local:8080"

        ctx.set("vscode_endpoint", external_endpoint)
        ctx.set("vscode_manifests", manifests)

        # Register service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-vscode-server",
            display_name="VS Code Server",
            version="1.1",
            endpoint=external_endpoint,
            username=username,
            metadata={
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
        }

    def _render_manifests(self, ctx: WorkflowContext) -> str:
        """Re-render manifests from context for teardown."""
        config: VScodeServerConfig = ctx.get("argus_vscode_server_config", VScodeServerConfig())
        namespace = ctx.get("k8s_namespace", f"argus-ws-{ctx.workspace_name}")
        return render_manifests("vscode", {
            "INSTANCE_ID": ctx.workspace_name,
            "USERNAME": ctx.get("creator_username", "default"),
            "K8S_NAMESPACE": namespace,
            "HOSTNAME": f"argus-vscode-{ctx.workspace_name}.argus-insight.{ctx.domain}",
            "DOMAIN": ctx.domain,
            "S3_ENDPOINT": "",
            "S3_ACCESS_KEY": "",
            "S3_SECRET_KEY": "",
            "S3_USE_SSL": "false",
            "WORKSPACE_BUCKET": "",
            "USER_BUCKET": "",
            "ARGUS_SERVER_HOST": "127.0.0.1",
            "APP_TYPE": "vscode",
        })

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("vscode_manifests")
        if manifests:
            kubeconfig = ctx.get("k8s_kubeconfig")
            await kubectl_delete(manifests, kubeconfig=kubeconfig)
            logger.info("Rolled back VS Code Server for workspace '%s'", ctx.workspace_name)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        manifests = ctx.get("vscode_manifests") or self._render_manifests(ctx)
        kubeconfig = ctx.get("k8s_kubeconfig")
        await kubectl_delete(manifests, kubeconfig=kubeconfig)
        logger.info("Teardown VS Code Server for workspace '%s'", ctx.workspace_name)
        return {"k8s_deleted": True}
