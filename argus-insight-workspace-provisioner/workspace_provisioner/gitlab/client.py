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
        namespace_id: int | None = None,
        description: str = "",
        initialize_with_readme: bool = True,
        default_branch: str = "main",
    ) -> dict:
        """Create a new GitLab project.

        Args:
            name: Project name (e.g., "ml-team-dev").
            namespace_id: GitLab group/namespace ID. None = root admin namespace.
            description: Optional project description.
            initialize_with_readme: Whether to create an initial README.md.
            default_branch: Default branch name.

        Returns:
            Dict with project id, name, path_with_namespace, web_url, http_url_to_repo,
            and ssh_url_to_repo.
        """
        project_data = {
            "name": name,
            "description": description,
            "initialize_with_readme": initialize_with_readme,
            "default_branch": default_branch,
            "visibility": "internal",
        }
        if namespace_id is not None:
            project_data["namespace_id"] = namespace_id
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

    async def path_exists(self, project_id: int, path: str, ref: str = "main") -> bool:
        """Check if a file or directory exists in a GitLab repo.

        Args:
            project_id: Target project ID.
            path: Path to check (e.g., "airflow-dags").
            ref: Branch or commit ref.

        Returns:
            True if the path exists, False otherwise.
        """
        try:
            project = await self._run_sync(self._gl.projects.get, project_id)
            await self._run_sync(
                project.repository_tree, path=path, ref=ref, per_page=1,
            )
            return True
        except gitlab.exceptions.GitlabGetError:
            return False

    async def find_user(self, username: str) -> dict | None:
        """Find a GitLab user by username.

        Returns:
            Dict with user id, username, email, or None if not found.
        """
        users = await self._run_sync(self._gl.users.list, username=username)
        for u in users:
            if u.username == username:
                return {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                }
        return None

    async def create_user(
        self,
        username: str,
        password: str,
        email: str,
        name: str,
    ) -> dict:
        """Create a new GitLab user.

        Args:
            username: Login username.
            password: Initial password (min 8 chars for GitLab).
            email: User email address.
            name: Display name.

        Returns:
            Dict with user id, username, email.
        """
        user_data = {
            "username": username,
            "password": password,
            "email": email,
            "name": name,
            "skip_confirmation": True,
        }
        user = await self._run_sync(self._gl.users.create, user_data)
        logger.info("GitLab user created: %s (id=%d)", username, user.id)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }

    async def add_group_member(
        self,
        group_id: int,
        user_id: int,
        access_level: int = 30,
    ) -> None:
        """Add a user to a GitLab group.

        Args:
            group_id: GitLab group ID.
            user_id: GitLab user ID.
            access_level: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner.
        """
        group = await self._run_sync(self._gl.groups.get, group_id)
        try:
            await self._run_sync(
                group.members.create, {"user_id": user_id, "access_level": access_level}
            )
            logger.info("Added user %d to group %d (level=%d)", user_id, group_id, access_level)
        except gitlab.exceptions.GitlabCreateError as e:
            if "already exists" in str(e).lower() or "Member already exists" in str(e):
                logger.info("User %d already a member of group %d", user_id, group_id)
            else:
                raise

    async def share_project_with_group(
        self,
        project_id: int,
        group_id: int,
        group_access: int = 30,
    ) -> None:
        """Share a GitLab project with a group.

        Args:
            project_id: GitLab project ID.
            group_id: GitLab group ID to share with.
            group_access: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer.
        """
        project = await self._run_sync(self._gl.projects.get, project_id)
        try:
            await self._run_sync(
                project.share, group_id, group_access
            )
            logger.info("Shared project %d with group %d (level=%d)", project_id, group_id, group_access)
        except gitlab.exceptions.GitlabCreateError as e:
            if "already" in str(e).lower():
                logger.info("Project %d already shared with group %d", project_id, group_id)
            else:
                raise

    async def add_project_member(
        self,
        project_id: int,
        user_id: int,
        access_level: int = 30,
    ) -> None:
        """Add a user as a direct member of a project.

        Args:
            project_id: GitLab project ID.
            user_id: GitLab user ID.
            access_level: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner.
        """
        project = await self._run_sync(self._gl.projects.get, project_id)
        try:
            await self._run_sync(
                project.members.create, {"user_id": user_id, "access_level": access_level}
            )
            logger.info("Added user %d to project %d (level=%d)", user_id, project_id, access_level)
        except gitlab.exceptions.GitlabCreateError as e:
            if "already" in str(e).lower() or "Member already exists" in str(e):
                logger.info("User %d already a member of project %d", user_id, project_id)
            else:
                raise

    async def remove_project_member(
        self,
        project_id: int,
        user_id: int,
    ) -> None:
        """Remove a user from a project.

        Args:
            project_id: GitLab project ID.
            user_id: GitLab user ID to remove.
        """
        project = await self._run_sync(self._gl.projects.get, project_id)
        try:
            member = await self._run_sync(project.members.get, user_id)
            await self._run_sync(member.delete)
            logger.info("Removed user %d from project %d", user_id, project_id)
        except Exception as e:
            logger.warning("Failed to remove user %d from project %d: %s", user_id, project_id, e)

    async def create_project_access_token(
        self,
        project_id: int,
        name: str,
        scopes: list[str] | None = None,
        access_level: int = 40,
        expires_at: str | None = None,
    ) -> dict:
        """Create a project access token.

        Args:
            project_id: GitLab project ID.
            name: Token name (e.g., "argus-admin-mlteamdev").
            scopes: Token scopes. Defaults to ["api", "read_repository", "write_repository"].
            access_level: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer.
            expires_at: Expiry date (YYYY-MM-DD). None = no expiry.

        Returns:
            Dict with token, name, scopes, expires_at.
        """
        if scopes is None:
            scopes = ["api", "read_repository", "write_repository"]

        project = await self._run_sync(self._gl.projects.get, project_id)
        token_data: dict = {
            "name": name,
            "scopes": scopes,
            "access_level": access_level,
        }
        if expires_at:
            token_data["expires_at"] = expires_at

        token = await self._run_sync(project.access_tokens.create, token_data)
        logger.info(
            "Project access token created: project=%d, name=%s, scopes=%s",
            project_id, name, scopes,
        )
        return {
            "token": token.token,
            "name": token.name,
            "scopes": token.scopes,
            "expires_at": getattr(token, "expires_at", None),
        }
