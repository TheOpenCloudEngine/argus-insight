"""Data catalog service layer.

Provides CRUD operations for datasets, platforms, tags, glossary terms, and owners.
"""

import logging
import os
import time

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import (
    Dataset,
    DatasetGlossaryTerm,
    DatasetProperty,
    DatasetSchema,
    DatasetTag,
    GlossaryTerm,
    Owner,
    Platform,
    PlatformConfiguration,
    PlatformDataType,
    PlatformFeature,
    PlatformStorageFormat,
    PlatformTableType,
    SchemaSnapshot,
    Tag,
)
from app.catalog.schemas import (
    CatalogStats,
    DatasetCreate,
    DatasetPropertyResponse,
    DatasetResponse,
    DatasetSummary,
    DatasetUpdate,
    GlossaryTermCreate,
    GlossaryTermResponse,
    OwnerCreate,
    OwnerResponse,
    PaginatedDatasets,
    PlatformCreate,
    PlatformUpdate,
    PlatformDataTypeResponse,
    PlatformFeatureResponse,
    PlatformMetadataResponse,
    PlatformResponse,
    PlatformStorageFormatResponse,
    PlatformTableTypeResponse,
    SchemaFieldResponse,
    PaginatedSchemaSnapshots,
    SchemaChangeEntry,
    SchemaSnapshotResponse,
    TagCreate,
    TagResponse,
    TagUsage,
)

logger = logging.getLogger(__name__)


def _generate_platform_id(platform_type: str) -> str:
    """Generate a platform ID: {type}-{timestamp_hex}{random_hex} (total suffix = 16 chars).

    Format: 10-char ms timestamp hex + 6-char random hex = 16 chars.
    Same millisecond → different random suffix (2^24 = 16M possibilities).
    """
    timestamp_ms = int(time.time() * 1000)
    ts_hex = format(timestamp_ms, "010x")
    rand_hex = os.urandom(3).hex()  # 6 hex chars = 24 bits
    return f"{platform_type}-{ts_hex}{rand_hex}"


def _generate_urn(platform_id: str, path: str, env: str, entity_type: str = "dataset") -> str:
    """Generate a URN: {platform_id}.{path}.{ENV}.{type}"""
    return f"{platform_id}.{path}.{env}.{entity_type}"


# ---------------------------------------------------------------------------
# Platform operations
# ---------------------------------------------------------------------------

async def list_platforms(session: AsyncSession) -> list[PlatformResponse]:
    result = await session.execute(select(Platform).order_by(Platform.name))
    return [PlatformResponse.model_validate(p) for p in result.scalars().all()]


async def create_platform(session: AsyncSession, req: PlatformCreate) -> PlatformResponse:
    platform = Platform(
        platform_id=_generate_platform_id(req.type),
        name=req.name,
        type=req.type,
        logo_url=req.logo_url,
    )
    session.add(platform)
    await session.commit()
    await session.refresh(platform)
    logger.info("Platform created: %s (id=%d)", platform.name, platform.id)
    return PlatformResponse.model_validate(platform)


async def get_platform(session: AsyncSession, platform_id: int) -> PlatformResponse | None:
    result = await session.execute(select(Platform).where(Platform.id == platform_id))
    platform = result.scalars().first()
    if not platform:
        return None
    return PlatformResponse.model_validate(platform)


async def update_platform(
    session: AsyncSession, platform_id: int, req: PlatformUpdate
) -> PlatformResponse | None:
    result = await session.execute(select(Platform).where(Platform.id == platform_id))
    platform = result.scalars().first()
    if not platform:
        return None
    if req.name is not None:
        platform.name = req.name
    await session.commit()
    await session.refresh(platform)
    logger.info("Platform updated: %s (id=%d)", platform.name, platform.id)
    return PlatformResponse.model_validate(platform)


async def delete_platform(session: AsyncSession, platform_id: int) -> bool:
    result = await session.execute(select(Platform).where(Platform.id == platform_id))
    platform = result.scalars().first()
    if not platform:
        return False
    await session.delete(platform)
    await session.commit()
    return True


