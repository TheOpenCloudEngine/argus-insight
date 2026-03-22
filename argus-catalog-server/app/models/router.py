"""ML Model Registry API endpoints.

Native Argus Catalog API for model management under /api/v1/models.
Provides CRUD operations for registered models and model versions,
dashboard statistics, model detail views, and download statistics.

For MLflow integration, use the UC-compatible API in uc_compat.py instead.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import service
from app.models.schemas import (
    ModelDownloadStats,
    ModelDetailResponse,
    ModelStats,
    ModelVersionCreate,
    ModelVersionFinalize,
    ModelVersionResponse,
    ModelVersionUpdate,
    PaginatedModelSummaries,
    PaginatedModelVersions,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=ModelStats)
async def get_model_stats(session: AsyncSession = Depends(get_session)):
    """Get dashboard statistics: summary cards, charts, download/publish trends."""
    logger.info("GET /models/stats")
    return await service.get_model_stats(session)


# ---------------------------------------------------------------------------
# RegisteredModel endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=RegisteredModelResponse)
async def create_registered_model(
    req: RegisteredModelCreate, session: AsyncSession = Depends(get_session),
):
    """Register a new ML model."""
    logger.info("POST /models: name=%s", req.name)
    try:
        result = await service.create_registered_model(session, req)
        logger.info("Model created: %s (id=%d)", result.name, result.id)
        return result
    except ValueError as e:
        logger.warning("POST /models conflict: %s", e)
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=PaginatedModelSummaries)
async def list_registered_models(
    search: str | None = Query(None, description="Search by model name"),
    status: str | None = Query(None, description="Filter by latest version status"),
    python_version: str | None = Query(None, description="Filter by Python version"),
    sklearn_version: str | None = Query(None, description="Filter by sklearn version"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List registered models with latest version status and metadata."""
    logger.info("GET /models: search=%s, status=%s, page=%d", search, status, page)
    return await service.list_model_summaries(
        session, search=search, status=status,
        python_version=python_version, sklearn_version=sklearn_version,
        page=page, page_size=page_size,
    )


