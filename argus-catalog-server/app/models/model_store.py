"""Model artifact store — S3/MinIO backend with OCI manifest support.

Handles:
  - Upload model files to S3 (direct or via presigned URL)
  - Download model files from S3 (presigned URL)
  - Generate OCI-compatible manifest.json
  - Import models from HuggingFace Hub
  - Content-addressable storage using SHA256 digests
"""

import datetime as _dt
import hashlib
import json
import logging
import tempfile
from pathlib import Path

from app.core.config import settings
from app.core.s3 import ensure_bucket, get_s3_client

logger = logging.getLogger(__name__)


# =========================================================================== #
# Helpers
# =========================================================================== #


def _s3_prefix(model_name: str, version: int) -> str:
    """Build the S3 key prefix for a model version."""
    return f"{model_name}/v{version}/"


def _sha256_bytes(data: bytes) -> str:
    """Compute SHA256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _media_type_for_file(filename: str) -> str:
    """Map filename to OCI media type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "pkl": "application/vnd.argus.model.weights",
        "bin": "application/vnd.argus.model.weights",
        "safetensors": "application/vnd.argus.model.weights.safetensors",
        "pt": "application/vnd.argus.model.weights.pytorch",
        "onnx": "application/vnd.argus.model.weights.onnx",
        "json": "application/vnd.argus.model.config+json",
        "yaml": "application/vnd.argus.model.config+yaml",
        "yml": "application/vnd.argus.model.config+yaml",
        "txt": "application/vnd.argus.model.metadata+text",
        "md": "application/vnd.argus.model.metadata+text",
    }
    # Special filenames
    name_mapping = {
        "MLmodel": "application/vnd.argus.model.mlflow.mlmodel+yaml",
        "conda.yaml": "application/vnd.argus.model.mlflow.conda+yaml",
        "python_env.yaml": "application/vnd.argus.model.mlflow.python-env+yaml",
        "requirements.txt": "application/vnd.argus.model.mlflow.requirements+text",
        "config.json": "application/vnd.argus.model.config+json",
        "tokenizer.json": "application/vnd.argus.model.tokenizer+json",
        "tokenizer_config.json": "application/vnd.argus.model.tokenizer-config+json",
    }
    return name_mapping.get(filename, mapping.get(ext, "application/octet-stream"))


# =========================================================================== #
# 1. Upload files to S3
# =========================================================================== #


async def upload_file(
    model_name: str,
    version: int,
    filename: str,
    data: bytes,
    bucket: str | None = None,
) -> dict:
    """Upload a single file to S3 under the model version prefix."""
    bucket = bucket or settings.os_bucket
    await ensure_bucket(bucket)
    key = _s3_prefix(model_name, version) + filename
    digest = _sha256_bytes(data)

    async with get_s3_client() as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            Metadata={"sha256": digest},
        )

    logger.info("Uploaded: s3://%s/%s (%d bytes, sha256=%s)", bucket, key, len(data), digest[:12])
    return {"key": key, "size": len(data), "sha256": digest}


async def upload_files(
    model_name: str,
    version: int,
    files: list[tuple[str, bytes]],
    bucket: str | None = None,
) -> list[dict]:
    """Upload multiple files. Each item is (filename, data)."""
    results = []
    for filename, data in files:
        result = await upload_file(model_name, version, filename, data, bucket)
        results.append(result)
    return results


# =========================================================================== #
# 2. Presigned URLs
# =========================================================================== #


async def generate_upload_url(
    model_name: str,
    version: int,
    filename: str,
    bucket: str | None = None,
) -> dict:
    """Generate a presigned PUT URL for direct upload to S3."""
    bucket = bucket or settings.os_bucket
    await ensure_bucket(bucket)
    key = _s3_prefix(model_name, version) + filename
    expiry = settings.os_presigned_url_expiry

    async with get_s3_client() as s3:
        url = await s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )

    return {"url": url, "key": key, "expires_in": expiry}


async def generate_download_url(
    model_name: str,
    version: int,
    filename: str,
    bucket: str | None = None,
) -> dict:
    """Generate a presigned GET URL for downloading a file."""
    bucket = bucket or settings.os_bucket
    key = _s3_prefix(model_name, version) + filename
    expiry = settings.os_presigned_url_expiry

    async with get_s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )

    return {"url": url, "key": key, "expires_in": expiry}


async def generate_download_urls(
    model_name: str,
    version: int,
    bucket: str | None = None,
) -> dict[str, str]:
    """Generate presigned download URLs for all files in a version."""
    bucket = bucket or settings.os_bucket
    prefix = _s3_prefix(model_name, version)
    expiry = settings.os_presigned_url_expiry

    async with get_s3_client() as s3:
        resp = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        urls = {}
        for obj in resp.get("Contents", []):
            filename = obj["Key"][len(prefix):]
            if not filename or filename.endswith("/"):
                continue
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": obj["Key"]},
                ExpiresIn=expiry,
            )
            urls[filename] = url

    return urls


