"""Workflow step: Create a GitLab project for a new workspace.

This step:
1. Ensures the "workspaces" group exists in GitLab.
2. Creates a new project under that group named after the workspace.
3. Commits an initial directory structure for Airflow DAGs, notebooks, etc.
4. Stores the GitLab project ID and URL in the workflow context.
"""

import logging

from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)

# Default directory structure committed to the new workspace repository.
INITIAL_FILES = [
    {
        "action": "create",
        "file_path": "airflow/dags/.gitkeep",
        "content": "",
    },
    {
        "action": "create",
        "file_path": "notebooks/.gitkeep",
        "content": "",
    },
    {
        "action": "create",
        "file_path": "vscode/.gitkeep",
        "content": "",
    },
    {
        "action": "create",
        "file_path": "mlflow/.gitkeep",
        "content": "",
    },
    {
        "action": "create",
        "file_path": ".argus/workspace.yml",
        "content": (
            "# Argus Insight Workspace Configuration\n"
            "# This file is auto-generated. Do not edit manually.\n"
        ),
    },
]


class GitLabCreateProjectStep(WorkflowStep):
    """Create a GitLab project for the workspace repository.

    Reads from context:
        - workspace_name: Used as the project name.
        - domain: Used to construct the GitLab URL.
        - gitlab_group (optional): Parent group path. Defaults to "workspaces".

    Writes to context:
        - gitlab_project_id: The created project's ID.
        - gitlab_project_url: The project's web URL.
        - gitlab_http_url: The HTTP clone URL.
        - gitlab_ssh_url: The SSH clone URL.
    """

    def __init__(self, gitlab_client: GitLabClient) -> None:
        self._client = gitlab_client

    @property
    def name(self) -> str:
        return "gitlab-create-project"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        group_path = ctx.get("gitlab_group", "workspaces")

        # Step 1: Ensure parent group exists
        group = await self._client.ensure_group(group_path)
        logger.info("Using GitLab group: %s (id=%d)", group["path"], group["id"])

        # Step 2: Create project
        project = await self._client.create_project(
            name=ctx.workspace_name,
            namespace_id=group["id"],
            description=f"Argus Insight workspace: {ctx.workspace_name}",
        )

        # Step 3: Commit initial directory structure
        workspace_yml_content = (
            "# Argus Insight Workspace Configuration\n"
            "# This file is auto-generated. Do not edit manually.\n"
            f"workspace_name: {ctx.workspace_name}\n"
            f"domain: {ctx.domain}\n"
            f"gitlab_project_id: {project['id']}\n"
        )
        actions = []
        for f in INITIAL_FILES:
            action = dict(f)
            if action["file_path"] == ".argus/workspace.yml":
                action["content"] = workspace_yml_content
            actions.append(action)

        await self._client.commit_files(
            project_id=project["id"],
            branch="main",
            commit_message="Initialize workspace repository structure",
            actions=actions,
        )

        # Step 4: Store results in context
        ctx.set("gitlab_project_id", project["id"])
        ctx.set("gitlab_project_url", project["web_url"])
        ctx.set("gitlab_http_url", project["http_url_to_repo"])
        ctx.set("gitlab_ssh_url", project["ssh_url_to_repo"])

        return {
            "project_id": project["id"],
            "project_url": project["web_url"],
            "http_url": project["http_url_to_repo"],
            "ssh_url": project["ssh_url_to_repo"],
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Delete the GitLab project if it was created."""
        project_id = ctx.get("gitlab_project_id")
        if project_id:
            await self._client.delete_project(project_id)
            logger.info("Rolled back GitLab project: id=%d", project_id)
