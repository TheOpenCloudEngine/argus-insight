"""SQLAlchemy models for Hive query history collection."""

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from sync.core.database import Base


class HiveQueryHistory(Base):
    """Hive query execution history collected from QueryAuditHook."""

    __tablename__ = "argus_collector_hive_query_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(256), nullable=False, index=True)
    short_username = Column(String(128), nullable=True)
    username = Column(String(256), nullable=True)
    operation_name = Column(String(64), nullable=True)
    start_time = Column(BigInteger, nullable=True)
    end_time = Column(BigInteger, nullable=True)
    duration_ms = Column(BigInteger, nullable=True)
    query = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, index=True)
    error_msg = Column(Text, nullable=True)
    received_at = Column(DateTime, server_default=func.now(), nullable=False)
