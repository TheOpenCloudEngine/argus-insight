"""Unity Catalog OSS compatible API router for MLflow integration.

This router translates MLflow's UC OSS registry API calls to Argus Catalog's
internal model service. It implements the endpoints that MLflow's
UnityCatalogOssStore (uc_oss_rest_store.py) expects.

Base path: /api/2.1/unity-catalog/
Source reference: mlflow/store/_unity_catalog/registry/uc_oss_rest_store.py

MLflow flow when `registered_model_name` is set:
  1. POST /models                     → CreateRegisteredModel
  2. POST /models/versions            → CreateModelVersion (PENDING)
  3. Artifacts uploaded to file:// storage_location via LocalArtifactRepository
  4. PATCH /models/{name}/versions/{ver}/finalize → READY

Key design decisions:
  - 3-part names (catalog.schema.model) are stored as-is in the name column
  - Route parameters use {cat}.{sch}.{mdl} to avoid wildcard path conflicts
  - storage_location uses file:// prefix → MLflow skips credential fetch
    and uses LocalArtifactRepository for direct filesystem access
  - /temporary-model-version-credentials returns empty (no-op for local storage)

Usage:
    mlflow.set_registry_uri("uc:http://localhost:4600")
    mlflow.sklearn.log_model(model, "model", registered_model_name="argus.ml.my_model")
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import service
from app.models.schemas import (
    ModelVersionCreate,
    ModelVersionFinalize,
    ModelVersionStatus,
    ModelVersionUpdate,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/2.1/unity-catalog",
    tags=["unity-catalog-compat"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_ms(dt) -> int:
    """Convert a datetime to millisecond timestamp for UC API responses."""
    if dt is None:
        return 0
    return int(dt.timestamp() * 1000)


def _model_to_uc(m: RegisteredModelResponse) -> dict:
    """Convert internal RegisteredModelResponse to UC API response format."""
    parts = m.name.split(".", 2)
    if len(parts) == 3:
        catalog_name, schema_name, model_name = parts
    else:
        catalog_name, schema_name, model_name = "default", "default", m.name
    return {
        "name": model_name,
        "catalog_name": catalog_name,
        "schema_name": schema_name,
        "full_name": m.name,
        "comment": m.description or "",
        "storage_location": m.storage_location or "",
        "owner": m.owner or "",
        "id": str(m.id),
        "created_at": _ts_ms(m.created_at),
        "created_by": m.created_by or "",
        "updated_at": _ts_ms(m.updated_at),
        "updated_by": m.updated_by or "",
    }


def _version_to_uc(v) -> dict:
    """Convert internal ModelVersionResponse to UC API response format."""
    parts = v.model_name.split(".", 2)
    if len(parts) == 3:
        catalog_name, schema_name, model_name = parts
    else:
        catalog_name, schema_name, model_name = "default", "default", v.model_name
    return {
        "model_name": model_name,
        "catalog_name": catalog_name,
        "schema_name": schema_name,
        "version": v.version,
        "source": v.source or "",
        "run_id": v.run_id or "",
        "comment": v.description or "",
        "status": v.status,
        "storage_location": v.storage_location or "",
        "id": str(v.id),
        "created_at": _ts_ms(v.created_at),
        "created_by": v.created_by or "",
        "updated_at": _ts_ms(v.updated_at),
        "updated_by": v.updated_by or "",
    }


# ---------------------------------------------------------------------------
# RegisteredModel endpoints
# ---------------------------------------------------------------------------

@router.post("/models")
async def create_registered_model(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    full_name = f"{body.get('catalog_name', 'default')}.{body.get('schema_name', 'default')}.{body.get('name', '')}"
    logger.info("[UC] CreateRegisteredModel: %s", full_name)
    try:
        result = await service.create_registered_model(session, RegisteredModelCreate(
            name=full_name, description=body.get("comment"), storage_location=body.get("storage_location"),
        ))
        return JSONResponse(_model_to_uc(result))
    except ValueError as e:
        return JSONResponse({"error_code": "ALREADY_EXISTS", "message": str(e)}, status_code=409)


@router.get("/models")
async def list_registered_models(request: Request, session: AsyncSession = Depends(get_session)):
    max_results = int(request.query_params.get("max_results", "100"))
    catalog_name = request.query_params.get("catalog_name")
    schema_name = request.query_params.get("schema_name")
    search = f"{catalog_name}.{schema_name}." if catalog_name and schema_name else None
    result = await service.list_registered_models(session, search=search, page=1, page_size=max_results)
    return JSONResponse({"registered_models": [_model_to_uc(m) for m in result.items]})


@router.post("/models/versions")
async def create_model_version(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    full_name = f"{body.get('catalog_name', 'default')}.{body.get('schema_name', 'default')}.{body.get('model_name', '')}"
    logger.info("[UC] CreateModelVersion: %s, source=%s", full_name, body.get("source"))
    try:
        result = await service.create_model_version(session, ModelVersionCreate(
            model_name=full_name, source=body.get("source"),
            run_id=body.get("run_id"), description=body.get("comment"),
        ))
        return JSONResponse(_version_to_uc(result))
    except ValueError as e:
        return JSONResponse({"error_code": "NOT_FOUND", "message": str(e)}, status_code=404)


@router.post("/temporary-model-version-credentials")
async def generate_temporary_credentials(request: Request):
    logger.info("[UC] GenerateTemporaryCredentials (no-op for local storage)")
    return JSONResponse({})


# ---------------------------------------------------------------------------
# Path-based endpoints: {catalog}.{schema}.{model}
# Using explicit 3-part path parameters to avoid wildcard conflicts
# ---------------------------------------------------------------------------

@router.get("/models/{cat}.{sch}.{mdl}")
async def get_registered_model(cat: str, sch: str, mdl: str, session: AsyncSession = Depends(get_session)):
    full_name = f"{cat}.{sch}.{mdl}"
    logger.info("[UC] GetRegisteredModel: %s", full_name)
    result = await service.get_registered_model_by_name(session, full_name)
    if not result:
        return JSONResponse({"error_code": "NOT_FOUND", "message": f"Model '{full_name}' not found"}, status_code=404)
    return JSONResponse(_model_to_uc(result))


@router.patch("/models/{cat}.{sch}.{mdl}")
async def update_registered_model(cat: str, sch: str, mdl: str, request: Request, session: AsyncSession = Depends(get_session)):
    full_name = f"{cat}.{sch}.{mdl}"
    body = await request.json()
    logger.info("[UC] UpdateRegisteredModel: %s", full_name)
    try:
        result = await service.update_registered_model(session, full_name, RegisteredModelUpdate(
            description=body.get("comment"), name=body.get("new_name"),
        ))
    except ValueError as e:
        return JSONResponse({"error_code": "ALREADY_EXISTS", "message": str(e)}, status_code=409)
    if not result:
        return JSONResponse({"error_code": "NOT_FOUND"}, status_code=404)
    return JSONResponse(_model_to_uc(result))


@router.delete("/models/{cat}.{sch}.{mdl}")
async def delete_registered_model(cat: str, sch: str, mdl: str, session: AsyncSession = Depends(get_session)):
    full_name = f"{cat}.{sch}.{mdl}"
    logger.info("[UC] DeleteRegisteredModel: %s", full_name)
    if not await service.delete_registered_model(session, full_name):
        return JSONResponse({"error_code": "NOT_FOUND"}, status_code=404)
    return JSONResponse({})


# ---------------------------------------------------------------------------
# ModelVersion endpoints
# ---------------------------------------------------------------------------

@router.get("/models/{cat}.{sch}.{mdl}/versions")
async def list_model_versions(
    cat: str, sch: str, mdl: str,
    request: Request, session: AsyncSession = Depends(get_session),
):
    full_name = f"{cat}.{sch}.{mdl}"
    max_results = int(request.query_params.get("max_results", "100"))
    result = await service.list_model_versions(session, full_name, page=1, page_size=max_results)
    if result is None:
        return JSONResponse({"model_versions": []})
    return JSONResponse({"model_versions": [_version_to_uc(v) for v in result.items]})


@router.get("/models/{cat}.{sch}.{mdl}/versions/{version}")
async def get_model_version(
    cat: str, sch: str, mdl: str, version: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    full_name = f"{cat}.{sch}.{mdl}"
    logger.info("[UC] GetModelVersion: %s v%d", full_name, version)
    result = await service.get_model_version(session, full_name, version)
    if not result:
        return JSONResponse({"error_code": "NOT_FOUND"}, status_code=404)

    # Log access
    from app.models.access_log import log_access
    await log_access(
        session, full_name, version, "load",
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return JSONResponse(_version_to_uc(result))


@router.patch("/models/{cat}.{sch}.{mdl}/versions/{version}/finalize")
async def finalize_model_version(
    cat: str, sch: str, mdl: str, version: int,
    request: Request, session: AsyncSession = Depends(get_session),
):
    full_name = f"{cat}.{sch}.{mdl}"
    logger.info("[UC] FinalizeModelVersion: %s v%d", full_name, version)
    try:
        result = await service.finalize_model_version(
            session, full_name, version,
            ModelVersionFinalize(status=ModelVersionStatus.READY),
        )
        return JSONResponse(_version_to_uc(result))
    except ValueError as e:
        return JSONResponse({"error_code": "INVALID_STATE", "message": str(e)}, status_code=409)


@router.patch("/models/{cat}.{sch}.{mdl}/versions/{version}")
async def update_model_version(
    cat: str, sch: str, mdl: str, version: int,
    request: Request, session: AsyncSession = Depends(get_session),
):
    full_name = f"{cat}.{sch}.{mdl}"
    body = await request.json()
    logger.info("[UC] UpdateModelVersion: %s v%d", full_name, version)
    result = await service.update_model_version(
        session, full_name, version, ModelVersionUpdate(description=body.get("comment")),
    )
    if not result:
        return JSONResponse({"error_code": "NOT_FOUND"}, status_code=404)
    return JSONResponse(_version_to_uc(result))


@router.delete("/models/{cat}.{sch}.{mdl}/versions/{version}")
async def delete_model_version(
    cat: str, sch: str, mdl: str, version: int,
    session: AsyncSession = Depends(get_session),
):
    full_name = f"{cat}.{sch}.{mdl}"
    logger.info("[UC] DeleteModelVersion: %s v%d", full_name, version)
    if not await service.delete_model_version(session, full_name, version):
        return JSONResponse({"error_code": "NOT_FOUND"}, status_code=404)
    return JSONResponse({})
