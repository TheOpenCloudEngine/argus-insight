# Data Quality System — 데이터 품질 관리

## 개요

Argus Catalog의 데이터 품질 시스템은 **프로파일링(Profiling)**과 **규칙 기반 검증(Rule-based Check)**을 결합하여 데이터셋의 품질을 정량적으로 측정하고 추적합니다.

방법 A(원본 DB 직접 SQL) + 방법 B(프로파일 기반 폴백)의 하이브리드 방식으로 동작하여, 원본 DB에 접근 가능하면 정확한 통계를 수집하고, 접근 불가 시에도 카탈로그의 스키마 정보를 기반으로 기본 프로파일을 제공합니다.

## 아키텍처

```
원본 DB (MySQL, PostgreSQL, ...)
    │
    ▼ 방법 A: 직접 SQL
┌──────────────────────┐
│  Data Profiling      │
│  COUNT(*), NULL,     │
│  DISTINCT, MIN/MAX,  │
│  AVG per column      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│  Profile Storage     │────▶│  Rule Evaluation     │
│  catalog_data_profile│     │  방법 B: 프로파일 기반  │
└──────────────────────┘     └──────────┬───────────┘
                                        │
                             ┌──────────▼───────────┐
                             │  Quality Score       │
                             │  = PASS / TOTAL × 100│
                             └──────────────────────┘
```

## 프로파일링 (Data Profiling)

### 수집 항목

| 항목 | 숫자형 | 문자형 | 날짜형 | SQL |
|------|--------|--------|--------|-----|
| 총 건수 | O | O | O | `SELECT COUNT(*)` |
| NULL 건수/비율 | O | O | O | `SELECT COUNT(*) WHERE col IS NULL` |
| 유니크 값 수/비율 | O | O | O | `SELECT COUNT(DISTINCT col)` |
| 최솟값 | O | O (길이) | O | `SELECT MIN(col)` |
| 최댓값 | O | O (길이) | O | `SELECT MAX(col)` |
| 평균 | O | - | - | `SELECT AVG(col)` |

### 프로파일링 방식

**방법 A — 원본 DB 직접 SQL (우선)**

플랫폼 설정(host, port, username, password)을 사용하여 원본 DB에 async 연결 후 컬럼별 통계 SQL을 실행합니다.

지원 플랫폼:
- MySQL / MariaDB (`mysql+aiomysql`)
- PostgreSQL (`postgresql+asyncpg`)

**방법 B — 스키마 폴백**

원본 DB 접속 실패 시 카탈로그에 저장된 스키마 정보(컬럼명, 타입)만으로 기본 프로파일을 생성합니다. 통계값(NULL 수, 유니크 수 등)은 0으로 표시됩니다.

### API

```
POST /api/v1/quality/datasets/{dataset_id}/profile
  → 프로파일링 실행 (원본 DB 접속 → SQL 실행 → 결과 저장)

GET /api/v1/quality/datasets/{dataset_id}/profile
  → 최신 프로파일 조회
```

### 프로파일 결과 예시

```json
{
  "id": 1,
  "dataset_id": 127,
  "row_count": 1000,
  "columns": [
    {
      "column_name": "film_id",
      "column_type": "NUMBER",
      "total_count": 1000,
      "null_count": 0,
      "null_percent": 0.0,
      "unique_count": 1000,
      "unique_percent": 100.0,
      "min_value": "1",
      "max_value": "1000",
      "mean_value": 500.5
    },
    {
      "column_name": "title",
      "column_type": "STRING",
      "total_count": 1000,
      "null_count": 0,
      "null_percent": 0.0,
      "unique_count": 1000,
      "unique_percent": 100.0,
      "min_value": "ACADEMY DINOSAUR",
      "max_value": "ZORRO ARK"
    }
  ],
  "profiled_at": "2026-03-24T10:30:00Z"
}
```

## 품질 규칙 (Quality Rule)

### 지원하는 규칙 유형

| check_type | 설명 | column 필요 | expected_value | threshold |
|-----------|------|------------|----------------|-----------|
| `NOT_NULL` | NULL 비율이 threshold 이하 | Yes | - | 100 (= NULL 0%) |
| `UNIQUE` | 유니크 비율이 threshold 이상 | Yes | - | 100 (= 전부 유니크) |
| `MIN_VALUE` | 최솟값이 expected 이상 | Yes | "0" | - |
| `MAX_VALUE` | 최댓값이 expected 이하 | Yes | "100000" | - |
| `ROW_COUNT` | 총 건수가 expected 이상 | No | "1000" | - |
| `FRESHNESS` | 마지막 프로파일 후 N시간 이내 | No | "24" (시간) | - |
| `ACCEPTED_VALUES` | 허용 값 목록에 포함 (원본 DB 필요) | Yes | `["A","B","C"]` | 95 |
| `REGEX` | 정규식 패턴 일치 (원본 DB 필요) | Yes | `"^[0-9]+$"` | 95 |

### 규칙 등록 예시

```json
POST /api/v1/quality/rules
{
  "dataset_id": 127,
  "rule_name": "film_id is not null",
  "check_type": "NOT_NULL",
  "column_name": "film_id",
  "threshold": 100,
  "severity": "BREAKING"
}
```

```json
{
  "dataset_id": 127,
  "rule_name": "rental_rate >= 0",
  "check_type": "MIN_VALUE",
  "column_name": "rental_rate",
  "expected_value": "0",
  "severity": "WARNING"
}
```

```json
{
  "dataset_id": 127,
  "rule_name": "row count >= 500",
  "check_type": "ROW_COUNT",
  "expected_value": "500",
  "severity": "WARNING"
}
```

### API

