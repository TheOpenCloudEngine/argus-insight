"""Workflow step: Create a workspace-dedicated MinIO bucket and grant member access.

This step:
1. Loads global MinIO connection from Settings > Argus > Object Storage.
2. Creates a bucket named {prefix}{workspace_name} (e.g., workspace-aaa).
3. For each workspace member, creates a MinIO user and grants readwrite policy.
4. Stores bucket name and endpoint in the workflow context.
"""

import json
import logging
import secrets
import tempfile

from workspace_provisioner.config import MinioWorkspaceConfig
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


class MinioWorkspaceStep(WorkflowStep):
    """Create workspace bucket and grant member access in global MinIO.

    Reads from context:
        - workspace_name
        - workspace_id
        - admin_user_id (optional)
        - argus_minio_workspace_config (optional MinioWorkspaceConfig)

    Writes to context:
        - minio_workspace_bucket
        - minio_workspace_endpoint
    """

    @property
    def name(self) -> str:
        return "argus-minio-workspace"

    async def _get_minio_settings(self) -> dict:
        """Load MinIO settings from DB."""
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

    async def _get_workspace_members(self, workspace_id: int) -> list[dict]:
        """Load workspace members with user info."""
        from sqlalchemy import select
        from app.core.database import async_session
        from app.usermgr.models import ArgusUser
        from workspace_provisioner.models import ArgusWorkspaceMember

        async with async_session() as session:
            result = await session.execute(
                select(ArgusWorkspaceMember).where(
                    ArgusWorkspaceMember.workspace_id == workspace_id
                )
            )
            members = result.scalars().all()

            member_list = []
            for m in members:
                user_result = await session.execute(
                    select(ArgusUser).where(ArgusUser.id == m.user_id)
                )
                user = user_result.scalars().first()
                if user:
                    member_list.append({
                        "user_id": m.user_id,
                        "username": user.username,
                        "member_id": m.id,
                    })
            return member_list

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        from workspace_provisioner.minio.client import MinioAdminClient

        workspace_name = ctx.workspace_name
        workspace_id = ctx.workspace_id
        config: MinioWorkspaceConfig = ctx.get(
            "argus_minio_workspace_config", MinioWorkspaceConfig()
        )

        # Step 1: Load global MinIO settings
        minio_cfg = await self._get_minio_settings()
        endpoint = minio_cfg["endpoint"]
        root_access = minio_cfg["access_key"]
        root_secret = minio_cfg["secret_key"]
        use_ssl = minio_cfg["use_ssl"] == "true"

        if not endpoint or not root_access:
            raise RuntimeError(
                "MinIO not configured. Set Object Storage in Settings > Argus."
            )

        # Strip protocol for MinIO SDK
        minio_endpoint = endpoint.replace("http://", "").replace("https://", "")

        client = MinioAdminClient(
            endpoint=minio_endpoint,
            root_user=root_access,
            root_password=root_secret,
            secure=use_ssl,
        )

        bucket_name = f"{config.bucket_prefix}{workspace_name}"
        result = {
            "bucket_name": bucket_name,
            "endpoint": endpoint,
            "members_provisioned": [],
        }

        # Step 2: Create workspace bucket
        await client.create_bucket(bucket_name)
        logger.info("Workspace bucket created: %s", bucket_name)

        # Step 3: Grant access to workspace members
        if config.create_user_per_member:
            members = await self._get_workspace_members(workspace_id)

            for member in members:
                username = member["username"]
                minio_username = f"user-{username}"

                try:
                    # Create MinIO user (or skip if exists)
                    user_secret = secrets.token_urlsafe(16)
                    user_info = await client.create_user(minio_username, user_secret)

                    # Set bucket policy
                    await client.set_user_bucket_policy(minio_username, bucket_name)

                    # Save credentials to workspace member
                    from sqlalchemy import select
                    from app.core.database import async_session
                    from workspace_provisioner.models import ArgusWorkspaceMember

                    if user_info.get("created"):
                        async with async_session() as session:
                            member_result = await session.execute(
                                select(ArgusWorkspaceMember).where(
                                    ArgusWorkspaceMember.id == member["member_id"]
                                )
                            )
                            ws_member = member_result.scalars().first()
                            if ws_member:
                                # Also update user's s3 credentials if not set
                                from app.usermgr.models import ArgusUser
                                user_result = await session.execute(
                                    select(ArgusUser).where(ArgusUser.id == member["user_id"])
                                )
                                user = user_result.scalars().first()
                                if user and not user.s3_access_key:
                                    user.s3_access_key = minio_username
                                    user.s3_secret_key = user_secret
                                    user.s3_bucket = bucket_name
                                await session.commit()

                    result["members_provisioned"].append({
                        "username": username,
                        "minio_user": minio_username,
                        "created": user_info.get("created", False),
                    })
                    logger.info(
                        "MinIO access granted: user=%s bucket=%s",
                        minio_username, bucket_name,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to provision MinIO access for %s: %s",
                        username, e,
                    )
                    result["members_provisioned"].append({
                        "username": username,
                        "error": str(e),
                    })

        # Step 4: Store in context
        ctx.set("minio_workspace_bucket", bucket_name)
        ctx.set("minio_workspace_endpoint", endpoint)

        # Register service
        from workspace_provisioner.service import register_workspace_service
        await register_workspace_service(
            workspace_id=ctx.workspace_id,
            plugin_name="argus-minio-workspace",
            display_name="MinIO Workspace Bucket",
            version="2025.02.28",
            endpoint=endpoint,
            metadata={
                "display": {},
                "internal": {
                    "bucket": bucket_name,
                    "members": len(result.get("members_provisioned", [])),
                },
            },
        )

        return result

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Delete the workspace bucket on failure."""
        bucket_name = ctx.get("minio_workspace_bucket")
        if not bucket_name:
            return
        try:
            from workspace_provisioner.minio.client import MinioAdminClient
            minio_cfg = await self._get_minio_settings()
            minio_endpoint = minio_cfg["endpoint"].replace("http://", "").replace("https://", "")
            client = MinioAdminClient(
                endpoint=minio_endpoint,
                root_user=minio_cfg["access_key"],
                root_password=minio_cfg["secret_key"],
                secure=minio_cfg["use_ssl"] == "true",
            )
            await client.drain_bucket(bucket_name)
            await client.delete_bucket(bucket_name)
            logger.info("Rolled back workspace bucket: %s", bucket_name)
        except Exception as e:
            logger.warning("Rollback workspace bucket failed: %s", e)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete workspace bucket and remove user policies on workspace deletion."""
        bucket_name = ctx.get("minio_workspace_bucket")
        if not bucket_name:
            logger.warning("No workspace bucket found in context, skipping teardown")
            return None

        try:
            from workspace_provisioner.minio.client import MinioAdminClient
            minio_cfg = await self._get_minio_settings()
            minio_endpoint = minio_cfg["endpoint"].replace("http://", "").replace("https://", "")
            client = MinioAdminClient(
                endpoint=minio_endpoint,
                root_user=minio_cfg["access_key"],
                root_password=minio_cfg["secret_key"],
                secure=minio_cfg["use_ssl"] == "true",
            )

            # Drain and delete bucket
            drained = await client.drain_bucket(bucket_name)
            await client.delete_bucket(bucket_name)
            logger.info("Teardown workspace bucket: %s (%d objects removed)", bucket_name, drained)
            return {"bucket": bucket_name, "deleted": True, "objects_removed": drained}
        except Exception as e:
            logger.warning("Teardown workspace bucket failed: %s", e)
            return {"bucket": bucket_name, "deleted": False, "error": str(e)}
