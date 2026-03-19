"""Workflow step: Custom hook for user-defined logic.

An empty implementation that receives the full workflow context, including:
- Original provisioning request parameters (workspace_name, domain, configs).
- All outputs from previously executed steps (endpoints, credentials, etc.).

Users can subclass this step or modify the execute() method to add
workspace-specific post-provisioning logic (e.g., DNS registration,
notification, external API calls).

Context keys available from previous steps:
    - workspace_name, domain (initial params)
    - gitlab_project_id, gitlab_project_url, gitlab_http_url, gitlab_ssh_url
    - minio_endpoint, minio_external_endpoint, minio_console_endpoint
    - minio_root_user, minio_root_password
    - minio_ws_admin_access_key, minio_ws_admin_secret_key
    - minio_default_bucket
    - airflow_endpoint, airflow_admin_password
    - mlflow_endpoint, mlflow_artifact_bucket
    - kserve_endpoint
    - k8s_namespace, k8s_kubeconfig
    - minio_config, airflow_config, mlflow_config, kserve_config
"""

import logging

from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class CustomHookStep(WorkflowStep):
    """Custom hook step executed during provisioning workflow.

    This step provides a hook point for user-defined logic. It receives
    the complete workflow context containing all parameters and results
    from previously executed steps.

    The default implementation is a no-op that logs context keys.
    Override execute() to add custom logic.

    Args:
        hook_name: Identifier for this hook instance (used as step name).
            Defaults to "custom-hook".
    """

    def __init__(self, hook_name: str = "custom-hook") -> None:
        self._hook_name = hook_name

    @property
    def name(self) -> str:
        return self._hook_name

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        """Execute custom hook logic.

        Override this method to implement workspace-specific post-provisioning
        tasks. The full context is available:

        - ctx.workspace_id: The workspace ID being provisioned.
        - ctx.workspace_name: Workspace slug name.
        - ctx.domain: Domain suffix.
        - ctx.get("key"): Read any value set by previous steps.
        - ctx.set("key", value): Write values for subsequent steps.

        Example subclass::

            class NotifySlackStep(CustomHookStep):
                def __init__(self, webhook_url: str):
                    super().__init__(hook_name="notify-slack")
                    self._webhook_url = webhook_url

                async def execute(self, ctx: WorkflowContext) -> dict | None:
                    await send_slack(
                        self._webhook_url,
                        text=f"Workspace {ctx.workspace_name} provisioned! "
                             f"Airflow: {ctx.get('airflow_endpoint')}",
                    )
                    return {"notified": True}
        """
        logger.info(
            "Custom hook '%s' executing for workspace '%s' (id=%d)",
            self._hook_name,
            ctx.workspace_name,
            ctx.workspace_id,
        )

        context_summary = {
            "workspace_id": ctx.workspace_id,
            "workspace_name": ctx.workspace_name,
            "domain": ctx.domain,
            "context_keys": sorted(ctx.data.keys()),
        }
        logger.info(
            "Custom hook '%s' context: %s",
            self._hook_name,
            context_summary,
        )

        # No-op: override in subclass or modify this method.
        return context_summary

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Rollback custom hook changes.

        Override this method if your custom logic creates resources
        that should be cleaned up on workflow failure.
        """
        logger.info(
            "Custom hook '%s' rollback (no-op) for workspace '%s'",
            self._hook_name,
            ctx.workspace_name,
        )