@router.get("/{model_name}/detail", response_model=ModelDetailResponse)
async def get_model_detail(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Get full model detail with latest version metadata and download count."""
    logger.info("GET /models/%s/detail", model_name)
    detail = await service.get_model_detail(session, model_name)
    if not detail:
        logger.warning("Model not found: %s", model_name)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return detail


@router.get("/{model_name}/download", response_model=ModelDownloadStats)
async def get_model_download_stats(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Get download statistics (daily chart + recent logs) for a specific model."""
    logger.info("GET /models/%s/download", model_name)
    return await service.get_model_download_stats(session, model_name)


@router.get("/{model_name}", response_model=RegisteredModelResponse)
async def get_registered_model(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Get a registered model by name."""
    logger.info("GET /models/%s", model_name)
    model = await service.get_registered_model_by_name(session, model_name)
    if not model:
        logger.warning("Model not found: %s", model_name)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return model


@router.patch("/{model_name}", response_model=RegisteredModelResponse)
async def update_registered_model(
    model_name: str,
    req: RegisteredModelUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a registered model's metadata (name, description, owner)."""
    logger.info("PATCH /models/%s", model_name)
    try:
        model = await service.update_registered_model(session, model_name, req)
    except ValueError as e:
        logger.warning("PATCH /models/%s conflict: %s", model_name, e)
        raise HTTPException(status_code=409, detail=str(e))
    if not model:
        logger.warning("Model not found for update: %s", model_name)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    logger.info("Model updated: %s", model_name)
    return model


@router.delete("/{model_name}")
async def delete_registered_model(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Soft-delete a registered model (hides from listings)."""
    logger.info("DELETE /models/%s (soft)", model_name)
    if not await service.delete_registered_model(session, model_name):
        logger.warning("Model not found for delete: %s", model_name)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    logger.info("Model soft-deleted: %s", model_name)
    return {"status": "ok", "message": f"Model '{model_name}' deleted"}


@router.post("/hard-delete")
async def hard_delete_models(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Permanently delete models: DB records (3 tables) + disk/S3 artifacts."""
    names: list[str] = body.get("names", [])
    if not names:
        raise HTTPException(status_code=400, detail="No model names provided")

    logger.info("Hard-delete requested for %d models: %s", len(names), names)
    deleted: list[str] = []
    not_found: list[str] = []
    for name in names:
        if await service.hard_delete_registered_model(session, name):
            deleted.append(name)
        else:
            not_found.append(name)

    logger.info("Hard-delete result: deleted=%s, not_found=%s", deleted, not_found)
    return {"deleted": deleted, "not_found": not_found}


# ---------------------------------------------------------------------------
# ModelVersion endpoints
# ---------------------------------------------------------------------------

@router.post("/{model_name}/versions", response_model=ModelVersionResponse)
async def create_model_version(
    model_name: str,
    req: ModelVersionCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new model version (initial status: PENDING_REGISTRATION)."""
    logger.info("POST /models/%s/versions: source=%s, run_id=%s", model_name, req.source, req.run_id)
    req.model_name = model_name
    try:
        return await service.create_model_version(session, req)
    except ValueError as e:
        logger.warning("POST /models/%s/versions failed: %s", model_name, e)
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{model_name}/versions", response_model=PaginatedModelVersions)
async def list_model_versions(
    model_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List all versions for a registered model with pagination."""
    logger.info("GET /models/%s/versions: page=%d", model_name, page)
    result = await service.list_model_versions(session, model_name, page=page, page_size=page_size)
    if result is None:
        logger.warning("Model not found for version listing: %s", model_name)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return result


@router.get("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def get_model_version(
    model_name: str, version: int, session: AsyncSession = Depends(get_session),
):
    """Get a specific model version by model name and version number."""
    logger.info("GET /models/%s/versions/%d", model_name, version)
    ver = await service.get_model_version(session, model_name, version)
    if not ver:
        logger.warning("Version not found: %s v%d", model_name, version)
        raise HTTPException(status_code=404, detail=f"Version {version} not found for model '{model_name}'")
    return ver


@router.patch("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def update_model_version(
    model_name: str,
    version: int,
    req: ModelVersionUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a model version's metadata (description, source)."""
    logger.info("PATCH /models/%s/versions/%d", model_name, version)
    ver = await service.update_model_version(session, model_name, version, req)
    if not ver:
        logger.warning("Version not found for update: %s v%d", model_name, version)
        raise HTTPException(status_code=404, detail=f"Version {version} not found for model '{model_name}'")
    logger.info("Version updated: %s v%d", model_name, version)
    return ver


@router.patch("/{model_name}/versions/{version}/finalize", response_model=ModelVersionResponse)
async def finalize_model_version(
    model_name: str,
    version: int,
    req: ModelVersionFinalize,
    session: AsyncSession = Depends(get_session),
):
    """Finalize a model version: transition from PENDING_REGISTRATION to READY or FAILED."""
    logger.info("PATCH /models/%s/versions/%d/finalize: status=%s", model_name, version, req.status)
    try:
        return await service.finalize_model_version(session, model_name, version, req)
    except ValueError as e:
        logger.warning("Finalize failed for %s v%d: %s", model_name, version, e)
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{model_name}/versions/{version}")
async def delete_model_version(
    model_name: str, version: int, session: AsyncSession = Depends(get_session),
):
    """Delete a model version."""
    logger.info("DELETE /models/%s/versions/%d", model_name, version)
    if not await service.delete_model_version(session, model_name, version):
        logger.warning("Version not found for delete: %s v%d", model_name, version)
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for model '{model_name}'",
        )
    logger.info("Version deleted: %s v%d", model_name, version)
    return {"status": "ok", "message": f"Version {version} of model '{model_name}' deleted"}
