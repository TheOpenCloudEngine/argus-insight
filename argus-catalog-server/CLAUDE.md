# Catalog Server

Argus 플랫폼의 **데이터 카탈로그 관리 서버**입니다. DataHub 스타일의 데이터 카탈로그 기능과 Unity Catalog OSS 호환 ML 모델 레지스트리를 제공합니다.

## 핵심 기능

- **데이터셋 관리** (`catalog`): 데이터셋 등록/조회/검색/수정/삭제
- **플랫폼 관리**: 데이터 플랫폼 등록 (Hive, MySQL, Kafka, S3 등 11개 플랫폼)
- **메타데이터 동기화** (`sync`): MySQL/MariaDB, PostgreSQL에서 테이블/컬럼 메타데이터 자동 수집
- **Cross-Platform 리니지** (`catalog`): 이기종 시스템 간 데이터 흐름 추적, 컬럼 수준 매핑, 파이프라인 레지스트리
- **ML 모델 레지스트리** (`models`): MLflow 연동, 버전 관리, Stage 관리 (STAGING/PRODUCTION), 메트릭 비교, 모델 카드
- **OCI Model Hub** (`oci_hub`): HuggingFace 스타일 모델 브라우저, OCI 매니페스트, Airgap 임포트
- **데이터 표준 관리** (`standard`): 멀티 표준 사전, 형태소 분석 기반 자동 용어 생성, 준수율 측정
- **데이터 품질** (`quality`): 소스 DB 직접 프로파일링, 8종 규칙 기반 품질 검사, 품질 점수 추적
- **알림 시스템** (`alert`): Rule 기반 스키마 변경 영향 분석, TAG/LINEAGE/PLATFORM 범위 감시, Webhook 알림
- **태그 관리**: 데이터셋 분류를 위한 태그 CRUD
- **용어집 관리** (`glossary`): 트리 분류 체계 (CATEGORY/TERM), Move to 기능
- **스키마 관리**: 데이터셋의 필드/컬럼 스키마 관리 (PK, Unique, Index 포함), 변경 이력 추적
- **소유자 관리**: 데이터셋 소유자 (Technical Owner, Business Owner, Data Steward)
- **시맨틱 검색** (`search`): pgvector 기반 하이브리드 검색 (키워드 + 시맨틱)
- **댓글** (`comments`): 모든 엔티티에 중첩 답글 지원
- **파일 브라우저** (`filesystemmgr`): 모델 아티팩트 파일 탐색, 미리보기
- **External API** (`external`): 외부 시스템용 캐시된 메타데이터/Avro 스키마 API, URN 기반 조회

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async)
- Pydantic v2
- PostgreSQL / MariaDB

## 프로젝트 구조

