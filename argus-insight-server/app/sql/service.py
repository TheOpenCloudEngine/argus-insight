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

# ---------------------------------------------------------------------------
# Paginated result cache with TTL
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = 500
CACHE_TTL_SECONDS = 300  # 5 minutes


class _PagedResultCache:
    """In-memory cache for query results with page-based access and TTL."""

    def __init__(self):
        self._store: dict[str, dict] = {}  # execution_id → {columns, pages, total_rows, ...}

    def put(self, execution_id: str, columns: list[dict], rows: list[list],
            elapsed_ms: int, page_size: int = DEFAULT_PAGE_SIZE):
        """Store result, split into pages."""
        total_rows = len(rows)
        pages: list[list[list]] = []
        for i in range(0, total_rows, page_size):
            pages.append(rows[i:i + page_size])
        self._store[execution_id] = {
            "columns": columns,
            "pages": pages,
            "total_rows": total_rows,
            "page_size": page_size,
            "total_pages": len(pages) if pages else 1,
            "elapsed_ms": elapsed_ms,
            "created_at": time.time(),
        }

    def get_page(self, execution_id: str, page: int = 1) -> dict | None:
        """Get a specific page. Returns None if not cached."""
        entry = self._store.get(execution_id)
        if not entry:
            return None
        # TTL check
        if time.time() - entry["created_at"] > CACHE_TTL_SECONDS:
            self._store.pop(execution_id, None)
            return None
        page_idx = max(0, page - 1)
        page_rows = entry["pages"][page_idx] if page_idx < len(entry["pages"]) else []
        return {
            "columns": entry["columns"],
            "rows": page_rows,
            "total_rows": entry["total_rows"],
            "page": page,
            "page_size": entry["page_size"],
            "total_pages": entry["total_pages"],
            "elapsed_ms": entry["elapsed_ms"],
        }

    def get_all_rows(self, execution_id: str) -> tuple[list[dict], list[list]] | None:
        """Get all rows for CSV export. Returns (columns, all_rows) or None."""
        entry = self._store.get(execution_id)
        if not entry:
            return None
        all_rows = []
        for page in entry["pages"]:
            all_rows.extend(page)
        return entry["columns"], all_rows

    def remove(self, execution_id: str):
        self._store.pop(execution_id, None)

    def cleanup_expired(self):
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["created_at"] > CACHE_TTL_SECONDS]
        for k in expired:
            del self._store[k]


_result_cache = _PagedResultCache()

# Legacy compat
_execution_results: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

def _create_adapter(
    engine_type: str, host: str, port: int, database: str,
    username: str, password: str, extra: dict | None = None,
) -> BaseAdapter:
    """Create a database adapter for the given engine type.

    Supported engines: trino, starrocks, postgresql, mariadb.
    MariaDB uses the StarRocks (MySQL-protocol) adapter.
    """
    config = ConnectionConfig(
        host=host, port=port, database=database,
        username=username, password=password, extra=extra or {},
    )
    et = engine_type.lower()
    if et == EngineType.TRINO:
        logger.debug("Creating Trino adapter: %s:%d/%s", host, port, database)
        return TrinoAdapter(config)
    elif et in (EngineType.STARROCKS, EngineType.MARIADB):
        logger.debug("Creating MySQL-compat adapter (%s): %s:%d/%s", et, host, port, database)
        return StarRocksAdapter(config)
    elif et == EngineType.POSTGRESQL:
        logger.debug("Creating PostgreSQL adapter: %s:%d/%s", host, port, database)
        return PostgreSQLAdapter(config)
    else:
        logger.warning("Unsupported engine type requested: %s", engine_type)
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


