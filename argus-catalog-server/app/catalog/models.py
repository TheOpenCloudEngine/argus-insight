"""SQLAlchemy ORM models for data catalog.

Core entity types modeled after DataHub:
- Dataset: Tables, views, topics, files
- Tag: Labels for categorization
- GlossaryTerm: Business glossary terms
- Owner: Dataset ownership tracking
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.core.database import Base


class Platform(Base):
    """Data platform registry (e.g. Hive, MySQL, Kafka, S3)."""

    __tablename__ = "catalog_platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    type = Column(String(100), nullable=False)
    logo_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlatformConfiguration(Base):
    """Connection and configuration settings for a platform instance."""

    __tablename__ = "catalog_platform_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="CASCADE"),
                         nullable=False, unique=True)
    config_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
    table_type = Column(String(100))
    storage_format = Column(String(100))
    platform_properties = Column(Text)  # JSON: platform-specific metadata
    is_synced = Column(String(5), default="false")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatasetProperty(Base):
    """Platform-specific key-value properties for a dataset."""

    __tablename__ = "catalog_dataset_properties"
    __table_args__ = (UniqueConstraint("dataset_id", "property_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    property_key = Column(String(100), nullable=False)
    property_value = Column(Text, nullable=False)


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
    is_primary_key = Column(String(5), default="false")
    is_unique = Column(String(5), default="false")
    is_indexed = Column(String(5), default="false")
    is_partition_key = Column(String(5), default="false")
    is_distribution_key = Column(String(5), default="false")
    ordinal = Column(Integer, nullable=False, default=0)


class SchemaSnapshot(Base):
    """Schema change history snapshot.

    Records a full schema snapshot each time sync detects changes.
    Only saved when actual changes (ADD/MODIFY/DROP) are detected.
    """

    __tablename__ = "catalog_schema_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    schema_json = Column(Text, nullable=False)       # Full schema as JSON array
    field_count = Column(Integer, default=0)
    change_summary = Column(String(500))              # e.g. "Added 2, Modified 1, Dropped 1"
    changes_json = Column(Text)                       # Individual changes as JSON array


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


# ---------------------------------------------------------------------------
# Platform metadata models
# ---------------------------------------------------------------------------

class DataPipeline(Base):
    """Data pipeline registry for ETL/CDC/file-export flows."""

    __tablename__ = "argus_data_pipeline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    pipeline_type = Column(String(64), nullable=False, default="ETL")
    schedule = Column(String(100))
    owner = Column(String(200))
    status = Column(String(20), nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatasetLineage(Base):
    """Aggregated dataset-to-dataset lineage (cross-platform supported)."""

    __tablename__ = "argus_dataset_lineage"
    __table_args__ = (
        UniqueConstraint("source_dataset_id", "target_dataset_id", "relation_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_dataset_id = Column(
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False
    )
    target_dataset_id = Column(
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(String(32), nullable=False, default="READ_WRITE")
    lineage_source = Column(String(32), nullable=False, default="QUERY_AGGREGATED")
    pipeline_id = Column(
        Integer, ForeignKey("argus_data_pipeline.id", ondelete="SET NULL")
    )
    description = Column(Text)
    created_by = Column(String(200))
    query_count = Column(Integer, nullable=False, default=0)
    last_query_id = Column(String(256))
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DatasetColumnMapping(Base):
    """Cross-platform column-level lineage mapping."""

    __tablename__ = "argus_dataset_column_mapping"
    __table_args__ = (
        UniqueConstraint("dataset_lineage_id", "source_column", "target_column"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_lineage_id = Column(
        Integer, ForeignKey("argus_dataset_lineage.id", ondelete="CASCADE"), nullable=False
    )
    source_column = Column(String(256), nullable=False)
    target_column = Column(String(256), nullable=False)
    transform_type = Column(String(64), nullable=False, default="DIRECT")
    transform_expr = Column(String(500))


class PlatformDataType(Base):
    """Supported data types per platform."""

    __tablename__ = "catalog_platform_data_types"
    __table_args__ = (UniqueConstraint("platform_id", "type_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="CASCADE"),
                         nullable=False)
    type_name = Column(String(100), nullable=False)
    type_category = Column(String(50), nullable=False)
    description = Column(String(500))
    ordinal = Column(Integer, nullable=False, default=0)


class PlatformTableType(Base):
    """Supported table/entity types per platform."""

    __tablename__ = "catalog_platform_table_types"
    __table_args__ = (UniqueConstraint("platform_id", "type_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="CASCADE"),
                         nullable=False)
    type_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(String(500))
    is_default = Column(String(5), default="false")
    ordinal = Column(Integer, nullable=False, default=0)


class PlatformStorageFormat(Base):
    """Supported storage/serialization formats per platform."""

    __tablename__ = "catalog_platform_storage_formats"
    __table_args__ = (UniqueConstraint("platform_id", "format_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="CASCADE"),
                         nullable=False)
    format_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(String(500))
    is_default = Column(String(5), default="false")
    ordinal = Column(Integer, nullable=False, default=0)


class PlatformFeature(Base):
    """Platform-specific features (partition keys, distribution, etc.)."""

    __tablename__ = "catalog_platform_features"
    __table_args__ = (UniqueConstraint("platform_id", "feature_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="CASCADE"),
                         nullable=False)
    feature_key = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(String(500))
    value_type = Column(String(50), nullable=False)
    is_required = Column(String(5), default="false")
    ordinal = Column(Integer, nullable=False, default=0)