```
argus-catalog-server/
├── app/
│   ├── __init__.py              # 버전 정의
│   ├── main.py                  # FastAPI 엔트리포인트, 라우터 등록
│   ├── core/
│   │   ├── config.py            # Settings 클래스
│   │   ├── config_loader.py     # properties + YAML 로더
│   │   ├── database.py          # SQLAlchemy 비동기 엔진
│   │   ├── auth.py              # JWT/Keycloak 인증
│   │   ├── logging.py           # 일별 롤링 로깅
│   │   ├── s3.py                # S3/MinIO 연결
│   │   └── security.py          # 보안 헤더 미들웨어
│   ├── catalog/
│   │   ├── router.py            # 카탈로그 API (datasets, platforms, tags, glossary, lineage, pipelines)
│   │   ├── schemas.py           # Pydantic 모델 (Pipeline, Lineage, ColumnMapping 포함)
│   │   ├── service.py           # 비즈니스 로직 (lineage, pipeline, glossary CRUD 포함)
│   │   ├── models.py            # ORM (DataPipeline, DatasetLineage, DatasetColumnMapping 포함)
│   │   ├── sync.py              # MySQL/PostgreSQL 메타데이터 동기화
│   │   └── platform_metadata.py # 플랫폼 메타데이터 시드
│   ├── alert/
│   │   ├── router.py            # 알림 API (rules CRUD, alerts, summary)
│   │   ├── schemas.py           # AlertRule, AlertResponse 스키마
│   │   ├── service.py           # Rule Engine (scope/trigger 평가, 영향 분석, 알림 전달)
│   │   └── models.py            # AlertRule, LineageAlert, AlertNotification ORM
│   ├── standard/
│   │   ├── router.py            # 데이터 표준 API (dictionary, word, domain, term, code, compliance)
│   │   ├── schemas.py           # 표준 스키마 (MorphemeResult, ComplianceStats 포함)
│   │   ├── service.py           # 형태소 분석, 자동 매핑, 준수율 계산
│   │   └── models.py            # StandardDictionary, Word, Domain, Term, CodeGroup ORM
│   ├── quality/
│   │   ├── router.py            # 데이터 품질 API (profile, rules, check, score)
│   │   ├── schemas.py           # 프로파일, 규칙, 결과, 점수 스키마
│   │   ├── service.py           # 소스 DB 프로파일링, 규칙 평가 (A+B 하이브리드)
│   │   └── models.py            # DataProfile, QualityRule, QualityResult, QualityScore ORM
│   ├── models/
│   │   ├── router.py            # ML 모델 API (CRUD, stage, metrics, lineage, card)
│   │   ├── schemas.py           # 모델/버전 Pydantic 스키마
│   │   ├── service.py           # 모델/버전 CRUD + finalize 로직
│   │   ├── models.py            # RegisteredModel, ModelVersion, ModelMetric, ModelCard ORM
│   │   ├── store_router.py      # S3 모델 스토어 API
│   │   └── uc_compat.py         # Unity Catalog OSS 호환 API (/api/2.1/unity-catalog)
│   ├── oci_hub/                 # OCI Model Hub (HuggingFace 스타일)
│   ├── search/                  # 시맨틱/하이브리드 검색
│   ├── embedding/               # 임베딩 서비스 (OpenAI, Ollama, Local)
│   ├── external/                # 외부 시스템용 API (캐시된 메타데이터/Avro 스키마)
│   │   ├── router.py            # External API (URN/ID 기반 조회, 캐시 관리)
│   │   ├── service.py           # 메타데이터/Avro JSON 빌드 + 캐시 로직
│   │   ├── cache.py             # Thread-safe LRU+TTL 캐시 (asyncio.Lock)
│   │   └── schemas.py           # ExternalMetadata, CacheConfig 스키마
│   ├── comments/                # 댓글 시스템
│   ├── filesystemmgr/           # 파일 브라우저
│   ├── auth/                    # 인증 (JWT, Keycloak OIDC)
│   ├── usermgr/                 # 사용자/역할 관리
│   └── settings/                # 설정 관리 (S3, 임베딩, Auth, CORS, Cache)
├── packaging/config/
│   ├── config.yml
│   ├── config.properties
│   ├── argus-catalog-mariadb.sql     # MariaDB DDL
│   └── argus-catalog-postgresql.sql  # PostgreSQL DDL
├── docs/
│   └── architecture.md          # Mermaid 아키텍처 다이어그램
├── alert.md                     # 알림 시스템 문서
├── standard.md                  # 데이터 표준 문서
├── profile.md                   # 데이터 품질 문서
├── MLFlow.md                    # MLflow 연동 가이드
├── OCI.md                       # OCI Model Hub 가이드
├── embedding.md                 # 임베딩/검색 가이드
├── pyproject.toml
└── Makefile
```

## 주요 명령어

```bash
cd argus-catalog-server
make dev      # pip install -e ".[dev]"
make run      # uvicorn --reload (port 4600)
make test     # pytest
make lint     # ruff check
make format   # ruff format
```

## URN 네이밍 규칙

Unity Catalog OSS의 3-level namespace를 참고한 URN 체계:

```
{platform_id}.{path}.{ENV}.{type}
```

### Dataset URN

```
mysql-19d0bfe954e2cfdaa.sakila.film_text.PROD.dataset
├── platform_id    ← 플랫폼 인스턴스 식별자
├── path           ← DB별 경로 (MySQL: db.table, PostgreSQL: schema.table)
├── ENV            ← PROD / STAGING / DEV
└── type           ← dataset
```

- `qualified_name`: `{platform_id}.{path}` (ENV, type 제외)
- `name`: `{db}.{table}` (display용)

### Model URN

```
argus.ml.iris_classifier.PROD.model
├── model_name     ← catalog.schema.model (3-part, MLflow 호환)
├── ENV            ← PROD
└── type           ← model
```

## ML 모델 레지스트리

### 개요

Unity Catalog OSS의 모델 관리 API를 호환 구현하여, MLflow에서 직접 모델을 등록하고 관리할 수 있습니다.