async def _adapter_from_workspace_service(session: AsyncSession, svc_id: int) -> BaseAdapter:
    """Create an adapter from a workspace service (argus_workspace_services) by ID.

    Reads connection info from the service metadata (display/internal fields)
    and creates the appropriate adapter. Uses raw SQL to avoid ORM metadata
    attribute name collision.
    """
    from sqlalchemy import text
    import json as json_mod

    logger.debug("Creating adapter from workspace service id=%d", svc_id)
    row = await session.execute(
        text("SELECT plugin_name, endpoint, username, metadata FROM argus_workspace_services WHERE id = :id"),
        {"id": svc_id},
    )
    svc = row.fetchone()
    if not svc:
        logger.warning("Workspace service id=%d not found", svc_id)
        raise ValueError(f"Workspace service {svc_id} not found")

    plugin_name, endpoint, ws_username, meta_raw = svc
    meta = meta_raw if isinstance(meta_raw, dict) else (
        json_mod.loads(meta_raw) if isinstance(meta_raw, str) else {}
    )
    display = meta.get("display", {})
    internal = meta.get("internal", {})

    engine_map = {
        "argus-trino": "trino",
        "argus-starrocks": "starrocks",
        "argus-postgresql": "postgresql",
        "argus-mariadb": "mariadb",
    }
    engine_type = engine_map.get(plugin_name, "postgresql")

    # Default ports per engine
    default_ports = {"trino": 8080, "starrocks": 9030, "postgresql": 5432, "mariadb": 3306}

    # Try to get host:port from display address field (e.g. "host:5432")
    address_keys = ["PostgreSQL Address", "MariaDB Address", "StarRocks Address", "Trino Address", "Address"]
    host, port = "", 0
    for ak in address_keys:
        addr = display.get(ak, "")
        if addr:
            if ":" in addr:
                parts = addr.rsplit(":", 1)
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    port = default_ports.get(engine_type, 0)
            else:
                host = addr
            break

    # Fallback: use internal.host
    if not host:
        host = internal.get("host", "")

    # Fallback: parse from endpoint URL
    if not host:
        from urllib.parse import urlparse
        parsed = urlparse(internal.get("endpoint", endpoint or ""))
        host = parsed.hostname or ""
        port = parsed.port or 0

    # Ensure port
    if not port:
        port = default_ports.get(engine_type, 5432)

    db_name = display.get("DB Name", display.get("Database", ""))
    db_user = display.get("DB User", ws_username or "")
    db_pass = display.get("DB Password", "")

    logger.info("Workspace service id=%d resolved: engine=%s host=%s:%d db=%s user=%s",
                svc_id, engine_type, host, port, db_name, db_user)
    return _create_adapter(engine_type, host, port, db_name, db_user, db_pass)


async def _get_adapter(session: AsyncSession, ds_id: int) -> BaseAdapter:
    """Get adapter for either custom datasource (positive ID) or workspace service (negative ID).

    Workspace services use negative IDs (e.g. -39 = workspace service id 39).
    """
    if ds_id < 0:
        logger.debug("Resolving workspace datasource: ds_id=%d → service_id=%d", ds_id, abs(ds_id))
        return await _adapter_from_workspace_service(session, abs(ds_id))
    logger.debug("Resolving custom datasource: ds_id=%d", ds_id)
    ds = await session.get(SqlDatasource, ds_id)
    if not ds:
        logger.warning("Custom datasource id=%d not found", ds_id)
        raise ValueError(f"Datasource {ds_id} not found")
    return _adapter_from_datasource(ds)


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
    """Fetch catalog list from datasource for schema browser."""
    adapter = await _get_adapter(session, ds_id)
    catalogs = await adapter.get_catalogs()
    logger.debug("get_catalogs ds_id=%d → %d catalogs", ds_id, len(catalogs))
    return [{"name": c.name} for c in catalogs]


async def get_schemas(session: AsyncSession, ds_id: int, catalog: str = "") -> list[dict]:
    adapter = await _get_adapter(session, ds_id)
    schemas = await adapter.get_schemas(catalog)
    return [{"name": s.name, "catalog": s.catalog} for s in schemas]


