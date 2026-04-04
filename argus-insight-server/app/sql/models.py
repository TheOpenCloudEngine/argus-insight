"""SQLAlchemy ORM models for SQL query editor module.

Tables:
- sql_datasources: Registered database connections (Trino, StarRocks, PostgreSQL).
- sql_saved_queries: User-saved SQL queries with folder organization.
- sql_query_history: Execution history log for all queries.
- sql_query_executions: Active/completed query execution state for long-running support.
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class SqlDatasource(Base):
    """Registered database connection."""

    __tablename__ = "sql_datasources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    engine_type = Column(String(20), nullable=False)  # trino, starrocks, postgresql
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(100), nullable=False, default="")
    username = Column(String(100), nullable=False, default="")
    password_encrypted = Column(String(500), nullable=False, default="")
    extra_params = Column(Text, nullable=False, default="{}")  # JSON: catalog, schema, etc.
    description = Column(String(255), nullable=False, default="")
    created_by = Column(String(100), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SqlSavedQuery(Base):
    """User-saved SQL query."""

    __tablename__ = "sql_saved_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    folder = Column(String(200), nullable=False, default="")
    datasource_id = Column(Integer, nullable=False)
    sql_text = Column(Text, nullable=False)
    description = Column(String(500), nullable=False, default="")
    created_by = Column(String(100), nullable=False, default="")
    shared = Column(String(10), nullable=False, default="private")  # private, team, public
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SqlQueryHistory(Base):
    """Query execution history log."""

    __tablename__ = "sql_query_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(Integer, nullable=False)
    datasource_name = Column(String(100), nullable=False, default="")
    engine_type = Column(String(20), nullable=False, default="")
    sql_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)  # RUNNING, FINISHED, FAILED, CANCELLED
    row_count = Column(Integer)
    elapsed_ms = Column(Integer)
    error_message = Column(Text)
    executed_by = Column(String(100), nullable=False, default="")
    executed_at = Column(DateTime(timezone=True), server_default=func.now())


class SqlQueryExecution(Base):
    """Active query execution state for long-running query tracking.

    Rows are created on query submit and updated as the query progresses.
    Enables cancel, status polling, and background execution.
    """

    __tablename__ = "sql_query_executions"

    id = Column(String(36), primary_key=True)  # UUID
    datasource_id = Column(Integer, nullable=False)
    sql_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="QUEUED")
    row_count = Column(Integer)
    elapsed_ms = Column(Integer)
    error_message = Column(Text)
    engine_query_id = Column(String(255))  # Trino query ID, PG PID, etc.
    executed_by = Column(String(100), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
