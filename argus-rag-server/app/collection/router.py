"""Collection API router — CRUD for collections, documents, and data sources."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection import service
from app.collection.schemas import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    DataSourceCreate,
    DataSourceResponse,
    DocumentBulkIngest,
    DocumentCreate,
    DocumentResponse,
    SyncJobResponse,
)
from app.core.auth import OptionalUser
from app.core.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    """List all collections."""
    return await service.list_collections(session)


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CollectionCreate,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    """Create a new collection."""
    existing = await service.get_collection_by_name(session, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Collection '{body.name}' already exists")
    return await service.create_collection(session, body.model_dump())


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    coll = await service.get_collection(session, collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return coll


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    coll = await service.update_collection(
        session, collection_id, body.model_dump(exclude_unset=True)
    )
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return coll


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    if not await service.delete_collection(session, collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


@router.get("/{collection_id}/documents", response_model=dict)
async def list_documents(
    collection_id: int,
    user: OptionalUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    docs, total = await service.list_documents(session, collection_id, limit, offset)
    return {
        "documents": [DocumentResponse.model_validate(d) for d in docs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{collection_id}/documents", response_model=DocumentResponse, status_code=201)
async def ingest_document(
    collection_id: int,
    body: DocumentCreate,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    """Ingest a single document (chunks automatically)."""
    try:
        return await service.ingest_document(session, collection_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{collection_id}/documents/bulk", response_model=dict)
async def bulk_ingest(
    collection_id: int,
    body: DocumentBulkIngest,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    """Bulk ingest multiple documents."""
    result = await service.bulk_ingest_documents(
        session, collection_id, [d.model_dump() for d in body.documents]
    )
    return result


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    doc = await service.get_document(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    if not await service.delete_document(session, document_id):
        raise HTTPException(status_code=404, detail="Document not found")


# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------


@router.get("/{collection_id}/sources", response_model=list[DataSourceResponse])
async def list_sources(
    collection_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    return await service.list_data_sources(session, collection_id)


@router.post("/{collection_id}/sources", response_model=DataSourceResponse, status_code=201)
async def create_source(
    collection_id: int,
    body: DataSourceCreate,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    return await service.create_data_source(session, collection_id, body.model_dump())


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    user: OptionalUser,
    session: AsyncSession = Depends(get_session),
):
    if not await service.delete_data_source(session, source_id):
        raise HTTPException(status_code=404, detail="Data source not found")


# ---------------------------------------------------------------------------
# Sync Jobs
# ---------------------------------------------------------------------------


@router.get("/{collection_id}/jobs", response_model=list[SyncJobResponse])
async def list_jobs(
    collection_id: int,
    user: OptionalUser,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_sync_jobs(session, collection_id, limit)
