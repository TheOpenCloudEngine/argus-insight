"""Workflow step: Set up MinIO bucket and workspace admin user.

This step runs after MinioDeployStep and:
1. Connects to the deployed MinIO instance using root credentials.
2. Creates a default bucket named after the workspace.
3. Creates a dedicated user for the WorkspaceAdmin.
4. Assigns a read-write policy scoped to the workspace bucket.

The WorkspaceAdmin user gets S3-compatible credentials that can be
used in Airflow connections, Jupyter notebooks, VS Code extensions, etc.
"""

import logging
import secrets
import string

from workspace_provisioner.minio.client import MinioAdminClient
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

logger = logging.getLogger(__name__)


def _generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key for MinIO user."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class MinioSetupStep(WorkflowStep):
    """Create default bucket and workspace admin user in MinIO.

    Reads from context:
        - workspace_name: Used as the default bucket name.
        - minio_endpoint: Internal K8s service endpoint (from MinioDeployStep).
        - minio_root_user: Root admin username (from MinioDeployStep).
        - minio_root_password: Root admin password (from MinioDeployStep).

    Writes to context:
        - minio_default_bucket: Name of the created default bucket.
        - minio_ws_admin_access_key: WorkspaceAdmin's S3 access key.
        - minio_ws_admin_secret_key: WorkspaceAdmin's S3 secret key.
    """

    @property
    def name(self) -> str:
        return "minio-setup"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        endpoint = ctx.get("minio_endpoint")
        root_user = ctx.get("minio_root_user")
        root_password = ctx.get("minio_root_password")

        if not endpoint or not root_user or not root_password:
            logger.error("MinIO endpoint/credentials not found in context for workspace '%s'", workspace_name)
            raise RuntimeError(
                "MinIO endpoint/credentials not found in context. "
                "Ensure MinioDeployStep runs before MinioSetupStep."
            )

        # Connect to MinIO
        client = MinioAdminClient(
            endpoint=endpoint,
            root_user=root_user,
            root_password=root_password,
        )

        # Step 1: Create default bucket (workspace name)
        bucket_name = workspace_name
        logger.info("Creating default bucket: %s", bucket_name)
        bucket_result = await client.create_bucket(bucket_name, versioning=True)

        # Step 2: Create WorkspaceAdmin user
        ws_admin_access_key = f"ws-{workspace_name}-admin"
        ws_admin_secret_key = _generate_secret_key()
        logger.info("Creating workspace admin user: %s", ws_admin_access_key)
        user_result = await client.create_user(ws_admin_access_key, ws_admin_secret_key)

        # Step 3: Assign read-write policy on the workspace bucket
        logger.info(
            "Assigning read-write policy for user '%s' on bucket '%s'",
            ws_admin_access_key,
            bucket_name,
        )
        await client.set_user_bucket_policy(ws_admin_access_key, bucket_name)

        # Store credentials in context
        ctx.set("minio_default_bucket", bucket_name)
        ctx.set("minio_ws_admin_access_key", ws_admin_access_key)
        ctx.set("minio_ws_admin_secret_key", ws_admin_secret_key)

        return {
            "default_bucket": bucket_name,
            "bucket_created": bucket_result.get("created", False),
            "ws_admin_access_key": ws_admin_access_key,
            "user_created": user_result.get("created", False),
        }

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Delete the workspace admin user and default bucket."""
        endpoint = ctx.get("minio_endpoint")
        root_user = ctx.get("minio_root_user")
        root_password = ctx.get("minio_root_password")

        if not endpoint or not root_user or not root_password:
            return

        try:
            client = MinioAdminClient(
                endpoint=endpoint,
                root_user=root_user,
                root_password=root_password,
            )

            # Delete user first
            ws_admin_key = ctx.get("minio_ws_admin_access_key")
            if ws_admin_key:
                await client.delete_user(ws_admin_key)

            # Delete bucket
            bucket_name = ctx.get("minio_default_bucket")
            if bucket_name:
                await client.delete_bucket(bucket_name)

            logger.info(
                "Rolled back MinIO setup for workspace '%s'",
                ctx.workspace_name,
            )
        except Exception as e:
            logger.error("MinIO setup rollback failed: %s", e)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Delete user, drain all bucket objects, then delete bucket.

        Unlike rollback() which expects an empty bucket (just created),
        teardown() handles production buckets with data by draining
        all objects first.
        """
        endpoint = ctx.get("minio_endpoint")
        root_user = ctx.get("minio_root_user")
        root_password = ctx.get("minio_root_password")

        if not endpoint or not root_user or not root_password:
            logger.warning(
                "MinIO credentials not available for teardown of workspace '%s'",
                ctx.workspace_name,
            )
            return None

        client = MinioAdminClient(
            endpoint=endpoint,
            root_user=root_user,
            root_password=root_password,
        )

        result = {}

        # 1. Delete user
        ws_admin_key = ctx.get("minio_ws_admin_access_key")
        if ws_admin_key:
            await client.delete_user(ws_admin_key)
            result["user_deleted"] = ws_admin_key

        # 2. Drain and delete bucket
        bucket_name = ctx.get("minio_default_bucket")
        if bucket_name:
            objects_deleted = await client.drain_bucket(bucket_name)
            await client.delete_bucket(bucket_name)
            result["bucket_deleted"] = bucket_name
            result["objects_drained"] = objects_deleted

        logger.info(
            "Teardown MinIO setup for workspace '%s': %s",
            ctx.workspace_name, result,
        )
        return result
