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
    parent_id = Column(Integer, ForeignKey("catalog_glossary_terms.id"))
    term_type = Column(String(20), nullable=False, default="TERM")  # CATEGORY or TERM
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
    """데이터 파이프라인 레지스트리.

    이기종 시스템 간 데이터 흐름(ETL, CDC, 파일 내보내기 등)을 등록하고 관리한다.
    DatasetLineage에서 pipeline_id로 참조하여 어떤 파이프라인이
    cross-platform 리니지를 만드는지 추적한다.

    예시: PostgreSQL → Parquet 변환 → Impala 적재 파이프라인
    """

    __tablename__ = "argus_data_pipeline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(255), nullable=False, unique=True)   # 파이프라인 고유 이름
    description = Column(Text)                                         # 파이프라인 설명
    pipeline_type = Column(String(64), nullable=False, default="ETL")  # 유형: ETL, FILE_EXPORT, CDC, REPLICATION, API, MANUAL
    schedule = Column(String(100))                                     # 실행 주기 (cron 표현식, 예: "0 2 * * *")
    owner = Column(String(200))                                        # 파이프라인 담당자
    status = Column(String(20), nullable=False, default="ACTIVE")      # 상태: ACTIVE, INACTIVE, DEPRECATED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatasetLineage(Base):
    """데이터셋 간 리니지 관계 (Cross-Platform 지원).

    이기종 시스템 간의 데이터 흐름 관계를 저장한다.
    동일 플랫폼 내 쿼리 기반 자동 수집과 수동/파이프라인 등록을 모두 지원.

    리니지 출처(lineage_source)에 따른 구분:
    - QUERY_AGGREGATED: 쿼리 로그 분석으로 자동 수집 (같은 플랫폼 내)
    - PIPELINE: 파이프라인 등록을 통해 명시적 연결 (이기종 간)
    - MANUAL: 사용자가 UI에서 직접 등록 (이기종 간)

    예시:
      PostgreSQL.hr_db.employees → Impala.analytics.emp_fact
      (lineage_source=PIPELINE, relation_type=ETL)
    """

    __tablename__ = "argus_dataset_lineage"
    __table_args__ = (
        UniqueConstraint("source_dataset_id", "target_dataset_id", "relation_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_dataset_id = Column(                                           # 원본 데이터셋 (데이터를 제공하는 쪽)
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False
    )
    target_dataset_id = Column(                                           # 대상 데이터셋 (데이터를 받는 쪽)
        Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(String(32), nullable=False, default="READ_WRITE")  # 관계 유형: ETL, FILE_EXPORT, CDC, REPLICATION, DERIVED, READ_WRITE
    lineage_source = Column(String(32), nullable=False, default="QUERY_AGGREGATED")  # 리니지 출처: QUERY_AGGREGATED, PIPELINE, MANUAL
    pipeline_id = Column(                                                 # 파이프라인 참조 (PIPELINE 출처일 때)
        Integer, ForeignKey("argus_data_pipeline.id", ondelete="SET NULL")
    )
    description = Column(Text)                                            # 리니지 관계 설명
    created_by = Column(String(200))                                      # 등록한 사용자
    query_count = Column(Integer, nullable=False, default=0)              # 이 관계를 확인한 쿼리 수 (자동 수집 시)
    last_query_id = Column(String(256))                                   # 마지막으로 확인된 쿼리 ID
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())  # 마지막 확인 시각
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DatasetColumnMapping(Base):
    """Cross-Platform 컬럼 수준 리니지 매핑.

    이기종 시스템 간 데이터셋 리니지에서 개별 컬럼 간의 매핑 관계를 저장한다.
    스키마 변경 시 영향 분석(Impact Analysis)의 핵심 데이터.

    변환 유형(transform_type):
    - DIRECT: 동일한 값을 그대로 전달
    - CAST: 타입 변환 (예: INT → BIGINT)
    - EXPRESSION: 수식/변환 적용 (transform_expr에 수식 기록)
    - DERIVED: 여러 컬럼에서 파생된 값 (집계, 계산 등)

    예시:
      source=emp_id → target=employee_key (transform_type=CAST, expr="CAST(emp_id AS BIGINT)")
    """

    __tablename__ = "argus_dataset_column_mapping"
    __table_args__ = (
        UniqueConstraint("dataset_lineage_id", "source_column", "target_column"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_lineage_id = Column(                                         # 소속 리니지 관계
        Integer, ForeignKey("argus_dataset_lineage.id", ondelete="CASCADE"), nullable=False
    )
    source_column = Column(String(256), nullable=False)                  # 원본 컬럼명
    target_column = Column(String(256), nullable=False)                  # 대상 컬럼명
    transform_type = Column(String(64), nullable=False, default="DIRECT")  # 변환 유형: DIRECT, CAST, EXPRESSION, DERIVED
    transform_expr = Column(String(500))                                 # 변환 수식 (CAST/EXPRESSION일 때, 예: "CAST(emp_id AS BIGINT)")


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
