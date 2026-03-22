"""ML Model Registry service layer.

CRUD operations for registered models and model versions.
Follows Unity Catalog OSS patterns for MLflow compatibility.

Model naming: 3-part format required (catalog.schema.model_name)
  e.g. "argus.ml.iris_classifier"

Version lifecycle: PENDING_REGISTRATION → READY / FAILED_REGISTRATION
  - create_model_version: creates with PENDING_REGISTRATION
  - finalize_model_version: transitions to READY (scans artifacts) or FAILED

Storage: file:// URIs under data_dir/model-artifacts/{name}/versions/{ver}/
  - file:// prefix is required for MLflow's LocalArtifactRepository to work
  - Without it, MLflow tries to fetch cloud credentials and fails

Audit fields (set at finalize time):
  - artifact_count/artifact_size: filesystem scan results
  - finished_at: completion timestamp
  - status_message: failure reason (if any)
"""

import datetime as _dt
import logging
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import CatalogModel, ModelVersion, RegisteredModel
from app.models.schemas import (
    DataPoint,
    DownloadLogEntry,
    CatalogModelDetail,
    ModelDownloadStats,
    ModelDetailResponse,
    ModelSizeInfo,
    ModelStats,
    ModelSummary,
    ModelVersionCount,
    ModelVersionCreate,
    ModelVersionFinalize,
    ModelVersionResponse,
    ModelVersionStatusCount,
    ModelVersionUpdate,
    PaginatedModelSummaries,
    PaginatedModelVersions,
    PaginatedRegisteredModels,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
)

logger = logging.getLogger(__name__)


def _model_artifacts_root() -> Path:
    """Return the root directory for MLflow model artifacts (data_dir/model-artifacts)."""
    return settings.data_dir / "model-artifacts"


def _generate_model_urn(name: str) -> str:
    """Generate URN for a registered model."""
    return f"{name}.PROD.model"


# ---------------------------------------------------------------------------
# RegisteredModel operations
# ---------------------------------------------------------------------------

async def create_registered_model(
    session: AsyncSession, req: RegisteredModelCreate,
) -> RegisteredModelResponse:
    # Check name uniqueness
    existing = await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == req.name)
    )
    if existing.scalars().first():
        raise ValueError(f"Model with name '{req.name}' already exists")

    raw_path = req.storage_location or str(_model_artifacts_root() / req.name)
    storage = raw_path if raw_path.startswith("file://") else f"file://{raw_path}"
    urn = _generate_model_urn(req.name)

    model = RegisteredModel(
        name=req.name,
        urn=urn,
        platform_id=req.platform_id,
        description=req.description,
        owner=req.owner,
        storage_location=storage,
        max_version_number=0,
        status="active",
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)

    # Create artifact directory
    try:
        Path(storage.replace("file://", "")).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Failed to create artifact directory for %s: %s", model.name, e)
    logger.info("RegisteredModel created: %s (id=%d, urn=%s)", model.name, model.id, model.urn)
    return RegisteredModelResponse.model_validate(model)


async def get_registered_model(
    session: AsyncSession, model_id: int,
) -> RegisteredModelResponse | None:
    result = await session.execute(
        select(RegisteredModel).where(RegisteredModel.id == model_id)
    )
    model = result.scalars().first()
    if not model:
        return None
    return RegisteredModelResponse.model_validate(model)


async def get_registered_model_by_name(
    session: AsyncSession, name: str,
) -> RegisteredModelResponse | None:
    """Look up a model by its 3-part name. Used by MLflow UC plugin."""
    result = await session.execute(
        select(RegisteredModel).where(
            RegisteredModel.name == name,
            RegisteredModel.status != "deleted",
        )
    )
    model = result.scalars().first()
    if not model:
        return None
    return RegisteredModelResponse.model_validate(model)


