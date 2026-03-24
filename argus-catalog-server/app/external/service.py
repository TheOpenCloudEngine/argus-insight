"""External metadata and Avro schema service — builds JSON and manages cache."""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import (
    Dataset,
    DatasetSchema,
    DatasetTag,
    Owner,
    Platform,
    Tag,
)
from app.external.cache import get_cache

logger = logging.getLogger(__name__)

# Catalog generic type → Avro type mapping
AVRO_TYPE_MAP = {
    "STRING": "string",
    "NUMBER": "long",
    "DATE": {"type": "long", "logicalType": "timestamp-millis"},
    "BOOLEAN": "boolean",
    "BYTES": "bytes",
    "MAP": {"type": "map", "values": "string"},
    "ARRAY": {"type": "array", "items": "string"},
    "ENUM": "string",
}

# Native type refinements for Avro
NATIVE_AVRO_OVERRIDES = {
    "int": "int",
    "integer": "int",
    "smallint": "int",
    "tinyint": "int",
    "mediumint": "int",
    "bigint": "long",
    "float": "float",
    "real": "float",
    "double": "double",
    "double precision": "double",
    "decimal": {"type": "bytes", "logicalType": "decimal", "precision": 38, "scale": 10},
    "numeric": {"type": "bytes", "logicalType": "decimal", "precision": 38, "scale": 10},
    "date": {"type": "int", "logicalType": "date"},
    "time": {"type": "long", "logicalType": "time-millis"},
    "timestamp": {"type": "long", "logicalType": "timestamp-millis"},
    "boolean": "boolean",
    "bool": "boolean",
    "bytea": "bytes",
    "blob": "bytes",
    "binary": "bytes",
    "varbinary": "bytes",
    "uuid": {"type": "string", "logicalType": "uuid"},
}


# ---------------------------------------------------------------------------
# Dataset Metadata
# ---------------------------------------------------------------------------


async def get_dataset_metadata(
    session: AsyncSession,
    dataset_id: int,
    no_cache: bool = False,
) -> dict | None:
    """Get dataset metadata JSON, using cache when available."""
    cache = get_cache()
    cache_key = f"metadata:{dataset_id}"

    if not no_cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            cached["_cache"] = {"cached": True, "hit": True, "ttl_seconds": cache.ttl_seconds}
            return cached

    metadata = await _build_metadata(session, dataset_id)
    if metadata is None:
        return None

    await cache.put(cache_key, metadata)
    metadata["_cache"] = {"cached": False, "hit": False, "ttl_seconds": cache.ttl_seconds}
    return metadata


# ---------------------------------------------------------------------------
# Avro Schema
# ---------------------------------------------------------------------------


async def get_dataset_avro_schema(
    session: AsyncSession,
    dataset_id: int,
    no_cache: bool = False,
) -> dict | None:
    """Get Avro schema for a dataset, using cache when available."""
    cache = get_cache()
    cache_key = f"avro:{dataset_id}"

    if not no_cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            cached["_cache"] = {"cached": True, "hit": True, "ttl_seconds": cache.ttl_seconds}
            return cached

    avro = await _build_avro_schema(session, dataset_id)
    if avro is None:
        return None

    await cache.put(cache_key, avro)
    avro["_cache"] = {"cached": False, "hit": False, "ttl_seconds": cache.ttl_seconds}
    return avro


