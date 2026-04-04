"""SQL query editor API endpoints.

Prefix: /api/v1/sql
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
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
# Editor Tabs (persistent per workspace-user)
# ---------------------------------------------------------------------------


@router.get("/tabs")
async def load_tabs(
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Load saved editor tabs for a workspace-user pair."""
    from app.sql.models import SqlEditorTab
    result = await session.execute(
        select(SqlEditorTab)
        .where(SqlEditorTab.workspace_id == workspace_id, SqlEditorTab.user_id == user_id)
        .order_by(SqlEditorTab.tab_order)
    )
    tabs = result.scalars().all()
    return {
        "tabs": [
            {
                "id": t.id,
                "title": t.title,
                "sql_text": t.sql_text,
                "datasource_id": t.datasource_id,
                "tab_order": t.tab_order,
            }
            for t in tabs
        ]
    }


class TabSaveItem(BaseModel):
    id: str
    title: str = "Query"
    sql_text: str = ""
    datasource_id: int | None = None
    tab_order: int = 0


class TabSaveRequest(BaseModel):
    workspace_id: int
    user_id: int
    tabs: list[TabSaveItem]


@router.post("/tabs/save")
async def save_tabs(
    req: TabSaveRequest,
    session: AsyncSession = Depends(get_session),
):
    """Save editor tabs (upsert only — does not delete other tabs)."""
    from app.sql.models import SqlEditorTab

    # Get existing tab IDs for this workspace-user
    existing = await session.execute(
        select(SqlEditorTab.id).where(
            SqlEditorTab.workspace_id == req.workspace_id,
            SqlEditorTab.user_id == req.user_id,
        )
    )
    existing_ids = set(row[0] for row in existing.fetchall())

    # Upsert each tab
    for tab in req.tabs:
        if tab.id in existing_ids:
            # Update
            from sqlalchemy import update
            await session.execute(
                update(SqlEditorTab).where(SqlEditorTab.id == tab.id).values(
                    title=tab.title,
                    sql_text=tab.sql_text,
                    datasource_id=tab.datasource_id,
                    tab_order=tab.tab_order,
                )
            )
        else:
            # Insert
            session.add(SqlEditorTab(
                id=tab.id,
                workspace_id=req.workspace_id,
                user_id=req.user_id,
                title=tab.title,
                sql_text=tab.sql_text,
                datasource_id=tab.datasource_id,
                tab_order=tab.tab_order,
            ))

    await session.commit()
    logger.info("Tabs saved: ws=%d user=%d saved=%d",
                req.workspace_id, req.user_id, len(req.tabs))
    return {"saved": len(req.tabs)}


@router.delete("/tabs/{tab_id}", status_code=204)
async def delete_tab(
    tab_id: str,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Delete a single editor tab."""
    from app.sql.models import SqlEditorTab
    from sqlalchemy import delete
    await session.execute(
        delete(SqlEditorTab).where(
            SqlEditorTab.id == tab_id,
            SqlEditorTab.workspace_id == workspace_id,
            SqlEditorTab.user_id == user_id,
        )
    )
    await session.commit()


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
# Workspace datasources (auto-discovered from workspace services)
# ---------------------------------------------------------------------------

# Mapping: workspace plugin_name → SQL engine_type
_WS_PLUGIN_ENGINE_MAP = {
    "argus-trino": "trino",
    "argus-starrocks": "starrocks",
    "argus-postgresql": "postgresql",
    "argus-mariadb": "mariadb",
}


@router.get("/datasources/workspace/{workspace_id}")
async def list_workspace_datasources(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List DB services from a workspace as datasource-compatible entries.

    Queries argus_workspace_services for running DB plugins (trino, starrocks,
    postgresql, mariadb) and returns them with negative IDs to distinguish
    from custom datasources.
    """
    from sqlalchemy import text
    import json as json_mod
    from urllib.parse import urlparse

    logger.debug("list_workspace_datasources: workspace_id=%d", workspace_id)

    plugins = list(_WS_PLUGIN_ENGINE_MAP.keys())
    placeholders = ", ".join(f":p{i}" for i in range(len(plugins)))
    params = {f"p{i}": p for i, p in enumerate(plugins)}
    params["ws_id"] = workspace_id

    rows = await session.execute(
        text(f"""
            SELECT id, plugin_name, display_name, endpoint, username, metadata,
                   created_at, updated_at
            FROM argus_workspace_services
            WHERE workspace_id = :ws_id
              AND status = 'running'
              AND plugin_name IN ({placeholders})
        """),
        params,
    )

    datasources = []
    for row in rows.fetchall():
        svc_id, plugin_name, display_name, endpoint, username, meta_raw, created_at, updated_at = row

        engine_type = _WS_PLUGIN_ENGINE_MAP.get(plugin_name, "")
        meta = meta_raw if isinstance(meta_raw, dict) else (
            json_mod.loads(meta_raw) if isinstance(meta_raw, str) else {}
        )
        internal = meta.get("internal", {})
        display = meta.get("display", {})

        # Parse host:port from internal endpoint or service endpoint
        int_endpoint = internal.get("endpoint", endpoint or "")
        host, port = "", 0
        if int_endpoint:
            parsed = urlparse(int_endpoint)
            host = parsed.hostname or ""
            port = parsed.port or 0

        # Extract DB name and user from display metadata
        db_name = display.get("DB Name", display.get("Database", ""))
        db_user = display.get("DB User", username or "")

        datasources.append({
            "id": -svc_id,  # Negative ID to distinguish from custom datasources
            "name": display_name or plugin_name,
            "engine_type": engine_type,
            "host": host,
            "port": port,
            "database_name": db_name,
            "username": db_user,
            "description": f"Workspace service ({plugin_name})",
            "extra_params": {},
            "source": "workspace",
            "created_by": "",
            "created_at": created_at.isoformat() if created_at else "",
            "updated_at": updated_at.isoformat() if updated_at else "",
        })

    logger.info("list_workspace_datasources: workspace_id=%d → %d datasources", workspace_id, len(datasources))
    return datasources


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
    execution_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated results of a completed execution."""
    result = await service.get_execution_result(session, execution_id, page=page)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.get("/executions/{execution_id}/export")
async def export_execution_csv(execution_id: str):
    """Export full query result as CSV (streaming)."""
    from fastapi.responses import StreamingResponse
    import io

    data = service.get_execution_all_rows(execution_id)
    if not data:
        raise HTTPException(status_code=404, detail="Result not found or expired")

    columns, rows = data

    def generate():
        buf = io.StringIO()
        # Header
        buf.write(",".join(c["name"] for c in columns) + "\n")
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()
        # Rows in chunks
        for i, row in enumerate(rows):
            vals = []
            for v in row:
                if v is None:
                    vals.append("")
                else:
                    s = str(v)
                    if "," in s or '"' in s or "\n" in s:
                        vals.append(f'"{s.replace(chr(34), chr(34)+chr(34))}"')
                    else:
                        vals.append(s)
            buf.write(",".join(vals) + "\n")
            if (i + 1) % 1000 == 0:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        remaining = buf.getvalue()
        if remaining:
            yield remaining

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=query_result.csv"},
    )


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