async def list_registered_models(
    session: AsyncSession,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedRegisteredModels:
    base = select(RegisteredModel).where(RegisteredModel.status != "deleted")

    if search:
        pattern = f"%{search}%"
        base = base.where(RegisteredModel.name.ilike(pattern))

    # Count
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = base.order_by(RegisteredModel.updated_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    items = [RegisteredModelResponse.model_validate(m) for m in result.scalars().all()]

    return PaginatedRegisteredModels(items=items, total=total, page=page, page_size=page_size)


async def list_model_summaries(
    session: AsyncSession,
    search: str | None = None,
    status: str | None = None,
    python_version: str | None = None,
    sklearn_version: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedModelSummaries:
    """List models with latest version status and catalog_models metadata joined.

    Filters (status, python_version, sklearn_version) are applied post-query
    since they require joining catalog_model_versions / catalog_models.
    """
    base = select(RegisteredModel).where(RegisteredModel.status != "deleted")
    if search:
        base = base.where(RegisteredModel.name.ilike(f"%{search}%"))

    # Fetch all matching models (before post-filters)
    query = base.order_by(RegisteredModel.updated_at.desc())
    result = await session.execute(query)
    models = result.scalars().all()

    # Pre-load download counts for all models
    from app.models.download_log import get_download_count_by_model
    download_counts = await get_download_count_by_model(session)

    # Build summaries with joined data
    all_items: list[ModelSummary] = []
    for m in models:
        # Get latest version status
        latest_ver = (await session.execute(
            select(ModelVersion.status).where(
                ModelVersion.model_id == m.id,
            ).order_by(ModelVersion.version.desc()).limit(1)
        )).scalar()

        # Get catalog_models for latest version
        cm = (await session.execute(
            select(CatalogModel).where(
                CatalogModel.model_name == m.name,
            ).order_by(CatalogModel.version.desc()).limit(1)
        )).scalars().first()

        summary = ModelSummary(
            id=m.id,
            name=m.name,
            description=m.description,
            owner=m.owner,
            max_version_number=m.max_version_number,
            status=m.status,
            latest_version_status=latest_ver,
            sklearn_version=cm.sklearn_version if cm else None,
            python_version=cm.python_version if cm else None,
            model_size_bytes=cm.model_size_bytes if cm else None,
            download_count=download_counts.get(m.name, 0),
            updated_at=m.updated_at,
        )

        # Apply post-query filters
        if status and latest_ver != status:
            continue
        if python_version and (summary.python_version or "") != python_version:
            continue
        if sklearn_version and (summary.sklearn_version or "") != sklearn_version:
            continue

        all_items.append(summary)

    # Manual pagination on filtered results
    total = len(all_items)
    offset = (page - 1) * page_size
    items = all_items[offset:offset + page_size]

    return PaginatedModelSummaries(items=items, total=total, page=page, page_size=page_size)


async def get_model_stats(session: AsyncSession) -> ModelStats:
    """Get dashboard statistics for MLFlow Models page.

    Only counts active (non-deleted) models and their versions.
    """
    # Active model IDs
    active_ids_q = select(RegisteredModel.id).where(RegisteredModel.status != "deleted")
    active_ids = (await session.execute(active_ids_q)).scalars().all()

    total_models = len(active_ids)

    if not active_ids:
        return ModelStats(
            total_models=0, total_versions=0,
            ready_models=0, ready_versions=0,
            pending_count=0, failed_count=0, total_download=0,
            status_distribution=[], model_sizes=[], versions_per_model=[],
            daily_download_1d=[], daily_download_7d=[], daily_download_30d=[],
            download_by_model={},
            total_publish=0,
            daily_publish_1d=[], daily_publish_7d=[], daily_publish_30d=[],
        )

    # Versions of active models only
    active_ver_base = select(ModelVersion).where(ModelVersion.model_id.in_(active_ids))

    total_versions = (await session.execute(
        select(func.count()).select_from(active_ver_base.subquery())
    )).scalar() or 0

    # Status counts (active models only)
    ready_versions = (await session.execute(
        select(func.count()).where(
            ModelVersion.model_id.in_(active_ids),
            ModelVersion.status == "READY",
        )
    )).scalar() or 0

    pending = (await session.execute(
        select(func.count()).where(
            ModelVersion.model_id.in_(active_ids),
            ModelVersion.status == "PENDING_REGISTRATION",
        )
    )).scalar() or 0

    failed = (await session.execute(
        select(func.count()).where(
            ModelVersion.model_id.in_(active_ids),
            ModelVersion.status == "FAILED_REGISTRATION",
        )
    )).scalar() or 0

    # Ready models: models that have at least one READY version
    ready_model_ids = (await session.execute(
        select(ModelVersion.model_id).where(
            ModelVersion.model_id.in_(active_ids),
            ModelVersion.status == "READY",
        ).group_by(ModelVersion.model_id)
    )).scalars().all()
    ready_models = len(ready_model_ids)

    status_distribution = [
        ModelVersionStatusCount(status="READY", count=ready_versions),
        ModelVersionStatusCount(status="PENDING", count=pending),
        ModelVersionStatusCount(status="FAILED", count=failed),
    ]

    # Model sizes (from catalog_models, active models only)
    active_names = (await session.execute(
        select(RegisteredModel.name).where(RegisteredModel.status != "deleted")
    )).scalars().all()

    cm_result = await session.execute(
        select(CatalogModel.model_name, CatalogModel.model_size_bytes)
        .where(
            CatalogModel.model_name.in_(active_names),
            CatalogModel.model_size_bytes.is_not(None),
        )
        .order_by(CatalogModel.model_size_bytes.desc())
    )
    seen: set[str] = set()
    model_sizes = []
    for name, size in cm_result.all():
        if name not in seen and size:
            seen.add(name)
            model_sizes.append(ModelSizeInfo(model_name=name, model_size_bytes=size))

    # Versions per model (active only)
    ver_result = await session.execute(
        select(RegisteredModel.name, RegisteredModel.max_version_number)
        .where(RegisteredModel.status != "deleted")
        .order_by(RegisteredModel.max_version_number.desc())
    )
    versions_per_model = [
        ModelVersionCount(model_name=name, version_count=count)
        for name, count in ver_result.all()
    ]

    # Download stats
    from app.models.download_log import (
        get_total_download_count,
        get_hourly_download,
        get_daily_download,
        get_download_count_by_model,
    )
    total_download = await get_total_download_count(session)

    hourly_raw = await get_hourly_download(session, hours=24)
    daily_1d = [DataPoint(date=d["date"], count=d["count"]) for d in hourly_raw]

    daily_7d_raw = await get_daily_download(session, days=7)
    daily_7d = [DataPoint(date=d["date"], count=d["count"]) for d in daily_7d_raw]

    daily_30d_raw = await get_daily_download(session, days=30)
    daily_30d = [DataPoint(date=d["date"], count=d["count"]) for d in daily_30d_raw]

    download_by_model = await get_download_count_by_model(session)

    # Publish stats
    from app.models.download_log import (
        get_total_publish_count,
        get_hourly_publish,
        get_daily_publish,
    )
    total_publish = await get_total_publish_count(session)

    pub_1d_raw = await get_hourly_publish(session, hours=24)
    pub_1d = [DataPoint(date=d["date"], count=d["count"]) for d in pub_1d_raw]

    pub_7d_raw = await get_daily_publish(session, days=7)
    pub_7d = [DataPoint(date=d["date"], count=d["count"]) for d in pub_7d_raw]

    pub_30d_raw = await get_daily_publish(session, days=30)
    pub_30d = [DataPoint(date=d["date"], count=d["count"]) for d in pub_30d_raw]

    return ModelStats(
        total_models=total_models,
        total_versions=total_versions,
        ready_models=ready_models,
        ready_versions=ready_versions,
        pending_count=pending,
        failed_count=failed,
        total_download=total_download,
        status_distribution=status_distribution,
        model_sizes=model_sizes,
        versions_per_model=versions_per_model,
        daily_download_1d=daily_1d,
        daily_download_7d=daily_7d,
        daily_download_30d=daily_30d,
        download_by_model=download_by_model,
        total_publish=total_publish,
        daily_publish_1d=pub_1d,
        daily_publish_7d=pub_7d,
        daily_publish_30d=pub_30d,
    )


async def get_model_detail(
    session: AsyncSession, name: str,
) -> ModelDetailResponse | None:
    """Get full model detail with latest version metadata and download count."""
    model = await _resolve_model(session, name)
    if not model:
        return None

    # Latest version status
    latest_ver = (await session.execute(
        select(ModelVersion.status).where(
            ModelVersion.model_id == model.id,
        ).order_by(ModelVersion.version.desc()).limit(1)
    )).scalar()

    # catalog_models for latest version
    cm = (await session.execute(
        select(CatalogModel).where(
            CatalogModel.model_name == name,
        ).order_by(CatalogModel.version.desc()).limit(1)
    )).scalars().first()

    catalog = None
    if cm:
        catalog = CatalogModelDetail(
            predict_fn=cm.predict_fn,
            python_version=cm.python_version,
            serialization_format=cm.serialization_format,
            sklearn_version=cm.sklearn_version,
            mlflow_version=cm.mlflow_version,
            mlflow_model_id=cm.mlflow_model_id,
            model_size_bytes=cm.model_size_bytes,
            utc_time_created=cm.utc_time_created,
            requirements=cm.requirements,
            conda=cm.conda,
            python_env=cm.python_env,
            source_type=cm.source_type,
        )

    # Download count
    from app.models.download_log import get_download_count_by_model
    download_counts = await get_download_count_by_model(session)

    return ModelDetailResponse(
        id=model.id,
        name=model.name,
        urn=model.urn,
        description=model.description,
        owner=model.owner,
        storage_type=model.storage_type,
        storage_location=model.storage_location,
        max_version_number=model.max_version_number,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
        latest_version_status=latest_ver,
        catalog=catalog,
        download_count=download_counts.get(name, 0),
    )


async def get_model_download_stats(
    session: AsyncSession, name: str,
) -> ModelDownloadStats:
    """Get download statistics for a specific model."""
    from app.models.models import ModelDownloadLog

    # Total download for this model
    total = (await session.execute(
        select(func.count()).where(ModelDownloadLog.model_name == name)
    )).scalar() or 0

    # Daily download (30 days)
    from datetime import timezone, timedelta
    since = _dt.datetime.now(timezone.utc) - timedelta(days=30)
    daily_result = await session.execute(
        select(
            func.date(ModelDownloadLog.downloaded_at).label("day"),
            func.count().label("count"),
        )
        .where(ModelDownloadLog.model_name == name, ModelDownloadLog.downloaded_at >= since)
        .group_by(func.date(ModelDownloadLog.downloaded_at))
        .order_by(func.date(ModelDownloadLog.downloaded_at))
    )
    daily = [DataPoint(date=str(r.day), count=r.count) for r in daily_result.all()]

    # Recent logs (last 50)
    recent_result = await session.execute(
        select(ModelDownloadLog)
        .where(ModelDownloadLog.model_name == name)
        .order_by(ModelDownloadLog.downloaded_at.desc())
        .limit(50)
    )
    recent = [
        DownloadLogEntry(
            downloaded_at=r.downloaded_at,
            version=r.version,
            download_type=r.download_type,
            client_ip=r.client_ip,
            user_agent=r.user_agent,
        )
        for r in recent_result.scalars().all()
    ]

    return ModelDownloadStats(total_download=total, daily_download=daily, recent_logs=recent)


async def update_registered_model(
    session: AsyncSession, name: str, req: RegisteredModelUpdate,
) -> RegisteredModelResponse | None:
    result = await session.execute(
        select(RegisteredModel).where(
            RegisteredModel.name == name,
            RegisteredModel.status != "deleted",
        )
    )
    model = result.scalars().first()
    if not model:
        return None

    if req.name is not None:
        # Check new name uniqueness
        if req.name != model.name:
            dup = await session.execute(
                select(RegisteredModel).where(RegisteredModel.name == req.name)
            )
            if dup.scalars().first():
                raise ValueError(f"Model with name '{req.name}' already exists")
            model.name = req.name
            model.urn = _generate_model_urn(req.name)
    if req.description is not None:
        model.description = req.description
    if req.owner is not None:
        model.owner = req.owner

    await session.commit()
    await session.refresh(model)
    logger.info("RegisteredModel updated: %s (id=%d)", model.name, model.id)
    return RegisteredModelResponse.model_validate(model)


async def delete_registered_model(session: AsyncSession, name: str) -> bool:
    result = await session.execute(
        select(RegisteredModel).where(
            RegisteredModel.name == name,
            RegisteredModel.status != "deleted",
        )
    )
    model = result.scalars().first()
    if not model:
        return False

    model.status = "deleted"

    # Mark pending versions as failed
    pending = await session.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.status == "PENDING_REGISTRATION",
        )
    )
    for ver in pending.scalars().all():
        ver.status = "FAILED_REGISTRATION"
        ver.status_message = "Model deleted during registration"

    await session.commit()
    logger.info("RegisteredModel deleted (soft): %s (id=%d)", model.name, model.id)
    return True


async def hard_delete_registered_model(session: AsyncSession, name: str) -> bool:
    """Permanently delete a model: DB records (all 3 tables) + disk artifacts."""
    import shutil

    result = await session.execute(
        select(RegisteredModel).where(RegisteredModel.name == name)
    )
    model = result.scalars().first()
    if not model:
        return False

    # Delete catalog_models rows
    cm_result = await session.execute(
        select(CatalogModel).where(CatalogModel.model_name == name)
    )
    for cm in cm_result.scalars().all():
        await session.delete(cm)

    # Delete model_versions rows
    mv_result = await session.execute(
        select(ModelVersion).where(ModelVersion.model_id == model.id)
    )
    for mv in mv_result.scalars().all():
        await session.delete(mv)

    # Delete registered model
    await session.delete(model)
    await session.commit()

    # Delete artifact directory from disk
    art_dir = _model_artifacts_root() / name
    if art_dir.exists():
        try:
            shutil.rmtree(art_dir)
            logger.info("Deleted artifact directory: %s", art_dir)
        except OSError as e:
            logger.warning("Failed to delete artifact directory %s: %s", art_dir, e)

    logger.info("RegisteredModel hard-deleted: %s (id=%d)", name, model.id)
    return True


# ---------------------------------------------------------------------------
# ModelVersion operations
# ---------------------------------------------------------------------------

def _build_version_response(model: RegisteredModel, ver: ModelVersion) -> ModelVersionResponse:
    """Build a ModelVersionResponse from ORM model and version objects."""
    return ModelVersionResponse(
        id=ver.id,
        model_id=ver.model_id,
        model_name=model.name,
        version=ver.version,
        source=ver.source,
        run_id=ver.run_id,
        run_link=ver.run_link,
        description=ver.description,
        status=ver.status,
        status_message=ver.status_message,
        storage_location=ver.storage_location,
        artifact_count=ver.artifact_count or 0,
        artifact_size=ver.artifact_size or 0,
        finished_at=ver.finished_at,
        created_at=ver.created_at,
        updated_at=ver.updated_at,
        created_by=ver.created_by,
        updated_by=ver.updated_by,
    )


async def _resolve_model(session: AsyncSession, name: str) -> RegisteredModel | None:
    """Look up an active (non-deleted) model by name. Returns None if not found."""
    result = await session.execute(
        select(RegisteredModel).where(
            RegisteredModel.name == name,
            RegisteredModel.status != "deleted",
        )
    )
    return result.scalars().first()


async def create_model_version(
    session: AsyncSession, req: ModelVersionCreate,
) -> ModelVersionResponse:
    """Create a new model version with PENDING_REGISTRATION status.

    MLflow calls this after creating the registered model. The version number
    is auto-incremented from the model's max_version_number. Storage location
    uses file:// prefix so MLflow uses LocalArtifactRepository for upload.
    """
    logger.info("Creating model version: model=%s, source=%s, run_id=%s",
                req.model_name, req.source, req.run_id)

    model = await _resolve_model(session, req.model_name)
    if not model:
        raise ValueError(f"Model '{req.model_name}' not found")

    # Atomically increment version number
    model.max_version_number += 1
    new_version = model.max_version_number
    logger.info("Version number assigned: %s → v%d", model.name, new_version)

    # Compute storage location (strip file:// for path operations, re-add for URI)
    base_path = model.storage_location.replace("file://", "") if model.storage_location else ""
    ver_path = str(Path(base_path) / "versions" / str(new_version))
    ver_storage = f"file://{ver_path}"

    ver = ModelVersion(
        model_id=model.id,
        version=new_version,
        source=req.source,
        run_id=req.run_id,
        run_link=req.run_link,
        description=req.description,
        status="PENDING_REGISTRATION",
        storage_location=ver_storage,
    )
    session.add(ver)
    await session.commit()
    await session.refresh(ver)

    # Create artifact directory
    try:
        Path(ver_path).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Failed to create version directory for %s v%d: %s", model.name, new_version, e)
    logger.info("ModelVersion created: %s v%d (id=%d, status=PENDING_REGISTRATION)",
                model.name, new_version, ver.id)
    return _build_version_response(model, ver)


async def get_model_version(
    session: AsyncSession, model_name: str, version: int,
) -> ModelVersionResponse | None:
    model = await _resolve_model(session, model_name)
    if not model:
        return None

    result = await session.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.version == version,
        )
    )
    ver = result.scalars().first()
    if not ver:
        return None
    return _build_version_response(model, ver)