async def _build_avro_schema(session: AsyncSession, dataset_id: int) -> dict | None:
    """Build an Avro schema from dataset metadata."""
    # Dataset + Platform
    result = await session.execute(
        select(
            Dataset.id,
            Dataset.name,
            Dataset.qualified_name,
            Dataset.description,
            Platform.type.label("platform_type"),
            Platform.name.label("platform_name"),
        )
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    if not row:
        return None

    # Schema fields
    schema_result = await session.execute(
        select(DatasetSchema)
        .where(DatasetSchema.dataset_id == dataset_id)
        .order_by(DatasetSchema.ordinal)
    )
    schema_rows = schema_result.scalars().all()

    # Build Avro fields
    avro_fields = []
    for s in schema_rows:
        avro_type = _resolve_avro_type(s.field_type, s.native_type, s.nullable == "true")
        field: dict = {
            "name": s.field_path,
            "type": avro_type,
        }
        if s.description:
            field["doc"] = s.description
        # Add field metadata
        field_meta = {}
        if s.native_type:
            field_meta["native_type"] = s.native_type
        if s.is_primary_key == "true":
            field_meta["primary_key"] = True
        if s.pii_type:
            field_meta["pii_type"] = s.pii_type
        if field_meta:
            field["metadata"] = field_meta

        avro_fields.append(field)

    # Build namespace from qualified_name
    name_parts = (row.name or "").replace(".", "_")
    namespace_parts = (row.qualified_name or row.name or "").split(".")
    namespace = ".".join(namespace_parts[:-1]) if len(namespace_parts) > 1 else "default"
    record_name = namespace_parts[-1] if namespace_parts else name_parts

    return {
        "type": "record",
        "name": record_name,
        "namespace": namespace,
        "doc": row.description or f"Avro schema for {row.name}",
        "fields": avro_fields,
        "metadata": {
            "dataset_id": row.id,
            "source_name": row.name,
            "platform_type": row.platform_type,
            "platform_name": row.platform_name,
            "generated_by": "argus-catalog-server",
        },
    }


def _resolve_avro_type(field_type: str, native_type: str | None, nullable: bool):
    """Resolve catalog type to Avro type, with nullable union support."""
    # Try native type override first (more precise)
    avro_type = None
    if native_type:
        # Extract base type (e.g., "varchar(200)" → "varchar", "decimal(5,2)" → "decimal")
        base_native = native_type.split("(")[0].strip().lower()
        # Remove "unsigned" suffix
        base_native = base_native.replace(" unsigned", "")
        avro_type = NATIVE_AVRO_OVERRIDES.get(base_native)

        # Handle decimal precision from native_type
        if base_native in ("decimal", "numeric") and "(" in native_type:
            try:
                params = native_type.split("(")[1].rstrip(")")
                parts = params.split(",")
                precision = int(parts[0].strip())
                scale = int(parts[1].strip()) if len(parts) > 1 else 0
                avro_type = {
                    "type": "bytes",
                    "logicalType": "decimal",
                    "precision": precision,
                    "scale": scale,
                }
            except (ValueError, IndexError):
                pass

    # Fall back to generic type mapping
    if avro_type is None:
        avro_type = AVRO_TYPE_MAP.get(field_type, "string")

    # Wrap in nullable union if needed
    if nullable:
        return ["null", avro_type]
    return avro_type


# ---------------------------------------------------------------------------
# Shared: Build metadata dict
# ---------------------------------------------------------------------------


async def _build_metadata(session: AsyncSession, dataset_id: int) -> dict | None:
    """Build metadata dict from DB queries."""
    result = await session.execute(
        select(
            Dataset.id,
            Dataset.urn,
            Dataset.name,
            Dataset.description,
            Dataset.origin,
            Dataset.status,
            Dataset.qualified_name,
            Dataset.table_type,
            Dataset.storage_format,
            Dataset.is_synced,
            Dataset.platform_properties,
            Platform.id.label("platform_pk"),
            Platform.platform_id.label("platform_uid"),
            Platform.name.label("platform_name"),
            Platform.type.label("platform_type"),
        )
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    if not row:
        return None

    schema_result = await session.execute(
        select(DatasetSchema)
        .where(DatasetSchema.dataset_id == dataset_id)
        .order_by(DatasetSchema.ordinal)
    )
    schema_rows = schema_result.scalars().all()

    tag_result = await session.execute(
        select(Tag.name)
        .join(DatasetTag, DatasetTag.tag_id == Tag.id)
        .where(DatasetTag.dataset_id == dataset_id)
    )
    tags = [t[0] for t in tag_result.all()]

    owner_result = await session.execute(
        select(Owner.owner_name, Owner.owner_type).where(Owner.dataset_id == dataset_id)
    )
    owners = [{"name": o[0], "type": o[1]} for o in owner_result.all()]

    properties = {}
    if row.platform_properties:
        try:
            properties = json.loads(row.platform_properties)
        except (json.JSONDecodeError, TypeError):
            properties = {}

    return {
        "dataset_id": row.id,
        "urn": row.urn,
        "name": row.name,
        "description": row.description,
        "origin": row.origin,
        "status": row.status,
        "qualified_name": row.qualified_name,
        "table_type": row.table_type,
        "storage_format": row.storage_format,
        "is_synced": row.is_synced,
        "platform": {
            "id": row.platform_pk,
            "platform_id": row.platform_uid,
            "name": row.platform_name,
            "type": row.platform_type,
        },
        "schema": [
            {
                "field_path": s.field_path,
                "field_type": s.field_type,
                "native_type": s.native_type,
                "description": s.description,
                "nullable": s.nullable,
                "is_primary_key": s.is_primary_key,
                "is_unique": s.is_unique,
                "is_indexed": s.is_indexed,
                "is_partition_key": s.is_partition_key,
                "is_distribution_key": s.is_distribution_key,
                "ordinal": s.ordinal,
                "pii_type": s.pii_type,
            }
            for s in schema_rows
        ],
        "tags": tags,
        "owners": owners,
        "properties": properties,
    }
