"""Data quality ORM models."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.core.database import Base


class DataProfile(Base):
    """Column-level statistics snapshot for a dataset."""

    __tablename__ = "catalog_data_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    profile_json = Column(Text, nullable=False, default="[]")
    profiled_at = Column(DateTime(timezone=True), server_default=func.now())


class QualityRule(Base):
    """Quality check rule definition for a dataset."""

    __tablename__ = "catalog_quality_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String(255), nullable=False)
    check_type = Column(String(50), nullable=False)       # NOT_NULL, UNIQUE, MIN_VALUE, MAX_VALUE, ACCEPTED_VALUES, REGEX, ROW_COUNT, FRESHNESS, CUSTOM_SQL
    column_name = Column(String(256))                      # NULL for table-level checks
    expected_value = Column(Text)                          # JSON: expected value or config
    threshold = Column(Numeric(5, 2), default=100.00)      # Pass threshold %
    severity = Column(String(16), nullable=False, default="WARNING")
    is_active = Column(String(5), nullable=False, default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class QualityResult(Base):
    """Execution result of a quality check."""

    __tablename__ = "catalog_quality_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("catalog_quality_rule.id", ondelete="CASCADE"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    passed = Column(String(5), nullable=False)
    actual_value = Column(Text)
    detail = Column(Text)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())


class QualityScore(Base):
    """Aggregated quality score for a dataset at a point in time."""

    __tablename__ = "catalog_quality_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    score = Column(Numeric(5, 2), nullable=False, default=0)
    total_rules = Column(Integer, nullable=False, default=0)
    passed_rules = Column(Integer, nullable=False, default=0)
    warning_rules = Column(Integer, nullable=False, default=0)
    failed_rules = Column(Integer, nullable=False, default=0)
    scored_at = Column(DateTime(timezone=True), server_default=func.now())
