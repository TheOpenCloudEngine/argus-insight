"""Sync API router — trigger sync and query preview operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import OptionalUser
from app.core.database import get_session
from app.models.collection import DataSource
from app.source.sync_service import sync_data_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/sources/{source_id}")
async def trigger_sync(
    source_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a full sync from a data source (fetch → ingest → embed)."""
    result = await session.execute(select(DataSource).where(DataSource.id == source_id))
    ds = result.scalars().first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    sync_result = await sync_data_source(session, ds)
    if "error" in sync_result:
        raise HTTPException(status_code=500, detail=sync_result["error"])
    return sync_result


@router.post("/collections/{collection_id}")
async def trigger_collection_sync(
    collection_id: int,
    user: OptionalUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger sync for all data sources in a collection."""
    result = await session.execute(
        select(DataSource).where(
            DataSource.collection_id == collection_id,
            DataSource.status == "active",
        )
    )
    sources = list(result.scalars().all())
    if not sources:
        raise HTTPException(status_code=404, detail="No active data sources")

    results = []
    for ds in sources:
        r = await sync_data_source(session, ds)
        results.append({"source_id": ds.id, "source_name": ds.name, **r})
    return {"syncs": results}


# ---------------------------------------------------------------------------
# Query Preview — test a SQL query and see columns + sample data
# ---------------------------------------------------------------------------


class QueryPreviewRequest(BaseModel):
    """Request to preview a SQL query against a source database."""

    db_type: str = Field(..., description="mysql, postgresql, oracle, mssql")
    host: str = Field(...)
    port: int = Field(0, description="0 = use default port for db_type")
    username: str = Field("")
    password: str = Field("")
    database: str = Field(...)
    query: str = Field(..., description="SELECT query to preview")
    max_rows: int = Field(10, ge=1, le=100)


@router.post("/query-preview")
async def query_preview(
    body: QueryPreviewRequest,
    user: OptionalUser = None,
):
    """Execute a SQL query and return column names + sample rows.

    This is used by the UI to let users:
    1. Enter connection details and a SQL query
    2. Preview the data
    3. Select which columns to use for id, title, and embedding text
    """
    from app.source.db_query_connector import DBQueryConnector

    config = {
        "db_type": body.db_type,
        "host": body.host,
        "port": body.port or None,
        "username": body.username,
        "password": body.password,
        "database": body.database,
        "query": body.query,
    }

    connector = DBQueryConnector(config)
    try:
        result = await connector.preview(max_rows=body.max_rows)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
