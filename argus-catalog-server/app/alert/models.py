"""SQLAlchemy ORM models for lineage alerts and subscriptions."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AlertSubscription(Base):
    """User subscription for lineage change notifications."""

    __tablename__ = "argus_alert_subscription"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(200), nullable=False)
    scope_type = Column(String(32), nullable=False)  # DATASET, PIPELINE, PLATFORM, ALL
    scope_id = Column(Integer)
    channels = Column(String(200), nullable=False, default="IN_APP")
    severity_filter = Column(String(16), nullable=False, default="WARNING")
    is_active = Column(String(5), nullable=False, default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LineageAlert(Base):
    """Schema change impact alert for lineage relationships."""

    __tablename__ = "argus_lineage_alert"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(32), nullable=False)  # SCHEMA_CHANGE, LINEAGE_BROKEN
    severity = Column(String(16), nullable=False)  # INFO, WARNING, BREAKING
    source_dataset_id = Column(
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False
    )
    affected_dataset_id = Column(
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE")
    )
    lineage_id = Column(
        Integer, ForeignKey("argus_dataset_lineage.id", ondelete="SET NULL")
    )
    change_summary = Column(String(500), nullable=False)
    change_detail = Column(Text)
    status = Column(String(20), nullable=False, default="OPEN")
    resolved_by = Column(String(200))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AlertNotification(Base):
    """Delivery record for an alert notification."""

    __tablename__ = "argus_alert_notification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(
        Integer, ForeignKey("argus_lineage_alert.id", ondelete="CASCADE"), nullable=False
    )
    channel = Column(String(32), nullable=False)
    recipient = Column(String(200), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), nullable=False, default="SENT")
