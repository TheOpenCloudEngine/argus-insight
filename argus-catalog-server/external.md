# External Metadata API

외부 시스템이 Argus Catalog의 데이터셋 메타데이터와 Avro 스키마를 조회할 수 있는 API입니다.
Thread-safe LRU+TTL 캐시를 내장하여 반복 요청에 대해 < 1ms 응답 성능을 제공합니다.

---

## API 엔드포인트

### URN 기반 조회 (외부 시스템 권장)

외부 시스템은 내부 dataset_id를 모르므로, URN으로 조회합니다.

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/external/metadata?urn={urn}` | 메타데이터 JSON 조회 |
| `GET` | `/api/v1/external/avro-schema?urn={urn}` | Avro 스키마 조회 |

**URN 형식**: `{platform_id}.{path}.{ENV}.{type}`

```
mysql-19d0bfe954e2cfdaa.sakila.actor.PROD.dataset
├── platform_id:  mysql-19d0bfe954e2cfdaa
├── path:         sakila.actor
├── ENV:          PROD
└── type:         dataset
```

**호출 예시:**

```bash
# 메타데이터
curl "http://localhost:4600/api/v1/external/metadata?urn=mysql-19d0bfe954e2cfdaa.sakila.actor.PROD.dataset"

# Avro 스키마
curl "http://localhost:4600/api/v1/external/avro-schema?urn=mysql-19d0bfe954e2cfdaa.sakila.actor.PROD.dataset"

# 캐시 무시 (DB 강제 조회)
curl "http://localhost:4600/api/v1/external/metadata?urn=...&no_cache=true"
```

### ID 기반 조회 (내부 시스템, 하위 호환)

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/external/datasets/{id}/metadata` | 메타데이터 JSON 조회 |
| `GET` | `/api/v1/external/datasets/{id}/avro-schema` | Avro 스키마 조회 |

### 캐시 관리

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/external/cache/stats` | 캐시 통계 (size, hit_rate) |
| `GET` | `/api/v1/external/cache/config` | 캐시 설정 조회 |
| `PUT` | `/api/v1/external/cache/config` | 캐시 설정 변경 |
| `DELETE` | `/api/v1/external/datasets/{id}/cache` | 특정 데이터셋 캐시 무효화 |
| `DELETE` | `/api/v1/external/cache` | 전체 캐시 초기화 |

---

## 응답 형식

### 메타데이터 JSON

```json
{
  "dataset_id": 123,
  "urn": "mysql-19d0bfe954e2cfdaa.sakila.actor.PROD.dataset",
  "name": "sakila.actor",
  "description": "Actor 마스터 테이블",
  "origin": "PROD",
  "status": "active",
  "qualified_name": "mysql-19d0bfe954e2cfdaa.sakila.actor",
  "table_type": "TABLE",
  "storage_format": null,
  "is_synced": "true",
  "platform": {
    "id": 2,
    "platform_id": "mysql-19d0bfe954e2cfdaa",
    "name": "Sakila MySQL",
    "type": "mysql"
  },
  "schema": [
    {
      "field_path": "actor_id",
      "field_type": "NUMBER",
      "native_type": "smallint(5) unsigned",
      "description": "배우 고유 식별자",
      "nullable": "false",
      "is_primary_key": "true",
      "is_unique": "true",
      "is_indexed": "true",
      "ordinal": 1,
      "pii_type": null
    }
  ],
  "tags": ["영화", "마스터"],
  "owners": [
    {"name": "data-team", "type": "TECHNICAL_OWNER"}
  ],
  "properties": {
    "table": {"engine": "InnoDB", "estimated_rows": 200},
    "ddl": "CREATE TABLE `actor` (...)"
  },
  "_cache": {
    "cached": true,
    "hit": true,
    "ttl_seconds": 300
  }
}
```

### Avro 스키마

```json
{
  "type": "record",
  "name": "actor",
  "namespace": "mysql-19d0bfe954e2cfdaa.sakila",
  "doc": "Actor 마스터 테이블",
  "fields": [
    {
      "name": "actor_id",
      "type": "int",
      "doc": "배우 고유 식별자",
      "metadata": {"native_type": "smallint(5) unsigned", "primary_key": true}
    },
    {
      "name": "first_name",
      "type": "string",
      "doc": "배우 이름",
      "metadata": {"native_type": "varchar(200)"}
    },
    {
      "name": "rating",
      "type": ["null", {"type": "bytes", "logicalType": "decimal", "precision": 5, "scale": 2}],
      "doc": "배우 평점",
      "metadata": {"native_type": "decimal(5,2)"}
    },
    {
      "name": "last_update",
      "type": {"type": "long", "logicalType": "timestamp-millis"},
      "doc": "마지막 수정 시각",
      "metadata": {"native_type": "timestamp"}
    }
  ],
  "metadata": {
    "dataset_id": 123,
    "source_name": "sakila.actor",
    "platform_type": "mysql",
    "platform_name": "Sakila MySQL",
    "generated_by": "argus-catalog-server"
  },
  "_cache": {"cached": false, "hit": false, "ttl_seconds": 300}
}
```

### Avro 타입 매핑

| Catalog Type | Native Type | Avro Type |
|-------------|-------------|-----------|
| NUMBER | tinyint, smallint, mediumint, int | `int` |
| NUMBER | bigint | `long` |
| NUMBER | float, real | `float` |
| NUMBER | double | `double` |
| NUMBER | decimal(p,s) | `{"type":"bytes","logicalType":"decimal","precision":p,"scale":s}` |
| STRING | varchar, char, text | `string` |
| DATE | date | `{"type":"int","logicalType":"date"}` |
| DATE | timestamp | `{"type":"long","logicalType":"timestamp-millis"}` |
| DATE | time | `{"type":"long","logicalType":"time-millis"}` |
| BOOLEAN | boolean, bool | `boolean` |
| BYTES | bytea, blob, binary | `bytes` |
| MAP | json, jsonb | `{"type":"map","values":"string"}` |
| ARRAY | array | `{"type":"array","items":"string"}` |
| — | uuid | `{"type":"string","logicalType":"uuid"}` |

- **Nullable 필드**: Avro union으로 변환 → `["null", type]`
- **Decimal 정밀도**: native_type에서 추출 (예: `decimal(10,2)` → precision=10, scale=2)
- **PII 필드**: `metadata.pii_type`에 PII 분류 포함

---

## 캐시 아키텍처

### 3단계 캐시 전략

```
외부 요청: urn=mysql-xxx.sakila.actor.PROD.dataset
              │
              ▼
  ① URN→ID 매핑 캐시 확인
     key: "urn_map:{urn}"
     HIT → dataset_id=123 (< 0.01ms)
     MISS → DB: SELECT id FROM datasets WHERE urn=? (unique index, ~1ms)
             → 매핑 캐시에 저장
              │
              ▼
  ② 데이터 캐시 확인
     key: "metadata:{urn}" 또는 "avro:{urn}"
     HIT → 즉시 JSON 반환 (< 1ms) ✅
     MISS → 다음 단계로
              │
              ▼
  ③ DB에서 JSON 빌드 (~20ms)
     Dataset + Platform + Schema + Tags + Owners
     → 데이터 캐시에 저장 → 응답
