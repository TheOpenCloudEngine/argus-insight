# Greenplum Metadata Sync

Greenplum DB 메타데이터를 수집하여 Argus Catalog Server에 동기화하는 플랫폼 모듈.

## 개요

PostgreSQL 프로토콜(psycopg2/SQLAlchemy)로 Greenplum 시스템 카탈로그에 접속하여 database, schema, table, column 메타데이터를 수집한다. Greenplum 고유의 **분산키(distribution key)**, **파티션키(partition key)**, **스토리지 포맷(HEAP/AORO/AOCO)**을 포함한다.

GP7(`pg_partitioned_table`)과 GP6(`pg_partition`) 모두 지원하며, 자동으로 감지하여 적절한 쿼리를 사용한다.

## 파일 구조

```
src/sync/platforms/greenplum/
├── __init__.py
└── sync.py          # GreenplumMetadataSync(BasePlatformSync)
```

## 설정 (config.yml)

```yaml
platforms:
  greenplum:
    enabled: false
    host: "localhost"
    port: 5432
    database: ""                                         # 특정 DB만 수집 시 지정 (빈값 = 전체)
    username: "gpadmin"
    password: ""
    databases: []                                        # 화이트리스트 (빈값 = 전체)
    exclude_databases: ["template0", "template1", "postgres"]
    schemas: []                                          # 스키마 화이트리스트 (빈값 = 전체)
    exclude_schemas: ["pg_catalog", "information_schema", "gp_toolkit", "pg_toast"]
    origin: "PROD"
    schedule:
      interval_minutes: 60
      enabled: true
```

## Multi-database 접속

Greenplum은 cross-database 쿼리를 지원하지 않으므로, 각 database마다 별도 SQLAlchemy engine을 생성하여 접속한다.

1. 초기 접속: `postgres` DB (또는 설정된 database)로 연결
2. `pg_database`에서 전체 database 목록 조회
3. `databases`/`exclude_databases` 필터 적용
4. 각 database에 개별 접속 → schema → table 순회

## GP 버전 감지

`connect()` 시 자동 감지:
- `gp_distribution_policy` 존재 여부 → Greenplum 인스턴스 확인 (vanilla PostgreSQL 거부)
- `pg_partitioned_table` 존재 여부 → GP7 파티션 지원 여부 캐시

## 수집 항목

### 테이블 메타데이터

| GP 속성 | Catalog 필드 | 비고 |
|---|---|---|
| `relname` | `name` | 테이블명 |
| `database.schema.table` | `qualified_name` | 전체 경로 |
| `obj_description()` | `description` | 테이블 코멘트 |
| `pg_roles.rolname` | `owners[].owner_name` | TECHNICAL_OWNER 타입 |
| `relkind` mapped | `table_type` | 아래 매핑표 참조 |
| `reloptions` detected | `storage_format` | HEAP / AORO / AOCO |

### relkind → table_type 매핑

| relkind | table_type |
|---|---|
| `'r'` | `TABLE` |
| `'p'` | `PARTITIONED_TABLE` |
| `'v'` | `VIEW` |
| `'m'` | `MATERIALIZED_VIEW` |
| `'f'` | `FOREIGN_TABLE` |

### 스토리지 포맷 감지

`pg_class.reloptions` 배열에서 판별:

| 조건 | storage_format | 설명 |
|---|---|---|
| `appendoptimized=true` + `orientation=column` | `AOCO` | Append-Optimized Column-Oriented |
| `appendoptimized=true` | `AORO` | Append-Optimized Row-Oriented |
| 기타 | `HEAP` | 기본 Heap 스토리지 |
| view / materialized view | (없음) | |

### 컬럼 스키마 (schema_fields)

| GP 속성 | Catalog 필드 | 비고 |
|---|---|---|
| `attname` | `field_path` | |
| `format_type()` normalized | `field_type` | 타입 매핑 적용 |
| `format_type()` raw | `native_type` | `numeric(10,2)` 등 그대로 |
| `col_description()` | `description` | |
| `NOT attnotnull` | `nullable` | |
| `attnum - 1` | `ordinal` | 0-based |
| `pg_constraint` | `is_primary_key` | PK 여부 |
| `gp_distribution_policy` | `is_distribution_key` | 분산키 여부 (GP 전용) |
| `pg_partitioned_table` | `is_partition_key` | 파티션키 여부 |

### 컬럼 타입 매핑

**기본 타입:**

| GP typname | Catalog Type |
|---|---|
| `int2` | `SMALLINT` |
| `int4` | `INT` |
| `int8` | `BIGINT` |
| `float4` | `FLOAT` |
| `float8` | `DOUBLE` |
| `numeric` | `DECIMAL` |
| `bool` | `BOOLEAN` |
| `varchar` | `VARCHAR` |
| `bpchar` | `CHAR` |
| `text` | `TEXT` |
| `timestamp` / `timestamptz` | `TIMESTAMP` |
| `date` | `DATE` |
| `time` / `timetz` | `TIME` |
| `bytea` | `BINARY` |
| `json` / `jsonb` | `JSON` |
| `uuid` | `UUID` |
| `xml` | `XML` |
| `inet` / `cidr` / `macaddr` | `STRING` |
| `money` | `DECIMAL` |
| `interval` | `STRING` |
| `tsvector` / `tsquery` | `STRING` |

**배열 타입** (pg_type.typname이 `_` prefix):

