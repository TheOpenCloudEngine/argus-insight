"""Data catalog API endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import service
from app.core.config import settings
from app.catalog.schemas import (
    CatalogStats,
    ColumnMappingCreate,
    DatasetCreate,
    DatasetLineageCreate,
    DatasetLineageResponse,
    DatasetResponse,
    DatasetUpdate,
    GlossaryTermCreate,
    GlossaryTermResponse,
    OwnerCreate,
    OwnerResponse,
    PaginatedDatasets,
    PipelineCreate,
    PipelineResponse,
    PipelineUpdate,
    PlatformConfigurationResponse,
    PlatformConfigurationSave,
    PlatformCreate,
    PlatformMetadataResponse,
    PlatformResponse,
    PlatformUpdate,
    SchemaFieldCreate,
    SchemaFieldResponse,
    TagCreate,
    TagResponse,
    TagUsage,
)
from app.core.auth import AdminUser
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=CatalogStats)
async def get_catalog_stats(session: AsyncSession = Depends(get_session)):
    """Get catalog overview statistics."""
    return await service.get_catalog_stats(session)


# ---------------------------------------------------------------------------
# Platform endpoints
# ---------------------------------------------------------------------------

@router.get("/platforms", response_model=list[PlatformResponse])
async def list_platforms(session: AsyncSession = Depends(get_session)):
    """List all data platforms."""
    return await service.list_platforms(session)


@router.post("/platforms", response_model=PlatformResponse)
async def create_platform(req: PlatformCreate, session: AsyncSession = Depends(get_session)):
    """Register a new data platform."""
    return await service.create_platform(session, req)


@router.put("/platforms/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    platform_id: int, req: PlatformUpdate, session: AsyncSession = Depends(get_session)
):
    """Update platform metadata (e.g. display name)."""
    platform = await service.update_platform(session, platform_id, req)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return platform


@router.get("/platforms/{platform_id}/metadata", response_model=PlatformMetadataResponse)
async def get_platform_metadata(
    platform_id: int, session: AsyncSession = Depends(get_session)
):
    """Get platform metadata (data types, table types, storage formats, features)."""
    metadata = await service.get_platform_metadata(session, platform_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Platform not found")
    return metadata


@router.get("/platforms/{platform_id}/configuration", response_model=PlatformConfigurationResponse)
async def get_platform_configuration(
    platform_id: int, session: AsyncSession = Depends(get_session)
):
    """Get connection/configuration settings for a platform."""
    config = await service.get_platform_configuration(session, platform_id)
    if not config:
        raise HTTPException(status_code=404, detail="Platform configuration not found")
    return config


@router.put("/platforms/{platform_id}/configuration", response_model=PlatformConfigurationResponse)
async def save_platform_configuration(
    platform_id: int,
    req: PlatformConfigurationSave,
    session: AsyncSession = Depends(get_session),
):
    """Save or update connection/configuration settings for a platform."""
    platform = await service.get_platform(session, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return await service.save_platform_configuration(session, platform_id, req.config)


@router.get("/platforms/{platform_id}/dataset-count")
async def get_platform_dataset_count(
    platform_id: int, session: AsyncSession = Depends(get_session)
):
    """Get the number of datasets using this platform."""
    platform = await service.get_platform(session, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    count = await service.get_platform_dataset_count(session, platform_id)
    return {"platform_id": platform_id, "dataset_count": count}


@router.delete("/platforms/{platform_id}")
async def delete_platform(platform_id: int, session: AsyncSession = Depends(get_session)):
    """Remove a data platform."""
    count = await service.get_platform_dataset_count(session, platform_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete platform: {count} dataset(s) are using this platform.",
        )
    if not await service.delete_platform(session, platform_id):
        raise HTTPException(status_code=404, detail="Platform not found")
    return {"status": "ok", "message": "Platform deleted"}


@router.post("/platforms/{platform_id}/sync")
async def sync_platform(
    request: Request,
    platform_id: int,
    database: str | None = Query(None, description="Specific database to sync (optional)"),
    session: AsyncSession = Depends(get_session),
):
    """Sync metadata from external platform into the catalog."""
    platform = await service.get_platform(session, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")

    logger.info("Sync requested: platform=%s (id=%d), database=%s",
                platform.platform_id, platform_id, database or "all")

    # Derive catalog base URL from the incoming request
    catalog_url = f"{request.url.scheme}://{request.url.netloc}"

    from app.catalog.sync import sync_platform_metadata
    result = await sync_platform_metadata(
        session, platform.platform_id, database, catalog_url=catalog_url,
    )

    if result.errors:
        logger.warning("Sync failed: platform=%s, error=%s", platform.platform_id, result.errors[0])
        raise HTTPException(status_code=400, detail=result.errors[0])

    logger.info("Sync completed: platform=%s, created=%d, updated=%d, removed=%d, samples=%d",
                result.platform_id, result.tables_created, result.tables_updated,
                result.tables_removed, result.samples_uploaded)

    return {
        "status": "ok",
        "platform_id": result.platform_id,
        "databases_scanned": result.databases_scanned,
        "tables_created": result.tables_created,
        "tables_updated": result.tables_updated,
        "tables_removed": result.tables_removed,
        "tables_total": result.tables_total,
        "samples_uploaded": result.samples_uploaded,
    }


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------

@router.get("/tags", response_model=list[TagResponse])
async def list_tags(session: AsyncSession = Depends(get_session)):
    """List all tags."""
    return await service.list_tags(session)


@router.post("/tags", response_model=TagResponse)
async def create_tag(req: TagCreate, _admin: AdminUser, session: AsyncSession = Depends(get_session)):
    """Create a new tag. Requires admin role."""
    return await service.create_tag(session, req)


@router.get("/tags/{tag_id}/usage", response_model=TagUsage)
async def get_tag_usage(tag_id: int, session: AsyncSession = Depends(get_session)):
    """Get tag usage across datasets."""
    usage = await service.get_tag_usage(session, tag_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Tag not found")
    return usage


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, _admin: AdminUser, session: AsyncSession = Depends(get_session)):
    """Delete a tag. Requires admin role."""
    if not await service.delete_tag(session, tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "ok", "message": "Tag deleted"}


# ---------------------------------------------------------------------------
# Glossary term endpoints
# ---------------------------------------------------------------------------

@router.get("/glossary", response_model=list[GlossaryTermResponse])
async def list_glossary_terms(session: AsyncSession = Depends(get_session)):
    """List all glossary terms."""
    return await service.list_glossary_terms(session)


@router.post("/glossary", response_model=GlossaryTermResponse)
async def create_glossary_term(
    req: GlossaryTermCreate, _admin: AdminUser, session: AsyncSession = Depends(get_session),
):
    """Create a new glossary term. Requires admin role."""
    return await service.create_glossary_term(session, req)


@router.put("/glossary/{term_id}", response_model=GlossaryTermResponse)
async def update_glossary_term(
    term_id: int, req: GlossaryTermCreate, _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Update a glossary term. Requires admin role."""
    result = await service.update_glossary_term(session, term_id, req.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    return result


@router.delete("/glossary/{term_id}")
async def delete_glossary_term(term_id: int, _admin: AdminUser, session: AsyncSession = Depends(get_session)):
    """Delete a glossary term. Requires admin role."""
    if not await service.delete_glossary_term(session, term_id):
        raise HTTPException(status_code=404, detail="Glossary term not found")
    return {"status": "ok", "message": "Glossary term deleted"}


# ---------------------------------------------------------------------------
# Dataset endpoints
# ---------------------------------------------------------------------------

@router.get("/datasets", response_model=PaginatedDatasets)
async def list_datasets(
    search: str | None = Query(None, description="Search in name, description, URN"),
    platform: str | None = Query(None, description="Filter by platform_id"),
    origin: str | None = Query(None, description="Filter by origin (PROD/DEV/STAGING)"),
    tag: str | None = Query(None, description="Filter by tag name"),
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    """List datasets with optional filters and pagination."""
    return await service.list_datasets(
        session, search=search, platform=platform, origin=origin,
        tag=tag, status=status, page=page, page_size=page_size,
    )


@router.post("/datasets", response_model=DatasetResponse)
async def create_dataset(req: DatasetCreate, _admin: AdminUser, session: AsyncSession = Depends(get_session)):
    """Register a new dataset. Requires admin role."""
    try:
        return await service.create_dataset(session, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Get dataset details by ID."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/datasets/urn/{urn:path}", response_model=DatasetResponse)
async def get_dataset_by_urn(urn: str, session: AsyncSession = Depends(get_session)):
    """Get dataset details by URN."""
    dataset = await service.get_dataset_by_urn(session, urn)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int, req: DatasetUpdate, _admin: AdminUser, session: AsyncSession = Depends(get_session),
):
    """Update dataset metadata. Requires admin role."""
    dataset = await service.update_dataset(session, dataset_id, req)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a dataset."""
    if not await service.delete_dataset(session, dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"status": "ok", "message": "Dataset deleted"}


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

@router.get("/datasets/{dataset_id}/lineage")
async def get_dataset_lineage(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Get upstream and downstream lineage for a dataset.

    Returns nodes (datasets) and edges (source→target relationships) suitable
    for rendering a lineage DAG in the UI.  Merges both query-based lineage
    (argus_query_lineage) and dataset-level lineage (argus_dataset_lineage)
    so that cross-platform relationships are included.
    """
    # Verify dataset exists
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # ------------------------------------------------------------------
    # 1. Collect related IDs from BOTH lineage sources
    # ------------------------------------------------------------------
    related_ids: set[int] = {dataset_id}
    edge_set: set[tuple] = set()  # (source_id, target_id)
    edge_meta: dict[tuple, dict] = {}  # extra info per edge

    # 1a. Query-based lineage (same-platform, auto-collected)
    upstream_rows = (await session.execute(text("""
        SELECT DISTINCT source_table, source_dataset_id
        FROM argus_query_lineage
        WHERE target_dataset_id = :ds_id AND source_dataset_id IS NOT NULL
    """), {"ds_id": dataset_id})).fetchall()

    downstream_rows = (await session.execute(text("""
        SELECT DISTINCT target_table, target_dataset_id
        FROM argus_query_lineage
        WHERE source_dataset_id = :ds_id AND target_dataset_id IS NOT NULL
    """), {"ds_id": dataset_id})).fetchall()

    for row in upstream_rows:
        related_ids.add(row[1])
        key = (row[1], dataset_id)
        edge_set.add(key)
        edge_meta.setdefault(key, {
            "sourceTable": row[0], "targetTable": "",
            "lineageSource": "QUERY_AGGREGATED", "lineageId": None,
        })

    for row in downstream_rows:
        related_ids.add(row[1])
        key = (dataset_id, row[1])
        edge_set.add(key)
        edge_meta.setdefault(key, {
            "sourceTable": "", "targetTable": row[0],
            "lineageSource": "QUERY_AGGREGATED", "lineageId": None,
        })

    # 1b. Dataset-level lineage (cross-platform, manual/pipeline)
    dl_rows = (await session.execute(text("""
        SELECT id, source_dataset_id, target_dataset_id, lineage_source, relation_type
        FROM argus_dataset_lineage
        WHERE source_dataset_id = :ds_id OR target_dataset_id = :ds_id
    """), {"ds_id": dataset_id})).fetchall()

    for row in dl_rows:
        related_ids.add(row[1])
        related_ids.add(row[2])
        key = (row[1], row[2])
        edge_set.add(key)
        edge_meta[key] = {
            "sourceTable": "", "targetTable": "",
            "lineageSource": row[3], "lineageId": row[0],
            "relationType": row[4],
        }

    # 2. Fetch second-level connections (2 hops) from both sources
    first_level_ids = related_ids - {dataset_id}
    if first_level_ids:
        placeholders = ", ".join(f":id{i}" for i in range(len(first_level_ids)))
        params = {f"id{i}": fid for i, fid in enumerate(first_level_ids)}

        # Query lineage 2nd hop
        for direction_col, filter_col in [
            ("source_dataset_id", "target_dataset_id"),
            ("target_dataset_id", "source_dataset_id"),
        ]:
            rows2 = (await session.execute(text(f"""
                SELECT DISTINCT {direction_col}
                FROM argus_query_lineage
                WHERE {filter_col} IN ({placeholders}) AND {direction_col} IS NOT NULL
            """), params)).fetchall()
            for r in rows2:
                related_ids.add(r[0])

        # Dataset lineage 2nd hop
        rows2 = (await session.execute(text(f"""
            SELECT DISTINCT source_dataset_id, target_dataset_id,
                   id, lineage_source, relation_type
            FROM argus_dataset_lineage
            WHERE source_dataset_id IN ({placeholders})
               OR target_dataset_id IN ({placeholders})
        """), params)).fetchall()
        for r in rows2:
            related_ids.add(r[0])
            related_ids.add(r[1])
            key = (r[0], r[1])
            edge_set.add(key)
            edge_meta.setdefault(key, {
                "sourceTable": "", "targetTable": "",
                "lineageSource": r[3], "lineageId": r[2],
                "relationType": r[4],
            })

    # 3. Build nodes
    nodes = []
    if related_ids:
        placeholders = ", ".join(f":id{i}" for i in range(len(related_ids)))
        params = {f"id{i}": rid for i, rid in enumerate(related_ids)}
        ds_rows = (await session.execute(text(f"""
            SELECT d.id, d.name, d.urn, p.type AS platform_type, p.name AS platform_name
            FROM catalog_datasets d
            JOIN catalog_platforms p ON d.platform_id = p.id
            WHERE d.id IN ({placeholders})
        """), params)).fetchall()
        for row in ds_rows:
            nodes.append({
                "id": row[0],
                "name": row[1],
                "urn": row[2],
                "platformType": row[3],
                "platformName": row[4],
                "isCurrent": row[0] == dataset_id,
            })

    # 4. Build edges (query-based)
    edges = []
    if related_ids:
        placeholders = ", ".join(f":id{i}" for i in range(len(related_ids)))
        params = {f"id{i}": rid for i, rid in enumerate(related_ids)}
        edge_rows = (await session.execute(text(f"""
            SELECT DISTINCT source_dataset_id, target_dataset_id, source_table, target_table
            FROM argus_query_lineage
            WHERE source_dataset_id IN ({placeholders})
              AND target_dataset_id IN ({placeholders})
              AND source_dataset_id IS NOT NULL
              AND target_dataset_id IS NOT NULL
        """), params)).fetchall()
        seen_edges = set()
        for row in edge_rows:
            key = (row[0], row[1])
            seen_edges.add(key)
            edges.append({
                "source": row[0],
                "target": row[1],
                "sourceTable": row[2],
                "targetTable": row[3],
                "lineageSource": "QUERY_AGGREGATED",
                "lineageId": None,
            })

        # Add dataset-level lineage edges (cross-platform)
        dl_edge_rows = (await session.execute(text(f"""
            SELECT id, source_dataset_id, target_dataset_id,
                   lineage_source, relation_type, description
            FROM argus_dataset_lineage
            WHERE source_dataset_id IN ({placeholders})
              AND target_dataset_id IN ({placeholders})
        """), params)).fetchall()
        for row in dl_edge_rows:
            key = (row[1], row[2])
            if key not in seen_edges:
                edges.append({
                    "source": row[1],
                    "target": row[2],
                    "sourceTable": "",
                    "targetTable": "",
                    "lineageSource": row[3],
                    "lineageId": row[0],
                    "relationType": row[4],
                    "description": row[5],
                })

    # 5. Column lineage (merge query-based + dataset-level)
    column_lineage = []
    direct_ids = [dataset_id]
    for row in upstream_rows:
        direct_ids.append(row[1])
    for row in downstream_rows:
        direct_ids.append(row[1])
    # Add direct connections from dataset lineage
    for dl in dl_rows:
        if dl[1] not in direct_ids:
            direct_ids.append(dl[1])
        if dl[2] not in direct_ids:
            direct_ids.append(dl[2])

    if direct_ids:
        placeholders = ", ".join(f":id{i}" for i in range(len(direct_ids)))
        params = {f"id{i}": did for i, did in enumerate(direct_ids)}

        # Query-based column lineage
        cl_rows = (await session.execute(text(f"""
            SELECT ql.source_dataset_id, ql.target_dataset_id,
                   cl.source_column, cl.target_column, cl.transform_type
            FROM argus_column_lineage cl
            JOIN argus_query_lineage ql ON cl.query_lineage_id = ql.id
            WHERE ql.source_dataset_id IN ({placeholders})
              AND ql.target_dataset_id IN ({placeholders})
              AND ql.source_dataset_id IS NOT NULL
              AND ql.target_dataset_id IS NOT NULL
        """), params)).fetchall()
        for row in cl_rows:
            column_lineage.append({
                "sourceDatasetId": row[0],
                "targetDatasetId": row[1],
                "sourceColumn": row[2],
                "targetColumn": row[3],
                "transformType": row[4],
            })

        # Dataset-level column mappings (cross-platform)
        dcm_rows = (await session.execute(text(f"""
            SELECT dl.source_dataset_id, dl.target_dataset_id,
                   cm.source_column, cm.target_column, cm.transform_type
            FROM argus_dataset_column_mapping cm
            JOIN argus_dataset_lineage dl ON cm.dataset_lineage_id = dl.id
            WHERE dl.source_dataset_id IN ({placeholders})
              AND dl.target_dataset_id IN ({placeholders})
        """), params)).fetchall()
        for row in dcm_rows:
            column_lineage.append({
                "sourceDatasetId": row[0],
                "targetDatasetId": row[1],
                "sourceColumn": row[2],
                "targetColumn": row[3],
                "transformType": row[4],
            })

    return {
        "datasetId": dataset_id,
        "nodes": nodes,
        "edges": edges,
        "columnLineage": column_lineage,
    }


# ---------------------------------------------------------------------------
# Dataset relationship endpoints
# ---------------------------------------------------------------------------

@router.post("/datasets/{dataset_id}/tags/{tag_id}")
async def add_dataset_tag(
    dataset_id: int, tag_id: int, session: AsyncSession = Depends(get_session)
):
    """Attach a tag to a dataset."""
    if not await service.add_dataset_tag(session, dataset_id, tag_id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"status": "ok"}


@router.delete("/datasets/{dataset_id}/tags/{tag_id}")
async def remove_dataset_tag(
    dataset_id: int, tag_id: int, session: AsyncSession = Depends(get_session)
):
    """Remove a tag from a dataset."""
    if not await service.remove_dataset_tag(session, dataset_id, tag_id):
        raise HTTPException(status_code=404, detail="Tag association not found")
    return {"status": "ok"}


@router.post("/datasets/{dataset_id}/owners", response_model=OwnerResponse)
async def add_dataset_owner(
    dataset_id: int, req: OwnerCreate, session: AsyncSession = Depends(get_session)
):
    """Add an owner to a dataset."""
    owner = await service.add_dataset_owner(session, dataset_id, req)
    if not owner:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return owner


@router.delete("/datasets/{dataset_id}/owners/{owner_id}")
async def remove_dataset_owner(
    dataset_id: int, owner_id: int, session: AsyncSession = Depends(get_session)
):
    """Remove an owner from a dataset."""
    if not await service.remove_dataset_owner(session, owner_id):
        raise HTTPException(status_code=404, detail="Owner not found")
    return {"status": "ok"}


@router.post("/datasets/{dataset_id}/glossary/{term_id}")
async def add_dataset_glossary_term(
    dataset_id: int, term_id: int, session: AsyncSession = Depends(get_session)
):
    """Attach a glossary term to a dataset."""
    if not await service.add_dataset_glossary_term(session, dataset_id, term_id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"status": "ok"}


@router.delete("/datasets/{dataset_id}/glossary/{term_id}")
async def remove_dataset_glossary_term(
    dataset_id: int, term_id: int, session: AsyncSession = Depends(get_session)
):
    """Remove a glossary term from a dataset."""
    if not await service.remove_dataset_glossary_term(session, dataset_id, term_id):
        raise HTTPException(status_code=404, detail="Glossary term association not found")
    return {"status": "ok"}


@router.put("/datasets/{dataset_id}/schema", response_model=list[SchemaFieldResponse])
async def update_schema_fields(
    dataset_id: int,
    fields: list[SchemaFieldCreate],
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Replace all schema fields for a dataset. Requires admin role."""
    return await service.update_schema_fields(
        session, dataset_id,
        [f.model_dump() for f in fields],
    )


@router.get("/datasets/{dataset_id}/schema/history")
async def get_schema_history(
    dataset_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get schema change history snapshots for a dataset."""
    return await service.get_schema_history(session, dataset_id, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Sample data endpoints
# ---------------------------------------------------------------------------

def _sample_dir(qualified_name: str):
    """Resolve sample directory under data_dir/samples/{qualified_name}/."""
    safe_name = qualified_name.replace("/", "_").replace("\\", "_")
    return settings.data_dir / "samples" / safe_name


def _sample_dir_by_platform(platform_id: str, name: str):
    """Resolve sample directory: data_dir/samples/{platform_id}/{name}/."""
    return settings.data_dir / "samples" / platform_id / name


def _sample_path(qualified_name: str):
    """Resolve sample CSV path under data_dir/samples/{qualified_name}/sample.csv."""
    return _sample_dir(qualified_name) / "sample.csv"


@router.post("/datasets/{dataset_id}/sample")
async def upload_sample_data(
    dataset_id: int,
    file: UploadFile,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Upload a CSV sample data file for a dataset. Requires admin role."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    dest = _sample_path(qn)
    dest.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    if len(content) > 100 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({len(content) / 1024:.1f} KB) exceeds the 100 KB limit.",
        )
    dest.write_bytes(content)
    logger.info("Sample data uploaded: %s (%d bytes)", dest, len(content))
    return {"status": "ok", "path": str(dest), "size": len(content)}


@router.get("/datasets/{dataset_id}/sample")
async def get_sample_data(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Download sample data for a dataset.

    Returns JSON {format, columns, rows} for parquet, or raw CSV for legacy files.
    """
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Try parquet path first
    parquet_path = _sample_dir_by_platform(
        dataset.platform.platform_id, dataset.name,
    ) / "sample.parquet"
    if parquet_path.is_file():
        import pyarrow.parquet as pq
        table = pq.read_table(parquet_path)
        columns = table.column_names
        rows = []
        for i in range(table.num_rows):
            rows.append([
                str(v) if v is not None else None
                for v in (table.column(c)[i].as_py() for c in range(table.num_columns))
            ])
        return JSONResponse(content={
            "format": "parquet",
            "columns": columns,
            "rows": rows,
        })

    # Fallback to legacy CSV path
    qn = dataset.qualified_name or dataset.name
    csv_path = _sample_path(qn)
    if csv_path.is_file():
        return FileResponse(csv_path, media_type="text/csv", filename="sample.csv")

    raise HTTPException(status_code=404, detail="No sample data available")


@router.post("/datasets/{dataset_id}/sample/convert-to-parquet")
async def convert_sample_to_parquet(
    dataset_id: int,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Convert an existing CSV sample to parquet format. Requires admin role."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    csv_path = _sample_path(qn)
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail="No CSV sample data to convert")

    import csv as csv_mod
    import io
    import pyarrow as pa
    import pyarrow.parquet as _pq

    text = csv_path.read_text(encoding="utf-8", errors="replace")
    reader = csv_mod.reader(io.StringIO(text))
    all_rows = list(reader)
    if not all_rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    header = all_rows[0]
    data_rows = all_rows[1:] if len(all_rows) > 1 else []

    columns = {}
    for ci, col_name in enumerate(header):
        columns[col_name or f"col_{ci}"] = [
            row[ci] if ci < len(row) else None for row in data_rows
        ]

    arrow_table = pa.table(columns)
    dest_dir = _sample_dir_by_platform(dataset.platform.platform_id, dataset.name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "sample.parquet"
    _pq.write_table(arrow_table, dest)

    # Remove old CSV and delimiter config
    csv_path.unlink()
    delim_path = csv_path.parent / "delimiter.json"
    if delim_path.is_file():
        delim_path.unlink()
    try:
        csv_path.parent.rmdir()
    except OSError:
        pass

    logger.info("Converted CSV to parquet: %s (%d rows)", dest, len(data_rows))
    return {"status": "ok", "rows": len(data_rows), "columns": len(header)}


@router.delete("/datasets/{dataset_id}/sample")
async def delete_sample_data(
    dataset_id: int,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete sample data for a dataset (parquet or CSV). Requires admin role."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    deleted = False

    # Try parquet path
    parquet_path = _sample_dir_by_platform(
        dataset.platform.platform_id, dataset.name,
    ) / "sample.parquet"
    if parquet_path.is_file():
        parquet_path.unlink()
        try:
            parquet_path.parent.rmdir()
        except OSError:
            pass
        deleted = True

    # Try legacy CSV path
    qn = dataset.qualified_name or dataset.name
    csv_path = _sample_path(qn)
    if csv_path.is_file():
        csv_path.unlink()
        delim_path = csv_path.parent / "delimiter.json"
        if delim_path.is_file():
            delim_path.unlink()
        try:
            csv_path.parent.rmdir()
        except OSError:
            pass
        deleted = True

    if deleted:
        return {"status": "ok", "message": "Sample data deleted"}
    raise HTTPException(status_code=404, detail="No sample data available")


class DelimiterConfig(BaseModel):
    """Delimiter / parse settings stored alongside the sample CSV."""
    encoding: str = "UTF-8"
    line_delimiter: str = "\n"
    delimiter: str = ","
    delimiter_mode: str | None = None
    delimiter_input: str = ""
    has_header: bool = True
    quote_char: str = "__none__"
    custom_quote_char: str = ""
    is_custom_quote: bool = False


@router.put("/datasets/{dataset_id}/sample/delimiter")
async def save_delimiter_config(
    dataset_id: int,
    config: DelimiterConfig,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Save delimiter / parse settings for a dataset's sample data. Requires admin role."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    sample_dir = _sample_dir(qn)
    sample_dir.mkdir(parents=True, exist_ok=True)

    dest = sample_dir / "delimiter.json"
    dest.write_text(json.dumps(config.model_dump(), ensure_ascii=False), encoding="utf-8")
    logger.info("Delimiter config saved: %s", dest)
    return {"status": "ok"}


@router.get("/datasets/{dataset_id}/sample/delimiter")
async def get_delimiter_config(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get delimiter / parse settings for a dataset's sample data."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    path = _sample_dir(qn) / "delimiter.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No delimiter config available")

    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Sample data ingestion (sync upload)
# ---------------------------------------------------------------------------

@router.post("/samples/upload")
async def upload_sample_parquet(
    request: Request,
    x_platform_id: str = Header(..., alias="X-Platform-Id"),
    x_dataset_name: str = Header(..., alias="X-Dataset-Name"),
):
    """Receive a parquet sample file from a sync process.

    Headers:
        X-Platform-Id: platform_id (e.g. mysql-19d0bfe954e2cfdaa)
        X-Dataset-Name: database.table (e.g. sakila.country)
    Body:
        Raw parquet bytes.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty body")

    dest_dir = _sample_dir_by_platform(x_platform_id, x_dataset_name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "sample.parquet"
    dest.write_bytes(body)
    logger.info("Sample parquet uploaded: %s (%d bytes)", dest, len(body))
    return {"status": "ok", "path": str(dest), "size": len(body)}


# ---------------------------------------------------------------------------
# Data Pipeline CRUD
# ---------------------------------------------------------------------------

@router.post("/pipelines", response_model=PipelineResponse, status_code=201)
async def create_pipeline(data: PipelineCreate, session: AsyncSession = Depends(get_session)):
    """Register a data pipeline (ETL, CDC, file export, etc.)."""
    result = await service.create_pipeline(session, data)
    await session.commit()
    return result


@router.get("/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(session: AsyncSession = Depends(get_session)):
    """List all registered data pipelines."""
    return await service.list_pipelines(session)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """Get a data pipeline by ID."""
    pipeline = await service.get_pipeline(session, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return PipelineResponse.model_validate(pipeline)


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int, data: PipelineUpdate, session: AsyncSession = Depends(get_session),
):
    """Update a data pipeline."""
    result = await service.update_pipeline(session, pipeline_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    await session.commit()
    return result


@router.delete("/pipelines/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a data pipeline."""
    deleted = await service.delete_pipeline(session, pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Cross-Platform Dataset Lineage
# ---------------------------------------------------------------------------

@router.post("/lineage", response_model=DatasetLineageResponse, status_code=201)
async def create_lineage(
    data: DatasetLineageCreate, session: AsyncSession = Depends(get_session),
):
    """Register a cross-platform dataset lineage relationship."""
    # Validate source and target datasets exist
    src = await service.get_dataset(session, data.source_dataset_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source dataset not found")
    tgt = await service.get_dataset(session, data.target_dataset_id)
    if not tgt:
        raise HTTPException(status_code=404, detail="Target dataset not found")
    if data.source_dataset_id == data.target_dataset_id:
        raise HTTPException(status_code=400, detail="Source and target must be different")
    if data.pipeline_id:
        pipeline = await service.get_pipeline(session, data.pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")

    result = await service.create_dataset_lineage(session, data)
    await session.commit()
    return result


@router.get("/lineage", response_model=list[DatasetLineageResponse])
async def list_lineages(
    dataset_id: int | None = Query(None, description="Filter by dataset ID"),
    lineage_source: str | None = Query(None, description="Filter: MANUAL, PIPELINE, etc."),
    session: AsyncSession = Depends(get_session),
):
    """List dataset lineage relationships."""
    return await service.list_dataset_lineages(session, dataset_id, lineage_source)


@router.get("/lineage/{lineage_id}", response_model=DatasetLineageResponse)
async def get_lineage(lineage_id: int, session: AsyncSession = Depends(get_session)):
    """Get a dataset lineage by ID with column mappings."""
    lineage = await service.get_dataset_lineage(session, lineage_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    return await service._build_lineage_response(session, lineage_id)


@router.put("/lineage/{lineage_id}/column-mappings", response_model=DatasetLineageResponse)
async def update_lineage_column_mappings(
    lineage_id: int,
    column_mappings: list[ColumnMappingCreate],
    session: AsyncSession = Depends(get_session),
):
    """Replace column mappings for a dataset lineage."""
    result = await service.update_dataset_lineage_column_mappings(
        session, lineage_id, column_mappings,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Lineage not found")
    await session.commit()
    return result


@router.delete("/lineage/{lineage_id}", status_code=204)
async def delete_lineage(lineage_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a dataset lineage relationship."""
    deleted = await service.delete_dataset_lineage(session, lineage_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lineage not found")
    await session.commit()