async def get_platform_configuration(
    session: AsyncSession, platform_id: int
) -> dict | None:
    """Return the configuration dict for a platform, or None if not found."""
    import json as _json

    result = await session.execute(
        select(PlatformConfiguration).where(
            PlatformConfiguration.platform_id == platform_id
        )
    )
    row = result.scalars().first()
    if not row:
        return None
    return {
        "id": row.id,
        "platform_id": row.platform_id,
        "config": _json.loads(row.config_json),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def save_platform_configuration(
    session: AsyncSession, platform_id: int, config_dict: dict
) -> dict:
    """Upsert the configuration for a platform and return the saved record."""
    import json as _json

    result = await session.execute(
        select(PlatformConfiguration).where(
            PlatformConfiguration.platform_id == platform_id
        )
    )
    row = result.scalars().first()

    config_text = _json.dumps(config_dict, ensure_ascii=False)

    if row:
        row.config_json = config_text
    else:
        row = PlatformConfiguration(
            platform_id=platform_id,
            config_json=config_text,
        )
        session.add(row)

    await session.commit()
    await session.refresh(row)
    logger.info("Platform configuration saved: platform_id=%d", platform_id)
    return {
        "id": row.id,
        "platform_id": row.platform_id,
        "config": _json.loads(row.config_json),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def get_platform_dataset_count(session: AsyncSession, platform_id: int) -> int:
    """Count datasets that belong to the given platform."""
    result = await session.execute(
        select(func.count()).select_from(Dataset).where(
            Dataset.platform_id == platform_id,
            Dataset.status != "removed",
        )
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------

async def list_tags(session: AsyncSession) -> list[TagResponse]:
    result = await session.execute(select(Tag).order_by(Tag.name))
    return [TagResponse.model_validate(t) for t in result.scalars().all()]


async def create_tag(session: AsyncSession, req: TagCreate) -> TagResponse:
    tag = Tag(name=req.name, description=req.description, color=req.color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    logger.info("Tag created: %s (id=%d)", tag.name, tag.id)
    return TagResponse.model_validate(tag)


async def get_tag_usage(session: AsyncSession, tag_id: int) -> TagUsage | None:
    """Get tag usage: which datasets reference this tag."""
    result = await session.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalars().first()
    if not tag:
        return None

    tag_resp = TagResponse.model_validate(tag)

    # Find datasets using this tag
    dataset_query = (
        select(
            Dataset.id,
            Dataset.urn,
            Dataset.name,
            Platform.name.label("platform_name"),
            Platform.type.label("platform_type"),
            Dataset.description,
            Dataset.origin,
            Dataset.status,
            Dataset.created_at,
            Dataset.updated_at,
        )
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(
            Dataset.id.in_(
                select(DatasetTag.dataset_id).where(DatasetTag.tag_id == tag_id)
            )
        )
        .order_by(Dataset.name)
    )
    result = await session.execute(dataset_query)
    rows = result.all()

    datasets = [
        DatasetSummary(
            id=row.id,
            urn=row.urn,
            name=row.name,
            platform_name=row.platform_name,
            platform_type=row.platform_type,
            description=row.description,
            origin=row.origin,
            status=row.status,
            is_synced="false",
            tag_count=0,
            owner_count=0,
            schema_field_count=0,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]

    return TagUsage(tag=tag_resp, datasets=datasets, total_datasets=len(datasets))


async def delete_tag(session: AsyncSession, tag_id: int) -> bool:
    result = await session.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalars().first()
    if not tag:
        return False
    await session.delete(tag)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Glossary term operations
# ---------------------------------------------------------------------------

async def list_glossary_terms(session: AsyncSession) -> list[GlossaryTermResponse]:
    result = await session.execute(select(GlossaryTerm).order_by(GlossaryTerm.name))
    return [GlossaryTermResponse.model_validate(t) for t in result.scalars().all()]


async def create_glossary_term(
    session: AsyncSession, req: GlossaryTermCreate
) -> GlossaryTermResponse:
    term = GlossaryTerm(
        name=req.name, description=req.description,
        source=req.source, parent_id=req.parent_id,
    )
    session.add(term)
    await session.commit()
    await session.refresh(term)
    logger.info("Glossary term created: %s (id=%d)", term.name, term.id)
    return GlossaryTermResponse.model_validate(term)


async def delete_glossary_term(session: AsyncSession, term_id: int) -> bool:
    result = await session.execute(
        select(GlossaryTerm).where(GlossaryTerm.id == term_id)
    )
    term = result.scalars().first()
    if not term:
        return False
    await session.delete(term)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Dataset operations
# ---------------------------------------------------------------------------

async def _build_dataset_response(
    session: AsyncSession, dataset: Dataset
) -> DatasetResponse:
    """Build a full DatasetResponse with all related entities."""
    # Platform
    result = await session.execute(select(Platform).where(Platform.id == dataset.platform_id))
    platform = result.scalars().first()

    # Schema fields
    result = await session.execute(
        select(DatasetSchema)
        .where(DatasetSchema.dataset_id == dataset.id)
        .order_by(DatasetSchema.ordinal)
    )
    schema_fields = [SchemaFieldResponse.model_validate(f) for f in result.scalars().all()]

    # Tags
    result = await session.execute(
        select(Tag)
        .join(DatasetTag, DatasetTag.tag_id == Tag.id)
        .where(DatasetTag.dataset_id == dataset.id)
    )
    tags = [TagResponse.model_validate(t) for t in result.scalars().all()]

    # Owners
    result = await session.execute(
        select(Owner).where(Owner.dataset_id == dataset.id)
    )
    owners = [OwnerResponse.model_validate(o) for o in result.scalars().all()]

    # Glossary terms
    result = await session.execute(
        select(GlossaryTerm)
        .join(DatasetGlossaryTerm, DatasetGlossaryTerm.term_id == GlossaryTerm.id)
        .where(DatasetGlossaryTerm.dataset_id == dataset.id)
    )
    glossary_terms = [GlossaryTermResponse.model_validate(t) for t in result.scalars().all()]

    # Properties
    result = await session.execute(
        select(DatasetProperty).where(DatasetProperty.dataset_id == dataset.id)
    )
    properties = [DatasetPropertyResponse.model_validate(p) for p in result.scalars().all()]

    import json as _json
    pp = None
    if dataset.platform_properties:
        try:
            pp = _json.loads(dataset.platform_properties)
        except (ValueError, TypeError):
            pass

    return DatasetResponse(
        id=dataset.id,
        urn=dataset.urn,
        name=dataset.name,
        platform=PlatformResponse.model_validate(platform),
        description=dataset.description,
        origin=dataset.origin,
        qualified_name=dataset.qualified_name,
        table_type=dataset.table_type,
        storage_format=dataset.storage_format,
        status=dataset.status,
        is_synced=dataset.is_synced or "false",
        platform_properties=pp,
        schema_fields=schema_fields,
        tags=tags,
        owners=owners,
        glossary_terms=glossary_terms,
        properties=properties,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


async def create_dataset(session: AsyncSession, req: DatasetCreate) -> DatasetResponse:
    # Get platform for URN generation
    result = await session.execute(select(Platform).where(Platform.id == req.platform_id))
    platform = result.scalars().first()
    if not platform:
        raise ValueError(f"Platform with id {req.platform_id} not found")

    path = req.qualified_name or req.name
    urn = _generate_urn(platform.platform_id, path, req.origin.value)
    qualified_name = f"{platform.platform_id}.{path}"

    dataset = Dataset(
        urn=urn,
        name=req.name,
        platform_id=req.platform_id,
        description=req.description,
        origin=req.origin.value,
        qualified_name=qualified_name,
        table_type=req.table_type,
        storage_format=req.storage_format,
        status="active",
    )
    session.add(dataset)
    await session.flush()

    # Add schema fields
    for idx, field in enumerate(req.schema_fields):
        schema_field = DatasetSchema(
            dataset_id=dataset.id,
            field_path=field.field_path,
            field_type=field.field_type,
            native_type=field.native_type,
            description=field.description,
            nullable=field.nullable,
            ordinal=field.ordinal or idx,
        )
        session.add(schema_field)

    # Attach tags
    for tag_id in req.tags:
        session.add(DatasetTag(dataset_id=dataset.id, tag_id=tag_id))

    # Add owners
    for owner in req.owners:
        session.add(Owner(
            dataset_id=dataset.id,
            owner_name=owner.owner_name,
            owner_type=owner.owner_type.value,
        ))

    # Add properties
    for prop in req.properties:
        session.add(DatasetProperty(
            dataset_id=dataset.id,
            property_key=prop.key,
            property_value=prop.value,
        ))

    await session.commit()
    await session.refresh(dataset)
    logger.info("Dataset created: %s (id=%d, urn=%s)", dataset.name, dataset.id, dataset.urn)
    return await _build_dataset_response(session, dataset)


async def get_dataset(session: AsyncSession, dataset_id: int) -> DatasetResponse | None:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalars().first()
    if not dataset:
        return None
    return await _build_dataset_response(session, dataset)


async def get_dataset_by_urn(session: AsyncSession, urn: str) -> DatasetResponse | None:
    result = await session.execute(select(Dataset).where(Dataset.urn == urn))
    dataset = result.scalars().first()
    if not dataset:
        return None
    return await _build_dataset_response(session, dataset)


async def update_dataset(
    session: AsyncSession, dataset_id: int, req: DatasetUpdate
) -> DatasetResponse | None:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalars().first()
    if not dataset:
        return None

    if req.name is not None:
        dataset.name = req.name
    if req.description is not None:
        dataset.description = req.description
    if req.origin is not None:
        dataset.origin = req.origin.value
    if req.qualified_name is not None:
        dataset.qualified_name = req.qualified_name
    if req.table_type is not None:
        dataset.table_type = req.table_type
    if req.storage_format is not None:
        dataset.storage_format = req.storage_format
    if req.status is not None:
        dataset.status = req.status.value

    # Regenerate URN when origin or qualified_name changes
    if req.origin is not None or req.qualified_name is not None:
        platform_row = await session.execute(
            select(Platform).where(Platform.id == dataset.platform_id)
        )
        platform = platform_row.scalars().first()
        if platform:
            qn = dataset.qualified_name or dataset.name
            prefix = f"{platform.platform_id}."
            path = qn[len(prefix):] if qn.startswith(prefix) else qn
            dataset.urn = _generate_urn(platform.platform_id, path, dataset.origin)

    await session.commit()
    await session.refresh(dataset)
    logger.info("Dataset updated: %s (id=%d)", dataset.name, dataset.id)
    return await _build_dataset_response(session, dataset)


async def delete_dataset(session: AsyncSession, dataset_id: int) -> bool:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalars().first()
    if not dataset:
        return False
    await session.delete(dataset)
    await session.commit()
    logger.info("Dataset deleted: %s (id=%d)", dataset.name, dataset.id)
    return True


async def list_datasets(
    session: AsyncSession,
    search: str | None = None,
    platform: str | None = None,
    origin: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedDatasets:
    """List datasets with optional filtering and pagination."""
    base = (
        select(
            Dataset.id,
            Dataset.urn,
            Dataset.name,
            Platform.name.label("platform_name"),
            Platform.type.label("platform_type"),
            Dataset.description,
            Dataset.origin,
            Dataset.status,
            Dataset.is_synced,
            Dataset.created_at,
            Dataset.updated_at,
        )
        .join(Platform, Dataset.platform_id == Platform.id)
    )

    if search:
        pattern = f"%{search}%"
        base = base.where(
            or_(
                Dataset.name.ilike(pattern),
                Dataset.description.ilike(pattern),
                Dataset.urn.ilike(pattern),
                Dataset.qualified_name.ilike(pattern),
            )
        )

    if platform:
        base = base.where(Platform.platform_id == platform)

    if origin:
        base = base.where(Dataset.origin == origin)

    if status:
        base = base.where(Dataset.status == status)
    else:
        base = base.where(Dataset.status != "removed")

    if tag:
        base = base.where(
            Dataset.id.in_(
                select(DatasetTag.dataset_id)
                .join(Tag, DatasetTag.tag_id == Tag.id)
                .where(Tag.name == tag)
            )
        )

    # Count
    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = base.order_by(Dataset.updated_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.all()

    # Build summaries with counts
    items = []
    for row in rows:
        # Get counts for each dataset
        tag_count = (await session.execute(
            select(func.count()).where(DatasetTag.dataset_id == row.id)
        )).scalar() or 0
        owner_count = (await session.execute(
            select(func.count()).where(Owner.dataset_id == row.id)
        )).scalar() or 0
        field_count = (await session.execute(
            select(func.count()).where(DatasetSchema.dataset_id == row.id)
        )).scalar() or 0

        items.append(DatasetSummary(
            id=row.id,
            urn=row.urn,
            name=row.name,
            platform_name=row.platform_name,
            platform_type=row.platform_type,
            description=row.description,
            origin=row.origin,
            status=row.status,
            is_synced=row.is_synced or "false",
            tag_count=tag_count,
            owner_count=owner_count,
            schema_field_count=field_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ))

    return PaginatedDatasets(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Dataset relationship operations
# ---------------------------------------------------------------------------

async def add_dataset_tag(session: AsyncSession, dataset_id: int, tag_id: int) -> bool:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalars().first():
        return False
    session.add(DatasetTag(dataset_id=dataset_id, tag_id=tag_id))
    await session.commit()
    return True


async def remove_dataset_tag(session: AsyncSession, dataset_id: int, tag_id: int) -> bool:
    result = await session.execute(
        select(DatasetTag)
        .where(DatasetTag.dataset_id == dataset_id, DatasetTag.tag_id == tag_id)
    )
    dt = result.scalars().first()
    if not dt:
        return False
    await session.delete(dt)
    await session.commit()
    return True


async def add_dataset_owner(
    session: AsyncSession, dataset_id: int, req: OwnerCreate
) -> OwnerResponse | None:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalars().first():
        return None
    owner = Owner(
        dataset_id=dataset_id,
        owner_name=req.owner_name,
        owner_type=req.owner_type.value,
    )
    session.add(owner)
    await session.commit()
    await session.refresh(owner)
    return OwnerResponse.model_validate(owner)


async def remove_dataset_owner(session: AsyncSession, owner_id: int) -> bool:
    result = await session.execute(select(Owner).where(Owner.id == owner_id))
    owner = result.scalars().first()
    if not owner:
        return False
    await session.delete(owner)
    await session.commit()
    return True


async def add_dataset_glossary_term(
    session: AsyncSession, dataset_id: int, term_id: int
) -> bool:
    result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalars().first():
        return False
    session.add(DatasetGlossaryTerm(dataset_id=dataset_id, term_id=term_id))
    await session.commit()
    return True


async def remove_dataset_glossary_term(
    session: AsyncSession, dataset_id: int, term_id: int
) -> bool:
    result = await session.execute(
        select(DatasetGlossaryTerm)
        .where(DatasetGlossaryTerm.dataset_id == dataset_id,
               DatasetGlossaryTerm.term_id == term_id)
    )
    dgt = result.scalars().first()
    if not dgt:
        return False
    await session.delete(dgt)
    await session.commit()
    return True


async def update_schema_fields(
    session: AsyncSession, dataset_id: int, fields: list[dict]
) -> list[SchemaFieldResponse]:
    """Replace all schema fields for a dataset."""
    # Delete existing fields
    result = await session.execute(
        select(DatasetSchema).where(DatasetSchema.dataset_id == dataset_id)
    )
    for f in result.scalars().all():
        await session.delete(f)

    # Add new fields
    new_fields = []
    for idx, field_data in enumerate(fields):
        schema_field = DatasetSchema(
            dataset_id=dataset_id,
            field_path=field_data["field_path"],
            field_type=field_data["field_type"],
            native_type=field_data.get("native_type"),
            description=field_data.get("description"),
            nullable=field_data.get("nullable", "true"),
            ordinal=field_data.get("ordinal", idx),
        )
        session.add(schema_field)
        new_fields.append(schema_field)

    await session.commit()
    for f in new_fields:
        await session.refresh(f)
    return [SchemaFieldResponse.model_validate(f) for f in new_fields]


# ---------------------------------------------------------------------------
# Dashboard / stats
# ---------------------------------------------------------------------------

async def get_catalog_stats(session: AsyncSession) -> CatalogStats:
    total_datasets = (await session.execute(
        select(func.count()).select_from(Dataset).where(Dataset.status != "removed")
    )).scalar() or 0

    total_platforms = (await session.execute(
        select(func.count()).select_from(Platform)
    )).scalar() or 0

    total_tags = (await session.execute(
        select(func.count()).select_from(Tag)
    )).scalar() or 0

    total_glossary_terms = (await session.execute(
        select(func.count()).select_from(GlossaryTerm)
    )).scalar() or 0

    # Datasets by platform
    result = await session.execute(
        select(Platform.name, func.count(Dataset.id))
        .join(Dataset, Dataset.platform_id == Platform.id)
        .where(Dataset.status != "removed")
        .group_by(Platform.name)
        .order_by(func.count(Dataset.id).desc())
    )
    datasets_by_platform = [
        {"platform": name, "count": count} for name, count in result.all()
    ]

    # Datasets by origin
    result = await session.execute(
        select(Dataset.origin, func.count(Dataset.id))
        .where(Dataset.status != "removed")
        .group_by(Dataset.origin)
    )
    datasets_by_origin = [
        {"origin": origin, "count": count} for origin, count in result.all()
    ]

    # Recent datasets
    recent = await list_datasets(session, page=1, page_size=5)

    return CatalogStats(
        total_datasets=total_datasets,
        total_platforms=total_platforms,
        total_tags=total_tags,
        total_glossary_terms=total_glossary_terms,
        datasets_by_platform=datasets_by_platform,
        datasets_by_origin=datasets_by_origin,
        recent_datasets=recent.items,
    )


# ---------------------------------------------------------------------------
# Schema history
# ---------------------------------------------------------------------------

def _schema_field_to_dict(f) -> dict:
    """Convert a DatasetSchema ORM object to a comparable dict."""
    return {
        "field_type": f.field_type,
        "native_type": f.native_type or "",
        "nullable": f.nullable or "true",
        "is_primary_key": f.is_primary_key or "false",
        "is_unique": f.is_unique or "false",
        "is_indexed": f.is_indexed or "false",
    }


def _schema_field_to_snapshot(f) -> dict:
    """Convert a DatasetSchema ORM object to a full snapshot entry."""
    return {
        "field_path": f.field_path,
        "field_type": f.field_type,
        "native_type": f.native_type or "",
        "nullable": f.nullable or "true",
        "is_primary_key": f.is_primary_key or "false",
        "is_unique": f.is_unique or "false",
        "is_indexed": f.is_indexed or "false",
        "ordinal": f.ordinal,
    }


def _col_info_to_dict(col) -> dict:
    """Convert a sync ColumnInfo to a comparable dict."""
    return {
        "field_type": col.data_type,
        "native_type": col.native_type or "",
        "nullable": "true" if col.nullable else "false",
        "is_primary_key": "true" if col.is_primary_key else "false",
        "is_unique": "true" if col.is_unique else "false",
        "is_indexed": "true" if col.is_indexed else "false",
    }


def _col_info_to_snapshot(col) -> dict:
    """Convert a sync ColumnInfo to a full snapshot entry."""
    return {
        "field_path": col.name,
        "field_type": col.data_type,
        "native_type": col.native_type or "",
        "nullable": "true" if col.nullable else "false",
        "is_primary_key": "true" if col.is_primary_key else "false",
        "is_unique": "true" if col.is_unique else "false",
        "is_indexed": "true" if col.is_indexed else "false",
        "ordinal": col.ordinal,
    }


def detect_schema_changes(
    old_fields: list, new_columns: list, from_sync: bool = False,
) -> list[dict]:
    """Detect ADD/MODIFY/DROP changes between old schema fields and new columns.

    Args:
        old_fields: list of DatasetSchema ORM objects (existing)
        new_columns: list of DatasetSchema ORM objects or sync ColumnInfo objects
        from_sync: if True, new_columns are ColumnInfo objects from sync

    Returns:
        list of change dicts: [{type, field, before, after}, ...]
    """
    if from_sync:
        old_map = {f.field_path: _schema_field_to_dict(f) for f in old_fields}
        new_map = {c.name: _col_info_to_dict(c) for c in new_columns}
    else:
        old_map = {f.field_path: _schema_field_to_dict(f) for f in old_fields}
        new_map = {f.field_path: _schema_field_to_dict(f) for f in new_columns}

    changes = []
    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    # Added
    for key in sorted(new_keys - old_keys):
        changes.append({"type": "ADD", "field": key, "before": None, "after": new_map[key]})

    # Dropped
    for key in sorted(old_keys - new_keys):
        changes.append({"type": "DROP", "field": key, "before": old_map[key], "after": None})

    # Modified
    for key in sorted(old_keys & new_keys):
        old_val = old_map[key]
        new_val = new_map[key]
        if old_val != new_val:
            # Record only changed attributes
            before_diff = {k: v for k, v in old_val.items() if v != new_val.get(k)}
            after_diff = {k: v for k, v in new_val.items() if v != old_val.get(k)}
            changes.append({
                "type": "MODIFY", "field": key,
                "before": before_diff, "after": after_diff,
            })

    return changes


async def save_schema_snapshot(
    session: AsyncSession,
    dataset_id: int,
    old_fields: list,
    new_columns: list,
    from_sync: bool = False,
) -> SchemaSnapshot | None:
    """Compare old and new schema, save a snapshot if there are changes.

    Returns the saved snapshot, or None if no changes detected.
    """
    import json as _json

    changes = detect_schema_changes(old_fields, new_columns, from_sync=from_sync)

    # Check if this is the first snapshot for this dataset
    existing_snapshots = await session.execute(
        select(func.count()).where(SchemaSnapshot.dataset_id == dataset_id)
    )
    has_prior_snapshot = (existing_snapshots.scalar() or 0) > 0

    # Save if: changes detected, or no prior snapshot exists (initial baseline)
    if not changes and has_prior_snapshot:
        return None

    # Build snapshot JSON from new columns
    if from_sync:
        schema_entries = [_col_info_to_snapshot(c) for c in new_columns]
    else:
        schema_entries = [_schema_field_to_snapshot(f) for f in new_columns]

    # Build change summary
    added = sum(1 for c in changes if c["type"] == "ADD")
    modified = sum(1 for c in changes if c["type"] == "MODIFY")
    dropped = sum(1 for c in changes if c["type"] == "DROP")
    parts = []
    if added:
        parts.append(f"Added {added}")
    if modified:
        parts.append(f"Modified {modified}")
    if dropped:
        parts.append(f"Dropped {dropped}")
    summary = ", ".join(parts) if parts else ("Initial sync" if not has_prior_snapshot else "No changes")

    snapshot = SchemaSnapshot(
        dataset_id=dataset_id,
        schema_json=_json.dumps(schema_entries, ensure_ascii=False),
        field_count=len(schema_entries),
        change_summary=summary,
        changes_json=_json.dumps(changes, ensure_ascii=False) if changes else "[]",
    )
    session.add(snapshot)
    await session.flush()

    # Keep only the latest 20 snapshots per dataset
    max_snapshots = 20
    count_result = await session.execute(
        select(func.count()).where(SchemaSnapshot.dataset_id == dataset_id)
    )
    total = count_result.scalar() or 0
    if total > max_snapshots:
        old_snaps = await session.execute(
            select(SchemaSnapshot)
            .where(SchemaSnapshot.dataset_id == dataset_id)
            .order_by(SchemaSnapshot.synced_at.asc())
            .limit(total - max_snapshots)
        )
        for old in old_snaps.scalars().all():
            await session.delete(old)
        logger.info("Pruned %d old snapshot(s) for dataset_id=%d", total - max_snapshots, dataset_id)

    logger.info("Schema snapshot saved: dataset_id=%d, %s, fields=%d",
                dataset_id, summary, len(schema_entries))
    return snapshot


async def get_schema_history(
    session: AsyncSession,
    dataset_id: int,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedSchemaSnapshots:
    """Get schema change history for a dataset."""
    import json as _json

    base = select(SchemaSnapshot).where(SchemaSnapshot.dataset_id == dataset_id)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(SchemaSnapshot.synced_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)

    items = []
    for snap in result.scalars().all():
        changes_raw = _json.loads(snap.changes_json) if snap.changes_json else []
        changes = [SchemaChangeEntry(**c) for c in changes_raw]
        items.append(SchemaSnapshotResponse(
            id=snap.id,
            dataset_id=snap.dataset_id,
            synced_at=snap.synced_at,
            field_count=snap.field_count,
            change_summary=snap.change_summary,
            changes=changes,
        ))

    return PaginatedSchemaSnapshots(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

async def seed_platforms(session: AsyncSession) -> None:
    """Insert default platforms if they do not exist."""
    defaults = [
        ("hive", "Apache Hive"),
        ("mysql", "MySQL"),
        ("postgresql", "PostgreSQL"),
        ("kafka", "Apache Kafka"),
        ("s3", "Amazon S3"),
        ("hdfs", "HDFS"),
        ("snowflake", "Snowflake"),
        ("bigquery", "Google BigQuery"),
        ("redshift", "Amazon Redshift"),
        ("elasticsearch", "Elasticsearch"),
        ("mongodb", "MongoDB"),
        ("trino", "Trino"),
        ("starrocks", "StarRocks"),
        ("greenplum", "Greenplum"),
        ("impala", "Apache Impala"),
        ("kudu", "Apache Kudu"),
        ("unity_catalog", "Unity Catalog"),
    ]
    for type_name, display_name in defaults:
        existing = await session.execute(select(Platform).where(Platform.type == type_name))
        if not existing.scalars().first():
            session.add(Platform(
                platform_id=_generate_platform_id(type_name),
                name=display_name,
                type=type_name,
            ))
            logger.info("Seeded platform: %s", type_name)
    await session.commit()


async def seed_platform_metadata(session: AsyncSession) -> None:
    """Seed platform metadata (data types, table types, storage formats, features)."""
    from app.catalog.platform_metadata import PLATFORM_METADATA

    for platform_name, meta in PLATFORM_METADATA.items():
        result = await session.execute(
            select(Platform).where(Platform.type == platform_name)
        )
        platform = result.scalars().first()
        if not platform:
            continue

        # Check if already seeded (any of the 4 tables)
        already_seeded = False
        for model_cls in (PlatformDataType, PlatformTableType, PlatformStorageFormat, PlatformFeature):
            cnt = (await session.execute(
                select(func.count()).where(model_cls.platform_id == platform.id)
            )).scalar() or 0
            if cnt > 0:
                already_seeded = True
                break
        if already_seeded:
            continue

        pid = platform.id

        for idx, (type_name, cat, desc) in enumerate(meta.get("data_types", [])):
            session.add(PlatformDataType(
                platform_id=pid, type_name=type_name, type_category=cat,
                description=desc, ordinal=idx,
            ))

        for idx, (type_name, display, desc, is_def) in enumerate(meta.get("table_types", [])):
            session.add(PlatformTableType(
                platform_id=pid, type_name=type_name, display_name=display,
                description=desc, is_default=is_def, ordinal=idx,
            ))

        for idx, (fmt, display, desc, is_def) in enumerate(meta.get("storage_formats", [])):
            session.add(PlatformStorageFormat(
                platform_id=pid, format_name=fmt, display_name=display,
                description=desc, is_default=is_def, ordinal=idx,
            ))

        for idx, (key, display, desc, vtype, is_req) in enumerate(meta.get("features", [])):
            session.add(PlatformFeature(
                platform_id=pid, feature_key=key, display_name=display,
                description=desc, value_type=vtype, is_required=is_req, ordinal=idx,
            ))

        logger.info("Seeded metadata for platform: %s", platform_name)

    await session.commit()


# ---------------------------------------------------------------------------
# Platform metadata queries
# ---------------------------------------------------------------------------

async def get_platform_metadata(
    session: AsyncSession, platform_id: int
) -> PlatformMetadataResponse | None:
    result = await session.execute(select(Platform).where(Platform.id == platform_id))
    platform = result.scalars().first()
    if not platform:
        return None

    data_types = (await session.execute(
        select(PlatformDataType)
        .where(PlatformDataType.platform_id == platform_id)
        .order_by(PlatformDataType.ordinal)
    )).scalars().all()

    table_types = (await session.execute(
        select(PlatformTableType)
        .where(PlatformTableType.platform_id == platform_id)
        .order_by(PlatformTableType.ordinal)
    )).scalars().all()

    storage_formats = (await session.execute(
        select(PlatformStorageFormat)
        .where(PlatformStorageFormat.platform_id == platform_id)
        .order_by(PlatformStorageFormat.ordinal)
    )).scalars().all()

    features = (await session.execute(
        select(PlatformFeature)
        .where(PlatformFeature.platform_id == platform_id)
        .order_by(PlatformFeature.ordinal)
    )).scalars().all()

    return PlatformMetadataResponse(
        platform=PlatformResponse.model_validate(platform),
        data_types=[PlatformDataTypeResponse.model_validate(t) for t in data_types],
        table_types=[PlatformTableTypeResponse.model_validate(t) for t in table_types],
        storage_formats=[PlatformStorageFormatResponse.model_validate(f) for f in storage_formats],
        features=[PlatformFeatureResponse.model_validate(f) for f in features],
    )
