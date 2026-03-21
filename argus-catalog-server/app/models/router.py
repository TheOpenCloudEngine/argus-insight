"""ML Model Registry API endpoints.

Native Argus Catalog API for model management under /api/v1/models.
For MLflow integration, use the UC-compatible API in uc_compat.py instead.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import service
from app.models.schemas import (
    ModelVersionCreate,
    ModelVersionFinalize,
    ModelVersionResponse,
    ModelVersionUpdate,
    PaginatedModelSummaries,
    PaginatedModelVersions,
    PaginatedRegisteredModels,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


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
        return await service.create_registered_model(session, req)
    except ValueError as e:
        logger.warning("POST /models conflict: %s", e)
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=PaginatedModelSummaries)
async def list_registered_models(
    search: str | None = Query(None, description="Search by model name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List registered models with latest version status and metadata."""
    return await service.list_model_summaries(session, search=search, page=page, page_size=page_size)


@router.get("/{model_name}", response_model=RegisteredModelResponse)
async def get_registered_model(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Get a registered model by name."""
    model = await service.get_registered_model_by_name(session, model_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return model


@router.patch("/{model_name}", response_model=RegisteredModelResponse)
async def update_registered_model(
    model_name: str,
    req: RegisteredModelUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a registered model's metadata."""
    try:
        model = await service.update_registered_model(session, model_name, req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return model


@router.delete("/{model_name}")
async def delete_registered_model(
    model_name: str, session: AsyncSession = Depends(get_session),
):
    """Soft-delete a registered model."""
    if not await service.delete_registered_model(session, model_name):
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return {"status": "ok", "message": f"Model '{model_name}' deleted"}


@router.post("/hard-delete")
async def hard_delete_models(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Permanently delete models: DB records + disk artifacts."""
    names: list[str] = body.get("names", [])
    if not names:
        raise HTTPException(status_code=400, detail="No model names provided")

    deleted: list[str] = []
    not_found: list[str] = []
    for name in names:
        if await service.hard_delete_registered_model(session, name):
            deleted.append(name)
        else:
            not_found.append(name)

    logger.info("Hard-deleted %d models: %s", len(deleted), deleted)
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
    """Create a new model version (status: PENDING_REGISTRATION)."""
    logger.info("POST /models/%s/versions: source=%s, run_id=%s", model_name, req.source, req.run_id)
    # Override model_name from path
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
    """List all versions for a registered model."""
    result = await service.list_model_versions(session, model_name, page=page, page_size=page_size)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    return result


@router.get("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def get_model_version(
    model_name: str, version: int, session: AsyncSession = Depends(get_session),
):
    """Get a specific model version."""
    ver = await service.get_model_version(session, model_name, version)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for model '{model_name}'")
    return ver


@router.patch("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def update_model_version(
    model_name: str,
    version: int,
    req: ModelVersionUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a model version's metadata."""
    ver = await service.update_model_version(session, model_name, version, req)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for model '{model_name}'")
    return ver


@router.patch("/{model_name}/versions/{version}/finalize", response_model=ModelVersionResponse)
async def finalize_model_version(
    model_name: str,
    version: int,
    req: ModelVersionFinalize,
    session: AsyncSession = Depends(get_session),
):
    """Finalize a model version (transition from PENDING_REGISTRATION to READY or FAILED)."""
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
    if not await service.delete_model_version(session, model_name, version):
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for model '{model_name}'",
        )
    return {"status": "ok", "message": f"Version {version} of model '{model_name}' deleted"}
