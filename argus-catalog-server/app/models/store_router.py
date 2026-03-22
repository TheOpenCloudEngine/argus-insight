"""Model Store API endpoints — S3-based model artifact management.

Provides REST API for:
  - Upload model files (direct or presigned URL)
  - Download model files (presigned URL)
  - List model version files
  - Generate/retrieve OCI manifest
  - Import from HuggingFace Hub
  - Import from local directory (airgap)
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models import model_store, service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model-store", tags=["model-store"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class UploadUrlRequest(BaseModel):
    filename: str = Field(..., description="Name of the file to upload")


class UploadUrlResponse(BaseModel):
    url: str
    key: str
    expires_in: int


class DownloadUrlResponse(BaseModel):
    url: str
    key: str
    expires_in: int


class FileInfo(BaseModel):
    filename: str
    key: str
    size: int
    last_modified: str = ""


class FinalizeRequest(BaseModel):
    annotations: dict[str, str] | None = None


class FinalizeResponse(BaseModel):
    status: str
    file_count: int
    total_size: int
    manifest: dict | None = None


class HuggingFaceImportRequest(BaseModel):
    hf_model_id: str = Field(..., description="HuggingFace model ID (e.g. 'bert-base-uncased')")
    model_name: str = Field(..., description="Target model name (e.g. 'argus.ml.bert')")
    revision: str = Field("main", description="HuggingFace revision/branch")
    description: str | None = None
    owner: str | None = None


class LocalImportRequest(BaseModel):
    local_dir: str = Field(..., description="Path to local directory containing model files")
    model_name: str = Field(..., description="Target model name")
    description: str | None = None
    owner: str | None = None
    source: str = Field("local", description="Source label")


class ImportResponse(BaseModel):
    model_name: str
    version: int
    file_count: int
    total_size: int
    storage_location: str


# ---------------------------------------------------------------------------
# Upload endpoints
# ---------------------------------------------------------------------------

@router.post("/{model_name}/versions/{version}/upload")
async def upload_file(
    model_name: str,
    version: int,
    file: UploadFile,
):
    """Upload a single file to the model version in S3."""
    try:
        data = await file.read()
        filename = file.filename or "uploaded_file"
        result = await model_store.upload_file(model_name, version, filename, data)
        return result
    except Exception as e:
        logger.error("Upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_name}/versions/{version}/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    model_name: str,
    version: int,
    body: UploadUrlRequest,
):
    """Generate a presigned URL for direct upload to S3."""
    try:
        return await model_store.generate_upload_url(model_name, version, body.filename)
    except Exception as e:
        logger.error("Upload URL error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Download endpoints
# ---------------------------------------------------------------------------

@router.get("/{model_name}/versions/{version}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    model_name: str,
    version: int,
    filename: str = Query(..., description="File to download"),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate a presigned download URL for a file."""
    try:
        from app.models.access_log import log_access
        await log_access(
            session, model_name, version, "download",
            client_ip=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
        return await model_store.generate_download_url(model_name, version, filename)
    except Exception as e:
        logger.error("Download URL error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_name}/versions/{version}/download-urls")
async def get_download_urls(
    model_name: str,
    version: int,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate presigned download URLs for all files in a version."""
    try:
        from app.models.access_log import log_access
        await log_access(
            session, model_name, version, "pull",
            client_ip=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
        urls = await model_store.generate_download_urls(model_name, version)
        return {"files": urls}
    except Exception as e:
        logger.error("Download URLs error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# List / Manifest
# ---------------------------------------------------------------------------

@router.get("/{model_name}/versions/{version}/files", response_model=list[FileInfo])
async def list_version_files(
    model_name: str,
    version: int,
):
    """List all files for a model version in S3."""
    try:
        return await model_store.list_files(model_name, version)
    except Exception as e:
        logger.error("List files error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_name}/versions/{version}/manifest")
async def get_manifest(
    model_name: str,
    version: int,
):
    """Retrieve the OCI manifest for a model version."""
    try:
        data = await model_store.download_file(model_name, version, "manifest.json")
        return json.loads(data)
    except Exception:
        raise HTTPException(status_code=404, detail="Manifest not found")


# ---------------------------------------------------------------------------
# Finalize (generate manifest + update DB)
# ---------------------------------------------------------------------------

@router.post("/{model_name}/versions/{version}/finalize", response_model=FinalizeResponse)
async def finalize_version(
    model_name: str,
    version: int,
    body: FinalizeRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Finalize a model version: scan files, generate manifest, update DB."""
    try:
        # Count files
        file_count, total_size = await model_store.get_total_size(model_name, version)
        if file_count == 0:
            raise HTTPException(status_code=400, detail="No files found for this version")

        # Generate OCI manifest
        annotations = body.annotations if body else None
        manifest = await model_store.generate_manifest(
            model_name, version, annotations,
        )

        return FinalizeResponse(
            status="READY",
            file_count=file_count,
            total_size=total_size,
            manifest=manifest,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Finalize error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Import: HuggingFace
# ---------------------------------------------------------------------------

@router.post("/import/huggingface", response_model=ImportResponse)
async def import_huggingface(
    body: HuggingFaceImportRequest,
    session: AsyncSession = Depends(get_session),
):
    """Import a model from HuggingFace Hub.

    Downloads the model, stores in S3, creates DB records.
    """
    try:
        # Create or get registered model
        from app.models.schemas import RegisteredModelCreate
        try:
            model = await service.create_registered_model(
                session,
                RegisteredModelCreate(
                    name=body.model_name,
                    description=body.description,
                    owner=body.owner,
                    storage_location=f"s3://{settings.os_bucket}/{body.model_name}",
                ),
            )
        except ValueError:
            # Model already exists, get it
            model = await service.get_registered_model_by_name(session, body.model_name)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model '{body.model_name}' not found")

        # Update storage_type to s3
        from sqlalchemy import select, update
        from app.models.models import RegisteredModel
        await session.execute(
            update(RegisteredModel).where(
                RegisteredModel.name == body.model_name
            ).values(
                storage_type="s3",
                bucket_name=settings.os_bucket,
                storage_location=f"s3://{settings.os_bucket}/{body.model_name}",
            )
        )

        # Create version
        from app.models.schemas import ModelVersionCreate
        version_resp = await service.create_model_version(
            session,
            ModelVersionCreate(model_name=body.model_name),
        )
        version = version_resp.version

        # Import from HuggingFace
        metadata = await model_store.import_from_huggingface(
            hf_model_id=body.hf_model_id,
            model_name=body.model_name,
            version=version,
            revision=body.revision,
        )

        # Update version to READY
        from app.models.schemas import ModelVersionFinalize, ModelVersionStatus
        await service.finalize_model_version(
            session, body.model_name, version,
            ModelVersionFinalize(status=ModelVersionStatus.READY),
        )

        # Save catalog_models metadata
        from app.models.models import CatalogModel
        import json as _json
        cm = CatalogModel(
            model_version_id=version_resp.id,
            model_name=body.model_name,
            version=version,
            source_type="huggingface",
            manifest=_json.dumps(metadata.get("manifest")),
        )
        # Parse HF config metadata
        if metadata.get("model_type"):
            cm.serialization_format = metadata["model_type"]
        if metadata.get("transformers_version"):
            cm.mlflow_version = metadata["transformers_version"]

        session.add(cm)
        await session.commit()

        storage_loc = f"s3://{settings.os_bucket}/{body.model_name}/v{version}/"
        logger.info("HuggingFace import complete: %s -> %s v%d", body.hf_model_id, body.model_name, version)

        return ImportResponse(
            model_name=body.model_name,
            version=version,
            file_count=metadata["file_count"],
            total_size=metadata["total_size"],
            storage_location=storage_loc,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("HuggingFace import error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Import: Local directory (airgap)
# ---------------------------------------------------------------------------

@router.post("/import/local", response_model=ImportResponse)
async def import_local(
    body: LocalImportRequest,
    session: AsyncSession = Depends(get_session),
):
    """Import model files from a local directory to S3.

    Used for airgap scenarios: files are transferred via USB/SCP first,
    then imported from the local filesystem into MinIO.
    """
    try:
        # Create or get registered model
        from app.models.schemas import RegisteredModelCreate
        try:
            model = await service.create_registered_model(
                session,
                RegisteredModelCreate(
                    name=body.model_name,
                    description=body.description,
                    owner=body.owner,
                    storage_location=f"s3://{settings.os_bucket}/{body.model_name}",
                ),
            )
        except ValueError:
            model = await service.get_registered_model_by_name(session, body.model_name)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model '{body.model_name}' not found")

        # Update storage_type to s3
        from sqlalchemy import update
        from app.models.models import RegisteredModel
        await session.execute(
            update(RegisteredModel).where(
                RegisteredModel.name == body.model_name
            ).values(
                storage_type="s3",
                bucket_name=settings.os_bucket,
                storage_location=f"s3://{settings.os_bucket}/{body.model_name}",
            )
        )

        # Create version
        from app.models.schemas import ModelVersionCreate
        version_resp = await service.create_model_version(
            session,
            ModelVersionCreate(model_name=body.model_name),
        )
        version = version_resp.version

        # Import from local
        metadata = await model_store.import_from_local_directory(
            local_dir=body.local_dir,
            model_name=body.model_name,
            version=version,
            source=body.source,
        )

        # Finalize
        from app.models.schemas import ModelVersionFinalize, ModelVersionStatus
        await service.finalize_model_version(
            session, body.model_name, version,
            ModelVersionFinalize(status=ModelVersionStatus.READY),
        )

        # Save catalog_models
        from app.models.models import CatalogModel
        import json as _json
        cm = CatalogModel(
            model_version_id=version_resp.id,
            model_name=body.model_name,
            version=version,
            source_type=body.source,
            manifest=_json.dumps(metadata.get("manifest")),
        )
        session.add(cm)
        await session.commit()

        storage_loc = f"s3://{settings.os_bucket}/{body.model_name}/v{version}/"

        return ImportResponse(
            model_name=body.model_name,
            version=version,
            file_count=metadata["file_count"],
            total_size=metadata["total_size"],
            storage_location=storage_loc,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Local import error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
