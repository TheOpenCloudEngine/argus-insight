"""SQLAlchemy ORM models for data catalog.

Core entity types modeled after DataHub:
- Dataset: Tables, views, topics, files
- Tag: Labels for categorization
- GlossaryTerm: Business glossary terms
- Owner: Dataset ownership tracking
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class Platform(Base):
    """Data platform registry (e.g. Hive, MySQL, Kafka, S3)."""

    __tablename__ = "catalog_platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    logo_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Dataset(Base):
    """Dataset entity - a table, view, topic, or file in a data platform."""

    __tablename__ = "catalog_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    urn = Column(String(500), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id"), nullable=False)
    description = Column(Text)
    origin = Column(String(50), nullable=False, default="PROD")
    qualified_name = Column(String(500))
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatasetSchema(Base):
    """Schema fields for a dataset."""

    __tablename__ = "catalog_dataset_schemas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    field_path = Column(String(500), nullable=False)
    field_type = Column(String(100), nullable=False)
    native_type = Column(String(100))
    description = Column(Text)
    nullable = Column(String(5), default="true")
    ordinal = Column(Integer, nullable=False, default=0)


class Tag(Base):
    """Tag for categorizing datasets."""

    __tablename__ = "catalog_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    color = Column(String(7), default="#3b82f6")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DatasetTag(Base):
    """Many-to-many relationship between datasets and tags."""

    __tablename__ = "catalog_dataset_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    tag_id = Column(Integer, ForeignKey("catalog_tags.id", ondelete="CASCADE"), nullable=False)


class GlossaryTerm(Base):
    """Business glossary term."""

    __tablename__ = "catalog_glossary_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    source = Column(String(100))
    parent_id = Column(Integer, ForeignKey("catalog_glossary_terms.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatasetGlossaryTerm(Base):
    """Many-to-many relationship between datasets and glossary terms."""

    __tablename__ = "catalog_dataset_glossary_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    term_id = Column(Integer, ForeignKey("catalog_glossary_terms.id", ondelete="CASCADE"),
                     nullable=False)


class Owner(Base):
    """Dataset ownership."""

    __tablename__ = "catalog_owners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    owner_name = Column(String(200), nullable=False)
    owner_type = Column(String(50), nullable=False, default="TECHNICAL_OWNER")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