```
POST   /api/v1/quality/rules              규칙 생성
GET    /api/v1/quality/rules?dataset_id=   규칙 목록
PUT    /api/v1/quality/rules/{id}          규칙 수정
DELETE /api/v1/quality/rules/{id}          규칙 삭제
```

## 품질 검사 실행 (Run Check)

### 동작 흐름

```
[Run Check] 클릭
    │
    ▼
최신 프로파일이 있는가?
    ├── 없으면 → 자동 프로파일 실행
    └── 있으면 → 프로파일 데이터 사용
    │
    ▼
활성 규칙 전체 조회 (is_active = true)
    │
    ▼
각 규칙을 프로파일 데이터와 대조하여 평가
    │
    ├── NOT_NULL: null_percent <= (100 - threshold)?
    ├── UNIQUE: unique_percent >= threshold?
    ├── MIN_VALUE: min_value >= expected?
    ├── MAX_VALUE: max_value <= expected?
    ├── ROW_COUNT: row_count >= expected?
    └── FRESHNESS: profiled_at + expected hours >= now?
    │
    ▼
각 규칙별 PASS/FAIL 결과 저장 (catalog_quality_result)
    │
    ▼
품질 점수 계산 및 저장 (catalog_quality_score)
    score = PASS 규칙 수 / 전체 규칙 수 × 100%
```

### API

```
POST /api/v1/quality/datasets/{dataset_id}/check
  → 모든 활성 규칙 평가 + 점수 산출

GET /api/v1/quality/datasets/{dataset_id}/results
  → 최신 검사 결과 (규칙별 PASS/FAIL)

GET /api/v1/quality/datasets/{dataset_id}/score
  → 최신 품질 점수

GET /api/v1/quality/datasets/{dataset_id}/score/history?limit=30
  → 점수 이력 (트렌드용)
```

### 검사 결과 예시

```json
{
  "dataset_id": 127,
  "score": 80.0,
  "total_rules": 5,
  "passed": 4,
  "failed": 1,
  "results": [
    {
      "rule_name": "film_id not null",
      "check_type": "NOT_NULL",
      "column_name": "film_id",
      "passed": "true",
      "actual_value": "100.0%",
      "detail": "Non-null: 100.0% (threshold: 100%)",
      "severity": "BREAKING"
    },
    {
      "rule_name": "freshness <= 24h",
      "check_type": "FRESHNESS",
      "passed": "false",
      "actual_value": "36.2h",
      "detail": "Data age: 36.2h (max: 24h)",
      "severity": "WARNING"
    }
  ]
}
```

## 심각도 (Severity)

| Severity | 의미 | 사용 예시 |
|----------|------|----------|
| `BREAKING` | 즉시 대응 필요 | PK 컬럼 NULL, 건수 0 |
| `WARNING` | 확인 필요 | NULL 비율 증가, 값 범위 초과 |
| `INFO` | 참고용 | 유니크 비율 변동 |

## UI

### Dataset Detail > Quality 탭

```
┌────────────────────────────────────────────────────────┐
│ Quality Score: 80%  [Profile] [Run Check] [+ Add Rule] │
│ ████████████████████████░░░░░░                          │
│ ✅ 4  ❌ 1  / 5 rules                                  │
├────────────────────────────────────────────────────────┤
│ Results                                                │
│ ✅ film_id NOT_NULL     100%     threshold 100%        │
│ ✅ rental_rate MIN_VAL  0.99     expected >= 0         │
│ ✅ row count >= 500     1000     expected >= 500       │
│ ✅ film_id UNIQUE       100%     threshold 100%        │
│ ❌ freshness <= 24h     36.2h    max 24h               │
├────────────────────────────────────────────────────────┤
│ Data Profile                                           │
│ Column      Type    NULLs  Unique  Min     Max    Mean │
│ film_id     NUMBER  0%     100%    1       1000   500  │
│ title       STRING  0%     100%    -       -      -    │
│ rental_rate NUMBER  0%     68%     0.99    4.99   2.98 │
└────────────────────────────────────────────────────────┘
```

## 데이터 모델

```sql
-- 프로파일 결과
catalog_data_profile (id, dataset_id, row_count, profile_json, profiled_at)

-- 품질 규칙
catalog_quality_rule (id, dataset_id, rule_name, check_type, column_name,
                      expected_value, threshold, severity, is_active)

-- 검사 결과
catalog_quality_result (id, rule_id, dataset_id, passed, actual_value,
                        detail, checked_at)

-- 품질 점수 이력
catalog_quality_score (id, dataset_id, score, total_rules, passed_rules,
                       warning_rules, failed_rules, scored_at)
```

## 사용 시나리오

### 시나리오 1: 데이터 분석가가 데이터 신뢰성 확인

1. 데이터셋 상세 > Quality 탭 진입
2. **[Profile]** 클릭 → 컬럼별 NULL 비율, 유니크 비율, 값 범위 확인
3. NULL 비율이 높은 컬럼 발견 → 원천 시스템 담당자에게 확인 요청

### 시나리오 2: DBA가 품질 규칙 설정

1. 핵심 테이블(orders, payments)에 규칙 등록
   - PK 컬럼 NOT_NULL + UNIQUE (BREAKING)
   - 금액 컬럼 MIN_VALUE >= 0 (WARNING)
   - 건수 ROW_COUNT >= 1000 (WARNING)
2. 주기적으로 **[Run Check]** 실행
3. 점수 이력으로 품질 추이 모니터링

### 시나리오 3: 거버넌스 담당자가 전사 품질 현황 파악

1. 각 데이터셋의 Quality Score 확인
2. Score가 낮은 데이터셋 → 규칙 추가 또는 데이터 정제 요청
3. Alert Rule과 연동하여 품질 하락 시 자동 알림 (향후)
