"""SQLAlchemy models for Hive query history collection and lineage."""

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, UniqueConstraint, func

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
    platform_id = Column(String(100), nullable=True, index=True)
    received_at = Column(DateTime, server_default=func.now(), nullable=False)


class QueryLineage(Base):
    """Per-query source→target table mapping extracted from SQL."""

    __tablename__ = "argus_query_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hist_id = Column(Integer, nullable=True, index=True)
    source_table = Column(String(512), nullable=False, index=True)
    target_table = Column(String(512), nullable=False, index=True)
    source_dataset_id = Column(Integer, nullable=True)
    target_dataset_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ColumnLineage(Base):
    """Per-query source→target column mapping with transform type."""

    __tablename__ = "argus_column_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_lineage_id = Column(Integer, nullable=False, index=True)
    source_column = Column(String(256), nullable=False)
    target_column = Column(String(256), nullable=False)
    transform_type = Column(String(64), nullable=False, default="DIRECT")


class DatasetLineage(Base):
    """Aggregated dataset-to-dataset lineage relationships."""

    __tablename__ = "argus_dataset_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_dataset_id = Column(Integer, nullable=False, index=True)
    target_dataset_id = Column(Integer, nullable=False, index=True)
    relation_type = Column(String(32), nullable=False, default="READ_WRITE")
    query_count = Column(Integer, nullable=False, default=1)
    last_query_id = Column(String(256), nullable=True)
    last_seen_at = Column(DateTime, server_default=func.now(), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_dataset_id", "target_dataset_id", "relation_type",
            name="uq_dataset_lineage",
        ),
    )
