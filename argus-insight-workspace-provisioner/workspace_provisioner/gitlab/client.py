"""GitLab API client wrapper using python-gitlab.

Provides a thin async-friendly wrapper around the python-gitlab library
for operations needed by workspace provisioning workflows.

The client is initialized with the GitLab server URL and a private token
(typically the root admin token or a service account token).

Usage:
    client = GitLabClient(url="https://gitlab-global.argus-insight.dev.net", token="glpat-xxx")
    project = await client.create_project("workspaces/my-workspace", ...)
"""

import logging
from functools import partial
from typing import Any

import asyncio
import gitlab

logger = logging.getLogger(__name__)


class GitLabClient:
    """Wrapper around python-gitlab for workspace-related GitLab operations.

    All methods run the synchronous python-gitlab calls in a thread executor
    to avoid blocking the async event loop.
    """

    def __init__(self, url: str, private_token: str) -> None:
        self._url = url
        self._gl = gitlab.Gitlab(url=url, private_token=private_token)
        self._gl.auth()
        logger.info("GitLab client authenticated: %s", url)

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        """Run a synchronous function in the default thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def ensure_group(self, group_path: str) -> dict:
        """Ensure a GitLab group exists, creating it if necessary.

        Handles nested groups (e.g., "workspaces/team-a") by creating
        parent groups first.

        Args:
            group_path: Full group path (e.g., "workspaces").

        Returns:
            Dict with group id, name, path, and web_url.
        """
        parts = group_path.strip("/").split("/")
        parent_id = None
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            try:
                group = await self._run_sync(self._gl.groups.get, current_path)
                parent_id = group.id
                logger.info("GitLab group exists: %s (id=%d)", current_path, group.id)
            except gitlab.exceptions.GitlabGetError:
                group_data = {"name": part, "path": part}
                if parent_id is not None:
                    group_data["parent_id"] = parent_id
                group = await self._run_sync(self._gl.groups.create, group_data)
                parent_id = group.id
                logger.info("GitLab group created: %s (id=%d)", current_path, group.id)

        return {
            "id": group.id,
            "name": group.name,
            "path": group.full_path,
            "web_url": group.web_url,
        }

    async def create_project(
        self,
        name: str,
        namespace_id: int,
        description: str = "",
        initialize_with_readme: bool = True,
        default_branch: str = "main",
    ) -> dict:
        """Create a new GitLab project under the specified namespace (group).

        Args:
            name: Project name (e.g., "ml-team-dev").
            namespace_id: GitLab group/namespace ID to create the project in.
            description: Optional project description.
            initialize_with_readme: Whether to create an initial README.md.
            default_branch: Default branch name.

        Returns:
            Dict with project id, name, path_with_namespace, web_url, http_url_to_repo,
            and ssh_url_to_repo.
        """
        project_data = {
            "name": name,
            "namespace_id": namespace_id,
            "description": description,
            "initialize_with_readme": initialize_with_readme,
            "default_branch": default_branch,
            "visibility": "internal",
        }
        project = await self._run_sync(self._gl.projects.create, project_data)
        logger.info(
            "GitLab project created: %s (id=%d)",
            project.path_with_namespace,
            project.id,
        )
        return {
            "id": project.id,
            "name": project.name,
            "path_with_namespace": project.path_with_namespace,
            "web_url": project.web_url,
            "http_url_to_repo": project.http_url_to_repo,
            "ssh_url_to_repo": project.ssh_url_to_repo,
        }

    async def delete_project(self, project_id: int) -> None:
        """Delete a GitLab project by ID.

        Args:
            project_id: The GitLab project ID to delete.
        """
        project = await self._run_sync(self._gl.projects.get, project_id)
        await self._run_sync(project.delete)
        logger.info("GitLab project deleted: id=%d", project_id)

    async def get_project(self, project_id: int) -> dict | None:
        """Get project details by ID.

        Returns:
            Dict with project info, or None if not found.
        """
        try:
            project = await self._run_sync(self._gl.projects.get, project_id)
            return {
                "id": project.id,
                "name": project.name,
                "path_with_namespace": project.path_with_namespace,
                "web_url": project.web_url,
                "http_url_to_repo": project.http_url_to_repo,
                "ssh_url_to_repo": project.ssh_url_to_repo,
            }
        except gitlab.exceptions.GitlabGetError:
            return None

    async def commit_files(
        self,
        project_id: int,
        branch: str,
        commit_message: str,
        actions: list[dict],
    ) -> dict:
        """Create a commit with multiple file actions.

        Args:
            project_id: Target project ID.
            branch: Branch to commit to.
            commit_message: Commit message.
            actions: List of file actions, each a dict with:
                - action: "create", "update", or "delete"
                - file_path: Path within the repository
                - content: File content (for create/update)

        Returns:
            Dict with commit id, short_id, and message.
        """
        project = await self._run_sync(self._gl.projects.get, project_id)
        commit_data = {
            "branch": branch,
            "commit_message": commit_message,
            "actions": actions,
        }
        commit = await self._run_sync(project.commits.create, commit_data)
        logger.info(
            "GitLab commit created: project=%d, sha=%s",
            project_id,
            commit.short_id,
        )
        return {
            "id": commit.id,
            "short_id": commit.short_id,
            "message": commit.message,
        }
