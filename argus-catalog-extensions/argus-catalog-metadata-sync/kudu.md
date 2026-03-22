# Kudu Metadata Sync

Apache Kudu 메타데이터를 수집하여 Argus Catalog Server에 동기화하는 플랫폼 모듈.

## 개요

kudu-python 클라이언트를 통해 Kudu master에 접속하여 테이블, 컬럼, 통계 등 메타데이터를 수집한다.
Kudu는 네이티브 database 개념이 없으므로, Impala 연동 시 사용하는 `impala::database.table_name` 네이밍 컨벤션을 파싱하여 database/table을 분리한다.

## 파일 구조

```
src/sync/platforms/kudu/
├── __init__.py
└── sync.py          # KuduMetadataSync(BasePlatformSync)
```

## 설정 (config.yml)

```yaml
platforms:
  kudu:
    enabled: false
    master_addresses: "localhost:7051"           # 쉼표 구분, 멀티 마스터 지원
    table_filter: ""                             # list_tables match_substring 필터
    default_database: "default"                  # impala:: prefix 없는 테이블의 기본 DB명
    parse_impala_naming: true                    # impala::db.table 파싱 여부
    origin: "PROD"                               # 환경 구분 (PROD, DEV 등)
    schedule:
      interval_minutes: 60                       # 동기화 주기 (분)
      enabled: true
```

## 테이블 이름 파싱

| Raw Table Name | database | table_name |
|---|---|---|
| `impala::mydb.my_table` | `mydb` | `my_table` |
| `impala::my_table` | `default` | `my_table` |
| `my_table` | `default` | `my_table` |

`parse_impala_naming: false`로 설정하면 모든 테이블이 `default_database`에 매핑된다.

## 수집 항목

### 테이블 메타데이터

| Kudu 속성 | Catalog 필드 | 비고 |
|---|---|---|
| parsed table name | `name` | 파싱된 테이블명 |
| `db.table` | `qualified_name` | `impala::` 파싱 결과 |
| `table.comment` | `description` | |
| `table.owner` | `owners[].owner_name` | TECHNICAL_OWNER 타입 |
| 항상 `"TABLE"` | `table_type` | Kudu에 view/external 없음 |
| 항상 `"KUDU"` | `storage_format` | Kudu 자체 스토리지 엔진 |

### 컬럼 스키마 (schema_fields)

| Kudu 속성 | Catalog 필드 | 비고 |
|---|---|---|
| `col.name` | `field_path` | |
| mapped type | `field_type` | 정규화된 타입 (아래 매핑표 참조) |
| `col.type` | `native_type` | DECIMAL(p,s), VARCHAR(l) 포함 |
| `col.comment` | `description` | |
| `col.nullable` | `nullable` | |
| column index | `ordinal` | |
| PK 포함 여부 | `is_primary_key` | `schema.primary_keys()`로 판별 |

### Properties (kudu. prefix)

| Property Key | 설명 |
|---|---|
| `kudu.table_id` | Kudu 내부 테이블 UUID |
| `kudu.num_replicas` | Tablet 복제 수 |
| `kudu.raw_table_name` | 파싱 전 원본 테이블명 |
| `kudu.on_disk_size` | 디스크 사용량 (bytes, 지원 시) |
| `kudu.live_row_count` | 행 수 (지원 시) |
| `kudu.primary_keys` | PK 컬럼 목록 (쉼표 구분) |
| `kudu.encoding.<col>` | 컬럼별 인코딩 방식 |
| `kudu.compression.<col>` | 컬럼별 압축 방식 |

## 컬럼 타입 매핑

| Kudu Type | Catalog Type |
|---|---|
| `int8` | `TINYINT` |
| `int16` | `SMALLINT` |
| `int32` | `INT` |
| `int64` | `BIGINT` |
| `float` | `FLOAT` |
| `double` | `DOUBLE` |
| `decimal` | `DECIMAL` |
| `string` | `STRING` |
| `binary` | `BINARY` |
| `bool` | `BOOLEAN` |
| `unixtime_micros` | `TIMESTAMP` |
| `varchar` | `VARCHAR` |
| `date` | `DATE` |

## API 엔드포인트

기본 엔드포인트 (SyncScheduler 자동 지원):

| Method | Path | 설명 |
|---|---|---|
| GET | `/sync/kudu/status` | 동기화 상태 조회 |
| POST | `/sync/kudu/run` | 즉시 동기화 실행 |
| GET | `/sync/kudu/discover` | 테이블 목록 미리보기 |
| GET | `/sync/kudu/schedule` | 동기화 주기 조회 |
| PUT | `/sync/kudu/schedule` | 동기화 주기 변경 |

Kudu 전용 엔드포인트:

| Method | Path | 설명 |
|---|---|---|
| PUT | `/sync/kudu/connection` | 연결 설정 변경 |
| POST | `/sync/kudu/test` | 연결 테스트 |

## 실행 방법

```bash
# API 서버 모드 (스케줄러 포함)
metadata-sync --mode server

# 배치 모드 (1회 실행 후 종료)
metadata-sync --mode batch --platform kudu
```

## 의존성

```toml
[project.optional-dependencies]
kudu = ["kudu-python>=1.17.0"]
```

kudu-python은 Kudu C++ 클라이언트 라이브러리가 시스템에 설치되어 있어야 한다.
설치되지 않은 환경에서는 `connect()` 시 명확한 에러 메시지를 출력한다.

```bash
pip install "argus-catalog-metadata-sync[kudu]"
```

## 동기화 흐름

```
connect()
  └─ kudu.connect(host, port)
  └─ list_tables() 로 연결 검증

sync()
  └─ get_platform_by_name("kudu") → platform_id
  └─ list_tables(match_substring=table_filter)
  └─ for each table:
       └─ _sync_table()
            ├─ _parse_table_name() → (database, table_name)
            ├─ client.table(raw_name) → Table 객체
            ├─ get_table_statistics() → on_disk_size, live_row_count
            ├─ schema 순회 → schema_fields 빌드
            ├─ properties 빌드 (kudu. prefix)
            ├─ _generate_urn() → URN 생성
            └─ get_dataset_by_urn()
                 ├─ 존재 → update_dataset + update_schema_fields
                 └─ 없음 → create_dataset (owners, properties 포함)

disconnect()
  └─ kudu_client = None
```
