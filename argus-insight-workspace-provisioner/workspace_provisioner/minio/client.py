"""MinIO admin client for workspace user and bucket management.

Provides async-friendly operations for:
- Bucket creation/deletion
- User creation/deletion with access key credentials
- Policy assignment (read-write access scoped to a specific bucket)

Uses the MinIO Python SDK (minio) with synchronous calls wrapped in
a thread executor to avoid blocking the async event loop.

Usage:
    client = MinioAdminClient(
        endpoint="minio-my-ws.argus-insight.dev.net:9000",
        root_user="minioadmin",
        root_password="minioadmin123",
    )
    await client.create_bucket("my-workspace")
    await client.create_user("ws-admin", "secretpass123")
    await client.set_user_bucket_policy("ws-admin", "my-workspace")
"""

import asyncio
import json
import logging
from functools import partial

from minio import Minio
from minio.commonconfig import ENABLED
from minio.versioningconfig import VersioningConfig

logger = logging.getLogger(__name__)


def _build_readwrite_policy(bucket_name: str) -> dict:
    """Build an S3 bucket policy granting full read/write access to a bucket.

    Args:
        bucket_name: Target bucket name.

    Returns:
        S3 policy document as a dict.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:ListMultipartUploadParts",
                    "s3:AbortMultipartUpload",
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            }
        ],
    }


class MinioAdminClient:
    """MinIO admin operations for workspace provisioning.

    Wraps the minio Python SDK for bucket, user, and policy management.
    All methods are async-safe by running sync calls in a thread executor.
    """

    def __init__(
        self,
        endpoint: str,
        root_user: str,
        root_password: str,
        secure: bool = False,
    ) -> None:
        """Initialize MinIO client with root credentials.

        Args:
            endpoint: MinIO endpoint (host:port, e.g., "minio-my-ws:9000").
            root_user: Root admin username.
            root_password: Root admin password.
            secure: Whether to use HTTPS.
        """
        self._endpoint = endpoint
        self._client = Minio(
            endpoint=endpoint,
            access_key=root_user,
            secret_key=root_password,
            secure=secure,
        )
        logger.info("MinIO admin client connected: %s", endpoint)

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the default thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    # -----------------------------------------------------------------------
    # Bucket operations
    # -----------------------------------------------------------------------

    async def create_bucket(
        self, bucket_name: str, versioning: bool = False
    ) -> dict:
        """Create a bucket if it does not exist.

        Args:
            bucket_name: Name of the bucket to create.
            versioning: Whether to enable versioning on the bucket.

        Returns:
            Dict with bucket name and creation status.
        """
        exists = await self._run_sync(self._client.bucket_exists, bucket_name)
        if exists:
            logger.info("MinIO bucket already exists: %s", bucket_name)
            return {"bucket": bucket_name, "created": False}

        await self._run_sync(self._client.make_bucket, bucket_name)
        logger.info("MinIO bucket created: %s", bucket_name)

        if versioning:
            config = VersioningConfig(ENABLED)
            await self._run_sync(
                self._client.set_bucket_versioning, bucket_name, config
            )
            logger.info("MinIO bucket versioning enabled: %s", bucket_name)

        return {"bucket": bucket_name, "created": True}

    async def delete_bucket(self, bucket_name: str) -> None:
        """Delete a bucket.

        Note: The bucket must be empty before deletion.

        Args:
            bucket_name: Name of the bucket to delete.
        """
        exists = await self._run_sync(self._client.bucket_exists, bucket_name)
        if not exists:
            logger.info("MinIO bucket does not exist, skip delete: %s", bucket_name)
            return

        await self._run_sync(self._client.remove_bucket, bucket_name)
        logger.info("MinIO bucket deleted: %s", bucket_name)

    async def set_bucket_policy(self, bucket_name: str, policy: dict) -> None:
        """Set a bucket policy.

        Args:
            bucket_name: Target bucket.
            policy: S3 policy document as a dict.
        """
        policy_json = json.dumps(policy)
        await self._run_sync(
            self._client.set_bucket_policy, bucket_name, policy_json
        )
        logger.info("MinIO bucket policy set: %s", bucket_name)

    # -----------------------------------------------------------------------
    # User operations via mc admin (subprocess)
    # -----------------------------------------------------------------------

    async def _mc_admin(self, *args: str) -> str:
        """Execute an mc admin command.

        Uses the MinIO Client (mc) CLI for admin operations that are
        not available in the minio Python SDK (user management, policy).

        Args:
            *args: mc admin subcommand and arguments.

        Returns:
            stdout from the mc command.

        Raises:
            RuntimeError: If mc exits with non-zero code.
        """
        # Configure mc alias for this endpoint
        alias = "provisioner"
        setup_cmd = [
            "mc", "alias", "set", alias,
            f"http://{self._endpoint}",
            self._client._provider._credentials.access_key,
            self._client._provider._credentials.secret_key,
        ]
        proc = await asyncio.create_subprocess_exec(
            *setup_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Run the actual admin command
        cmd = ["mc", "admin", *args]
        # Replace target references with alias
        cmd = [c.replace("TARGET", alias) for c in cmd]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode().strip()
        stderr_str = stderr.decode().strip()

        if proc.returncode != 0:
            logger.error("mc admin command failed (rc=%d): %s", proc.returncode, stderr_str)
            raise RuntimeError(f"mc admin command failed: {stderr_str}")

        return stdout_str

    async def create_user(self, access_key: str, secret_key: str) -> dict:
        """Create a MinIO user with the given credentials.

        Args:
            access_key: Username / access key for the new user.
            secret_key: Password / secret key (min 8 characters).

        Returns:
            Dict with access_key and creation status.
        """
        try:
            await self._mc_admin("user", "add", "TARGET", access_key, secret_key)
            logger.info("MinIO user created: %s", access_key)
            return {"access_key": access_key, "created": True}
        except RuntimeError as e:
            if "already exists" in str(e).lower():
                logger.info("MinIO user already exists: %s", access_key)
                return {"access_key": access_key, "created": False}
            raise

    async def delete_user(self, access_key: str) -> None:
        """Delete a MinIO user.

        Args:
            access_key: Username / access key to delete.
        """
        try:
            await self._mc_admin("user", "remove", "TARGET", access_key)
            logger.info("MinIO user deleted: %s", access_key)
        except RuntimeError:
            logger.warning("MinIO user delete failed (may not exist): %s", access_key)

    async def set_user_bucket_policy(
        self, access_key: str, bucket_name: str
    ) -> None:
        """Create and assign a read-write policy for a user on a specific bucket.

        Creates a policy named "rw-<bucket_name>" that grants full
        read/write access to the bucket, then assigns it to the user.

        Args:
            access_key: Target user's access key.
            bucket_name: Bucket to grant access to.
        """
        policy_name = f"rw-{bucket_name}"
        policy_doc = _build_readwrite_policy(bucket_name)

        # Create policy file via mc admin
        # mc admin policy create requires a JSON file, so we write to a temp approach
        # using mc admin policy create <alias> <policy_name> /dev/stdin
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(policy_doc, f)
            policy_file = f.name

        try:
            await self._mc_admin(
                "policy", "create", "TARGET", policy_name, policy_file
            )
            logger.info("MinIO policy created: %s", policy_name)
        except RuntimeError as e:
            if "already exists" not in str(e).lower():
                raise
            logger.info("MinIO policy already exists: %s", policy_name)

        # Attach policy to user
        await self._mc_admin(
            "policy", "attach", "TARGET", policy_name,
            "--user", access_key,
        )
        logger.info(
            "MinIO policy '%s' attached to user '%s'", policy_name, access_key
        )

        # Clean up temp file
        import os
        os.unlink(policy_file)
