"""ML Model Registry API endpoints.

Native Argus Catalog API for model management under /api/v1/models.
Provides CRUD operations for registered models and model versions,
dashboard statistics, model detail views, and download statistics.

For MLflow integration, use the UC-compatible API in uc_compat.py instead.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser
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
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Permanently delete models: DB records (3 tables) + disk/S3 artifacts. Requires admin role."""
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


# ---------------------------------------------------------------------------
# Stage Management
# ---------------------------------------------------------------------------

@router.put("/{model_name}/versions/{version}/stage")
async def update_version_stage(
    model_name: str, version: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update model version stage (NONE → STAGING → PRODUCTION → ARCHIVED)."""
    from app.models.models import RegisteredModel, ModelVersion
    from sqlalchemy import select
    from datetime import datetime, timezone

    stage = body.get("stage", "NONE")
    changed_by = body.get("changed_by", "")

    if stage not in ("NONE", "STAGING", "PRODUCTION", "ARCHIVED"):
        raise HTTPException(status_code=400, detail=f"Invalid stage: {stage}")

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    ver = (await session.execute(
        select(ModelVersion).where(ModelVersion.model_id == model.id, ModelVersion.version == version)
    )).scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")

    ver.stage = stage
    ver.stage_changed_at = datetime.now(timezone.utc)
    ver.stage_changed_by = changed_by
    await session.commit()
    logger.info("Stage updated: %s v%d → %s by %s", model_name, version, stage, changed_by)
    return {"status": "ok", "model": model_name, "version": version, "stage": stage}


# ---------------------------------------------------------------------------
# Model-Dataset Lineage
# ---------------------------------------------------------------------------

@router.post("/{model_name}/lineage")
async def add_model_dataset_lineage(
    model_name: str, body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Link a model to a training/evaluation dataset."""
    from app.models.models import RegisteredModel, ModelDatasetLineage
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    lineage = ModelDatasetLineage(
        model_id=model.id,
        model_version=body.get("model_version"),
        dataset_id=body["dataset_id"],
        relation_type=body.get("relation_type", "TRAINING_DATA"),
        description=body.get("description"),
    )
    session.add(lineage)
    await session.commit()
    await session.refresh(lineage)
    logger.info("Model-dataset lineage created: %s → dataset_id=%d", model_name, body["dataset_id"])
    return {"id": lineage.id, "model": model_name, "dataset_id": body["dataset_id"], "relation_type": lineage.relation_type}


@router.get("/{model_name}/lineage")
async def get_model_dataset_lineage(model_name: str, session: AsyncSession = Depends(get_session)):
    """Get datasets linked to a model."""
    from app.models.models import RegisteredModel, ModelDatasetLineage
    from app.catalog.models import Dataset, Platform
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    lineages = (await session.execute(
        select(ModelDatasetLineage).where(ModelDatasetLineage.model_id == model.id)
    )).scalars().all()

    results = []
    for l in lineages:
        ds = (await session.execute(
            select(Dataset.name, Platform.type)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(Dataset.id == l.dataset_id)
        )).first()
        results.append({
            "id": l.id,
            "model_version": l.model_version,
            "dataset_id": l.dataset_id,
            "dataset_name": ds[0] if ds else None,
            "platform_type": ds[1] if ds else None,
            "relation_type": l.relation_type,
            "description": l.description,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return results


@router.delete("/{model_name}/lineage/{lineage_id}")
async def delete_model_dataset_lineage(
    model_name: str, lineage_id: int, session: AsyncSession = Depends(get_session),
):
    """Remove a model-dataset lineage link."""
    from app.models.models import ModelDatasetLineage
    from sqlalchemy import select

    l = (await session.execute(
        select(ModelDatasetLineage).where(ModelDatasetLineage.id == lineage_id)
    )).scalar_one_or_none()
    if not l:
        raise HTTPException(status_code=404, detail="Lineage not found")
    await session.delete(l)
    await session.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Model Metrics
# ---------------------------------------------------------------------------

@router.post("/{model_name}/versions/{version}/metrics")
async def add_model_metrics(
    model_name: str, version: int, body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Add or update metrics for a model version. body: {"metrics": {"accuracy": 0.95, "f1": 0.88}}"""
    from app.models.models import RegisteredModel, ModelMetric
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    metrics = body.get("metrics", {})
    for key, value in metrics.items():
        existing = (await session.execute(
            select(ModelMetric).where(
                ModelMetric.model_id == model.id,
                ModelMetric.version == version,
                ModelMetric.metric_key == key,
            )
        )).scalar_one_or_none()
        if existing:
            existing.metric_value = value
        else:
            session.add(ModelMetric(
                model_id=model.id, version=version,
                metric_key=key, metric_value=value,
            ))

    await session.commit()
    logger.info("Metrics recorded: %s v%d, %d metrics", model_name, version, len(metrics))
    return {"status": "ok", "model": model_name, "version": version, "metrics_count": len(metrics)}


@router.get("/{model_name}/metrics")
async def get_model_metrics(model_name: str, session: AsyncSession = Depends(get_session)):
    """Get metrics for all versions of a model (for comparison)."""
    from app.models.models import RegisteredModel, ModelMetric
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    metrics = (await session.execute(
        select(ModelMetric).where(ModelMetric.model_id == model.id)
        .order_by(ModelMetric.version, ModelMetric.metric_key)
    )).scalars().all()

    # Group by version
    by_version: dict[int, dict] = {}
    for m in metrics:
        if m.version not in by_version:
            by_version[m.version] = {"version": m.version, "metrics": {}}
        by_version[m.version]["metrics"][m.metric_key] = float(m.metric_value)

    return list(by_version.values())


# ---------------------------------------------------------------------------
# Model Card
# ---------------------------------------------------------------------------

@router.get("/{model_name}/card")
async def get_model_card(model_name: str, session: AsyncSession = Depends(get_session)):
    """Get the model card."""
    from app.models.models import RegisteredModel, ModelCard
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    card = (await session.execute(
        select(ModelCard).where(ModelCard.model_id == model.id)
    )).scalar_one_or_none()

    if not card:
        return {"model_id": model.id, "purpose": None, "performance": None,
                "limitations": None, "training_data": None, "framework": None,
                "license": None, "contact": None}

    return {
        "model_id": card.model_id, "purpose": card.purpose,
        "performance": card.performance, "limitations": card.limitations,
        "training_data": card.training_data, "framework": card.framework,
        "license": card.license, "contact": card.contact,
        "updated_at": card.updated_at.isoformat() if card.updated_at else None,
    }


@router.put("/{model_name}/card")
async def update_model_card(model_name: str, body: dict, session: AsyncSession = Depends(get_session)):
    """Create or update the model card."""
    from app.models.models import RegisteredModel, ModelCard
    from sqlalchemy import select

    model = (await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )).scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    card = (await session.execute(
        select(ModelCard).where(ModelCard.model_id == model.id)
    )).scalar_one_or_none()

    if card:
        for k in ("purpose", "performance", "limitations", "training_data", "framework", "license", "contact"):
            if k in body:
                setattr(card, k, body[k])
    else:
        card = ModelCard(model_id=model.id, **{k: body.get(k) for k in
            ("purpose", "performance", "limitations", "training_data", "framework", "license", "contact")})
        session.add(card)

    await session.commit()
    logger.info("Model card updated: %s", model_name)
    return {"status": "ok", "model": model_name}