# =========================================================================== #
# 3. List / Stat files
# =========================================================================== #


async def list_files(
    model_name: str,
    version: int,
    bucket: str | None = None,
) -> list[dict]:
    """List all files for a model version in S3."""
    bucket = bucket or settings.os_bucket
    prefix = _s3_prefix(model_name, version)

    async with get_s3_client() as s3:
        resp = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    files = []
    for obj in resp.get("Contents", []):
        filename = obj["Key"][len(prefix):]
        if not filename or filename.endswith("/"):
            continue
        files.append({
            "filename": filename,
            "key": obj["Key"],
            "size": obj.get("Size", 0),
            "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else "",
        })
    return files


async def get_total_size(
    model_name: str,
    version: int,
    bucket: str | None = None,
) -> tuple[int, int]:
    """Return (file_count, total_size_bytes) for a model version."""
    files = await list_files(model_name, version, bucket)
    return len(files), sum(f["size"] for f in files)


# =========================================================================== #
# 4. OCI Manifest Generation
# =========================================================================== #


async def generate_manifest(
    model_name: str,
    version: int,
    annotations: dict[str, str] | None = None,
    bucket: str | None = None,
) -> dict:
    """Generate an OCI-compatible manifest.json for a model version.

    Scans all files in S3 under the version prefix, computes digests,
    and builds a manifest following the OCI Image Manifest spec.
    """
    bucket = bucket or settings.os_bucket
    prefix = _s3_prefix(model_name, version)

    layers = []
    config_digest = None
    config_size = 0

    async with get_s3_client() as s3:
        resp = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in resp.get("Contents", []):
            filename = obj["Key"][len(prefix):]
            if not filename or filename.endswith("/"):
                continue

            size = obj.get("Size", 0)

            # Read file to compute digest
            file_resp = await s3.get_object(Bucket=bucket, Key=obj["Key"])
            data = await file_resp["Body"].read()
            digest = f"sha256:{_sha256_bytes(data)}"

            media_type = _media_type_for_file(filename)

            layer = {
                "mediaType": media_type,
                "digest": digest,
                "size": size,
                "annotations": {
                    "org.opencontainers.image.title": filename,
                },
            }
            layers.append(layer)

            # Use config.json or MLmodel as the config descriptor
            if filename in ("config.json", "MLmodel") and config_digest is None:
                config_digest = digest
                config_size = size

    # If no config file found, create an empty config
    if config_digest is None:
        empty_config = json.dumps({"model_name": model_name, "version": version}).encode()
        config_digest = f"sha256:{_sha256_bytes(empty_config)}"
        config_size = len(empty_config)

    base_annotations = {
        "org.opencontainers.image.created": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "ai.argus.model.name": model_name,
        "ai.argus.model.version": str(version),
    }
    if annotations:
        base_annotations.update(annotations)

    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.argus.model.config.v1+json",
            "digest": config_digest,
            "size": config_size,
        },
        "layers": layers,
        "annotations": base_annotations,
    }

    # Store manifest in S3
    manifest_json = json.dumps(manifest, indent=2).encode()
    manifest_key = prefix + "manifest.json"
    async with get_s3_client() as s3:
        await s3.put_object(Bucket=bucket, Key=manifest_key, Body=manifest_json)

    logger.info(
        "OCI manifest generated: %s v%d (%d layers, %d bytes)",
        model_name, version, len(layers), sum(l["size"] for l in layers),
    )
    return manifest


# =========================================================================== #
# 5. Download / Pull
# =========================================================================== #


async def download_file(
    model_name: str,
    version: int,
    filename: str,
    bucket: str | None = None,
) -> bytes:
    """Download a single file from S3."""
    bucket = bucket or settings.os_bucket
    key = _s3_prefix(model_name, version) + filename

    async with get_s3_client() as s3:
        resp = await s3.get_object(Bucket=bucket, Key=key)
        return await resp["Body"].read()


