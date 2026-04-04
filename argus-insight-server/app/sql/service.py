"""SQL query editor service.

Manages datasource connections, query execution (sync/async),
metadata browsing, history, and saved queries.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.sql.adapters.base import BaseAdapter, ConnectionConfig
from app.sql.adapters.postgresql_adapter import PostgreSQLAdapter
from app.sql.adapters.starrocks_adapter import StarRocksAdapter
from app.sql.adapters.trino_adapter import TrinoAdapter
from app.sql.models import SqlDatasource, SqlQueryExecution, SqlQueryHistory, SqlSavedQuery
from app.sql.schemas import (
    AutocompleteResponse,
    DatasourceCreate,
    DatasourceResponse,
    DatasourceTestRequest,
    DatasourceTestResponse,
    DatasourceUpdate,
    EngineType,
    QueryCancelResponse,
    QueryExplainRequest,
    QueryExplainResponse,
    QueryHistoryItem,
    QueryHistoryListResponse,
    QueryResultColumn,
    QueryResultResponse,
    QueryStatus,
    QueryStatusResponse,
    QuerySubmitResponse,
    SavedQueryCreate,
    SavedQueryListResponse,
    SavedQueryResponse,
    SavedQueryUpdate,
)

logger = logging.getLogger(__name__)

# In-memory cache for active query results (execution_id → QueryResult)
_execution_results: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

def _create_adapter(
    engine_type: str, host: str, port: int, database: str,
    username: str, password: str, extra: dict | None = None,
) -> BaseAdapter:
    config = ConnectionConfig(
        host=host, port=port, database=database,
        username=username, password=password, extra=extra or {},
    )
    et = engine_type.lower()
    if et == EngineType.TRINO:
        return TrinoAdapter(config)
    elif et == EngineType.STARROCKS:
        return StarRocksAdapter(config)
    elif et == EngineType.POSTGRESQL:
        return PostgreSQLAdapter(config)
    else:
        raise ValueError(f"Unsupported engine type: {engine_type}")


def _adapter_from_datasource(ds: SqlDatasource) -> BaseAdapter:
    extra = json.loads(ds.extra_params) if isinstance(ds.extra_params, str) else ds.extra_params
    return _create_adapter(
        engine_type=ds.engine_type,
        host=ds.host,
        port=ds.port,
        database=ds.database_name,
        username=ds.username,
        password=_decrypt_password(ds.password_encrypted),
        extra=extra,
    )


def _encrypt_password(plain: str) -> str:
    """Encrypt password for storage. TODO: use Fernet in production."""
    return plain


def _decrypt_password(encrypted: str) -> str:
    """Decrypt stored password. TODO: use Fernet in production."""
    return encrypted


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Datasource CRUD
# ---------------------------------------------------------------------------

async def create_datasource(
    session: AsyncSession, req: DatasourceCreate, username: str = "",
) -> DatasourceResponse:
    extra_json = json.dumps(req.extra_params or {})
    ds = SqlDatasource(
        name=req.name,
        engine_type=req.engine_type.value,
        host=req.host,
        port=req.port,
        database_name=req.database_name,
        username=req.username,
        password_encrypted=_encrypt_password(req.password),
        extra_params=extra_json,
        description=req.description,
        created_by=username,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    logger.info("Datasource created: id=%d name=%s engine=%s", ds.id, ds.name, ds.engine_type)
    return _ds_to_response(ds)


async def list_datasources(session: AsyncSession) -> list[DatasourceResponse]:
    result = await session.execute(
        select(SqlDatasource).order_by(SqlDatasource.name)
    )
    return [_ds_to_response(ds) for ds in result.scalars().all()]


async def get_datasource(session: AsyncSession, ds_id: int) -> DatasourceResponse | None:
    ds = await session.get(SqlDatasource, ds_id)
    return _ds_to_response(ds) if ds else None


async def update_datasource(
    session: AsyncSession, ds_id: int, req: DatasourceUpdate,
) -> DatasourceResponse | None:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return None
    if req.name is not None:
        ds.name = req.name
    if req.host is not None:
        ds.host = req.host
    if req.port is not None:
        ds.port = req.port
    if req.database_name is not None:
        ds.database_name = req.database_name
    if req.username is not None:
        ds.username = req.username
    if req.password is not None:
        ds.password_encrypted = _encrypt_password(req.password)
    if req.extra_params is not None:
        ds.extra_params = json.dumps(req.extra_params)
    if req.description is not None:
        ds.description = req.description
    await session.commit()
    await session.refresh(ds)
    return _ds_to_response(ds)


async def delete_datasource(session: AsyncSession, ds_id: int) -> bool:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return False
    await session.delete(ds)
    await session.commit()
    logger.info("Datasource deleted: id=%d name=%s", ds.id, ds.name)
    return True


def _ds_to_response(ds: SqlDatasource) -> DatasourceResponse:
    extra = json.loads(ds.extra_params) if isinstance(ds.extra_params, str) else ds.extra_params
    return DatasourceResponse(
        id=ds.id,
        name=ds.name,
        engine_type=EngineType(ds.engine_type),
        host=ds.host,
        port=ds.port,
        database_name=ds.database_name,
        username=ds.username,
        extra_params=extra or {},
        description=ds.description,
        created_by=ds.created_by,
        created_at=ds.created_at.isoformat() if ds.created_at else "",
        updated_at=ds.updated_at.isoformat() if ds.updated_at else "",
    )


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

async def test_connection(req: DatasourceTestRequest) -> DatasourceTestResponse:
    adapter = _create_adapter(
        engine_type=req.engine_type.value,
        host=req.host,
        port=req.port,
        database=req.database_name,
        username=req.username,
        password=req.password,
        extra=req.extra_params,
    )
    success, message, latency = await adapter.test_connection()
    return DatasourceTestResponse(success=success, message=message, latency_ms=round(latency, 2))


async def test_datasource_by_id(session: AsyncSession, ds_id: int) -> DatasourceTestResponse:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return DatasourceTestResponse(success=False, message="Datasource not found")
    adapter = _adapter_from_datasource(ds)
    success, message, latency = await adapter.test_connection()
    return DatasourceTestResponse(success=success, message=message, latency_ms=round(latency, 2))


# ---------------------------------------------------------------------------
# Metadata browsing
# ---------------------------------------------------------------------------

async def get_catalogs(session: AsyncSession, ds_id: int) -> list[dict]:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return []
    adapter = _adapter_from_datasource(ds)
    catalogs = await adapter.get_catalogs()
    return [{"name": c.name} for c in catalogs]


async def get_schemas(session: AsyncSession, ds_id: int, catalog: str = "") -> list[dict]:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return []
    adapter = _adapter_from_datasource(ds)
    schemas = await adapter.get_schemas(catalog)
    return [{"name": s.name, "catalog": s.catalog} for s in schemas]


async def get_tables(
    session: AsyncSession, ds_id: int, catalog: str = "", schema: str = "",
) -> list[dict]:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return []
    adapter = _adapter_from_datasource(ds)
    tables = await adapter.get_tables(catalog, schema)
    return [
        {"name": t.name, "table_type": t.table_type,
         "catalog": t.catalog, "schema_name": t.schema_name}
        for t in tables
    ]


async def get_columns(
    session: AsyncSession, ds_id: int, table: str,
    catalog: str = "", schema: str = "",
) -> list[dict]:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return []
    adapter = _adapter_from_datasource(ds)
    columns = await adapter.get_columns(table, catalog, schema)
    return [
        {"name": c.name, "data_type": c.data_type, "nullable": c.nullable,
         "comment": c.comment, "ordinal_position": c.ordinal_position}
        for c in columns
    ]


async def get_table_preview(
    session: AsyncSession, ds_id: int, table: str,
    catalog: str = "", schema: str = "", limit: int = 100,
) -> dict:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return {"columns": [], "rows": [], "total_rows": 0}
    adapter = _adapter_from_datasource(ds)
    result = await adapter.get_table_preview(table, catalog, schema, limit)
    return {
        "columns": result.columns,
        "rows": result.rows,
        "total_rows": result.row_count,
    }


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------

async def execute_query(
    session: AsyncSession,
    datasource_id: int,
    sql: str,
    max_rows: int = 1000,
    timeout_seconds: int = 300,
    username: str = "",
) -> QueryResultResponse:
    """Execute a query synchronously and return results immediately."""
    ds = await session.get(SqlDatasource, datasource_id)
    if not ds:
        raise ValueError(f"Datasource not found: {datasource_id}")

    execution_id = str(uuid.uuid4())
    adapter = _adapter_from_datasource(ds)

    # Record execution start
    execution = SqlQueryExecution(
        id=execution_id,
        datasource_id=datasource_id,
        sql_text=sql,
        status=QueryStatus.RUNNING.value,
        executed_by=username,
    )
    session.add(execution)
    await session.commit()

    try:
        result = await adapter.execute(sql, max_rows, timeout_seconds)

        # Update execution record
        await session.execute(
            update(SqlQueryExecution)
            .where(SqlQueryExecution.id == execution_id)
            .values(
                status=QueryStatus.FINISHED.value,
                row_count=result.row_count,
                elapsed_ms=result.elapsed_ms,
                engine_query_id=result.engine_query_id,
            )
        )

        # Record history
        history = SqlQueryHistory(
            datasource_id=datasource_id,
            datasource_name=ds.name,
            engine_type=ds.engine_type,
            sql_text=sql,
            status=QueryStatus.FINISHED.value,
            row_count=result.row_count,
            elapsed_ms=result.elapsed_ms,
            executed_by=username,
        )
        session.add(history)
        await session.commit()

        columns = [
            QueryResultColumn(name=c["name"], data_type=c.get("type", "VARCHAR"))
            for c in result.columns
        ]

        return QueryResultResponse(
            execution_id=execution_id,
            status=QueryStatus.FINISHED,
            columns=columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed_ms=result.elapsed_ms,
            has_more=result.row_count >= max_rows,
        )

    except Exception as e:
        error_msg = str(e)
        await session.execute(
            update(SqlQueryExecution)
            .where(SqlQueryExecution.id == execution_id)
            .values(status=QueryStatus.FAILED.value, error_message=error_msg)
        )
        history = SqlQueryHistory(
            datasource_id=datasource_id,
            datasource_name=ds.name,
            engine_type=ds.engine_type,
            sql_text=sql,
            status=QueryStatus.FAILED.value,
            error_message=error_msg,
            executed_by=username,
        )
        session.add(history)
        await session.commit()

        return QueryResultResponse(
            execution_id=execution_id,
            status=QueryStatus.FAILED,
            error_message=error_msg,
        )


async def submit_query(
    session: AsyncSession,
    datasource_id: int,
    sql: str,
    max_rows: int = 1000,
    timeout_seconds: int = 300,
    username: str = "",
) -> QuerySubmitResponse:
    """Submit a query for async execution. Returns immediately with execution_id."""
    ds = await session.get(SqlDatasource, datasource_id)
    if not ds:
        raise ValueError(f"Datasource not found: {datasource_id}")

    execution_id = str(uuid.uuid4())
    execution = SqlQueryExecution(
        id=execution_id,
        datasource_id=datasource_id,
        sql_text=sql,
        status=QueryStatus.QUEUED.value,
        executed_by=username,
    )
    session.add(execution)
    await session.commit()

    # Launch background execution
    import asyncio
    asyncio.create_task(
        _run_query_background(execution_id, ds, sql, max_rows, timeout_seconds, username)
    )

    return QuerySubmitResponse(execution_id=execution_id, status=QueryStatus.QUEUED)


async def _run_query_background(
    execution_id: str,
    ds: SqlDatasource,
    sql: str,
    max_rows: int,
    timeout_seconds: int,
    username: str,
) -> None:
    """Background task that executes a query and stores results."""
    from app.core.database import async_session

    adapter = _adapter_from_datasource(ds)

    async with async_session() as session:
        await session.execute(
            update(SqlQueryExecution)
            .where(SqlQueryExecution.id == execution_id)
            .values(status=QueryStatus.RUNNING.value)
        )
        await session.commit()

    try:
        result = await adapter.execute(sql, max_rows, timeout_seconds)

        # Store results in memory for later retrieval
        _execution_results[execution_id] = {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "elapsed_ms": result.elapsed_ms,
            "has_more": result.row_count >= max_rows,
        }

        async with async_session() as session:
            await session.execute(
                update(SqlQueryExecution)
                .where(SqlQueryExecution.id == execution_id)
                .values(
                    status=QueryStatus.FINISHED.value,
                    row_count=result.row_count,
                    elapsed_ms=result.elapsed_ms,
                    engine_query_id=result.engine_query_id,
                )
            )
            history = SqlQueryHistory(
                datasource_id=ds.id,
                datasource_name=ds.name,
                engine_type=ds.engine_type,
                sql_text=sql,
                status=QueryStatus.FINISHED.value,
                row_count=result.row_count,
                elapsed_ms=result.elapsed_ms,
                executed_by=username,
            )
            session.add(history)
            await session.commit()

    except Exception as e:
        error_msg = str(e)
        logger.error("Background query %s failed: %s", execution_id, error_msg)

        async with async_session() as session:
            await session.execute(
                update(SqlQueryExecution)
                .where(SqlQueryExecution.id == execution_id)
                .values(status=QueryStatus.FAILED.value, error_message=error_msg)
            )
            history = SqlQueryHistory(
                datasource_id=ds.id,
                datasource_name=ds.name,
                engine_type=ds.engine_type,
                sql_text=sql,
                status=QueryStatus.FAILED.value,
                error_message=error_msg,
                executed_by=username,
            )
            session.add(history)
            await session.commit()


async def get_execution_status(
    session: AsyncSession, execution_id: str,
) -> QueryStatusResponse | None:
    ex = await session.get(SqlQueryExecution, execution_id)
    if not ex:
        return None
    return QueryStatusResponse(
        execution_id=ex.id,
        status=QueryStatus(ex.status),
        row_count=ex.row_count,
        elapsed_ms=ex.elapsed_ms,
        error_message=ex.error_message,
        engine_query_id=ex.engine_query_id,
    )


async def get_execution_result(
    session: AsyncSession, execution_id: str,
) -> QueryResultResponse | None:
    ex = await session.get(SqlQueryExecution, execution_id)
    if not ex:
        return None

    cached = _execution_results.pop(execution_id, None)
    if cached:
        columns = [
            QueryResultColumn(name=c["name"], data_type=c.get("type", "VARCHAR"))
            for c in cached["columns"]
        ]
        return QueryResultResponse(
            execution_id=execution_id,
            status=QueryStatus(ex.status),
            columns=columns,
            rows=cached["rows"],
            row_count=cached["row_count"],
            elapsed_ms=cached["elapsed_ms"],
            has_more=cached["has_more"],
        )

    return QueryResultResponse(
        execution_id=execution_id,
        status=QueryStatus(ex.status),
        row_count=ex.row_count,
        elapsed_ms=ex.elapsed_ms,
        error_message=ex.error_message,
    )


async def cancel_query(
    session: AsyncSession, execution_id: str,
) -> QueryCancelResponse | None:
    ex = await session.get(SqlQueryExecution, execution_id)
    if not ex:
        return None

    if ex.status not in (QueryStatus.QUEUED.value, QueryStatus.RUNNING.value):
        return QueryCancelResponse(
            execution_id=execution_id,
            status=QueryStatus(ex.status),
            message=f"Query is already {ex.status}",
        )

    cancelled = False
    if ex.engine_query_id:
        ds = await session.get(SqlDatasource, ex.datasource_id)
        if ds:
            adapter = _adapter_from_datasource(ds)
            cancelled = await adapter.cancel(ex.engine_query_id)

    await session.execute(
        update(SqlQueryExecution)
        .where(SqlQueryExecution.id == execution_id)
        .values(status=QueryStatus.CANCELLED.value)
    )
    await session.commit()

    return QueryCancelResponse(
        execution_id=execution_id,
        status=QueryStatus.CANCELLED,
        message="Query cancelled" if cancelled else "Cancel signal sent",
    )


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

async def explain_query(
    session: AsyncSession, req: QueryExplainRequest,
) -> QueryExplainResponse:
    ds = await session.get(SqlDatasource, req.datasource_id)
    if not ds:
        raise ValueError(f"Datasource not found: {req.datasource_id}")
    adapter = _adapter_from_datasource(ds)
    plan = await adapter.explain(req.sql, req.analyze)
    return QueryExplainResponse(plan_text=plan, engine_type=EngineType(ds.engine_type))


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

async def get_query_history(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    datasource_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    username: str | None = None,
) -> QueryHistoryListResponse:
    query = select(SqlQueryHistory)
    count_query = select(func.count(SqlQueryHistory.id))

    if datasource_id:
        query = query.where(SqlQueryHistory.datasource_id == datasource_id)
        count_query = count_query.where(SqlQueryHistory.datasource_id == datasource_id)
    if status:
        query = query.where(SqlQueryHistory.status == status)
        count_query = count_query.where(SqlQueryHistory.status == status)
    if search:
        query = query.where(SqlQueryHistory.sql_text.ilike(f"%{search}%"))
        count_query = count_query.where(SqlQueryHistory.sql_text.ilike(f"%{search}%"))
    if username:
        query = query.where(SqlQueryHistory.executed_by == username)
        count_query = count_query.where(SqlQueryHistory.executed_by == username)

    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(SqlQueryHistory.executed_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)

    items = [
        QueryHistoryItem(
            id=h.id,
            datasource_id=h.datasource_id,
            datasource_name=h.datasource_name,
            engine_type=h.engine_type,
            sql_text=h.sql_text,
            status=h.status,
            row_count=h.row_count,
            elapsed_ms=h.elapsed_ms,
            error_message=h.error_message,
            executed_by=h.executed_by,
            executed_at=h.executed_at.isoformat() if h.executed_at else "",
        )
        for h in result.scalars().all()
    ]

    return QueryHistoryListResponse(items=items, total=total, page=page, page_size=page_size)


async def delete_query_history(session: AsyncSession, history_id: int) -> bool:
    result = await session.execute(
        delete(SqlQueryHistory).where(SqlQueryHistory.id == history_id)
    )
    await session.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Saved queries
# ---------------------------------------------------------------------------

async def create_saved_query(
    session: AsyncSession, req: SavedQueryCreate, username: str = "",
) -> SavedQueryResponse:
    sq = SqlSavedQuery(
        name=req.name,
        folder=req.folder,
        datasource_id=req.datasource_id,
        sql_text=req.sql_text,
        description=req.description,
        shared=req.shared.value,
        created_by=username,
    )
    session.add(sq)
    await session.commit()
    await session.refresh(sq)
    return _sq_to_response(sq)


async def list_saved_queries(
    session: AsyncSession,
    username: str | None = None,
    folder: str | None = None,
    datasource_id: int | None = None,
) -> SavedQueryListResponse:
    query = select(SqlSavedQuery)
    count_query = select(func.count(SqlSavedQuery.id))

    if folder is not None:
        query = query.where(SqlSavedQuery.folder == folder)
        count_query = count_query.where(SqlSavedQuery.folder == folder)
    if datasource_id:
        query = query.where(SqlSavedQuery.datasource_id == datasource_id)
        count_query = count_query.where(SqlSavedQuery.datasource_id == datasource_id)

    # Show own + shared
    if username:
        query = query.where(
            (SqlSavedQuery.created_by == username) | (SqlSavedQuery.shared != "private")
        )
        count_query = count_query.where(
            (SqlSavedQuery.created_by == username) | (SqlSavedQuery.shared != "private")
        )

    total = (await session.execute(count_query)).scalar() or 0
    query = query.order_by(SqlSavedQuery.folder, SqlSavedQuery.name)
    result = await session.execute(query)
    items = [_sq_to_response(sq) for sq in result.scalars().all()]
    return SavedQueryListResponse(items=items, total=total)


async def get_saved_query(session: AsyncSession, sq_id: int) -> SavedQueryResponse | None:
    sq = await session.get(SqlSavedQuery, sq_id)
    return _sq_to_response(sq) if sq else None


async def update_saved_query(
    session: AsyncSession, sq_id: int, req: SavedQueryUpdate,
) -> SavedQueryResponse | None:
    sq = await session.get(SqlSavedQuery, sq_id)
    if not sq:
        return None
    if req.name is not None:
        sq.name = req.name
    if req.folder is not None:
        sq.folder = req.folder
    if req.datasource_id is not None:
        sq.datasource_id = req.datasource_id
    if req.sql_text is not None:
        sq.sql_text = req.sql_text
    if req.description is not None:
        sq.description = req.description
    if req.shared is not None:
        sq.shared = req.shared.value
    await session.commit()
    await session.refresh(sq)
    return _sq_to_response(sq)


async def delete_saved_query(session: AsyncSession, sq_id: int) -> bool:
    sq = await session.get(SqlSavedQuery, sq_id)
    if not sq:
        return False
    await session.delete(sq)
    await session.commit()
    return True


def _sq_to_response(sq: SqlSavedQuery) -> SavedQueryResponse:
    return SavedQueryResponse(
        id=sq.id,
        name=sq.name,
        folder=sq.folder,
        datasource_id=sq.datasource_id,
        sql_text=sq.sql_text,
        description=sq.description,
        shared=sq.shared,
        created_by=sq.created_by,
        created_at=sq.created_at.isoformat() if sq.created_at else "",
        updated_at=sq.updated_at.isoformat() if sq.updated_at else "",
    )


# ---------------------------------------------------------------------------
# Autocomplete metadata
# ---------------------------------------------------------------------------

async def get_autocomplete(
    session: AsyncSession, ds_id: int,
    catalog: str = "", schema: str = "",
) -> AutocompleteResponse:
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        return AutocompleteResponse()

    adapter = _adapter_from_datasource(ds)

    tables_list: list[str] = []
    columns_list: list[str] = []
    try:
        tables = await adapter.get_tables(catalog, schema)
        tables_list = [t.name for t in tables]
        # Collect columns from all tables (limit to avoid excessive queries)
        for t in tables[:50]:
            cols = await adapter.get_columns(t.name, catalog, schema)
            columns_list.extend(c.name for c in cols)
        columns_list = sorted(set(columns_list))
    except Exception as e:
        logger.warning("Autocomplete metadata fetch failed for ds=%d: %s", ds_id, e)

    return AutocompleteResponse(
        keywords=adapter.get_keywords(),
        functions=adapter.get_functions(),
        data_types=adapter.get_data_types(),
        tables=tables_list,
        columns=columns_list,
    )
