"""Pydantic schemas for SQL query editor module."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EngineType(str, Enum):
    TRINO = "trino"
    STARROCKS = "starrocks"
    POSTGRESQL = "postgresql"
    MARIADB = "mariadb"


class QueryStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ShareScope(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


# ---------------------------------------------------------------------------
# Datasource
# ---------------------------------------------------------------------------

class DatasourceCreate(BaseModel):
    name: str = Field(..., max_length=100, description="Display name")
    engine_type: EngineType
    host: str = Field(..., max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field("", max_length=100, description="Default database/catalog")
    username: str = Field("", max_length=100)
    password: str = Field("", max_length=200, description="Plain-text; encrypted before storage")
    extra_params: dict | None = Field(None, description="Engine-specific params (catalog, schema)")
    description: str = Field("", max_length=255)


class DatasourceUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = Field(None, ge=1, le=65535)
    database_name: str | None = None
    username: str | None = None
    password: str | None = Field(None, description="Omit to keep existing")
    extra_params: dict | None = None
    description: str | None = None


class DatasourceResponse(BaseModel):
    id: int
    name: str
    engine_type: EngineType
    host: str
    port: int
    database_name: str
    username: str
    extra_params: dict
    description: str
    created_by: str
    created_at: str
    updated_at: str


class DatasourceTestRequest(BaseModel):
    engine_type: EngineType
    host: str
    port: int = Field(..., ge=1, le=65535)
    database_name: str = ""
    username: str = ""
    password: str = ""
    extra_params: dict | None = None


class DatasourceTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: float | None = None


# ---------------------------------------------------------------------------
# Metadata browsing
# ---------------------------------------------------------------------------

class CatalogInfo(BaseModel):
    name: str


class SchemaInfo(BaseModel):
    name: str
    catalog: str = ""


class TableInfo(BaseModel):
    name: str
    table_type: str = "TABLE"  # TABLE, VIEW, etc.
    catalog: str = ""
    schema_name: str = ""


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    comment: str = ""
    ordinal_position: int = 0


class TableDetail(BaseModel):
    catalog: str = ""
    schema_name: str
    table_name: str
    table_type: str = "TABLE"
    columns: list[ColumnInfo] = []
    row_count: int | None = None
    comment: str = ""


class TablePreviewResponse(BaseModel):
    columns: list[ColumnInfo]
    rows: list[list] = []
    total_rows: int = 0


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------

class QueryExecuteRequest(BaseModel):
    datasource_id: int
    sql: str = Field(..., min_length=1, description="SQL statement(s) to execute")
    max_rows: int = Field(1000, ge=1, le=100000, description="Max rows to return")
    timeout_seconds: int = Field(300, ge=1, le=3600, description="Execution timeout")


class QuerySubmitResponse(BaseModel):
    """Returned immediately when a query is submitted for async execution."""
    execution_id: str
    status: QueryStatus


class QueryStatusResponse(BaseModel):
    execution_id: str
    status: QueryStatus
    row_count: int | None = None
    elapsed_ms: int | None = None
    error_message: str | None = None
    engine_query_id: str | None = None


class QueryResultColumn(BaseModel):
    name: str
    data_type: str


class QueryResultResponse(BaseModel):
    execution_id: str
    status: QueryStatus
    columns: list[QueryResultColumn] = []
    rows: list[list] = []
    row_count: int = 0
    elapsed_ms: int = 0
    error_message: str | None = None
    has_more: bool = False
    page: int = 1
    page_size: int = 500
    total_pages: int = 1


class QueryCancelResponse(BaseModel):
    execution_id: str
    status: QueryStatus
    message: str


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

class QueryExplainRequest(BaseModel):
    datasource_id: int
    sql: str = Field(..., min_length=1)
    analyze: bool = Field(False, description="Use EXPLAIN ANALYZE if supported")


class QueryExplainResponse(BaseModel):
    plan_text: str
    engine_type: EngineType


# ---------------------------------------------------------------------------
# Query history
# ---------------------------------------------------------------------------

class QueryHistoryItem(BaseModel):
    id: int
    datasource_id: int
    datasource_name: str
    engine_type: str
    sql_text: str
    status: str
    row_count: int | None
    elapsed_ms: int | None
    error_message: str | None
    executed_by: str
    executed_at: str


class QueryHistoryListResponse(BaseModel):
    items: list[QueryHistoryItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Saved queries
# ---------------------------------------------------------------------------

class SavedQueryCreate(BaseModel):
    name: str = Field(..., max_length=200)
    folder: str = Field("", max_length=200)
    datasource_id: int
    sql_text: str
    description: str = Field("", max_length=500)
    shared: ShareScope = ShareScope.PRIVATE


class SavedQueryUpdate(BaseModel):
    name: str | None = None
    folder: str | None = None
    datasource_id: int | None = None
    sql_text: str | None = None
    description: str | None = None
    shared: ShareScope | None = None


class SavedQueryResponse(BaseModel):
    id: int
    name: str
    folder: str
    datasource_id: int
    sql_text: str
    description: str
    shared: str
    created_by: str
    created_at: str
    updated_at: str


class SavedQueryListResponse(BaseModel):
    items: list[SavedQueryResponse]
    total: int


# ---------------------------------------------------------------------------
# Autocomplete metadata
# ---------------------------------------------------------------------------

class AutocompleteResponse(BaseModel):
    keywords: list[str] = []
    functions: list[str] = []
    data_types: list[str] = []
    schemas: list[str] = []
    tables: list[str] = []
    columns: list[str] = []