async def download_all(
    model_name: str,
    version: int,
    dest_dir: str | Path,
    bucket: str | None = None,
) -> list[str]:
    """Download all files for a model version to a local directory."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    files = await list_files(model_name, version, bucket)

    downloaded = []
    for f in files:
        data = await download_file(model_name, version, f["filename"], bucket)
        file_path = dest / f["filename"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        downloaded.append(str(file_path))

    logger.info("Downloaded %d files to %s", len(downloaded), dest)
    return downloaded


# =========================================================================== #
# 6. Delete
# =========================================================================== #


async def delete_version_files(
    model_name: str,
    version: int,
    bucket: str | None = None,
) -> int:
    """Delete all files for a model version from S3."""
    bucket = bucket or settings.os_bucket
    prefix = _s3_prefix(model_name, version)

    async with get_s3_client() as s3:
        resp = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = resp.get("Contents", [])
        if not objects:
            return 0

        await s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
        )

    logger.info("Deleted %d objects from s3://%s/%s", len(objects), bucket, prefix)
    return len(objects)


async def delete_model_files(
    model_name: str,
    bucket: str | None = None,
) -> int:
    """Delete all files for a model (all versions) from S3."""
    bucket = bucket or settings.os_bucket
    prefix = f"{model_name}/"

    async with get_s3_client() as s3:
        total = 0
        continuation = None
        while True:
            params = {"Bucket": bucket, "Prefix": prefix}
            if continuation:
                params["ContinuationToken"] = continuation
            resp = await s3.list_objects_v2(**params)
            objects = resp.get("Contents", [])
            if objects:
                await s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                )
                total += len(objects)
            if not resp.get("IsTruncated"):
                break
            continuation = resp.get("NextContinuationToken")

    logger.info("Deleted %d objects from s3://%s/%s", total, bucket, prefix)
    return total


# =========================================================================== #
# 7. HuggingFace Import
# =========================================================================== #


async def import_from_huggingface(
    hf_model_id: str,
    model_name: str,
    version: int,
    revision: str = "main",
    bucket: str | None = None,
) -> dict:
    """Download a model from HuggingFace Hub and upload to S3.

    Uses huggingface_hub library to download all model files,
    then uploads each file to S3 under the model version prefix.

    Returns metadata about the imported model.
    """
    from huggingface_hub import snapshot_download

    logger.info("Importing HuggingFace model: %s (revision=%s) -> %s v%d",
                hf_model_id, revision, model_name, version)

    # Download to temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_dir = snapshot_download(
            repo_id=hf_model_id,
            revision=revision,
            local_dir=tmp_dir,
        )
        local_path = Path(local_dir)

        # Collect all files
        all_files: list[tuple[str, bytes]] = []
        total_size = 0
        for file_path in sorted(local_path.rglob("*")):
            if file_path.is_file():
                # Skip .git internals
                rel = file_path.relative_to(local_path)
                if str(rel).startswith("."):
                    continue
                data = file_path.read_bytes()
                all_files.append((str(rel), data))
                total_size += len(data)

        logger.info("Downloaded %d files from HuggingFace (%d bytes total)",
                    len(all_files), total_size)

        # Upload to S3
        results = await upload_files(model_name, version, all_files, bucket)

        # Parse config.json if present for metadata
        metadata = {
            "source": f"huggingface:{hf_model_id}",
            "revision": revision,
            "file_count": len(results),
            "total_size": total_size,
        }

        config_path = local_path / "config.json"
        if config_path.is_file():
            try:
                config = json.loads(config_path.read_text())
                metadata["model_type"] = config.get("model_type")
                metadata["architectures"] = config.get("architectures")
                metadata["torch_dtype"] = config.get("torch_dtype")
                metadata["transformers_version"] = config.get("transformers_version")
            except Exception:
                pass

    # Generate OCI manifest
    annotations = {
        "ai.argus.model.source": f"huggingface:{hf_model_id}",
        "ai.argus.model.source.revision": revision,
    }
    if metadata.get("model_type"):
        annotations["ai.argus.model.type"] = metadata["model_type"]

    manifest = await generate_manifest(model_name, version, annotations, bucket)
    metadata["manifest"] = manifest

    logger.info("HuggingFace import complete: %s -> %s v%d (%d files, %d bytes)",
                hf_model_id, model_name, version, len(results), total_size)
    return metadata


async def import_from_local_directory(
    local_dir: str | Path,
    model_name: str,
    version: int,
    source: str = "local",
    bucket: str | None = None,
) -> dict:
    """Import model files from a local directory to S3.

    Used for airgap scenarios: files are transferred via USB/SCP first,
    then imported from the local filesystem into MinIO.
    """
    local_path = Path(local_dir)
    if not local_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {local_path}")

    all_files: list[tuple[str, bytes]] = []
    total_size = 0
    for file_path in sorted(local_path.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(local_path)
            if str(rel).startswith("."):
                continue
            data = file_path.read_bytes()
            all_files.append((str(rel), data))
            total_size += len(data)

    logger.info("Importing %d files from %s (%d bytes)", len(all_files), local_path, total_size)

    results = await upload_files(model_name, version, all_files, bucket)

    annotations = {"ai.argus.model.source": source}
    manifest = await generate_manifest(model_name, version, annotations, bucket)

    return {
        "source": source,
        "file_count": len(results),
        "total_size": total_size,
        "manifest": manifest,
    }
