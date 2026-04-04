"""SQL query editor API endpoints.

Prefix: /api/v1/sql
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.sql import service
from app.sql.schemas import (
    AutocompleteResponse,
    DatasourceCreate,
    DatasourceResponse,
    DatasourceTestRequest,
    DatasourceTestResponse,
    DatasourceUpdate,
    QueryCancelResponse,
    QueryExplainRequest,
    QueryExplainResponse,
    QueryExecuteRequest,
    QueryHistoryListResponse,
    QueryResultResponse,
    QueryStatusResponse,
    QuerySubmitResponse,
    SavedQueryCreate,
    SavedQueryListResponse,
    SavedQueryResponse,
    SavedQueryUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql", tags=["sql"])


# ---------------------------------------------------------------------------
# Datasource CRUD
# ---------------------------------------------------------------------------

@router.post("/datasources", response_model=DatasourceResponse, status_code=201)
async def create_datasource(
    req: DatasourceCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new datasource connection."""
    return await service.create_datasource(session, req)


@router.get("/datasources", response_model=list[DatasourceResponse])
async def list_datasources(session: AsyncSession = Depends(get_session)):
    """List all registered datasources."""
    return await service.list_datasources(session)


@router.get("/datasources/{ds_id}", response_model=DatasourceResponse)
async def get_datasource(ds_id: int, session: AsyncSession = Depends(get_session)):
    """Get datasource details."""
    ds = await service.get_datasource(session, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return ds


@router.put("/datasources/{ds_id}", response_model=DatasourceResponse)
async def update_datasource(
    ds_id: int, req: DatasourceUpdate, session: AsyncSession = Depends(get_session),
):
    """Update datasource connection info."""
    ds = await service.update_datasource(session, ds_id, req)
    if not ds:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return ds


@router.delete("/datasources/{ds_id}", status_code=204)
async def delete_datasource(ds_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a datasource."""
    if not await service.delete_datasource(session, ds_id):
        raise HTTPException(status_code=404, detail="Datasource not found")


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

@router.post("/datasources/test", response_model=DatasourceTestResponse)
async def test_connection(req: DatasourceTestRequest):
    """Test connection with provided credentials (without saving)."""
    return await service.test_connection(req)


@router.post("/datasources/{ds_id}/test", response_model=DatasourceTestResponse)
async def test_datasource(ds_id: int, session: AsyncSession = Depends(get_session)):
    """Test connection of an existing datasource."""
    return await service.test_datasource_by_id(session, ds_id)


# ---------------------------------------------------------------------------
# Metadata browsing
# ---------------------------------------------------------------------------

@router.get("/datasources/{ds_id}/catalogs")
async def get_catalogs(ds_id: int, session: AsyncSession = Depends(get_session)):
    """List catalogs for a datasource."""
    return await service.get_catalogs(session, ds_id)


@router.get("/datasources/{ds_id}/schemas")
async def get_schemas(
    ds_id: int,
    catalog: str = Query("", description="Catalog name"),
    session: AsyncSession = Depends(get_session),
):
    """List schemas within a catalog."""
    return await service.get_schemas(session, ds_id, catalog)


@router.get("/datasources/{ds_id}/tables")
async def get_tables(
    ds_id: int,
    catalog: str = Query("", description="Catalog name"),
    schema: str = Query("", description="Schema name"),
    session: AsyncSession = Depends(get_session),
):
    """List tables within a schema."""
    return await service.get_tables(session, ds_id, catalog, schema)


@router.get("/datasources/{ds_id}/tables/{table}/columns")
async def get_columns(
    ds_id: int,
    table: str,
    catalog: str = Query("", description="Catalog name"),
    schema: str = Query("", description="Schema name"),
    session: AsyncSession = Depends(get_session),
):
    """List columns of a table."""
    return await service.get_columns(session, ds_id, table, catalog, schema)


@router.get("/datasources/{ds_id}/tables/{table}/preview")
async def get_table_preview(
    ds_id: int,
    table: str,
    catalog: str = Query("", description="Catalog name"),
    schema: str = Query("", description="Schema name"),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    """Preview sample data from a table."""
    return await service.get_table_preview(session, ds_id, table, catalog, schema, limit)


# ---------------------------------------------------------------------------
# Autocomplete
# ---------------------------------------------------------------------------

@router.get("/datasources/{ds_id}/autocomplete", response_model=AutocompleteResponse)
async def get_autocomplete(
    ds_id: int,
    catalog: str = Query("", description="Catalog name"),
    schema: str = Query("", description="Schema name"),
    session: AsyncSession = Depends(get_session),
):
    """Get autocomplete suggestions (keywords, functions, tables, columns)."""
    return await service.get_autocomplete(session, ds_id, catalog, schema)


# ---------------------------------------------------------------------------
# Query execution (sync)
# ---------------------------------------------------------------------------

@router.post("/execute", response_model=QueryResultResponse)
async def execute_query(
    req: QueryExecuteRequest,
    session: AsyncSession = Depends(get_session),
):
    """Execute a SQL query synchronously and return results."""
    try:
        return await service.execute_query(
            session, req.datasource_id, req.sql, req.max_rows, req.timeout_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Query execution (async / long-running)
# ---------------------------------------------------------------------------

@router.post("/submit", response_model=QuerySubmitResponse)
async def submit_query(
    req: QueryExecuteRequest,
    session: AsyncSession = Depends(get_session),
):
    """Submit a query for background execution. Returns execution_id for polling."""
    try:
        return await service.submit_query(
            session, req.datasource_id, req.sql, req.max_rows, req.timeout_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/executions/{execution_id}/status", response_model=QueryStatusResponse)
async def get_execution_status(
    execution_id: str, session: AsyncSession = Depends(get_session),
):
    """Poll execution status."""
    result = await service.get_execution_status(session, execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.get("/executions/{execution_id}/result", response_model=QueryResultResponse)
async def get_execution_result(
    execution_id: str, session: AsyncSession = Depends(get_session),
):
    """Get results of a completed execution."""
    result = await service.get_execution_result(session, execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.post("/executions/{execution_id}/cancel", response_model=QueryCancelResponse)
async def cancel_query(
    execution_id: str, session: AsyncSession = Depends(get_session),
):
    """Cancel a running query."""
    result = await service.cancel_query(session, execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

@router.post("/explain", response_model=QueryExplainResponse)
async def explain_query(
    req: QueryExplainRequest,
    session: AsyncSession = Depends(get_session),
):
    """Get execution plan for a query."""
    try:
        return await service.explain_query(session, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get("/history", response_model=QueryHistoryListResponse)
async def get_query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    datasource_id: int | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List query execution history."""
    return await service.get_query_history(
        session, page, page_size, datasource_id, status, search,
    )


@router.delete("/history/{history_id}", status_code=204)
async def delete_history(history_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a history entry."""
    if not await service.delete_query_history(session, history_id):
        raise HTTPException(status_code=404, detail="History entry not found")


# ---------------------------------------------------------------------------
# Saved queries
# ---------------------------------------------------------------------------

@router.post("/saved-queries", response_model=SavedQueryResponse, status_code=201)
async def create_saved_query(
    req: SavedQueryCreate,
    session: AsyncSession = Depends(get_session),
):
    """Save a SQL query."""
    return await service.create_saved_query(session, req)


@router.get("/saved-queries", response_model=SavedQueryListResponse)
async def list_saved_queries(
    folder: str | None = Query(None),
    datasource_id: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List saved queries."""
    return await service.list_saved_queries(session, folder=folder, datasource_id=datasource_id)


@router.get("/saved-queries/{sq_id}", response_model=SavedQueryResponse)
async def get_saved_query(sq_id: int, session: AsyncSession = Depends(get_session)):
    """Get a saved query."""
    sq = await service.get_saved_query(session, sq_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return sq


@router.put("/saved-queries/{sq_id}", response_model=SavedQueryResponse)
async def update_saved_query(
    sq_id: int, req: SavedQueryUpdate, session: AsyncSession = Depends(get_session),
):
    """Update a saved query."""
    sq = await service.update_saved_query(session, sq_id, req)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return sq


@router.delete("/saved-queries/{sq_id}", status_code=204)
async def delete_saved_query(sq_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a saved query."""
    if not await service.delete_saved_query(session, sq_id):
        raise HTTPException(status_code=404, detail="Saved query not found")