async def list_model_versions(
    session: AsyncSession,
    model_name: str,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedModelVersions | None:
    model = await _resolve_model(session, model_name)
    if not model:
        return None

    base = select(ModelVersion).where(ModelVersion.model_id == model.id)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(ModelVersion.version.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    items = [_build_version_response(model, v) for v in result.scalars().all()]

    return PaginatedModelVersions(items=items, total=total, page=page, page_size=page_size)


async def update_model_version(
    session: AsyncSession, model_name: str, version: int, req: ModelVersionUpdate,
) -> ModelVersionResponse | None:
    model = await _resolve_model(session, model_name)
    if not model:
        return None

    result = await session.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.version == version,
        )
    )
    ver = result.scalars().first()
    if not ver:
        return None

    if req.description is not None:
        ver.description = req.description
    if req.source is not None:
        ver.source = req.source

    await session.commit()
    await session.refresh(ver)
    logger.info("ModelVersion updated: %s v%d", model.name, version)
    return _build_version_response(model, ver)


async def finalize_model_version(
    session: AsyncSession, model_name: str, version: int, req: ModelVersionFinalize,
) -> ModelVersionResponse:
    """Transition a version from PENDING_REGISTRATION to READY or FAILED.

    Called by MLflow after artifact upload is complete. At finalize time:
    - Scans the artifact directory to count files and total size
    - Records finished_at timestamp
    - Optionally records status_message for failures

    These audit fields allow DB-only determination of version health:
      READY + artifact_count>0 + finished_at≠NULL → healthy
      PENDING + finished_at=NULL + old created_at → stuck
    """
    logger.info("Finalizing model version: %s v%d → %s", model_name, version, req.status.value)

    model = await _resolve_model(session, model_name)
    if not model:
        raise ValueError(f"Model '{model_name}' not found")

    result = await session.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.version == version,
        )
    )
    ver = result.scalars().first()
    if not ver:
        raise ValueError(f"Version {version} not found for model '{model_name}'")

    if ver.status != "PENDING_REGISTRATION":
        raise ValueError(
            f"Cannot finalize version {version}: current status is '{ver.status}', "
            "expected 'PENDING_REGISTRATION'"
        )

    if req.status.value not in ("READY", "FAILED_REGISTRATION"):
        raise ValueError(f"Invalid finalize status: {req.status.value}")

    ver.status = req.status.value
    ver.status_message = req.status_message
    ver.finished_at = _dt.datetime.now(_dt.timezone.utc)

    # Count artifacts on disk
    art_path = None
    if ver.storage_location:
        art_path = Path(ver.storage_location.replace("file://", ""))
        if art_path.exists():
            files = [f for f in art_path.rglob("*") if f.is_file()]
            ver.artifact_count = len(files)
            ver.artifact_size = sum(f.stat().st_size for f in files)

    # Parse artifact files and insert into catalog_models (READY only)
    if req.status.value == "READY" and art_path and art_path.exists():
        await _save_catalog_model(session, model.name, version, ver.id, art_path)

    await session.commit()
    await session.refresh(ver)
    logger.info("ModelVersion finalized: %s v%d → %s (artifacts=%d, size=%d)",
                model.name, version, ver.status,
                ver.artifact_count or 0, ver.artifact_size or 0)
    return _build_version_response(model, ver)


