"""Data catalog schemas for request/response validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DatasetOrigin(str, Enum):
    PROD = "PROD"
    DEV = "DEV"
    STAGING = "STAGING"


class DatasetStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


class OwnerType(str, Enum):
    TECHNICAL_OWNER = "TECHNICAL_OWNER"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    DATA_STEWARD = "DATA_STEWARD"


# ---------------------------------------------------------------------------
# Platform schemas
# ---------------------------------------------------------------------------

class PlatformCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., min_length=1, max_length=100)
    logo_url: str | None = None


class PlatformResponse(BaseModel):
    id: int
    platform_id: str
    name: str
    type: str
    logo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformConfigurationSave(BaseModel):
    config: dict


class PlatformUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)


class PlatformConfigurationResponse(BaseModel):
    id: int
    platform_id: int
    config: dict
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Schema field schemas
# ---------------------------------------------------------------------------

class SchemaFieldCreate(BaseModel):
    field_path: str = Field(..., min_length=1, max_length=500)
    field_type: str = Field(..., min_length=1, max_length=100)
    native_type: str | None = None
    description: str | None = None
    nullable: str = "true"
    is_primary_key: str = "false"
    is_unique: str = "false"
    is_indexed: str = "false"
    is_partition_key: str = "false"
    is_distribution_key: str = "false"
    ordinal: int = 0


class SchemaFieldResponse(BaseModel):
    id: int
    field_path: str
    field_type: str
    native_type: str | None = None
    description: str | None = None
    nullable: str
    is_primary_key: str = "false"
    is_unique: str = "false"
    is_indexed: str = "false"
    is_partition_key: str = "false"
    is_distribution_key: str = "false"
    ordinal: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tag schemas
# ---------------------------------------------------------------------------

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    color: str = "#3b82f6"


class TagResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Glossary term schemas
# ---------------------------------------------------------------------------

class GlossaryTermCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    parent_id: int | None = None
    term_type: str = "TERM"  # CATEGORY or TERM


class GlossaryTermUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: int | None = None
    term_type: str | None = None


class GlossaryTermResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    parent_id: int | None = None
    term_type: str = "TERM"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Owner schemas
# ---------------------------------------------------------------------------

class OwnerCreate(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=200)
    owner_type: OwnerType = OwnerType.TECHNICAL_OWNER


class OwnerResponse(BaseModel):
    id: int
    dataset_id: int
    owner_name: str
    owner_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dataset schemas
# ---------------------------------------------------------------------------

class DatasetPropertyCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str


class DatasetPropertyResponse(BaseModel):
    id: int
    property_key: str
    property_value: str

    model_config = {"from_attributes": True}


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform_id: int
    description: str | None = None
    origin: DatasetOrigin = DatasetOrigin.PROD
    qualified_name: str | None = None
    table_type: str | None = None
    storage_format: str | None = None
    schema_fields: list[SchemaFieldCreate] = Field(default_factory=list)
    tags: list[int] = Field(default_factory=list, description="Tag IDs to attach")
    owners: list[OwnerCreate] = Field(default_factory=list)
    properties: list[DatasetPropertyCreate] = Field(default_factory=list)


class DatasetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    origin: DatasetOrigin | None = None
    qualified_name: str | None = None
    table_type: str | None = None
    storage_format: str | None = None
    status: DatasetStatus | None = None


class DatasetResponse(BaseModel):
    id: int
    urn: str
    name: str
    platform: PlatformResponse
    description: str | None = None
    origin: str
    qualified_name: str | None = None
    table_type: str | None = None
    storage_format: str | None = None
    status: str
    is_synced: str = "false"
    platform_properties: dict | None = None
    schema_fields: list[SchemaFieldResponse] = Field(default_factory=list)
    tags: list[TagResponse] = Field(default_factory=list)
    owners: list[OwnerResponse] = Field(default_factory=list)
    glossary_terms: list[GlossaryTermResponse] = Field(default_factory=list)
    properties: list[DatasetPropertyResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DatasetSummary(BaseModel):
    """Lightweight dataset representation for list views."""
    id: int
    urn: str
    name: str
    platform_name: str
    platform_type: str
    description: str | None = None
    origin: str
    status: str
    is_synced: str = "false"
    tag_count: int = 0
    owner_count: int = 0
    schema_field_count: int = 0
    created_at: datetime
    updated_at: datetime


class PaginatedDatasets(BaseModel):
    items: list[DatasetSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Schema history schemas
# ---------------------------------------------------------------------------

class SchemaChangeEntry(BaseModel):
    type: str  # ADD, MODIFY, DROP
    field: str
    before: dict | None = None
    after: dict | None = None


class SchemaSnapshotResponse(BaseModel):
    id: int
    dataset_id: int
    synced_at: datetime
    field_count: int
    change_summary: str | None = None
    changes: list[SchemaChangeEntry] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PaginatedSchemaSnapshots(BaseModel):
    items: list[SchemaSnapshotResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Search schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = ""
    platform: str | None = None
    origin: str | None = None
    tag: str | None = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    datasets: PaginatedDatasets


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class TagUsage(BaseModel):
    """Tag usage information across the catalog."""
    tag: TagResponse
    datasets: list[DatasetSummary] = Field(default_factory=list)
    total_datasets: int = 0


class CatalogStats(BaseModel):
    total_datasets: int
    total_platforms: int
    total_tags: int
    total_glossary_terms: int
    total_owners: int
    synced_datasets: int
    datasets_by_platform: list[dict]
    datasets_by_origin: list[dict]
    datasets_by_platform_type: list[dict]
    schema_fields_by_platform: list[dict]
    top_tagged_datasets: list[dict]
    daily_datasets_1d: list[dict]
    daily_datasets_7d: list[dict]
    daily_datasets_30d: list[dict]
    recent_datasets: list[DatasetSummary]


# ---------------------------------------------------------------------------
# Platform metadata schemas
# ---------------------------------------------------------------------------

class PlatformDataTypeResponse(BaseModel):
    id: int
    type_name: str
    type_category: str
    description: str | None = None
    ordinal: int

    model_config = {"from_attributes": True}


class PlatformTableTypeResponse(BaseModel):
    id: int
    type_name: str
    display_name: str
    description: str | None = None
    is_default: str
    ordinal: int

    model_config = {"from_attributes": True}


class PlatformStorageFormatResponse(BaseModel):
    id: int
    format_name: str
    display_name: str
    description: str | None = None
    is_default: str
    ordinal: int

    model_config = {"from_attributes": True}


class PlatformFeatureResponse(BaseModel):
    id: int
    feature_key: str
    display_name: str
    description: str | None = None
    value_type: str
    is_required: str
    ordinal: int

    model_config = {"from_attributes": True}


class PlatformMetadataResponse(BaseModel):
    platform: PlatformResponse
    data_types: list[PlatformDataTypeResponse] = Field(default_factory=list)
    table_types: list[PlatformTableTypeResponse] = Field(default_factory=list)
    storage_formats: list[PlatformStorageFormatResponse] = Field(default_factory=list)
    features: list[PlatformFeatureResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 데이터 파이프라인 스키마
# 이기종 시스템 간 데이터 흐름(ETL, CDC, 파일 내보내기 등)을 등록/관리하기 위한 스키마
# ---------------------------------------------------------------------------

class PipelineType(str, Enum):
    """파이프라인 유형."""
    ETL = "ETL"                  # Extract-Transform-Load
    FILE_EXPORT = "FILE_EXPORT"  # 파일 내보내기 (Parquet, CSV 등)
    CDC = "CDC"                  # Change Data Capture (실시간 변경 동기화)
    REPLICATION = "REPLICATION"  # 데이터 복제
    API = "API"                  # API 기반 데이터 전송
    MANUAL = "MANUAL"            # 수동 전달


class PipelineStatus(str, Enum):
    """파이프라인 상태."""
    ACTIVE = "ACTIVE"            # 운영 중
    INACTIVE = "INACTIVE"        # 비활성 (일시 중지)
    DEPRECATED = "DEPRECATED"    # 폐기 예정


class PipelineCreate(BaseModel):
    """파이프라인 생성 요청."""
    pipeline_name: str = Field(..., min_length=1, max_length=255)  # 파이프라인 고유 이름
    description: str | None = None                                  # 설명
    pipeline_type: PipelineType = PipelineType.ETL                  # 유형
    schedule: str | None = None                                     # 실행 주기 (cron 표현식)
    owner: str | None = None                                        # 담당자


class PipelineUpdate(BaseModel):
    """파이프라인 수정 요청. 변경할 필드만 포함."""
    pipeline_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    pipeline_type: PipelineType | None = None
    schedule: str | None = None
    owner: str | None = None
    status: PipelineStatus | None = None


class PipelineResponse(BaseModel):
    """파이프라인 응답."""
    id: int
    pipeline_name: str
    description: str | None = None
    pipeline_type: str
    schedule: str | None = None
    owner: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cross-Platform 리니지 스키마
# 이기종 시스템 간 데이터셋 관계 및 컬럼 매핑을 관리하기 위한 스키마.
# 예: PostgreSQL.employees → Impala.emp_fact
# ---------------------------------------------------------------------------

class LineageSource(str, Enum):
    """리니지 출처. 관계가 어떻게 등록되었는지를 나타냄."""
    QUERY_AGGREGATED = "QUERY_AGGREGATED"  # 쿼리 로그 분석으로 자동 수집 (같은 플랫폼 내)
    PIPELINE = "PIPELINE"                  # 파이프라인 등록을 통해 명시적 연결
    MANUAL = "MANUAL"                      # 사용자가 UI에서 직접 등록


class LineageRelationType(str, Enum):
    """리니지 관계 유형. 데이터가 어떤 방식으로 전달되는지를 나타냄."""
    READ_WRITE = "READ_WRITE"    # 읽기/쓰기 (같은 플랫폼 내 쿼리 기반)
    ETL = "ETL"                  # ETL 처리
    FILE_EXPORT = "FILE_EXPORT"  # 파일 내보내기를 통한 전달
    CDC = "CDC"                  # 실시간 변경 동기화
    REPLICATION = "REPLICATION"  # 데이터 복제
    DERIVED = "DERIVED"          # 파생 (집계, 변환 등)


class ColumnMappingCreate(BaseModel):
    """컬럼 매핑 생성 요청. 원본↔대상 컬럼 간 매핑 관계를 정의."""
    source_column: str = Field(..., min_length=1, max_length=256)  # 원본 컬럼명
    target_column: str = Field(..., min_length=1, max_length=256)  # 대상 컬럼명
    transform_type: str = "DIRECT"   # 변환 유형: DIRECT, CAST, EXPRESSION, DERIVED
    transform_expr: str | None = None  # 변환 수식 (예: "CAST(emp_id AS BIGINT)")


class ColumnMappingResponse(BaseModel):
    """컬럼 매핑 응답."""
    id: int
    source_column: str
    target_column: str
    transform_type: str
    transform_expr: str | None = None

    model_config = {"from_attributes": True}


class DatasetLineageCreate(BaseModel):
    """데이터셋 리니지 생성 요청.

    이기종 시스템 간 데이터셋 관계를 등록한다.
    column_mappings를 함께 제공하면 컬럼 수준 매핑도 동시에 생성.
    컬럼 매핑은 선택사항이며, 나중에 별도로 추가할 수도 있음.
    """
    source_dataset_id: int                                          # 원본 데이터셋 ID
    target_dataset_id: int                                          # 대상 데이터셋 ID
    relation_type: LineageRelationType = LineageRelationType.ETL     # 관계 유형
    lineage_source: LineageSource = LineageSource.MANUAL             # 출처 (수동/파이프라인)
    pipeline_id: int | None = None                                  # 파이프라인 참조 (PIPELINE 출처일 때)
    description: str | None = None                                  # 관계 설명
    created_by: str | None = None                                   # 등록자
    column_mappings: list[ColumnMappingCreate] = Field(default_factory=list)  # 컬럼 매핑 (선택)


class DatasetLineageResponse(BaseModel):
    """데이터셋 리니지 응답.

    원본/대상 데이터셋의 이름과 플랫폼 정보를 포함하여
    UI에서 이기종 시스템 간 관계를 시각적으로 표현할 수 있도록 한다.
    """
    id: int
    source_dataset_id: int                          # 원본 데이터셋 ID
    target_dataset_id: int                          # 대상 데이터셋 ID
    source_dataset_name: str | None = None          # 원본 데이터셋 이름 (JOIN 조회)
    target_dataset_name: str | None = None          # 대상 데이터셋 이름 (JOIN 조회)
    source_platform_type: str | None = None         # 원본 플랫폼 타입 (예: PostgreSQL)
    target_platform_type: str | None = None         # 대상 플랫폼 타입 (예: Impala)
    source_platform_name: str | None = None         # 원본 플랫폼 인스턴스 이름
    target_platform_name: str | None = None         # 대상 플랫폼 인스턴스 이름
    relation_type: str                              # 관계 유형 (ETL, FILE_EXPORT 등)
    lineage_source: str                             # 출처 (MANUAL, PIPELINE, QUERY_AGGREGATED)
    pipeline_id: int | None = None                  # 파이프라인 ID
    pipeline_name: str | None = None                # 파이프라인 이름 (JOIN 조회)
    description: str | None = None                  # 관계 설명
    created_by: str | None = None                   # 등록자
    query_count: int = 0                            # 이 관계를 확인한 쿼리 수
    last_seen_at: datetime | None = None            # 마지막 확인 시각
    created_at: datetime                            # 생성 시각
    column_mappings: list[ColumnMappingResponse] = Field(default_factory=list)  # 컬럼 매핑 목록