### MLflow 연동 방법

```python
import mlflow

# Argus Catalog를 Model Registry로 설정
mlflow.set_registry_uri("uc:http://<argus-catalog-host>:4600")

# 모델 학습 후 등록 (한 줄)
mlflow.sklearn.log_model(
    model, "model",
    registered_model_name="argus.ml.iris_classifier",  # catalog.schema.model 형식 필수
)

# 등록된 모델 로딩 (추론)
model = mlflow.pyfunc.load_model("models:/argus.ml.iris_classifier/1")
predictions = model.predict(X_test)
```

### 네이밍 규칙

MLflow UC 플러그인은 **반드시 3-part name** (`catalog.schema.model`)을 요구합니다:

```python
# 올바른 예시
"argus.ml.iris_classifier"      # catalog=argus, schema=ml, model=iris_classifier
"prod.recommendation.user_sim"  # catalog=prod, schema=recommendation, model=user_sim
"datateam.fraud.detector_v2"    # catalog=datateam, schema=fraud, model=detector_v2

# 잘못된 예시 (에러 발생)
"iris_classifier"               # 1-part → ValueError
"ml.iris_classifier"            # 2-part → ValueError
```

### 모델 버전 상태 (Status Lifecycle)

```
create_model_version()
    ↓
PENDING_REGISTRATION (생성됨, 아티팩트 업로드 중)
    ↓
finalize_model_version()
    ↓
READY (성공, 아티팩트 업로드 완료)  ←  또는  → FAILED_REGISTRATION (실패)
```

### ModelVersion 컬럼 설명

| 컬럼 | 용도 |
|------|------|
| `status` | `PENDING_REGISTRATION` → `READY` / `FAILED_REGISTRATION` |
| `status_message` | 실패 시 사유 (예: "Model deleted during registration") |
| `artifact_count` | finalize 시점의 아티팩트 파일 수 (0이면 비정상) |
| `artifact_size` | finalize 시점의 아티팩트 총 바이트 (0이면 비정상) |
| `finished_at` | finalize 완료 시각 (NULL이면 미완료, 오래되면 stuck) |
| `source` | MLflow 아티팩트 원본 URI |
| `run_id` | MLflow run ID (학습 추적용) |
| `storage_location` | 서버의 아티팩트 저장 경로 (`file:///var/lib/.../versions/N/`) |

### 정상/비정상 판단 기준

```
status=READY, artifact_count>0, finished_at≠NULL       → 정상
status=FAILED_REGISTRATION, status_message="..."        → 실패 (원인 확인)
status=PENDING_REGISTRATION, finished_at=NULL, 1시간 경과 → stuck (비정상)
```

### 아티팩트 저장 경로

```
{data_dir}/model-artifacts/
  {model_name}/                              ← RegisteredModel
    versions/
      1/                                     ← ModelVersion v1
        MLmodel, model.pkl, conda.yaml, ...
      2/                                     ← ModelVersion v2
        MLmodel, model.pkl, conda.yaml, ...
```

### MLflow 내부 동작 흐름

`mlflow.sklearn.log_model(model, "model", registered_model_name="a.b.c")` 실행 시:

1. `POST /api/2.1/unity-catalog/models` → RegisteredModel 생성
2. `POST /api/2.1/unity-catalog/models/versions` → ModelVersion 생성 (PENDING)
3. `storage_location`이 `file://` 접두사 → MLflow가 로컬 파일시스템에 직접 아티팩트 복사
4. `PATCH /api/2.1/unity-catalog/models/{name}/versions/{ver}/finalize` → READY 전환
5. finalize 시 서버가 아티팩트 디렉토리를 스캔하여 `artifact_count`, `artifact_size` 기록

## API 엔드포인트

