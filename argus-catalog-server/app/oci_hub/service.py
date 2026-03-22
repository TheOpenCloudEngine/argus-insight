"""OCI Model Hub service — CRUD, tags, lineage, import."""

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.oci_hub.models import OciModel, OciModelLineage, OciModelTag, OciModelVersion
from app.oci_hub.schemas import (
    ImportResponse,
    LineageResponse,
    OciModelCreate,
    OciModelDetail,
    OciModelSummary,
    OciModelUpdate,
    OciModelVersionResponse,
    PaginatedOciModels,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tags(session: AsyncSession, model_id: int) -> list[dict]:
    """Get tags for a model (joined with catalog_tags)."""
    from sqlalchemy import text
    result = await session.execute(text(
        "SELECT t.id, t.name, t.color FROM catalog_tags t "
        "JOIN catalog_oci_model_tags mt ON mt.tag_id = t.id "
        "WHERE mt.model_id = :mid ORDER BY t.name"
    ), {"mid": model_id})
    return [{"id": r[0], "name": r[1], "color": r[2]} for r in result.all()]


async def _get_lineage(session: AsyncSession, model_id: int) -> list[dict]:
    """Get lineage entries for a model."""
    result = await session.execute(
        select(OciModelLineage).where(OciModelLineage.model_id == model_id)
        .order_by(OciModelLineage.created_at)
    )
    return [
        {
            "id": r.id, "source_type": r.source_type, "source_id": r.source_id,
            "source_name": r.source_name, "relation_type": r.relation_type,
            "description": r.description, "created_at": r.created_at.isoformat(),
        }
        for r in result.scalars().all()
    ]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_models(
    session: AsyncSession,
    search: str | None = None,
    task: str | None = None,
    framework: str | None = None,
    language: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 12,
) -> PaginatedOciModels:
    """List OCI models with filters and pagination."""
    base = select(OciModel)
    if search:
        base = base.where(OciModel.name.ilike(f"%{search}%"))
    if task:
        base = base.where(OciModel.task == task)
    if framework:
        base = base.where(OciModel.framework == framework)
    if language:
        base = base.where(OciModel.language == language)
    if status:
        base = base.where(OciModel.status == status)

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(OciModel.updated_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    models = result.scalars().all()

    items = []
    for m in models:
        tags = await _get_tags(session, m.id)
        items.append(OciModelSummary(
            id=m.id, name=m.name, display_name=m.display_name,
            description=m.description, task=m.task, framework=m.framework,
            language=m.language, license=m.license, source_type=m.source_type,
            owner=m.owner, version_count=m.version_count,
            total_size=m.total_size or 0, download_count=m.download_count,
            status=m.status, tags=tags,
            created_at=m.created_at, updated_at=m.updated_at,
        ))

    logger.info("Listed OCI models: search=%s, total=%d, page=%d", search, total, page)
    return PaginatedOciModels(items=items, total=total, page=page, page_size=page_size)


async def create_model(session: AsyncSession, req: OciModelCreate) -> OciModelDetail:
    """Create a new OCI model."""
    existing = await session.execute(
        select(OciModel).where(OciModel.name == req.name)
    )
    if existing.scalars().first():
        raise ValueError(f"Model '{req.name}' already exists")

    model = OciModel(
        name=req.name, display_name=req.display_name or req.name,
        description=req.description, readme=req.readme,
        task=req.task, framework=req.framework, language=req.language,
        license=req.license, source_type=req.source_type, source_id=req.source_id,
        owner=req.owner, status=req.status,
        bucket=settings.os_bucket, storage_prefix=f"{req.name}/",
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    logger.info("OCI model created: %s (id=%d)", model.name, model.id)
    return await get_model_detail(session, model.name)


async def get_model_detail(session: AsyncSession, name: str) -> OciModelDetail | None:
    """Get full model detail with tags and lineage."""
    result = await session.execute(
        select(OciModel).where(OciModel.name == name)
    )
    m = result.scalars().first()
    if not m:
        return None

    tags = await _get_tags(session, m.id)
    lineage = await _get_lineage(session, m.id)

    return OciModelDetail(
        id=m.id, name=m.name, display_name=m.display_name,
        description=m.description, readme=m.readme,
        task=m.task, framework=m.framework, language=m.language,
        license=m.license, source_type=m.source_type, source_id=m.source_id,
        source_revision=m.source_revision, bucket=m.bucket,
        storage_prefix=m.storage_prefix, owner=m.owner,
        version_count=m.version_count, total_size=m.total_size or 0,
        download_count=m.download_count, status=m.status,
        tags=tags, lineage=lineage,
        created_at=m.created_at, updated_at=m.updated_at,
    )


async def update_model(session: AsyncSession, name: str, req: OciModelUpdate) -> OciModelDetail | None:
    """Update model metadata."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return None

    for field in ["display_name", "description", "task", "framework", "language", "license", "owner", "status"]:
        val = getattr(req, field)
        if val is not None:
            setattr(m, field, val)

    await session.commit()
    await session.refresh(m)
    logger.info("OCI model updated: %s", name)
    return await get_model_detail(session, name)


async def update_readme(session: AsyncSession, name: str, readme: str) -> bool:
    """Update model README (Markdown)."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return False
    m.readme = readme
    await session.commit()
    logger.info("OCI model README updated: %s", name)
    return True


async def delete_model(session: AsyncSession, name: str) -> bool:
    """Delete a model and all associated data."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return False
    await session.delete(m)
    await session.commit()
    logger.info("OCI model deleted: %s (id=%d)", name, m.id)
    return True


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

async def add_tag(session: AsyncSession, name: str, tag_id: int) -> bool:
    """Add a tag to a model."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return False
    session.add(OciModelTag(model_id=m.id, tag_id=tag_id))
    await session.commit()
    logger.info("Tag %d added to OCI model %s", tag_id, name)
    return True


async def remove_tag(session: AsyncSession, name: str, tag_id: int) -> bool:
    """Remove a tag from a model."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return False
    tag = (await session.execute(
        select(OciModelTag).where(OciModelTag.model_id == m.id, OciModelTag.tag_id == tag_id)
    )).scalars().first()
    if not tag:
        return False
    await session.delete(tag)
    await session.commit()
    logger.info("Tag %d removed from OCI model %s", tag_id, name)
    return True


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

async def add_lineage(session: AsyncSession, name: str, **kwargs) -> LineageResponse | None:
    """Add a lineage entry."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return None
    entry = OciModelLineage(model_id=m.id, **kwargs)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    logger.info("Lineage added to OCI model %s: %s -> %s", name, kwargs.get("relation_type"), kwargs.get("source_id"))
    return LineageResponse.model_validate(entry)


async def remove_lineage(session: AsyncSession, lineage_id: int) -> bool:
    """Remove a lineage entry."""
    entry = await session.get(OciModelLineage, lineage_id)
    if not entry:
        return False
    await session.delete(entry)
    await session.commit()
    logger.info("Lineage %d removed", lineage_id)
    return True


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

async def list_versions(session: AsyncSession, name: str) -> list[OciModelVersionResponse]:
    """List all versions for a model."""
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    m = result.scalars().first()
    if not m:
        return []
    versions = (await session.execute(
        select(OciModelVersion).where(OciModelVersion.model_id == m.id)
        .order_by(OciModelVersion.version.desc())
    )).scalars().all()
    return [OciModelVersionResponse.model_validate(v) for v in versions]


# ---------------------------------------------------------------------------
# Finalize Push (SDK/manual upload)
# ---------------------------------------------------------------------------

async def finalize_push(
    session: AsyncSession,
    name: str,
    version: int,
    readme: str | None = None,
) -> OciModelVersionResponse | None:
    """Finalize a manually pushed version.

    Scans S3 files, generates OCI manifest, creates version record,
    and updates model stats (version_count, total_size, readme).
    Called by SDK after uploading files via model-store API.
    """
    from app.models import model_store

    result = await session.execute(select(OciModel).where(OciModel.name == name))
    model = result.scalars().first()
    if not model:
        return None

    # Scan S3 files
    file_count, total_size = await model_store.get_total_size(name, version)
    if file_count == 0:
        raise ValueError(f"No files found in S3 for {name}/v{version}")

    # Generate OCI manifest
    manifest = await model_store.generate_manifest(name, version)

    # Check if version record already exists
    existing = (await session.execute(
        select(OciModelVersion).where(
            OciModelVersion.model_id == model.id,
            OciModelVersion.version == version,
        )
    )).scalars().first()

    if existing:
        # Update existing
        existing.file_count = file_count
        existing.total_size = total_size
        existing.manifest = json.dumps(manifest)
        existing.status = "ready"
        ver = existing
    else:
        # Create new version record
        ver = OciModelVersion(
            model_id=model.id, version=version,
            manifest=json.dumps(manifest),
            file_count=file_count,
            total_size=total_size,
            status="ready",
        )
        session.add(ver)

    # Update model stats
    model.version_count = max(model.version_count, version)
    model.total_size = total_size
    if readme:
        model.readme = readme
    if model.status == "draft":
        model.status = "approved"

    await session.commit()
    await session.refresh(ver)

    logger.info("Finalize push: %s v%d (%d files, %d bytes)", name, version, file_count, total_size)
    return OciModelVersionResponse.model_validate(ver)


# ---------------------------------------------------------------------------
# Import from HuggingFace
# ---------------------------------------------------------------------------

async def import_from_huggingface(session: AsyncSession, **kwargs) -> ImportResponse:
    """Import a model from HuggingFace Hub into OCI Model Hub."""
    from app.models import model_store

    hf_model_id = kwargs["hf_model_id"]
    name = kwargs.get("name") or hf_model_id.replace("/", "-")
    revision = kwargs.get("revision", "main")

    logger.info("Importing HF model %s as %s", hf_model_id, name)

    # Create or get model
    result = await session.execute(select(OciModel).where(OciModel.name == name))
    model = result.scalars().first()
    if not model:
        model = OciModel(
            name=name, display_name=name,
            description=kwargs.get("description"),
            task=kwargs.get("task"), framework=kwargs.get("framework"),
            language=kwargs.get("language"),
            source_type="huggingface", source_id=hf_model_id,
            source_revision=revision, owner=kwargs.get("owner"),
            bucket=settings.os_bucket, storage_prefix=f"{name}/",
            status="draft",
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)

    # Increment version
    model.version_count += 1
    version = model.version_count

    # Import files to S3
    metadata = await model_store.import_from_huggingface(
        hf_model_id=hf_model_id, model_name=name,
        version=version, revision=revision,
    )

    # Create version record with full metadata
    ver_metadata = {
        "source": f"huggingface:{hf_model_id}",
        "model_type": metadata.get("model_type"),
        "architectures": metadata.get("architectures"),
        "torch_dtype": metadata.get("torch_dtype"),
        "transformers_version": metadata.get("transformers_version"),
        "hidden_size": metadata.get("hidden_size"),
        "num_hidden_layers": metadata.get("num_hidden_layers"),
        "num_attention_heads": metadata.get("num_attention_heads"),
        "vocab_size": metadata.get("vocab_size"),
        "tokenizer_class": metadata.get("tokenizer_class"),
    }
    # Remove None values
    ver_metadata = {k: v for k, v in ver_metadata.items() if v is not None}

    ver = OciModelVersion(
        model_id=model.id, version=version,
        manifest=json.dumps(metadata.get("manifest")),
        file_count=metadata["file_count"],
        total_size=metadata["total_size"],
        extra_metadata=ver_metadata,
        status="ready",
    )
    session.add(ver)
    model.total_size = metadata["total_size"]

    # Fill model fields from HF metadata
    if not model.framework and metadata.get("transformers_version"):
        model.framework = "pytorch"
    if metadata.get("model_type"):
        model.description = model.description or f"{metadata['model_type']} model from HuggingFace"

    # Store README as Model Card
    if metadata.get("readme") and not model.readme:
        model.readme = metadata["readme"]

    # Import complete — set status to approved
    model.status = "approved"

    await session.commit()

    logger.info("HF import complete: %s v%d (%d files, %d bytes)",
                name, version, metadata["file_count"], metadata["total_size"])

    return ImportResponse(
        name=name, version=version,
        file_count=metadata["file_count"],
        total_size=metadata["total_size"],
        status="ready",
    )


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

async def get_hub_stats(session: AsyncSession) -> dict:
    """Get OCI Model Hub dashboard statistics."""
    # Total models
    total_models = (await session.execute(select(func.count()).select_from(OciModel))).scalar() or 0

    # Total versions
    total_versions = (await session.execute(select(func.count()).select_from(OciModelVersion))).scalar() or 0

    # By source type
    source_counts_raw = (await session.execute(
        select(OciModel.source_type, func.count()).group_by(OciModel.source_type)
    )).all()
    source_counts = {(s or "unknown"): c for s, c in source_counts_raw}
    hf_count = source_counts.get("huggingface", 0)
    my_count = source_counts.get("my", 0)

    # Total downloads
    total_downloads = (await session.execute(
        select(func.sum(OciModel.download_count))
    )).scalar() or 0

    # Source distribution (for donut chart)
    source_distribution = [
        {"source": s, "count": c} for s, c in source_counts.items()
    ]

    # Model sizes top 10
    size_result = (await session.execute(
        select(OciModel.name, OciModel.total_size)
        .where(OciModel.total_size > 0)
        .order_by(OciModel.total_size.desc())
        .limit(10)
    )).all()
    model_sizes = [{"model_name": n, "total_size": s} for n, s in size_result]

    # Downloads top 10
    dl_result = (await session.execute(
        select(OciModel.name, OciModel.download_count)
        .where(OciModel.download_count > 0)
        .order_by(OciModel.download_count.desc())
        .limit(10)
    )).all()
    top_downloads = [{"model_name": n, "download_count": c} for n, c in dl_result]

    # Download trends (from OCI-specific download log)
    from datetime import timezone, timedelta
    from sqlalchemy import text
    import datetime as _dt
    from app.oci_hub.models import OciModelDownloadLog

    now = _dt.datetime.now(timezone.utc)

    # Hourly download (24h)
    since_1d = now - timedelta(hours=24)
    result = await session.execute(
        select(
            func.date_trunc("hour", OciModelDownloadLog.downloaded_at).label("hour"),
            func.count().label("count"),
        )
        .where(OciModelDownloadLog.downloaded_at >= since_1d)
        .group_by(text("hour")).order_by(text("hour"))
    )
    download_1d = [{"date": r.hour.strftime("%H:%M") if r.hour else "", "count": r.count} for r in result.all()]

    # Daily download (7d)
    since_7d = now - timedelta(days=7)
    result = await session.execute(
        select(func.date(OciModelDownloadLog.downloaded_at).label("day"), func.count().label("count"))
        .where(OciModelDownloadLog.downloaded_at >= since_7d)
        .group_by(func.date(OciModelDownloadLog.downloaded_at)).order_by(text("day"))
    )
    download_7d = [{"date": str(r.day), "count": r.count} for r in result.all()]

    # Daily download (30d)
    since_30d = now - timedelta(days=30)
    result = await session.execute(
        select(func.date(OciModelDownloadLog.downloaded_at).label("day"), func.count().label("count"))
        .where(OciModelDownloadLog.downloaded_at >= since_30d)
        .group_by(func.date(OciModelDownloadLog.downloaded_at)).order_by(text("day"))
    )
    download_30d = [{"date": str(r.day), "count": r.count} for r in result.all()]

    # Total download for OCI models
    total_download = (await session.execute(
        select(func.count()).select_from(OciModelDownloadLog)
    )).scalar() or 0

    # Publish trends (from oci_model_versions.created_at)
    # Hourly publish (24h)
    pub_1d_result = await session.execute(
        select(func.date_trunc("hour", OciModelVersion.created_at).label("hour"), func.count().label("count"))
        .where(OciModelVersion.created_at >= now - timedelta(hours=24))
        .group_by(text("hour")).order_by(text("hour"))
    )
    publish_1d = [{"date": r.hour.strftime("%H:%M") if r.hour else "", "count": r.count} for r in pub_1d_result.all()]

    # Daily publish (7d)
    pub_7d_result = await session.execute(
        select(func.date(OciModelVersion.created_at).label("day"), func.count().label("count"))
        .where(OciModelVersion.created_at >= now - timedelta(days=7))
        .group_by(func.date(OciModelVersion.created_at)).order_by(text("day"))
    )
    publish_7d = [{"date": str(r.day), "count": r.count} for r in pub_7d_result.all()]

    # Daily publish (30d)
    pub_30d_result = await session.execute(
        select(func.date(OciModelVersion.created_at).label("day"), func.count().label("count"))
        .where(OciModelVersion.created_at >= now - timedelta(days=30))
        .group_by(func.date(OciModelVersion.created_at)).order_by(text("day"))
    )
    publish_30d = [{"date": str(r.day), "count": r.count} for r in pub_30d_result.all()]

    total_publish = total_versions

    return {
        "total_models": total_models,
        "total_versions": total_versions,
        "hf_count": hf_count,
        "my_count": my_count,
        "total_downloads": total_downloads,
        "total_download": total_download,
        "total_publish": total_publish,
        "source_distribution": source_distribution,
        "model_sizes": model_sizes,
        "top_downloads": top_downloads,
        "download_1d": download_1d,
        "download_7d": download_7d,
        "download_30d": download_30d,
        "publish_1d": publish_1d,
        "publish_7d": publish_7d,
        "publish_30d": publish_30d,
    }
