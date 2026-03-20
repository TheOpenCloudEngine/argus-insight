"""Data catalog API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import service
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
    PlatformCreate,
    PlatformResponse,
    SchemaFieldCreate,
    SchemaFieldResponse,
    TagCreate,
    TagResponse,
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


@router.delete("/platforms/{platform_id}")
async def delete_platform(platform_id: int, session: AsyncSession = Depends(get_session)):
    """Remove a data platform."""
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
