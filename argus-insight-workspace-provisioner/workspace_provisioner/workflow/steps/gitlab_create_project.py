"""Workflow step: Set up GitLab user, group, and project for a workspace.

This step:
1. Checks if the workspace creator exists in GitLab; creates them if not.
2. Ensures a group named after the workspace exists; creates it if not.
3. Adds the creator to the workspace group.
4. Creates a project under the workspace group.
5. Shares the project with the workspace group.
6. Stores the workspace URL in the workflow context.
"""

import logging

from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class GitLabCreateProjectStep(WorkflowStep):
    """Set up GitLab user, group, and project for a workspace.

    Reads from context:
        - workspace_name: Used as group name and project name.
        - creator_username: Username of the workspace creator.
        - creator_email: Email of the workspace creator.
        - creator_name: Display name of the workspace creator.
        - creator_password: Password for GitLab user creation.

    Writes to context:
        - gitlab_workspace_url: The project's web URL.
        - gitlab_group_id: The workspace group ID.
        - gitlab_user_id: The GitLab user ID.
        - gitlab_project_id: The project ID (for teardown).
    """

    def __init__(self, gitlab_client: GitLabClient) -> None:
        self._client = gitlab_client

    @property
    def name(self) -> str:
        return "argus-gitlab"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        import secrets
        from sqlalchemy import select
        from app.core.database import async_session
        from app.usermgr.models import ArgusUser

        workspace_name = ctx.workspace_name
        creator_username = ctx.get("creator_username", "")
        creator_email = ctx.get("creator_email", "")
        creator_name = ctx.get("creator_name", creator_username)

        result = {}

        # Step 1: Ensure user exists in GitLab
        # All Argus users get "argus-" prefix in GitLab
        gitlab_username = f"argus-{creator_username}"

        gitlab_user = await self._client.find_user(gitlab_username)
        if gitlab_user:
            logger.info("GitLab user exists: %s (id=%d)", gitlab_username, gitlab_user["id"])
            result["user_action"] = "exists"
        else:
            if not creator_email:
                creator_email = f"{gitlab_username}@argus.local"
            # Generate a strong password (meets GitLab complexity requirements)
            safe_password = secrets.token_urlsafe(12) + "!A1a"
            gitlab_user = await self._client.create_user(
                username=gitlab_username,
                password=safe_password,
                email=creator_email,
                name=creator_name or gitlab_username,
            )
            logger.info("GitLab user created: %s (id=%d)", gitlab_username, gitlab_user["id"])
            result["user_action"] = "created"

            # Save gitlab credentials to argus_users table
            async with async_session() as db_session:
                user_result = await db_session.execute(
                    select(ArgusUser).where(ArgusUser.username == creator_username)
                )
                argus_user = user_result.scalars().first()
                if argus_user:
                    argus_user.gitlab_username = gitlab_username
                    argus_user.gitlab_password = safe_password
                    await db_session.commit()
                    logger.info(
                        "GitLab credentials saved for user '%s' (gitlab: %s)",
                        creator_username, gitlab_username,
                    )

        ctx.set("gitlab_user_id", gitlab_user["id"])
        ctx.set("gitlab_username", gitlab_username)
        result["gitlab_user_id"] = gitlab_user["id"]
        result["gitlab_username"] = gitlab_username

        # Step 2: Create project (root-level)
        project = await self._client.create_project(
            name=workspace_name,
            description=f"Argus Insight workspace: {workspace_name}",
        )
        logger.info("GitLab project created: %s (id=%d)", project["path_with_namespace"], project["id"])

        ctx.set("gitlab_project_id", project["id"])
        result["gitlab_project_id"] = project["id"]

        # Step 3: Add user as project member (Maintainer)
        await self._client.add_project_member(
            project_id=project["id"],
            user_id=gitlab_user["id"],
            access_level=40,  # Maintainer
        )
        result["member_added"] = True

        # Step 4: Create project access token for this user
        token_name = f"{gitlab_username}-{workspace_name}"
        try:
            token_info = await self._client.create_project_access_token(
                project_id=project["id"],
                name=token_name,
            )
            result["gitlab_token_name"] = token_name
            result["gitlab_access_token_created"] = True

            # Save token to workspace member record
            async with async_session() as db_session:
                from workspace_provisioner.models import ArgusWorkspaceMember
                member_result = await db_session.execute(
                    select(ArgusWorkspaceMember).where(
                        ArgusWorkspaceMember.workspace_id == ctx.workspace_id,
                        ArgusWorkspaceMember.user_id == ctx.get("admin_user_id"),
                    )
                )
                member = member_result.scalars().first()
                if member:
                    member.gitlab_access_token = token_info["token"]
                    member.gitlab_token_name = token_name
                    await db_session.commit()
                    logger.info(
                        "GitLab access token saved for user in workspace %d",
                        ctx.workspace_id,
                    )
        except Exception as e:
            logger.warning("Failed to create project access token: %s", e)
            result["gitlab_access_token_created"] = False

        # Step 5: Store workspace URL
        workspace_url = project["web_url"]
        ctx.set("gitlab_workspace_url", workspace_url)
        result["gitlab_workspace_url"] = workspace_url

        # Register service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-gitlab",
            display_name="GitLab Project",
            version=None,
            endpoint=workspace_url,
            username=gitlab_username,
            access_token=token_info["token"] if "token_info" in dir() and token_info else None,
            metadata={
                "display": {},
                "internal": {
                    "project_id": project["id"],
                },
            },
        )

        return result

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Delete the GitLab project if it was created."""
        project_id = ctx.get("gitlab_project_id")
        if project_id:
            try:
                await self._client.delete_project(project_id)
                logger.info("Rolled back GitLab project: id=%d", project_id)
            except Exception as e:
                logger.warning("Rollback GitLab project failed: %s", e)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete the GitLab project during workspace deletion."""
        project_id = ctx.get("gitlab_project_id")
        if not project_id:
            logger.warning("GitLab project ID not found, skipping teardown")
            return None
        try:
            await self._client.delete_project(project_id)
            logger.info("Teardown GitLab project: id=%d", project_id)
            return {"project_id": project_id, "deleted": True}
        except Exception as e:
            logger.warning("GitLab project deletion failed: %s", e)
            return {"project_id": project_id, "deleted": False, "error": str(e)}
