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

import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import ModelVersion, RegisteredModel
from app.models.schemas import (
    ModelVersionCreate,
    ModelVersionFinalize,
    ModelVersionResponse,
    ModelVersionUpdate,
    PaginatedModelVersions,
    PaginatedRegisteredModels,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
)

logger = logging.getLogger(__name__)


def _model_artifacts_root() -> Path:
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
    Path(storage.replace("file://", "")).mkdir(parents=True, exist_ok=True)
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


# ---------------------------------------------------------------------------
# ModelVersion operations
# ---------------------------------------------------------------------------

def _build_version_response(model: RegisteredModel, ver: ModelVersion) -> ModelVersionResponse:
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
    Path(ver_path).mkdir(parents=True, exist_ok=True)
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

    import datetime as _dt

    ver.status = req.status.value
    ver.status_message = req.status_message
    ver.finished_at = _dt.datetime.now(_dt.timezone.utc)

    # Count artifacts on disk
    if ver.storage_location:
        art_path = Path(ver.storage_location.replace("file://", ""))
        if art_path.exists():
            files = [f for f in art_path.rglob("*") if f.is_file()]
            ver.artifact_count = len(files)
            ver.artifact_size = sum(f.stat().st_size for f in files)

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