### 카탈로그 API (`/api/v1/catalog`)

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 |
| GET | /api/v1/catalog/stats | 카탈로그 통계 |
| GET | /api/v1/catalog/platforms | 플랫폼 목록 |
| POST | /api/v1/catalog/platforms | 플랫폼 등록 |
| PUT | /api/v1/catalog/platforms/{id} | 플랫폼 수정 |
| POST | /api/v1/catalog/platforms/{id}/sync | 메타데이터 동기화 |
| GET | /api/v1/catalog/datasets | 데이터셋 검색/목록 |
| POST | /api/v1/catalog/datasets | 데이터셋 등록 |
| GET | /api/v1/catalog/datasets/{id} | 데이터셋 상세 |
| PUT | /api/v1/catalog/datasets/{id} | 데이터셋 수정 |
| DELETE | /api/v1/catalog/datasets/{id} | 데이터셋 삭제 |
| GET | /api/v1/catalog/datasets/{id}/lineage | 리니지 조회 (쿼리 + 데이터셋 통합) |
| POST | /api/v1/catalog/pipelines | 파이프라인 등록 |
| GET | /api/v1/catalog/pipelines | 파이프라인 목록 |
| POST | /api/v1/catalog/lineage | 리니지 등록 (cross-platform) |
| GET | /api/v1/catalog/lineage | 리니지 목록 |
| PUT | /api/v1/catalog/glossary/{id} | 용어집 수정 |

### 알림 API (`/api/v1/alerts`)

| Method | Path | 설명 |
|--------|------|------|
| GET | /api/v1/alerts/summary | 미해결 알림 건수 (벨 배지) |
| GET | /api/v1/alerts | 알림 목록 |
| PUT | /api/v1/alerts/{id}/status | 알림 상태 변경 |
| POST | /api/v1/alerts/rules | 알림 규칙 생성 |
| GET | /api/v1/alerts/rules | 알림 규칙 목록 |
| PUT | /api/v1/alerts/rules/{id} | 알림 규칙 수정 |
| DELETE | /api/v1/alerts/rules/{id} | 알림 규칙 삭제 |

### 데이터 표준 API (`/api/v1/standards`)

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/standards/dictionaries | 사전 생성 |
| POST | /api/v1/standards/words | 단어 등록 |
| POST | /api/v1/standards/domains | 도메인 등록 |
| GET | /api/v1/standards/terms/analyze | 형태소 분석 |
| POST | /api/v1/standards/terms | 용어 등록 |
| POST | /api/v1/standards/mappings/auto-map | 자동 매핑 |
| GET | /api/v1/standards/compliance | 준수율 조회 |

### 데이터 품질 API (`/api/v1/quality`)

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/quality/datasets/{id}/profile | 프로파일링 실행 |
| GET | /api/v1/quality/datasets/{id}/profile | 프로파일 조회 |
| POST | /api/v1/quality/rules | 품질 규칙 생성 |
| POST | /api/v1/quality/datasets/{id}/check | 품질 검사 실행 |
| GET | /api/v1/quality/datasets/{id}/score | 품질 점수 조회 |

### ML 모델 레지스트리 API (`/api/v1/models`)

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/models/ | 모델 등록 |
| GET | /api/v1/models/ | 모델 목록 |
| GET | /api/v1/models/{name} | 모델 조회 |
| PATCH | /api/v1/models/{name} | 모델 수정 |
| DELETE | /api/v1/models/{name} | 모델 삭제 (soft) |
| POST | /api/v1/models/{name}/versions | 버전 생성 |
| PATCH | /api/v1/models/{name}/versions/{ver}/finalize | 버전 확정 |
| PUT | /api/v1/models/{name}/versions/{ver}/stage | Stage 변경 |
| POST | /api/v1/models/{name}/versions/{ver}/metrics | 메트릭 기록 |
| GET | /api/v1/models/{name}/metrics | 메트릭 비교 |
| POST | /api/v1/models/{name}/lineage | 모델-데이터셋 리니지 |
| GET | /api/v1/models/{name}/card | 모델 카드 조회 |
| PUT | /api/v1/models/{name}/card | 모델 카드 수정 |

### Unity Catalog 호환 API (`/api/2.1/unity-catalog`)

MLflow의 `uc:` URI scheme이 사용하는 API. 직접 호출할 필요 없음.

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/2.1/unity-catalog/models | 모델 등록 |
| GET | /api/2.1/unity-catalog/models | 모델 목록 |
| GET | /api/2.1/unity-catalog/models/{cat}.{sch}.{mdl} | 모델 조회 |
| POST | /api/2.1/unity-catalog/models/versions | 버전 생성 |
| PATCH | /api/2.1/unity-catalog/models/{cat}.{sch}.{mdl}/versions/{ver}/finalize | 버전 확정 |

## 코딩 규칙

- ruff: `target-version = "py311"`, `line-length = 100`
- 모듈 패턴: `router.py`, `schemas.py`, `service.py`, `models.py`
- 기본 포트: **4600**
