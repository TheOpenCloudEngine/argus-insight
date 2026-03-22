"""OCI Model Hub ORM models.

Tables:
  - catalog_oci_models: Model metadata with README, classification, lifecycle
  - catalog_oci_model_versions: Versioned artifacts with OCI manifest
  - catalog_oci_model_tags: Tag associations (reuses catalog_tags)
  - catalog_oci_model_lineage: Training data / base model relationships
  - catalog_oci_model_download_log: Download event log for OCI models
"""

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class OciModel(Base):
    """OCI Model Hub — registered model with README and lifecycle."""

    __tablename__ = "catalog_oci_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255))
    description = Column(Text)
    readme = Column(Text)

    # Classification
    task = Column(String(50))
    framework = Column(String(50))
    language = Column(String(50))
    license = Column(String(100))

    # Source
    source_type = Column(String(50))
    source_id = Column(String(500))
    source_revision = Column(String(100))

    # Storage
    bucket = Column(String(255))
    storage_prefix = Column(String(500))

    # Ownership
    owner = Column(String(200))

    # Denormalized stats
    version_count = Column(Integer, nullable=False, default=0)
    total_size = Column(BigInteger, default=0)
    download_count = Column(Integer, nullable=False, default=0)

    # Lifecycle: draft → review → approved → production → deprecated → archived
    status = Column(String(20), nullable=False, default="draft")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OciModelVersion(Base):
    """Versioned model artifacts with OCI manifest."""

    __tablename__ = "catalog_oci_model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_oci_models.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)

    manifest = Column(Text)
    content_digest = Column(String(100))

    file_count = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)

    extra_metadata = Column("metadata", JSONB)

    status = Column(String(20), nullable=False, default="ready")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OciModelTag(Base):
    """Tag association for OCI models (reuses catalog_tags)."""

    __tablename__ = "catalog_oci_model_tags"
    __table_args__ = (UniqueConstraint("model_id", "tag_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_oci_models.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("catalog_tags.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OciModelLineage(Base):
    """Model lineage — training data and base model relationships."""

    __tablename__ = "catalog_oci_model_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_oci_models.id", ondelete="CASCADE"), nullable=False)

    source_type = Column(String(20), nullable=False)
    source_id = Column(String(255), nullable=False)
    source_name = Column(String(255))

    relation_type = Column(String(30), nullable=False)
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OciModelDownloadLog(Base):
    """Download event log for OCI models.

    Separate from MLflow's catalog_model_download_log to allow independent
    download trend analysis per hub.
    """

    __tablename__ = "catalog_oci_model_download_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(255), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    download_type = Column(String(20), nullable=False)
    client_ip = Column(String(45))
    user_agent = Column(String(500))
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