async def delete_model_version(
    session: AsyncSession, model_name: str, version: int,
) -> bool:
    model = await _resolve_model(session, model_name)
    if not model:
        return False

    result = await session.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.version == version,
        )
    )
    ver = result.scalars().first()
    if not ver:
        return False

    await session.delete(ver)
    await session.commit()
    logger.info("ModelVersion deleted: %s v%d", model.name, version)
    return True


# ---------------------------------------------------------------------------
# Catalog model metadata extraction
# ---------------------------------------------------------------------------

def _read_file_text(path: Path) -> str | None:
    """Read a text file, returning None if it doesn't exist."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _parse_utc_to_local(utc_str: str | None) -> _dt.datetime | None:
    """Convert a UTC datetime string (e.g. '2026-03-20 19:40:55.665301') to local timezone."""
    if not utc_str:
        return None
    try:
        utc_dt = _dt.datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S.%f").replace(
            tzinfo=_dt.timezone.utc,
        )
        return utc_dt.astimezone()
    except (ValueError, TypeError):
        logger.warning("Failed to parse utc_time_created: %s", utc_str)
        return None


def _extract_mlmodel_fields(art_path: Path) -> dict:
    """Parse MLmodel YAML and extract metadata fields."""
    mlmodel_path = art_path / "MLmodel"
    if not mlmodel_path.is_file():
        logger.warning("MLmodel file not found in %s", art_path)
        return {}

    try:
        data = yaml.safe_load(mlmodel_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to parse MLmodel YAML in %s: %s", art_path, e)
        return {}

    if not isinstance(data, dict):
        return {}

    # Top-level fields
    utc_time_created = data.get("utc_time_created")
    model_size_bytes = data.get("model_size_bytes")
    mlflow_version = data.get("mlflow_version")
    model_id = data.get("model_uuid") or data.get("model_id")

    # Flavors — extract from sklearn or python_function
    flavors = data.get("flavors", {})

    sklearn_flavor = flavors.get("sklearn", {})
    sklearn_version = sklearn_flavor.get("sklearn_version")
    serialization_format = sklearn_flavor.get("serialization_format")

    python_fn = flavors.get("python_function", {})
    predict_fn = python_fn.get("predict_fn")
    python_version = python_fn.get("python_version")

    return {
        "predict_fn": predict_fn,
        "python_version": python_version,
        "serialization_format": serialization_format,
        "sklearn_version": sklearn_version,
        "mlflow_version": mlflow_version,
        "mlflow_model_id": model_id,
        "model_size_bytes": int(model_size_bytes) if model_size_bytes is not None else None,
        "utc_time_created": utc_time_created,
        "time_created": _parse_utc_to_local(utc_time_created),
    }


async def _save_catalog_model(
    session: AsyncSession,
    model_name: str,
    version: int,
    model_version_id: int,
    art_path: Path,
) -> None:
    """Extract metadata from artifact files and save to catalog_models table."""
    try:
        # Read raw text files
        requirements = _read_file_text(art_path / "requirements.txt")
        conda = _read_file_text(art_path / "conda.yaml")
        python_env = _read_file_text(art_path / "python_env.yaml")

        # Parse MLmodel YAML
        ml_fields = _extract_mlmodel_fields(art_path)

        catalog_model = CatalogModel(
            model_version_id=model_version_id,
            model_name=model_name,
            version=version,
            requirements=requirements,
            conda=conda,
            python_env=python_env,
            **ml_fields,
        )
        session.add(catalog_model)
        logger.info(
            "CatalogModel saved: %s v%d (predict_fn=%s, sklearn=%s, mlflow=%s)",
            model_name, version,
            ml_fields.get("predict_fn"),
            ml_fields.get("sklearn_version"),
            ml_fields.get("mlflow_version"),
        )
    except Exception as e:
        logger.error("Failed to save catalog_model for %s v%d: %s", model_name, version, e)
