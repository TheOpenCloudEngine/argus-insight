"""Data catalog API endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import service
from app.core.config import settings
from app.catalog.schemas import (
    CatalogStats,
    DatasetCreate,
    DatasetResponse,
    DatasetUpdate,
    GlossaryTermCreate,
    GlossaryTermResponse,
    OwnerCreate,
    OwnerResponse,
    PaginatedDatasets,
    PlatformConfigurationResponse,
    PlatformConfigurationSave,
    PlatformCreate,
    PlatformMetadataResponse,
    PlatformResponse,
    SchemaFieldCreate,
    SchemaFieldResponse,
    TagCreate,
    TagResponse,
    TagUsage,
)
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


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------

@router.get("/tags", response_model=list[TagResponse])
async def list_tags(session: AsyncSession = Depends(get_session)):
    """List all tags."""
    return await service.list_tags(session)


@router.post("/tags", response_model=TagResponse)
async def create_tag(req: TagCreate, session: AsyncSession = Depends(get_session)):
    """Create a new tag."""
    return await service.create_tag(session, req)


@router.get("/tags/{tag_id}/usage", response_model=TagUsage)
async def get_tag_usage(tag_id: int, session: AsyncSession = Depends(get_session)):
    """Get tag usage across datasets."""
    usage = await service.get_tag_usage(session, tag_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Tag not found")
    return usage


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a tag."""
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
    req: GlossaryTermCreate, session: AsyncSession = Depends(get_session)
):
    """Create a new glossary term."""
    return await service.create_glossary_term(session, req)


@router.delete("/glossary/{term_id}")
async def delete_glossary_term(term_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a glossary term."""
    if not await service.delete_glossary_term(session, term_id):
        raise HTTPException(status_code=404, detail="Glossary term not found")
    return {"status": "ok", "message": "Glossary term deleted"}


# ---------------------------------------------------------------------------
# Dataset endpoints
# ---------------------------------------------------------------------------

@router.get("/datasets", response_model=PaginatedDatasets)
async def list_datasets(
    search: str | None = Query(None, description="Search in name, description, URN"),
    platform: str | None = Query(None, description="Filter by platform name"),
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
async def create_dataset(req: DatasetCreate, session: AsyncSession = Depends(get_session)):
    """Register a new dataset."""
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
    dataset_id: int, req: DatasetUpdate, session: AsyncSession = Depends(get_session)
):
    """Update dataset metadata."""
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
    session: AsyncSession = Depends(get_session),
):
    """Replace all schema fields for a dataset."""
    return await service.update_schema_fields(
        session, dataset_id,
        [f.model_dump() for f in fields],
    )


# ---------------------------------------------------------------------------
# Sample data endpoints
# ---------------------------------------------------------------------------

def _sample_dir(qualified_name: str):
    """Resolve sample directory under data_dir/samples/{qualified_name}/."""
    safe_name = qualified_name.replace("/", "_").replace("\\", "_")
    return settings.data_dir / "samples" / safe_name


def _sample_path(qualified_name: str):
    """Resolve sample CSV path under data_dir/samples/{qualified_name}/sample.csv."""
    return _sample_dir(qualified_name) / "sample.csv"


@router.post("/datasets/{dataset_id}/sample")
async def upload_sample_data(
    dataset_id: int,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
):
    """Upload a CSV sample data file for a dataset."""
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
    """Download the sample CSV for a dataset."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    path = _sample_path(qn)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No sample data available")

    return FileResponse(path, media_type="text/csv", filename="sample.csv")


@router.delete("/datasets/{dataset_id}/sample")
async def delete_sample_data(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete the sample CSV for a dataset."""
    dataset = await service.get_dataset(session, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    qn = dataset.qualified_name or dataset.name
    path = _sample_path(qn)
    if path.is_file():
        path.unlink()
        # Also remove delimiter.json if present
        delim_path = path.parent / "delimiter.json"
        if delim_path.is_file():
            delim_path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass
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
    session: AsyncSession = Depends(get_session),
):
    """Save delimiter / parse settings for a dataset's sample data."""
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