| GP typname | Catalog Type |
|---|---|
| `_int4` | `ARRAY<INT>` |
| `_int8` | `ARRAY<BIGINT>` |
| `_text` | `ARRAY<TEXT>` |
| `_varchar` | `ARRAY<VARCHAR>` |
| `_float8` | `ARRAY<DOUBLE>` |
| `_json` / `_jsonb` | `ARRAY<JSON>` |
| `_timestamp` | `ARRAY<TIMESTAMP>` |
| ... | `ARRAY<기본타입>` |

**범위 타입:**

| GP typname | Catalog Type |
|---|---|
| `int4range` | `RANGE<INT>` |
| `int8range` | `RANGE<BIGINT>` |
| `numrange` | `RANGE<DECIMAL>` |
| `tsrange` / `tstzrange` | `RANGE<TIMESTAMP>` |
| `daterange` | `RANGE<DATE>` |

**Multirange 타입 (PG14+):**

| GP typname | Catalog Type |
|---|---|
| `int4multirange` | `MULTIRANGE<INT>` |
| `datemultirange` | `MULTIRANGE<DATE>` |
| ... | `MULTIRANGE<기본타입>` |

### Properties (greenplum. prefix)

| Property Key | 설명 | 예시 |
|---|---|---|
| `greenplum.database` | 소스 데이터베이스명 | `analytics` |
| `greenplum.distribution_policy` | 분산 정책 (DDL 형태) | `DISTRIBUTED BY (id, region)` |
| `greenplum.distribution_columns` | 분산키 컬럼 목록 | `id,region` |
| `greenplum.numsegments` | 세그먼트 수 | `16` |
| `greenplum.partition_strategy` | 파티션 전략 | `RANGE` / `LIST` / `HASH` |
| `greenplum.partition_columns` | 파티션키 컬럼 목록 | `created_date` |
| `greenplum.storage_type` | 스토리지 타입 | `HEAP` / `AORO` / `AOCO` |
| `greenplum.tablespace` | 테이블스페이스 | `pg_default` |
| `greenplum.table_size` | 테이블 크기 (bytes) | `1073741824` |
| `greenplum.estimated_rows` | 추정 행 수 | `1000000` |

## 분산키 (Distribution Key) 수집

`gp_distribution_policy` 시스템 카탈로그에서 조회:

| policytype | 의미 | distribution_policy 값 |
|---|---|---|
| `'p'` | Hash 분산 | `DISTRIBUTED BY (col1, col2)` |
| `'r'` | 복제 | `DISTRIBUTED REPLICATED` |
| `''` / null | 랜덤 분산 | `DISTRIBUTED RANDOMLY` |

분산키 컬럼은 `distkey` (int2vector) → `pg_attribute` JOIN으로 컬럼명 추출.

## 파티션키 (Partition Key) 수집

### GP7 (pg_partitioned_table)

| partstrat | 의미 |
|---|---|
| `'r'` | RANGE 파티션 |
| `'l'` | LIST 파티션 |
| `'h'` | HASH 파티션 |

`partattrs` (int2vector) → `pg_attribute` JOIN으로 파티션 컬럼명 추출.

### GP6 (pg_partition - fallback)

| parkind | 의미 |
|---|---|
| `'r'` | RANGE 파티션 |
| `'l'` | LIST 파티션 |

GP7에서 `pg_partitioned_table` 조회 실패 시 자동으로 `pg_partition` fallback.

## API 엔드포인트

기본 엔드포인트 (SyncScheduler 자동 지원):

| Method | Path | 설명 |
|---|---|---|
| GET | `/sync/greenplum/status` | 동기화 상태 조회 |
| POST | `/sync/greenplum/run` | 즉시 동기화 실행 |
| GET | `/sync/greenplum/discover` | 테이블 목록 미리보기 |
| GET | `/sync/greenplum/schedule` | 동기화 주기 조회 |
| PUT | `/sync/greenplum/schedule` | 동기화 주기 변경 |

Greenplum 전용 엔드포인트:

| Method | Path | 설명 |
|---|---|---|
| PUT | `/sync/greenplum/connection` | 연결 설정 변경 |
| POST | `/sync/greenplum/test` | 연결 테스트 |

## 실행 방법

```bash
# API 서버 모드 (스케줄러 포함)
metadata-sync --mode server

# 배치 모드 (1회 실행 후 종료)
metadata-sync --mode batch --platform greenplum
```

## 의존성

추가 의존성 없음. 이미 포함된 패키지 사용:
- `psycopg2-binary >= 2.9` (PostgreSQL 드라이버)
- `sqlalchemy >= 2.0` (ORM/SQL 실행)

## 동기화 흐름

```
connect()
  ├─ postgres DB 접속
  ├─ gp_distribution_policy 존재 확인 → Greenplum 검증
  └─ pg_partitioned_table 존재 확인 → GP7 여부 캐시

sync()
  └─ for each database:
       ├─ create_engine(database) → 별도 접속
       └─ for each schema:
            └─ for each table:
                 ├─ _get_columns() → schema_fields
                 ├─ _get_primary_keys() → PK 컬럼 set
                 ├─ _get_distribution_info() → 분산키/정책/세그먼트 수
                 ├─ _get_partition_info() → 파티션키/전략 (GP7→GP6 fallback)
                 ├─ _detect_storage_type() → HEAP/AORO/AOCO
                 ├─ properties 빌드 (greenplum. prefix)
                 └─ get_dataset_by_urn()
                      ├─ 존재 → update_dataset + update_schema_fields
                      └─ 없음 → create_dataset (owners, properties 포함)

disconnect()
  └─ 모든 engine.dispose()
```
