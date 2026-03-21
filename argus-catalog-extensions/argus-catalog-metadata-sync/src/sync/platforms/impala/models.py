"""SQLAlchemy models for Impala query history collection."""

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from sync.core.database import Base


class ImpalaQueryHistory(Base):
    """Impala query execution history collected from Cloudera Manager API."""

    __tablename__ = "argus_collector_impala_query_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(256), nullable=False, unique=True, index=True)
    query_type = Column(String(32), nullable=True)       # DML, DDL, QUERY, UNKNOWN
    query_state = Column(String(32), nullable=True)       # FINISHED, EXCEPTION, etc.
    statement = Column(Text, nullable=True)
    database = Column(String(256), nullable=True)
    username = Column(String(256), nullable=True)
    coordinator_host = Column(String(512), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(BigInteger, nullable=True)
    rows_produced = Column(BigInteger, nullable=True)
    platform_id = Column(String(100), nullable=True, index=True)
    received_at = Column(DateTime, server_default=func.now(), nullable=False)
