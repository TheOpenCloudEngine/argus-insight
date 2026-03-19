"""Object file manager API endpoints.

Provides REST API for S3-compatible object storage operations:
  - Object CRUD (put, get, delete, copy, head, multi-delete)
  - Directory management (list, create folder)
  - Multipart upload (initiate, sign parts, complete, abort)
  - Presigned URLs (download, upload)
  - S3 Select (SQL query on CSV/JSON/Parquet)
  - Object tagging (get, put, delete)
"""

import logging
import mimetypes

from botocore.exceptions import (
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
)
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.objectfilemgr import service
from app.objectfilemgr.schemas import (
    AbortMultipartRequest,
    CompleteMultipartRequest,
    CompleteMultipartResponse,
    CopyObjectRequest,
    CopyObjectResponse,
    CreateFolderRequest,
    CreateFolderResponse,
    DeleteObjectsRequest,
    DeleteObjectsResponse,
    DocumentPreviewResponse,
    FilebrowserConfigResponse,
    HeadObjectResponse,
    ListObjectsResponse,
    MultipartUploadInitResponse,
    MultipartUploadUrlsRequest,
    MultipartUploadUrlsResponse,
    PresignedUploadUrlResponse,
    PresignedUrlResponse,
    PutTaggingRequest,
    S3SelectRequest,
    S3SelectResponse,
    TablePreviewResponse,
    TaggingResponse,
    UpdateBrowserSettingsRequest,
    UpdatePreviewCategoryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/objectfilemgr", tags=["objectfilemgr"])


def _bucket(bucket: str | None) -> str:
    """Resolve bucket name, falling back to the default."""
    return bucket or settings.s3_default_bucket


_S3_CONN_ERRORS = (
    ConnectionRefusedError,
    EndpointConnectionError,
    ConnectTimeoutError,
    ConnectionClosedError,
)


def _is_s3_connection_error(exc: Exception) -> bool:
    """Check if an exception is caused by S3/MinIO being unreachable."""
    if isinstance(exc, _S3_CONN_ERRORS):
        return True
    cause = exc.__cause__ or exc.__context__
    if cause and isinstance(cause, _S3_CONN_ERRORS):
        return True
    return False


def _raise_if_s3_unavailable(exc: Exception, context: str) -> None:
    """Raise HTTP 503 if the exception is an S3 connection error, else raise 500."""
    if _is_s3_connection_error(exc):
        logger.warning("Object storage unavailable (%s): %s", context, exc)
        raise HTTPException(
            status_code=503,
            detail="Object storage service (MinIO) is unavailable. "
            "Please check if the MinIO server is running.",
        )
    logger.error("%s error: %s", context, exc)
    raise HTTPException(status_code=500, detail=str(exc))


# =========================================================================== #
# File Browser Configuration
# =========================================================================== #


@router.get("/configuration", response_model=FilebrowserConfigResponse)
async def get_configuration(session: AsyncSession = Depends(get_session)):
    """Return File Browser configuration (browser settings + preview limits)."""
    try:
        return await service.get_filebrowser_config(session)
    except Exception as e:
        logger.error("get_configuration error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configuration/browser", status_code=204)
async def update_browser_settings(
    body: UpdateBrowserSettingsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update browser-level settings (sort_disable_threshold, max_keys_per_page, etc.)."""
    try:
        await service.update_browser_settings(session, body.browser)
    except Exception as e:
        logger.error("update_browser_settings error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configuration/preview", status_code=204)
async def update_preview_category(
    body: UpdatePreviewCategoryRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update a preview category's limits (max_file_size, max_preview_rows)."""
    try:
        await service.update_preview_category(
            session, body.category, body.max_file_size, body.max_preview_rows,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("update_preview_category error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# ListObjectsV2
# =========================================================================== #


@router.get("/objects", response_model=ListObjectsResponse)
async def list_objects(
    bucket: str | None = Query(None, description="Bucket name (default from config)"),
    prefix: str = Query("", description="Prefix (folder path)"),
    delimiter: str = Query("/", description="Hierarchy delimiter"),
    continuation_token: str | None = Query(None, description="Pagination token"),
    max_keys: int = Query(1000, ge=1, le=1000, description="Max items"),
):
    """List objects and folders under a prefix (ListObjectsV2)."""
    try:
        return await service.list_objects(
            bucket=_bucket(bucket),
            prefix=prefix,
            delimiter=delimiter,
            continuation_token=continuation_token,
            max_keys=max_keys,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "list_objects")


# =========================================================================== #
# HeadObject
# =========================================================================== #


@router.head("/objects/metadata")
@router.get("/objects/metadata", response_model=HeadObjectResponse)
async def head_object(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Get object metadata without downloading the body (HeadObject)."""
    try:
        return await service.head_object(bucket=_bucket(bucket), key=key)
    except Exception as e:
        if _is_s3_connection_error(e):
            _raise_if_s3_unavailable(e, "head_object")
        logger.error("head_object error: key=%s %s", key, e)
        raise HTTPException(status_code=404, detail=f"Object not found: {key}")


# =========================================================================== #
# GetObject (download)
# =========================================================================== #


@router.get("/objects/download")
async def get_object(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Download an object (GetObject). Returns the raw file bytes."""
    try:
        result = await service.get_object(bucket=_bucket(bucket), key=key)
    except Exception as e:
        if _is_s3_connection_error(e):
            _raise_if_s3_unavailable(e, "get_object")
        logger.error("get_object error: key=%s %s", key, e)
        raise HTTPException(status_code=404, detail=f"Object not found: {key}")

    filename = key.rsplit("/", 1)[-1]
    return Response(
        content=result["body"],
        media_type=result["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "ETag": result["etag"],
        },
    )


# =========================================================================== #
# PutObject (upload)
# =========================================================================== #


@router.post("/objects/upload")
async def put_object(
    file: UploadFile,
    key: str = Query(..., description="Destination object key"),
    bucket: str | None = Query(None),
):
    """Upload a file (PutObject).

    For files larger than the multipart threshold, the file is streamed to S3
    using multipart upload to avoid loading the entire file into memory.
    """
    content_type = file.content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
    threshold = settings.s3_multipart_threshold  # default 8 MB

    try:
        result = await service.put_object_stream(
            bucket=_bucket(bucket),
            key=key,
            file=file,
            content_type=content_type,
            multipart_threshold=threshold,
            chunk_size=settings.s3_multipart_chunksize,
        )
        return result
    except Exception as e:
        _raise_if_s3_unavailable(e, "put_object")


# =========================================================================== #
# DeleteObject / DeleteObjects
# =========================================================================== #


@router.delete("/objects")
async def delete_object(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Delete a single object (DeleteObject)."""
    try:
        await service.delete_object(bucket=_bucket(bucket), key=key)
        return {"deleted": key}
    except Exception as e:
        _raise_if_s3_unavailable(e, "delete_object")


@router.post("/objects/delete", response_model=DeleteObjectsResponse)
async def delete_objects(
    body: DeleteObjectsRequest,
    bucket: str | None = Query(None),
):
    """Delete multiple objects in one request (DeleteObjects, up to 1000)."""
    try:
        return await service.delete_objects(bucket=_bucket(bucket), keys=body.keys)
    except Exception as e:
        _raise_if_s3_unavailable(e, "delete_objects")


# =========================================================================== #
# CopyObject
# =========================================================================== #


@router.post("/objects/copy", response_model=CopyObjectResponse)
async def copy_object(
    body: CopyObjectRequest,
    bucket: str | None = Query(None),
):
    """Copy an object (CopyObject). Use copy + delete for move."""
    try:
        return await service.copy_object(
            bucket=_bucket(bucket),
            source_key=body.source_key,
            destination_key=body.destination_key,
            source_bucket=body.source_bucket,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "copy_object")


# =========================================================================== #
# Create folder
# =========================================================================== #


@router.post("/folders", response_model=CreateFolderResponse)
async def create_folder(
    body: CreateFolderRequest,
    bucket: str | None = Query(None),
):
    """Create a virtual folder (0-byte object with trailing slash)."""
    try:
        return await service.create_folder(bucket=_bucket(bucket), key=body.key)
    except Exception as e:
        _raise_if_s3_unavailable(e, "create_folder")


# =========================================================================== #
# Presigned URLs
# =========================================================================== #


@router.get("/objects/download-url", response_model=PresignedUrlResponse)
async def get_download_url(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Generate a presigned download URL."""
    try:
        return await service.generate_download_url(bucket=_bucket(bucket), key=key)
    except Exception as e:
        _raise_if_s3_unavailable(e, "generate_download_url")


@router.get("/objects/upload-url", response_model=PresignedUploadUrlResponse)
async def get_upload_url(
    key: str = Query(..., description="Destination key"),
    content_type: str = Query("application/octet-stream"),
    bucket: str | None = Query(None),
):
    """Generate a presigned upload URL for direct PUT."""
    try:
        return await service.generate_upload_url(
            bucket=_bucket(bucket), key=key, content_type=content_type,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "generate_upload_url")


# =========================================================================== #
# Multipart upload
# =========================================================================== #


@router.post("/multipart/initiate", response_model=MultipartUploadInitResponse)
async def initiate_multipart(
    key: str = Query(..., description="Object key"),
    content_type: str = Query("application/octet-stream"),
    bucket: str | None = Query(None),
):
    """Initiate a multipart upload."""
    try:
        return await service.initiate_multipart_upload(
            bucket=_bucket(bucket), key=key, content_type=content_type,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "initiate_multipart")


@router.post("/multipart/urls", response_model=MultipartUploadUrlsResponse)
async def get_multipart_urls(
    body: MultipartUploadUrlsRequest,
    bucket: str | None = Query(None),
):
    """Get presigned URLs for uploading individual parts."""
    try:
        return await service.get_multipart_upload_urls(
            bucket=_bucket(bucket),
            key=body.key,
            upload_id=body.upload_id,
            part_numbers=body.part_numbers,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "get_multipart_urls")


@router.post("/multipart/complete", response_model=CompleteMultipartResponse)
async def complete_multipart(
    body: CompleteMultipartRequest,
    bucket: str | None = Query(None),
):
    """Complete a multipart upload."""
    try:
        return await service.complete_multipart_upload(
            bucket=_bucket(bucket),
            key=body.key,
            upload_id=body.upload_id,
            parts=body.parts,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "complete_multipart")


@router.post("/multipart/abort")
async def abort_multipart(
    body: AbortMultipartRequest,
    bucket: str | None = Query(None),
):
    """Abort a multipart upload, discarding all uploaded parts."""
    try:
        await service.abort_multipart_upload(
            bucket=_bucket(bucket), key=body.key, upload_id=body.upload_id,
        )
        return {"status": "aborted", "key": body.key, "upload_id": body.upload_id}
    except Exception as e:
        _raise_if_s3_unavailable(e, "abort_multipart")


# =========================================================================== #
# S3 Select
# =========================================================================== #


@router.post("/objects/select", response_model=S3SelectResponse)
async def select_object_content(
    body: S3SelectRequest,
    bucket: str | None = Query(None),
):
    """Execute an S3 Select SQL query on a CSV/JSON/Parquet object."""
    try:
        return await service.s3_select(
            bucket=_bucket(bucket),
            key=body.key,
            expression=body.expression,
            input_format=body.input_format,
            output_format=body.output_format,
            compression=body.compression,
            csv_header=body.csv_header,
        )
    except Exception as e:
        _raise_if_s3_unavailable(e, "s3_select")


# =========================================================================== #
# Object Tagging
# =========================================================================== #


@router.get("/objects/tags", response_model=TaggingResponse)
async def get_object_tags(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Get the tag set of an object."""
    try:
        return await service.get_object_tagging(bucket=_bucket(bucket), key=key)
    except Exception as e:
        _raise_if_s3_unavailable(e, "get_object_tagging")


@router.put("/objects/tags")
async def put_object_tags(
    body: PutTaggingRequest,
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Set tags on an object (replaces existing tags)."""
    try:
        await service.put_object_tagging(bucket=_bucket(bucket), key=key, tags=body.tags)
        return {"key": key, "tags_count": len(body.tags)}
    except Exception as e:
        _raise_if_s3_unavailable(e, "put_object_tagging")


@router.delete("/objects/tags")
async def delete_object_tags(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
):
    """Remove all tags from an object."""
    try:
        await service.delete_object_tagging(bucket=_bucket(bucket), key=key)
        return {"key": key, "tags_deleted": True}
    except Exception as e:
        _raise_if_s3_unavailable(e, "delete_object_tagging")


# =========================================================================== #
# File Preview
# =========================================================================== #

_PREVIEW_FORMATS = {
    "parquet": "table",
    "xlsx": "table",
    "xls": "table",
    "docx": "document",
    "pptx": "document",
}


@router.get(
    "/objects/preview",
    response_model=TablePreviewResponse | DocumentPreviewResponse,
)
async def preview_object(
    key: str = Query(..., description="Object key"),
    bucket: str | None = Query(None),
    sheet: str | None = Query(None, description="Sheet name (xlsx/xls only)"),
    max_rows: int = Query(1000, ge=1, le=10000, description="Max rows for tabular preview"),
):
    """Preview a file by converting it on the server.

    Supported formats:
      - **parquet** → tabular JSON (columns + rows)
      - **xlsx / xls** → tabular JSON with sheet selection
      - **docx** → HTML
      - **pptx** → HTML with slide data
    """
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    if ext not in _PREVIEW_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported preview format: .{ext}. "
            f"Supported: {', '.join(_PREVIEW_FORMATS.keys())}",
        )

    try:
        b = _bucket(bucket)
        if ext == "parquet":
            return await service.preview_parquet(bucket=b, key=key, max_rows=max_rows)
        if ext in ("xlsx", "xls"):
            return await service.preview_xlsx(bucket=b, key=key, sheet=sheet, max_rows=max_rows)
        if ext == "docx":
            return await service.preview_docx(bucket=b, key=key)
        if ext == "pptx":
            return await service.preview_pptx(bucket=b, key=key)
    except Exception as e:
        _raise_if_s3_unavailable(e, "preview_object")