async def get_tables(
    session: AsyncSession, ds_id: int, catalog: str = "", schema: str = "",
) -> list[dict]:
    adapter = await _get_adapter(session, ds_id)
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
    adapter = await _get_adapter(session, ds_id)
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
    adapter = await _get_adapter(session, ds_id)
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
    logger.info("execute_query: ds_id=%d user=%s sql=%.80s", datasource_id, username, sql.strip())
    # Resolve adapter and datasource name/engine for history
    adapter = await _get_adapter(session, datasource_id)
    if datasource_id < 0:
        # Workspace datasource — get name/engine from service table
        from sqlalchemy import text as sa_text
        _svc = await session.execute(
            sa_text("SELECT display_name, plugin_name FROM argus_workspace_services WHERE id = :id"),
            {"id": abs(datasource_id)},
        )
        _row = _svc.fetchone()
        ds_name = _row[0] if _row else "Workspace"
        _engine_map = {"argus-trino": "trino", "argus-starrocks": "starrocks",
                       "argus-postgresql": "postgresql", "argus-mariadb": "mariadb"}
        ds_engine = _engine_map.get(_row[1], "postgresql") if _row else "postgresql"
    else:
        ds = await session.get(SqlDatasource, datasource_id)
        if not ds:
            raise ValueError(f"Datasource not found: {datasource_id}")
        ds_name = ds.name
        ds_engine = ds.engine_type

    execution_id = str(uuid.uuid4())

    # Record execution start
    execution = SqlQueryExecution(
        id=execution_id,
        datasource_id=abs(datasource_id),
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
            datasource_id=abs(datasource_id),
            datasource_name=ds_name,
            engine_type=ds_engine,
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
            datasource_id=abs(datasource_id),
            datasource_name=ds_name,
            engine_type=ds_engine,
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
    logger.info("submit_query: ds_id=%d user=%s sql=%.80s", datasource_id, username, sql.strip())
    adapter = await _get_adapter(session, datasource_id)

    # Resolve name/engine for history
    if datasource_id < 0:
        from sqlalchemy import text as sa_text
        _svc = await session.execute(
            sa_text("SELECT display_name, plugin_name FROM argus_workspace_services WHERE id = :id"),
            {"id": abs(datasource_id)},
        )
        _row = _svc.fetchone()
        ds_name = _row[0] if _row else "Workspace"
        _engine_map = {"argus-trino": "trino", "argus-starrocks": "starrocks",
                       "argus-postgresql": "postgresql", "argus-mariadb": "mariadb"}
        ds_engine = _engine_map.get(_row[1], "postgresql") if _row else "postgresql"
    else:
        ds = await session.get(SqlDatasource, datasource_id)
        if not ds:
            raise ValueError(f"Datasource not found: {datasource_id}")
        ds_name = ds.name
        ds_engine = ds.engine_type

    execution_id = str(uuid.uuid4())
    execution = SqlQueryExecution(
        id=execution_id,
        datasource_id=abs(datasource_id),
        sql_text=sql,
        status=QueryStatus.QUEUED.value,
        executed_by=username,
    )
    session.add(execution)
    await session.commit()

    # Launch background execution
    import asyncio
    asyncio.create_task(
        _run_query_background(execution_id, adapter, datasource_id,
                              ds_name, ds_engine, sql, max_rows, timeout_seconds, username)
    )

    return QuerySubmitResponse(execution_id=execution_id, status=QueryStatus.QUEUED)


async def _run_query_background(
    execution_id: str,
    adapter: BaseAdapter,
    datasource_id: int,
    ds_name: str,
    ds_engine: str,
    sql: str,
    max_rows: int,
    timeout_seconds: int,
    username: str,
) -> None:
    """Background task that executes a query and stores results in paginated cache."""
    from app.core.database import async_session
    logger.info("Background query started: execution_id=%s ds_name=%s", execution_id, ds_name)

    async with async_session() as session:
        await session.execute(
            update(SqlQueryExecution)
            .where(SqlQueryExecution.id == execution_id)
            .values(status=QueryStatus.RUNNING.value)
        )
        await session.commit()

    try:
        result = await adapter.execute(sql, max_rows, timeout_seconds)

        # Store results in paginated cache
        # Store results in paginated cache (500 rows/page, 5min TTL)
        _result_cache.put(execution_id, result.columns, result.rows, result.elapsed_ms)
        logger.info("Background query completed: execution_id=%s rows=%d elapsed=%dms",
                     execution_id, result.row_count, result.elapsed_ms)

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
                datasource_id=abs(datasource_id),
                datasource_name=ds_name,
                engine_type=ds_engine,
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
                datasource_id=abs(datasource_id),
                datasource_name=ds_name,
                engine_type=ds_engine,
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
    session: AsyncSession, execution_id: str, page: int = 1,
) -> QueryResultResponse | None:
    ex = await session.get(SqlQueryExecution, execution_id)
    if not ex:
        return None

    cached = _result_cache.get_page(execution_id, page)
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
            row_count=cached["total_rows"],
            elapsed_ms=cached["elapsed_ms"],
            has_more=page < cached["total_pages"],
            page=cached["page"],
            page_size=cached["page_size"],
            total_pages=cached["total_pages"],
        )

    return QueryResultResponse(
        execution_id=execution_id,
        status=QueryStatus(ex.status),
        row_count=ex.row_count,
        elapsed_ms=ex.elapsed_ms,
        error_message=ex.error_message,
    )