```

### 성능

| 시나리오 | 응답 시간 | 설명 |
|----------|----------|------|
| Cache HIT | **< 1ms** | OrderedDict 조회만 |
| Cache MISS (1차 요청) | **~20ms** | URN 인덱스 조회 + JOIN 5개 테이블 |
| URN 동일, 다른 타입 | **~15ms** | 매핑 캐시 HIT + 데이터 빌드만 |

### 캐시 구현 상세

```
MetadataCache (app/external/cache.py)
├── 자료구조: OrderedDict[str, CacheEntry]    ← LRU 순서 유지
├── 동시성: asyncio.Lock                       ← async-safe
├── 만료: time.monotonic() 기반 TTL            ← 벽시계 영향 없음
├── 키 형식: "urn_map:{urn}", "metadata:{urn}", "avro:{urn}"
├── LRU 제거: max_size 초과 시 가장 오래된 항목 제거
└── 통계: hits, misses, hit_rate 실시간 추적
```

### 캐시 무효화

| 이벤트 | 무효화 대상 |
|--------|-----------|
| `PUT /datasets/{id}` | `metadata:{urn}`, `avro:{urn}` |
| `POST /datasets/{id}/schema` | `metadata:{urn}`, `avro:{urn}` |
| `POST /datasets/{id}/tags` | `metadata:{urn}` |
| `DELETE /datasets/{id}` | `metadata:{urn}`, `avro:{urn}`, `urn_map:{urn}` |
| `POST /platforms/{id}/sync` | 동기화된 모든 dataset의 캐시 |

---

## 설정

### config.yml

```yaml
external:
  cache:
    max_size: 1000        # 최대 캐시 항목 수 (LRU 제거)
    ttl_seconds: 300      # 항목 만료 시간 (5분)
    enabled: true         # 캐시 활성화 여부
```

### 런타임 변경 (Settings API)

```bash
# 설정 조회
curl http://localhost:4600/api/v1/external/cache/config

# 설정 변경 (재시작 불필요)
curl -X PUT http://localhost:4600/api/v1/external/cache/config \
  -H "Content-Type: application/json" \
  -d '{"max_size": 2000, "ttl_seconds": 600, "enabled": true}'

# 통계 확인
curl http://localhost:4600/api/v1/external/cache/stats
# → {"size": 42, "max_size": 2000, "hits": 1234, "misses": 180, "hit_rate": 87.3}
```

### UI 설정

Settings > **Cache** 탭에서 설정 가능:
- Enable/Disable 토글
- Max Size 입력
- TTL 입력
- Save 버튼
- Clear Cache 버튼
- Statistics 카드 (size, hit_rate, hits, misses)
