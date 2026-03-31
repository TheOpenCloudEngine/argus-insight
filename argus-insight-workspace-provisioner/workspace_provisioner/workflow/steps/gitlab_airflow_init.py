"""Workflow step: Initialize airflow-dags directory in GitLab repo.

This step:
1. Checks if airflow-dags/ directory already exists in the workspace GitLab repo.
2. If not, creates airflow-dags/ with a sample DAG file.
3. Provides gitlab_http_url and gitlab_token in the workflow context
   so that Airflow's git-sync sidecar can clone and sync DAGs.
"""

import logging

from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)

SAMPLE_DAG = '''\
"""Example DAG for Argus Insight workspace."""
from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    "example_hello",
    description="Example DAG created by Argus Insight",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
):
    BashOperator(
        task_id="say_hello",
        bash_command='echo "Hello from Argus Insight workspace!"',
    )
'''


class GitlabAirflowInitStep(WorkflowStep):
    """Initialize airflow-dags directory in GitLab repo.

    Reads from context:
        - gitlab_project_id: GitLab project ID (set by argus-gitlab step).

    Writes to context:
        - gitlab_http_url: HTTP clone URL for the repo.
        - gitlab_token: Access token for git-sync authentication.
    """

    @property
    def name(self) -> str:
        return "argus-gitlab-airflow-init"

    async def _get_gitlab_client(self):
        """Get the initialized GitLab client singleton."""
        from workspace_provisioner.router import _get_gitlab_client
        return _get_gitlab_client()

    async def _get_gitlab_token(self) -> str:
        """Load GitLab admin token from settings DB."""
        from app.core.database import async_session
        from app.settings.service import get_config_by_category

        async with async_session() as session:
            cfg = await get_config_by_category(session, "gitlab")
            return cfg.get("gitlab_token", "")

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        project_id = ctx.get("gitlab_project_id")
        if not project_id:
            # Try to resolve from workspace services
            from sqlalchemy import select
            from app.core.database import async_session
            from workspace_provisioner.models import ArgusWorkspaceService

            async with async_session() as session:
                result = await session.execute(
                    select(ArgusWorkspaceService).where(
                        ArgusWorkspaceService.workspace_id == ctx.workspace_id,
                        ArgusWorkspaceService.plugin_name == "argus-gitlab",
                    )
                )
                gl_svc = result.scalars().first()
                if gl_svc and gl_svc.metadata_json:
                    internal = gl_svc.metadata_json.get("internal", gl_svc.metadata_json)
                    project_id = internal.get("project_id")

        if not project_id:
            logger.warning("GitLab project ID not found, skipping airflow-dags init")
            return {"skipped": True, "reason": "no_project_id"}

        gitlab_client = await self._get_gitlab_client()
        dags_sub_path = "airflow-dags"

        # Check if airflow-dags/ already exists
        exists = await gitlab_client.path_exists(project_id, dags_sub_path)

        files_created = 0
        if not exists:
            # Create airflow-dags/ with sample DAG
            await gitlab_client.commit_files(
                project_id=project_id,
                branch="main",
                commit_message="Initialize airflow-dags directory with sample DAG",
                actions=[
                    {
                        "action": "create",
                        "file_path": f"{dags_sub_path}/.gitkeep",
                        "content": "",
                    },
                    {
                        "action": "create",
                        "file_path": f"{dags_sub_path}/example_hello.py",
                        "content": SAMPLE_DAG,
                    },
                ],
            )
            files_created = 2
            logger.info(
                "Created airflow-dags/ in GitLab project %d with sample DAG",
                project_id,
            )
        else:
            logger.info(
                "airflow-dags/ already exists in GitLab project %d, skipping",
                project_id,
            )

        # Provide git-sync credentials to context
        project = await gitlab_client.get_project(project_id)
        http_url = project["http_url_to_repo"] if project else ""
        token = await self._get_gitlab_token()

        ctx.set("gitlab_http_url", http_url)
        ctx.set("gitlab_token", token)

        return {
            "project_id": project_id,
            "dags_dir_created": not exists,
            "files_created": files_created,
            "http_url": http_url,
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        # No rollback needed — files are part of the GitLab repo
        # which gets deleted by argus-gitlab rollback if needed
        pass

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        # No teardown — the GitLab project deletion handles cleanup
        return None