def get_execution_all_rows(execution_id: str) -> tuple[list[dict], list[list]] | None:
    """Get all rows for CSV export."""
    return _result_cache.get_all_rows(execution_id)


async def cancel_query(
    session: AsyncSession, execution_id: str,
) -> QueryCancelResponse | None:
    """Cancel a running query by sending pg_cancel_backend (or engine equivalent)."""
    logger.info("cancel_query: execution_id=%s", execution_id)
    ex = await session.get(SqlQueryExecution, execution_id)
    if not ex:
        logger.warning("cancel_query: execution_id=%s not found", execution_id)
        return None

    if ex.status not in (QueryStatus.QUEUED.value, QueryStatus.RUNNING.value):
        return QueryCancelResponse(
            execution_id=execution_id,
            status=QueryStatus(ex.status),
            message=f"Query is already {ex.status}",
        )

    cancelled = False
    if ex.engine_query_id:
        try:
            adapter = await _get_adapter(session, ex.datasource_id)
            cancelled = await adapter.cancel(ex.engine_query_id)
        except Exception as e:
            logger.warning("Cancel adapter creation failed: %s", e)

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
    try:
        adapter = await _get_adapter(session, ds_id)
    except ValueError:
        return AutocompleteResponse()

    schemas_list: list[str] = []
    tables_list: list[str] = []
    columns_list: list[str] = []
    try:
        # Fetch schemas
        schemas = await adapter.get_schemas(catalog)
        schemas_list = [s.name for s in schemas]

        # Fetch tables from all schemas (or specified one)
        if schema:
            tables = await adapter.get_tables(catalog, schema)
        else:
            tables = []
            for s in schemas:
                tables.extend(await adapter.get_tables(catalog, s.name))

        tables_list = sorted(set(t.name for t in tables))

        # Collect columns from tables (limit to avoid excessive queries)
        for t in tables[:50]:
            cols = await adapter.get_columns(t.name, catalog, t.schema_name or schema)
            columns_list.extend(c.name for c in cols)
        columns_list = sorted(set(columns_list))
    except Exception as e:
        logger.warning("Autocomplete metadata fetch failed for ds=%d: %s", ds_id, e)

    return AutocompleteResponse(
        keywords=adapter.get_keywords(),
        functions=adapter.get_functions(),
        data_types=adapter.get_data_types(),
        schemas=schemas_list,
        tables=tables_list,
        columns=columns_list,
    )
