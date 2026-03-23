# Argus Catalog - 종합 기술 가이드

## 1. 개요

**Argus Catalog**은 DataHub 스타일의 데이터 카탈로그 기능과 Unity Catalog OSS 호환 ML 모델 레지스트리를 제공하는 지능형 데이터 거버넌스 플랫폼입니다. 이기종 데이터 소스의 메타데이터를 통합 관리하고, 데이터 품질/표준/리니지/알림을 체계적으로 운영할 수 있습니다.

| 구성요소 | 기술 | 역할 |
|----------|------|------|
| **argus-catalog-server** | Python 3.11+ / FastAPI | 백엔드 API 서버 |
| **argus-catalog-ui** | Next.js 16 / React 19 / TypeScript 5.9 | 프론트엔드 웹 UI |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Argus Catalog UI (port 3000)                  │
│              Next.js 16 / React 19 / TypeScript 5.9             │
│   ┌──────────┬──────────┬────────┬────────┬─────────┬────────┐  │
│   │Dashboard │Datasets  │Models  │Standards│Alerts   │Settings│  │
│   │          │Schema    │MLflow  │Word     │Rules    │Auth    │  │
│   │          │Lineage   │OCI Hub │Domain   │Impact   │Embed   │  │
│   │          │Quality   │Metrics │Term     │Webhook  │LLM     │  │
│   └──────────┴──────────┴────────┴────────┴─────────┴────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API (middleware proxy)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Argus Catalog Server (port 4600)                 │
│                  Python 3.11+ / FastAPI / Uvicorn                │
│                                                                  │
│  ┌─────────────────────── API Layer ──────────────────────────┐  │
│  │ /api/v1/catalog    /api/v1/models    /api/v1/standards     │  │
│  │ /api/v1/alerts     /api/v1/ai        /api/v1/quality       │  │
│  │ /api/v1/search     /api/v1/oci-models /api/v1/settings     │  │
│  │ /api/v1/comments   /api/v1/filesystem /api/v1/auth         │  │
│  │ /api/v1/usermgr    /api/2.1/unity-catalog (MLflow 호환)    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌────────────────── Service Layer ───────────────────────────┐  │
│  │ Catalog Service   │ Model Service    │ Standard Service    │  │
│  │ Alert Service     │ AI Service       │ Quality Service     │  │
│  │ Embedding Service │ Search Service   │ Auth Service        │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌────────────────── Data Layer (SQLAlchemy 2.0 async) ───────┐  │
│  │ catalog_* tables  │ argus_* tables   │ catalog_standard_*  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────┬─────────────────┬──────────────────┬─────────────────────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌────────────┐  ┌──────────────┐  ┌──────────────────┐
│ PostgreSQL │  │ S3 / MinIO   │  │ Keycloak         │
│ + pgvector │  │ Model Artifacts│ │ OIDC Auth        │
└────────────┘  └──────────────┘  │ (선택사항)        │
                                  └──────────────────┘
```

---

## 3. 소프트웨어 스택

### 3.1 백엔드 (argus-catalog-server)

| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **언어** | Python | 3.11+ | 서버 개발 언어 |
| **웹 프레임워크** | FastAPI | 0.135+ | 비동기 REST API |
| **ASGI 서버** | Uvicorn | 0.41+ | 프로덕션 서버 |
| **검증** | Pydantic | 2.12+ | 요청/응답 스키마 |
| **ORM** | SQLAlchemy | 2.0+ | 비동기 DB 액세스 |
| **PostgreSQL 드라이버** | asyncpg | 0.31+ | PostgreSQL 비동기 연결 |
| **MySQL 드라이버** | aiomysql | 0.3+ | MySQL/MariaDB 비동기 연결 |
| **벡터 검색** | pgvector | 0.3+ | 시맨틱 검색 (PostgreSQL) |
| **임베딩 (로컬)** | sentence-transformers | 3.0+ | 로컬 벡터 생성 |
| **임베딩 (HF)** | transformers | 4.40+ | HuggingFace 모델 |
| **오브젝트 스토리지** | aioboto3 | 13.0+ | S3/MinIO 비동기 |
| **HTTP 클라이언트** | httpx | 0.27+ | 외부 API 통신 |
| **JWT 인증** | python-jose | 3.4+ | Keycloak OIDC 토큰 검증 |
| **캐싱** | cachetools | 5.3+ | JWKS 키 캐시 |
| **파일 처리** | pyarrow, openpyxl, mammoth, python-pptx | - | Parquet/Excel/Word/PPT 미리보기 |
| **설정** | PyYAML | 6.0+ | YAML 설정 로더 |
| **HuggingFace** | huggingface_hub | 0.28+ | 모델 임포트 |
| **린팅** | ruff | 0.3+ | 코드 스타일 검사/포맷 |
| **테스트** | pytest, pytest-asyncio | 8.0+ | 비동기 테스트 |

### 3.2 프론트엔드 (argus-catalog-ui)

| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **프레임워크** | Next.js | 16 | App Router + Turbopack |
| **UI 라이브러리** | React | 19 | 컴포넌트 렌더링 |
| **언어** | TypeScript | 5.9 | 타입 안전 개발 |
| **스타일링** | Tailwind CSS | v4 | OKLCH 색상 공간 |
| **컴포넌트** | shadcn/ui (Radix UI + CVA) | - | UI 컴포넌트 시스템 |
| **폼** | React Hook Form + Zod | - | 폼 관리 + 검증 |
| **데이터 테이블** | TanStack React Table v8 | - | 데이터 목록/정렬/필터 |
| **그리드** | AG Grid | - | 스키마 편집 (셀 편집) |
| **차트** | Recharts | - | 대시보드 통계 차트 |
| **아이콘** | lucide-react | - | 아이콘 시스템 |
| **텍스트 에디터** | Tiptap + Monaco Editor | - | 모델 카드, 코드 편집 |
| **CSV 파싱** | PapaParse | - | 샘플 데이터 파싱 |
| **모노레포** | Turborepo + pnpm | 9.0.6 | 워크스페이스 관리 |
| **패키지 매니저** | pnpm | 9.0.6 | 의존성 관리 |

### 3.3 인프라스트럭처

| 분류 | 기술 | 용도 |
|------|------|------|
| **데이터베이스** | PostgreSQL 12+ (권장) / MariaDB 10.5+ | 메타데이터 저장 |
| **벡터 확장** | pgvector (PostgreSQL only) | 시맨틱 검색 벡터 저장 |
| **오브젝트 스토리지** | MinIO / AWS S3 | ML 모델 아티팩트 저장 |
| **인증 서버** | Keycloak 22+ (선택사항) | SSO/OIDC 인증 |
| **Node.js** | 20+ | 프론트엔드 런타임 |

---

## 4. 시스템 요구사항

### 4.1 최소 사양

| 항목 | 요구사항 |
|------|----------|
| **OS** | Linux (RHEL 8+, Ubuntu 20.04+), macOS 12+ |
| **CPU** | 4 코어 이상 |
| **메모리** | 8GB RAM 이상 (로컬 임베딩 사용 시 16GB 권장) |
| **디스크** | 50GB 이상 (모델 아티팩트 규모에 따라 증가) |
| **Python** | 3.11 이상 |
| **Node.js** | 20 이상 |
| **pnpm** | 9.0 이상 |
| **PostgreSQL** | 12 이상 + pgvector 확장 |
| **네트워크 포트** | 4600 (서버), 3000 (UI), 5432 (PostgreSQL), 9000 (MinIO) |

### 4.2 선택 사항

| 항목 | 용도 |
|------|------|
| Keycloak 22+ | 기업 SSO 인증 (미사용 시 로컬 JWT 모드) |
| MinIO / AWS S3 | ML 모델 아티팩트 (미사용 시 로컬 파일시스템) |
| GPU (CUDA) | 로컬 임베딩 모델 가속 (선택) |
| OpenAI API 키 | OpenAI 임베딩/LLM 사용 시 |
| Ollama | 로컬 LLM/임베딩 사용 시 |

---

## 5. 핵심 기능

### 5.1 데이터 카탈로그 (`/api/v1/catalog`)

이기종 데이터 소스의 테이블/뷰 메타데이터를 통합 관리합니다.

**지원 플랫폼 (20종):**
MySQL, PostgreSQL, Oracle, MSSQL, Hive, Impala, Trino, StarRocks, Greenplum, Kudu, Snowflake, BigQuery, Redshift, Kafka, S3, HDFS, Elasticsearch, MongoDB, Unity Catalog, Java, Python

**핵심 기능:**
- **데이터셋 CRUD**: 테이블/뷰 등록, 검색, 수정, 삭제
- **메타데이터 자동 동기화**: MySQL/PostgreSQL에 직접 연결하여 테이블 구조, 컬럼 정보, DDL, 인덱스, 행 수 자동 수집
- **스키마 관리**: 컬럼 타입, PK/UK/Index 추적, 변경 이력(스냅샷) 관리
- **태그 관리**: 데이터셋 분류를 위한 태그 CRUD, 색상 지정
- **용어집 관리**: 비즈니스 용어의 트리 분류 체계 (CATEGORY/TERM), Move to 기능
- **소유자 관리**: Technical Owner, Business Owner, Data Steward
- **샘플 데이터**: 소스 DB에서 샘플 행 수집, Parquet 저장, 미리보기

**URN 네이밍 규칙:**
```
{platform_id}.{database}.{table}.{ENV}.dataset
예: mysql-19d0bfe954e2cfdaa.sakila.film_text.PROD.dataset
```

### 5.2 Cross-Platform 리니지 (`/api/v1/catalog/lineage`, `/api/v1/catalog/pipelines`)

이기종 시스템 간 데이터 흐름을 추적합니다.

- **데이터셋 리니지**: 소스→타겟 관계 등록 (ETL, CDC, FILE_EXPORT, REPLICATION 등)
- **컬럼 레벨 매핑**: 개별 컬럼 간 변환 관계 기록 (DIRECT, CAST, EXPRESSION, DERIVED)
- **파이프라인 레지스트리**: ETL/CDC 파이프라인 등록 및 리니지 연결
- **리니지 출처 구분**: QUERY_AGGREGATED (자동), PIPELINE (파이프라인 경유), MANUAL (수동 등록)
- **영향 분석**: 스키마 변경 시 다운스트림 데이터셋 영향 범위 추적

### 5.3 알림 시스템 (`/api/v1/alerts`)

스키마 변경에 대한 Rule 기반 영향 분석과 알림을 제공합니다.

**알림 규칙 구성:**

| 요소 | 옵션 | 설명 |
|------|------|------|
| **Scope** | DATASET, TAG, LINEAGE, PLATFORM, ALL | 감시 범위 |
| **Trigger** | ANY, SCHEMA_CHANGE, COLUMN_WATCH, MAPPING_BROKEN, SYNC_STALE | 발동 조건 |
| **Severity** | BREAKING, WARNING, INFO | 자동 판정 (컬럼 DROP→BREAKING, 타입 변경→WARNING) |
| **Channel** | IN_APP, WEBHOOK, EMAIL | 알림 전달 채널 |

**동작 흐름:**
1. 메타데이터 동기화 시 스키마 변경 감지
2. 활성 규칙의 Scope/Trigger 평가
3. 매칭 시 심각도 자동 판정
4. 알림 생성 + 리니지 기반 다운스트림 영향 분석
5. IN_APP 뱃지 + Webhook(Slack/Teams) 전달

### 5.4 데이터 표준 관리 (`/api/v1/standards`)

조직의 데이터 명명 규칙과 용어를 체계적으로 관리합니다.

**5단계 계층 구조:**
```
Dictionary (사전)
  └── Word (단어): 고객(CUST), 전화(TEL), 번호(NO)
       └── Domain (도메인): 번호 → VARCHAR(20)
            └── Term (용어): 고객전화번호 → CUST_TEL_NO
                 └── Code Group / Code Value (코드): 성별 → M/F
```

**핵심 기능:**
- **형태소 분석**: "고객전화번호" → [고객, 전화, 번호] (Greedy Longest Match)
- **자동 용어 생성**: 분해된 단어들로 영문명, 약어, 물리명 자동 조합
- **자동 매핑**: 데이터셋 컬럼과 표준 용어를 자동 매칭
- **준수율 측정**: MATCHED / VIOLATION / UNMAPPED 비율 산출

### 5.5 데이터 품질 (`/api/v1/quality`)

소스 DB에 직접 연결하여 데이터 프로파일링과 품질 검사를 수행합니다.

**프로파일링 (Method A+B Hybrid):**
- **Method A**: 소스 DB에 직접 SQL 실행 (null count, unique count, min/max, mean)
- **Method B**: 소스 DB 접근 불가 시 스키마 기반 폴백

**품질 규칙 (8종):**

| 규칙 | 설명 |
|------|------|
| NOT_NULL | NULL 값 비율 검사 |
| UNIQUE | 고유성 검사 |
| MIN_VALUE / MAX_VALUE | 범위 검사 |
| ACCEPTED_VALUES | 허용 값 목록 검사 |
| REGEX | 정규식 패턴 검사 |
| ROW_COUNT | 행 수 임계값 검사 |
| FRESHNESS | 데이터 최신성 검사 |

**품질 점수:** 규칙 통과율 기반 점수 산출, 이력 추적

### 5.6 ML 모델 레지스트리 (`/api/v1/models`)

Unity Catalog OSS 호환 API로 MLflow와 직접 연동됩니다.

**MLflow 연동:**
```python
import mlflow

# Argus Catalog를 Model Registry로 설정
mlflow.set_registry_uri("uc:http://<host>:4600")

# 모델 등록 (3-part name 필수)
mlflow.sklearn.log_model(
    model, "model",
    registered_model_name="argus.ml.iris_classifier"
)

# 모델 로딩
model = mlflow.pyfunc.load_model("models:/argus.ml.iris_classifier/1")
```

**핵심 기능:**
- **버전 관리**: PENDING_REGISTRATION → READY / FAILED_REGISTRATION
- **Stage 관리**: NONE → STAGING → PRODUCTION → ARCHIVED
- **메트릭**: accuracy, precision, recall 등 버전별 메트릭 비교
- **리니지**: 모델-데이터셋 학습 리니지 추적
- **모델 카드**: Markdown 형식 모델 문서화
- **아티팩트**: S3/MinIO 또는 로컬 파일시스템 저장

**UC 호환 API** (`/api/2.1/unity-catalog`): MLflow의 `uc:` URI scheme이 사용하는 내부 API.

### 5.7 OCI Model Hub (`/api/v1/oci-models`)

HuggingFace 스타일의 모델 브라우저를 제공합니다.

- **모델 브라우저**: 태스크, 프레임워크, 라이선스별 필터링
- **버전 관리**: OCI Image Manifest 형식의 버전 관리
- **HuggingFace 임포트**: Hub에서 모델 메타데이터 자동 수집
- **Airgap 지원**: 네트워크 격리 환경에서 로컬 임포트
- **다운로드 추적**: 다운로드 횟수, 로그 기록

### 5.8 시맨틱 검색 (`/api/v1/catalog/search`)

pgvector 기반 하이브리드 검색 (키워드 + 시맨틱)을 제공합니다.

**임베딩 프로바이더 (3종):**

| 프로바이더 | 모델 | 차원 | 특성 |
|------------|------|------|------|
| **local** | all-MiniLM-L6-v2 | 384 | 외부 연결 불필요, Air-gapped |
| **openai** | text-embedding-3-small | 1536 | 고품질, API 키 필요 |
| **ollama** | nomic-embed-text | 768 | 자체 호스팅 |

**검색 방식:**
- **Semantic Search**: pgvector 코사인 유사도 검색
- **Keyword Search**: ILIKE 패턴 매칭 (이름, 설명, URN, qualified_name)
- **Hybrid Search**: 가중 결합 (기본: 시맨틱 70% + 키워드 30%), 시맨틱 불가 시 키워드 자동 폴백

**임베딩 소스 텍스트:** `name | description | qualified_name | platform_name | platform_type | tags | owners`

### 5.9 AI 메타데이터 자동 생성 (`/api/v1/ai`)

LLM을 활용하여 메타데이터를 자동 생성합니다.

**LLM 프로바이더 (3종):**

| 프로바이더 | 기본 모델 | 특성 |
|------------|-----------|------|
| **openai** | gpt-4o-mini | API 기반, 고품질 |
| **ollama** | llama3.1 | 로컬 자체 호스팅 |
| **anthropic** | claude-sonnet-4-20250514 | API 기반 |

**생성 기능:**
- **테이블 설명 생성**: 테이블명 + 컬럼 + DDL + 샘플 데이터 → 한국어/영어 설명
- **컬럼 설명 일괄 생성**: 한 테이블의 모든 컬럼을 한 번의 호출로 생성
- **태그 추천**: 기존 카탈로그 태그 활용, 새 태그 제안
- **PII 탐지**: EMAIL, PHONE, SSN, NAME, ADDRESS 등 개인정보 컬럼 자동 탐지

**워크플로우:**
1. 미리보기 (apply=false): 생성 결과 확인 후 적용 여부 결정
2. 즉시 적용 (apply=true): 생성 즉시 메타데이터에 반영
3. 동기화 후 자동 생성: 메타데이터 동기화 시 빈 설명 자동 채움

**감사 추적:** `catalog_ai_generation_log` 테이블에 모든 생성 이력, 토큰 사용량, 적용 여부 기록

### 5.10 댓글 시스템 (`/api/v1/comments`)

모든 엔티티(데이터셋, 모델 등)에 댓글을 달 수 있습니다.

- 중첩 답글 (nested replies) 지원
- 개선 제안 플래그 (suggestion)

### 5.11 파일 브라우저 (`/api/v1/filesystem`)

서버 로컬 파일시스템을 탐색하고 파일을 관리합니다.

- 디렉토리 목록, 파일 상세 정보
- 파일 업로드/다운로드/이름 변경/삭제
- 미리보기: Parquet, Excel, Word, PowerPoint, CSV, 이미지, 오디오, 비디오

### 5.12 사용자 관리 (`/api/v1/usermgr`, `/api/v1/auth`)

- **인증**: Keycloak OIDC (프로덕션) / Local JWT (개발)
- **사용자 CRUD**: 생성, 수정, 삭제, 활성화/비활성화
- **역할**: argus-admin, argus-superuser, argus-user
- **토큰**: JWT 액세스 토큰 (8시간), 리프레시 토큰

---

## 6. 프론트엔드 UI

### 6.1 화면 구성

| 메뉴 그룹 | 페이지 | 경로 | 설명 |
|-----------|--------|------|------|
| **Data Catalog** | Dashboard | `/dashboard` | 통계 카드, 분포 차트, 성장 추세, 최근 데이터셋 |
| | Datasets | `/dashboard/datasets` | 데이터셋 검색/목록/상세 (스키마, 리니지, 품질, 태그, 소유자, 용어, 샘플 데이터) |
| | Platforms | `/dashboard/platforms` | 플랫폼 카드, 연결 설정, 메타데이터 동기화 |
| **Model Catalog** | MLflow Models | `/dashboard/models` | 모델 대시보드, 버전/Stage 관리, 메트릭, 리니지, 모델 카드 |
| | MLflow Files | `/dashboard/mlflow-files` | 모델 아티팩트 파일 브라우저 (관리자) |
| | OCI Model Hub | `/dashboard/oci-hub` | HuggingFace 스타일 모델 브라우저 |
| | OCI Files | `/dashboard/oci-files` | OCI 아티팩트 파일 브라우저 (관리자) |
| **Governance** | Data Standards | `/dashboard/standards` | 단어/도메인/용어/코드/준수율 탭 |
| | Glossary | `/dashboard/glossary` | 트리 분류 체계 용어집 |
| | Tags | `/dashboard/tags` | 태그 CRUD (색상 포함) |
| | Alerts | `/dashboard/alerts` | 알림 목록/규칙 관리 |
| **Administration** | Users | `/dashboard/users` | 사용자 CRUD, 역할/상태 관리 (관리자) |
| | Settings | `/dashboard/settings` | 인증, CORS, 임베딩, LLM 설정 (관리자) |
| **전역** | Search | `/dashboard/search` | 하이브리드 시맨틱 검색 결과 |

### 6.2 주요 UI 컴포넌트

- **데이터셋 상세 탭**: Schema (ag-grid 편집), Schema History, Tags, Owners, Sample Data (CSV 파싱), Quality (프로파일/규칙/점수), Terms (용어 매핑), Lineage (업/다운스트림), Pipeline Tabs (Airflow DAG, Kestra Flow, NiFi Flow), Comments
- **모델 상세**: Versions (상태 라이프사이클), Stage 관리, Metrics (차트 비교), Lineage (학습 데이터셋), Model Card (Markdown 에디터)
- **대시보드 차트**: Donut (플랫폼/Origin 분포), Bar (상위 플랫폼, Schema Fields), Line (일별 성장 추세)

---

## 7. API 엔드포인트 전체 목록

### 7.1 카탈로그 (`/api/v1/catalog`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/stats` | 카탈로그 통계 |
| GET/POST | `/platforms` | 플랫폼 목록/등록 |
| PUT | `/platforms/{id}` | 플랫폼 수정 |
| GET/PUT | `/platforms/{id}/config` | 플랫폼 연결 설정 |
| POST | `/platforms/{id}/sync` | 메타데이터 동기화 |
| GET/POST | `/datasets` | 데이터셋 목록/등록 |
| GET/PUT/DELETE | `/datasets/{id}` | 데이터셋 상세/수정/삭제 |
| PUT | `/datasets/{id}/schema` | 스키마 필드 수정 |
| GET | `/datasets/{id}/schema-history` | 스키마 변경 이력 |
| POST/DELETE | `/datasets/{id}/tags` | 태그 연결/해제 |
| POST/DELETE | `/datasets/{id}/owners` | 소유자 추가/삭제 |
| GET | `/datasets/{id}/lineage` | 통합 리니지 조회 |
| POST/GET | `/pipelines` | 파이프라인 등록/목록 |
| PUT/DELETE | `/pipelines/{id}` | 파이프라인 수정/삭제 |
| POST/GET | `/lineage` | 리니지 등록/목록 |
| DELETE | `/lineage/{id}` | 리니지 삭제 |
| POST/DELETE | `/lineage/{id}/columns` | 컬럼 매핑 추가/삭제 |
| GET/POST | `/tags` | 태그 목록/생성 |
| DELETE | `/tags/{id}` | 태그 삭제 |
| GET/POST | `/glossary` | 용어집 목록/생성 |
| PUT/DELETE | `/glossary/{id}` | 용어집 수정/삭제 |

### 7.2 알림 (`/api/v1/alerts`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/summary` | 미해결 알림 건수 (벨 배지) |
| GET | `/` | 알림 목록 (필터: status, severity) |
| GET | `/{id}` | 알림 상세 |
| PUT | `/{id}/status` | 상태 변경 (OPEN/ACKNOWLEDGED/RESOLVED/DISMISSED) |
| POST/GET | `/rules` | 규칙 생성/목록 |
| GET/PUT/DELETE | `/rules/{id}` | 규칙 상세/수정/삭제 |

### 7.3 데이터 표준 (`/api/v1/standards`)

| Method | Path | 설명 |
|--------|------|------|
| POST/GET | `/dictionaries` | 사전 생성/목록 |
| POST/GET | `/words` | 단어 등록/목록 |
| PUT/DELETE | `/words/{id}` | 단어 수정/삭제 |
| POST/GET | `/domains` | 도메인 등록/목록 |
| PUT/DELETE | `/domains/{id}` | 도메인 수정/삭제 |
| GET | `/terms/analyze` | 형태소 분석 |
| POST/GET | `/terms` | 용어 등록/목록 |
| PUT/DELETE | `/terms/{id}` | 용어 수정/삭제 |
| POST/GET | `/code-groups` | 코드그룹 생성/목록 |
| POST | `/code-groups/{id}/values` | 코드값 추가 |
| POST/GET | `/mappings` | 매핑 등록/목록 |
| DELETE | `/mappings/{id}` | 매핑 삭제 |
| POST | `/mappings/auto-map` | 자동 매핑 |
| GET | `/mappings/dataset` | 데이터셋 매핑 상태 |
| GET | `/compliance` | 준수율 조회 |
| GET | `/change-logs` | 변경 이력 |

### 7.4 데이터 품질 (`/api/v1/quality`)

| Method | Path | 설명 |
|--------|------|------|
| POST/GET | `/datasets/{id}/profile` | 프로파일링 실행/조회 |
| POST/GET | `/rules` | 규칙 생성/목록 |
| PUT/DELETE | `/rules/{id}` | 규칙 수정/삭제 |
| POST | `/datasets/{id}/check` | 품질 검사 실행 |
| GET | `/datasets/{id}/results` | 검사 결과 |
| GET | `/datasets/{id}/score` | 품질 점수 |
| GET | `/datasets/{id}/score/history` | 점수 이력 |

### 7.5 ML 모델 (`/api/v1/models`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/stats` | 모델 통계 |
| POST/GET | `/` | 모델 등록/목록 |
| GET/PATCH/DELETE | `/{name}` | 모델 조회/수정/삭제(soft) |
| GET | `/{name}/detail` | 상세 (다운로드 수 포함) |
| POST/GET | `/{name}/versions` | 버전 생성/목록 |
| GET/PATCH/DELETE | `/{name}/versions/{ver}` | 버전 상세/수정/삭제 |
| PATCH | `/{name}/versions/{ver}/finalize` | 버전 확정 (READY) |
| PUT | `/{name}/versions/{ver}/stage` | Stage 변경 |
| POST | `/{name}/versions/{ver}/metrics` | 메트릭 기록 |
| GET | `/{name}/metrics` | 메트릭 비교 |
| POST/GET | `/{name}/lineage` | 모델-데이터셋 리니지 |
| GET/PUT | `/{name}/card` | 모델 카드 |
| POST | `/hard-delete` | 하드 삭제 (관리자) |

### 7.6 Unity Catalog 호환 (`/api/2.1/unity-catalog`)

MLflow `uc:` URI scheme 전용. 직접 호출 불필요.

| Method | Path | 설명 |
|--------|------|------|
| POST/GET | `/models` | 모델 등록/목록 |
| GET | `/models/{cat}.{sch}.{mdl}` | 모델 조회 |
| POST | `/models/versions` | 버전 생성 |
| PATCH | `/models/{name}/versions/{ver}/finalize` | 버전 확정 |

### 7.7 OCI Model Hub (`/api/v1/oci-models`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/server-info` | 서버 호스트/포트 |
| GET | `/stats` | Hub 통계 |
| GET/POST | `/` | 모델 목록/등록 |
| GET/PATCH/DELETE | `/{name}` | 모델 상세/수정/삭제 |
| PUT | `/{name}/readme` | README 수정 |

### 7.8 시맨틱 검색 (`/api/v1/catalog/search`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/semantic` | 시맨틱 검색 |
| GET | `/hybrid` | 하이브리드 검색 (키워드+시맨틱) |
| GET | `/embeddings/stats` | 임베딩 커버리지 통계 |
| POST | `/embeddings/backfill` | 전체 재임베딩 |
| DELETE | `/embeddings` | 임베딩 초기화 |

### 7.9 AI 메타데이터 생성 (`/api/v1/ai`)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/datasets/{id}/describe` | 테이블 설명 생성 |
| POST | `/datasets/{id}/describe-columns` | 컬럼 설명 일괄 생성 |
| POST | `/datasets/{id}/suggest-tags` | 태그 추천 |
| POST | `/datasets/{id}/detect-pii` | PII 탐지 |
| POST | `/datasets/{id}/generate-all` | 전체 생성 (위 4개 동시) |
| POST | `/bulk-generate` | 다수 데이터셋 일괄 생성 |
| GET | `/datasets/{id}/suggestions` | 미적용 제안 목록 |
| POST | `/suggestions/{id}/apply` | 제안 적용 |
| POST | `/suggestions/{id}/reject` | 제안 거부 |
| GET | `/stats` | 생성 통계 |

### 7.10 기타

| Method | Path | 설명 |
|--------|------|------|
| GET/POST | `/api/v1/comments` | 댓글 목록/생성 |
| PUT/DELETE | `/api/v1/comments/{id}` | 댓글 수정/삭제 |
| GET | `/api/v1/filesystem/list` | 파일 목록 |
| GET/POST/DELETE | `/api/v1/filesystem/*` | 파일 CRUD/미리보기 |
| POST | `/api/v1/auth/login` | 로그인 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| GET/POST | `/api/v1/usermgr/users` | 사용자 CRUD |
| GET/PUT | `/api/v1/settings/{category}` | 설정 조회/수정 |
| POST | `/api/v1/settings/{category}/test` | 연결 테스트 |
| GET | `/health` | 헬스체크 (uptime, version) |

---

## 8. 설치 및 실행

### 8.1 사전 준비

#### PostgreSQL 설치 및 설정

```bash
# PostgreSQL 설치 (Ubuntu)
sudo apt install postgresql postgresql-contrib

# pgvector 확장 설치 (시맨틱 검색용)
sudo apt install postgresql-16-pgvector

# DB 및 사용자 생성
sudo -u postgres psql
CREATE USER argus WITH PASSWORD 'argus';
CREATE DATABASE argus_catalog OWNER argus;
\c argus_catalog
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

#### DDL 실행

```bash
# PostgreSQL
psql -U argus -d argus_catalog -f packaging/config/argus-catalog-postgresql.sql

# MariaDB (대안)
mysql -u argus -p argus_catalog < packaging/config/argus-catalog-mariadb.sql
```

> DDL 실행은 선택사항입니다. SQLAlchemy가 서버 시작 시 테이블을 자동 생성합니다. DDL은 인덱스 최적화와 pgvector 설정이 포함되어 있어 프로덕션 환경에 권장됩니다.

#### MinIO 설치 (선택, ML 모델 아티팩트용)

```bash
# MinIO 서버 실행
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
./minio server /data/minio --console-address ":9001"

# 기본 계정: minioadmin / minioadmin
```

#### Keycloak 설치 (선택, SSO 인증용)

```bash
# Keycloak 서버 실행 (Docker)
docker run -p 8180:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:26.0 start-dev
```

> Keycloak 미사용 시 서버는 Local JWT 모드로 동작합니다.

### 8.2 백엔드 서버 설치

```bash
cd argus-catalog-server

# Python 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
pip install -e ".[dev]"     # 또는: make dev

# 설정 파일 편집
cp packaging/config/config.properties packaging/config/my-config.properties
vi packaging/config/my-config.properties
# → db.host, db.password, auth.* 등 환경에 맞게 수정
```

#### config.properties 주요 설정

```properties
# 서버
server.host=0.0.0.0
server.port=4600

# 로깅
log.level=INFO
log.dir=/var/log/argus-catalog-server

# 데이터 디렉토리 (모델 아티팩트 로컬 저장)
data.dir=/var/lib/argus-catalog-server

# CORS
cors.origins=*

# 인증 (Keycloak)
auth.type=keycloak
auth.keycloak.server_url=http://localhost:8180
auth.keycloak.realm=argus
auth.keycloak.client_id=argus-client
auth.keycloak.client_secret=argus-client-secret

# 데이터베이스 (PostgreSQL)
db.type=postgresql
db.host=localhost
db.port=5432
db.name=argus_catalog
db.username=argus
db.password=argus
```

#### 서버 실행

```bash
# 개발 모드 (auto-reload)
make run
# 또는:
uvicorn app.main:app --host 0.0.0.0 --port 4600 --reload

# 프로덕션 모드 (설정 파일 지정)
argus-catalog-server \
  --config-yaml packaging/config/config.yml \
  --config-properties packaging/config/my-config.properties
```

#### 서버 시작 확인

```bash
curl http://localhost:4600/health
# {"status":"ok","service":"argus-catalog-server","uptime":5,"version":"0.1.0"}
```

### 8.3 프론트엔드 UI 설치

```bash
cd argus-catalog-ui

# Node.js 20+ 확인
node --version

# pnpm 설치 (없으면)
npm install -g pnpm@9

# 의존성 설치
pnpm install

# 환경 변수 설정
echo "API_BASE_URL=http://localhost:4600" > apps/web/.env.development

# 개발 서버 실행 (Turbopack)
pnpm dev
# → http://localhost:3000

# 프로덕션 빌드
pnpm build
```

### 8.4 초기 설정 (UI에서)

1. **로그인**: `http://localhost:3000/login` 접속 → 기본 계정으로 로그인
2. **Settings > Auth**: Keycloak 연결 설정 또는 Local JWT 모드 확인
3. **Settings > Embedding**: 임베딩 프로바이더 선택 (local/openai/ollama) → Test → Save
4. **Settings > LLM**: AI 메타데이터 생성 프로바이더 설정 (선택)
5. **Settings > Object Storage**: MinIO/S3 연결 설정 (ML 모델 사용 시)
6. **Platforms**: 데이터 소스 플랫폼 등록 → 연결 설정 → Sync 실행

### 8.5 Keycloak 자동 설정

Settings > Auth에서 Initialize 버튼으로 Keycloak을 자동 설정할 수 있습니다:
- Realm 생성 (argus)
- Client 생성 (argus-client)
- Client Secret 설정
- 역할 생성 (argus-admin, argus-superuser, argus-user)

---

## 9. 프로젝트 구조

### 9.1 백엔드 디렉토리

```
argus-catalog-server/
├── app/
│   ├── __init__.py                  # 버전 (0.1.0)
│   ├── main.py                      # FastAPI 엔트리포인트
│   ├── core/
│   │   ├── config.py                # Settings 클래스
│   │   ├── config_loader.py         # YAML + properties 로더
│   │   ├── database.py              # SQLAlchemy async 엔진
│   │   ├── auth.py                  # JWT/Keycloak 인증
│   │   ├── s3.py                    # S3/MinIO 클라이언트
│   │   ├── security.py              # 보안 헤더 미들웨어
│   │   └── logging.py               # 일별 롤링 로깅
│   ├── catalog/                     # 카탈로그 (데이터셋, 플랫폼, 태그, 용어집, 리니지)
│   │   ├── router.py / service.py / schemas.py / models.py
│   │   ├── sync.py                  # 메타데이터 동기화
│   │   └── platform_metadata.py     # 플랫폼 메타데이터 시드
│   ├── alert/                       # 알림 (규칙 엔진, 영향 분석)
│   ├── standard/                    # 데이터 표준 (사전, 단어, 도메인, 용어, 코드)
│   ├── quality/                     # 데이터 품질 (프로파일링, 규칙, 점수)
│   ├── models/                      # ML 모델 레지스트리
│   │   ├── router.py / service.py / schemas.py / models.py
│   │   ├── uc_compat.py             # Unity Catalog OSS 호환 API
│   │   ├── store_router.py          # 모델 아티팩트 스토어
│   │   └── download_log.py          # 다운로드 추적
│   ├── oci_hub/                     # OCI Model Hub
│   ├── search/                      # 시맨틱/하이브리드 검색
│   ├── embedding/                   # 임베딩 프로바이더 (local, OpenAI, Ollama)
│   │   ├── base.py                  # EmbeddingProvider ABC
│   │   ├── registry.py              # 싱글톤 프로바이더 관리
│   │   ├── service.py               # 임베딩 생성/관리
│   │   └── providers/               # local.py, openai.py, ollama.py
│   ├── ai/                          # AI 메타데이터 자동 생성
│   │   ├── base.py                  # LLMProvider ABC
│   │   ├── registry.py              # 싱글톤 LLM 프로바이더 관리
│   │   ├── prompts.py               # 프롬프트 템플릿
│   │   ├── service.py               # 생성 오케스트레이션
│   │   ├── schemas.py / router.py / models.py
│   │   └── providers/               # openai.py, ollama.py, anthropic.py
│   ├── comments/                    # 댓글 시스템
│   ├── filesystemmgr/               # 파일 브라우저
│   ├── auth/                        # 인증 (JWT, Keycloak OIDC)
│   ├── usermgr/                     # 사용자/역할 관리
│   └── settings/                    # 설정 관리 (DB-backed)
├── packaging/config/
│   ├── config.yml                   # YAML 설정 (Spring-style 플레이스홀더)
│   ├── config.properties            # 변수 파일
│   ├── argus-catalog-postgresql.sql # PostgreSQL DDL
│   └── argus-catalog-mariadb.sql    # MariaDB DDL
├── docs/
│   └── architecture.md              # Mermaid 아키텍처 다이어그램
├── pyproject.toml                   # 프로젝트 메타데이터
├── requirements.txt                 # 고정 의존성
└── Makefile                         # 빌드 명령어
```

### 9.2 프론트엔드 디렉토리

```
argus-catalog-ui/
├── apps/web/                        # Next.js 웹 애플리케이션
│   ├── app/                         # App Router
│   │   ├── layout.tsx               # 루트 레이아웃 (인증+테마)
│   │   ├── page.tsx                 # 홈 (로그인/대시보드 리디렉트)
│   │   ├── login/page.tsx           # 로그인 페이지
│   │   └── dashboard/               # 보호된 라우트
│   │       ├── layout.tsx           # 대시보드 레이아웃 (사이드바+메인)
│   │       ├── page.tsx             # 대시보드 통계
│   │       ├── datasets/            # 데이터셋 목록/상세
│   │       ├── platforms/           # 플랫폼 관리
│   │       ├── models/              # MLflow 모델
│   │       ├── alerts/              # 알림
│   │       ├── glossary/            # 용어집
│   │       ├── tags/                # 태그
│   │       ├── standards/           # 데이터 표준
│   │       ├── oci-hub/             # OCI Model Hub
│   │       ├── users/               # 사용자 (관리자)
│   │       ├── settings/            # 설정 (관리자)
│   │       └── search/              # 검색 결과
│   ├── components/                  # 재사용 컴포넌트 (143개)
│   ├── features/                    # 기능 모듈 (12개)
│   │   ├── auth/                    # 인증 컨텍스트, API
│   │   ├── datasets/                # 데이터셋 API, 스키마
│   │   ├── models/                  # 모델 API
│   │   ├── platforms/               # 플랫폼 설정
│   │   ├── alerts/                  # 알림 API
│   │   ├── comments/                # 댓글 API
│   │   └── ...
│   ├── data/menu.json               # 사이드바 메뉴 설정
│   ├── middleware.ts                 # API 프록시 미들웨어
│   └── .env.development             # API_BASE_URL=http://localhost:4600
├── packages/ui/                     # 공유 UI 컴포넌트 라이브러리
│   ├── src/components/              # shadcn/ui 컴포넌트
│   ├── src/hooks/                   # 공유 React 훅
│   └── tailwind.config.ts           # Tailwind 설정
└── turbo.json                       # Turborepo 설정
```

---

## 10. 설정 레퍼런스

### 10.1 config.yml 전체 구조

```yaml
app:
  name: argus-catalog-server
  version: 0.1.0
  debug: ${app.debug:false}

server:
  host: ${server.host:0.0.0.0}
  port: ${server.port:4600}

logging:
  level: ${log.level:INFO}              # DEBUG, INFO, WARNING, ERROR
  dir: ${log.dir:/var/log/argus-catalog-server}
  filename: ${log.filename:argus-catalog-server.log}
  rolling:
    type: daily                         # 일별 롤링
    backup_count: 30                    # 30일 보관

data:
  dir: ${data.dir:/var/lib/argus-catalog-server}  # 모델 아티팩트 저장 경로

cors:
  origins: ${cors.origins:*}            # 쉼표 구분 (예: http://localhost:3000,http://myhost:3000)

auth:
  type: ${auth.type:keycloak}           # keycloak 또는 local
  keycloak:
    server_url: ${auth.keycloak.server_url:http://localhost:8180}
    realm: ${auth.keycloak.realm:argus}
    client_id: ${auth.keycloak.client_id:argus-client}
    client_secret: ${auth.keycloak.client_secret:argus-client-secret}
    admin_role: ${auth.keycloak.admin_role:argus-admin}
    superuser_role: ${auth.keycloak.superuser_role:argus-superuser}
    user_role: ${auth.keycloak.user_role:argus-user}

database:
  type: ${db.type:postgresql}           # postgresql 또는 mariadb
  host: ${db.host:localhost}
  port: ${db.port:5432}                 # PostgreSQL: 5432, MariaDB: 3306
  name: ${db.name:argus_catalog}
  username: ${db.username:argus}
  password: ${db.password:argus}
  pool:
    size: ${db.pool.size:5}
    max_overflow: ${db.pool.max_overflow:10}
    recycle: ${db.pool.recycle:3600}
  echo: ${db.echo:false}               # SQL 로그 출력
```

### 10.2 런타임 설정 (DB-backed, Settings API)

서버 실행 중 UI/API로 변경 가능한 설정:

| 카테고리 | 키 | 기본값 | 설명 |
|----------|-----|--------|------|
| **object_storage** | object_storage_endpoint | http://localhost:9000 | S3 엔드포인트 |
| | object_storage_access_key | minioadmin | 액세스 키 |
| | object_storage_secret_key | minioadmin | 시크릿 키 |
| | object_storage_bucket | model-artifacts | 버킷 이름 |
| **embedding** | embedding_enabled | false | 시맨틱 검색 활성화 |
| | embedding_provider | local | local / openai / ollama |
| | embedding_model | all-MiniLM-L6-v2 | 임베딩 모델 |
| | embedding_api_key | | OpenAI API 키 |
| | embedding_api_url | | 커스텀 API URL |
| | embedding_dimension | 384 | 벡터 차원 |
| **llm** | llm_enabled | false | AI 메타데이터 생성 활성화 |
| | llm_provider | openai | openai / ollama / anthropic |
| | llm_model | gpt-4o-mini | LLM 모델 |
| | llm_api_key | | API 키 |
| | llm_api_url | | 커스텀 API URL |
| | llm_temperature | 0.3 | 생성 temperature |
| | llm_max_tokens | 1024 | 최대 토큰 |
| | llm_auto_generate_on_sync | false | 동기화 후 자동 생성 |
| | llm_language | ko | 생성 언어 (ko, en 등) |
| **auth** | auth_type | keycloak | 인증 방식 |
| | auth_keycloak_* | | Keycloak 설정들 |
| **cors** | cors_origins | * | 허용 오리진 |

---

## 11. 데이터베이스 스키마

### 주요 테이블 목록

| 테이블 | 설명 |
|--------|------|
| `catalog_platforms` | 데이터 플랫폼 레지스트리 |
| `catalog_platform_configurations` | 플랫폼 연결 설정 (JSON) |
| `catalog_datasets` | 데이터셋 (테이블, 뷰, 토픽 등) |
| `catalog_dataset_schemas` | 데이터셋 스키마 필드 (컬럼) |
| `catalog_schema_snapshots` | 스키마 변경 이력 스냅샷 |
| `catalog_tags` / `catalog_dataset_tags` | 태그 및 데이터셋-태그 매핑 |
| `catalog_glossary_terms` | 비즈니스 용어집 (트리 구조) |
| `catalog_owners` | 데이터셋 소유자 |
| `argus_data_pipeline` | 데이터 파이프라인 레지스트리 |
| `argus_dataset_lineage` | 데이터셋 리니지 관계 |
| `argus_dataset_column_mapping` | 컬럼 레벨 리니지 매핑 |
| `catalog_alert_rules` | 알림 규칙 |
| `catalog_lineage_alerts` | 생성된 알림 |
| `catalog_standard_dictionary` | 데이터 표준 사전 |
| `catalog_standard_word` | 표준 단어 |
| `catalog_standard_domain` | 표준 도메인 |
| `catalog_standard_term` | 표준 용어 |
| `catalog_data_profiles` | 데이터 프로파일 결과 |
| `catalog_quality_rules` | 품질 규칙 |
| `catalog_quality_results` | 품질 검사 결과 |
| `catalog_quality_scores` | 품질 점수 |
| `catalog_registered_models` | ML 등록 모델 |
| `catalog_model_versions` | 모델 버전 |
| `catalog_model_metrics` | 모델 메트릭 |
| `catalog_model_cards` | 모델 카드 |
| `catalog_dataset_embeddings` | 시맨틱 검색 벡터 (pgvector) |
| `catalog_ai_generation_log` | AI 생성 이력 |
| `catalog_configuration` | 런타임 설정 (카테고리별 key-value) |
| `catalog_users` / `catalog_roles` | 사용자 및 역할 |
| `catalog_comments` | 댓글 |

---

## 12. 보안

| 항목 | 내용 |
|------|------|
| **인증** | Keycloak OIDC (프로덕션) / Local JWT HS256 (개발) |
| **토큰** | JWT Access Token (8시간), Refresh Token |
| **JWKS 캐시** | Keycloak 공개키 1시간 캐시 (TTL) |
| **역할** | argus-admin (전체 권한), argus-superuser (관리 권한), argus-user (읽기) |
| **보안 헤더** | X-Content-Type-Options: nosniff, X-Frame-Options: DENY, X-XSS-Protection: 1 |
| **CORS** | 동적 미들웨어 (런타임 변경 가능, DB 설정 기반) |
| **비밀번호 마스킹** | 설정 API에서 secret 값 마스킹 (••••••••) |
| **API 프록시** | 프론트엔드 middleware.ts에서 백엔드로 프록시 (직접 노출 방지) |

---

## 13. 개발 명령어

### 백엔드

```bash
cd argus-catalog-server

make dev        # pip install -e ".[dev]"
make run        # uvicorn --reload (port 4600)
make test       # pytest tests/ -v
make lint       # ruff check + format check
make format     # ruff format + fix
make clean      # __pycache__, build 정리
```

### 프론트엔드

```bash
cd argus-catalog-ui

pnpm install    # 의존성 설치
pnpm dev        # 개발 서버 (Turbopack, port 3000)
pnpm build      # 프로덕션 빌드
pnpm lint       # ESLint 검사
```

---

## 14. 서버 시작 흐름

```
1. 설정 로드 (YAML + properties, Spring-style 변수 치환)
2. 로깅 설정 (일별 롤링 핸들러, 30일 보관)
3. 데이터베이스 연결 초기화 (SQLAlchemy async)
4. 테이블 자동 생성 (Base.metadata.create_all)
5. 시드 데이터 삽입
   ├── 기본 플랫폼 (MySQL, PostgreSQL, Hive, Impala 등)
   ├── 플랫폼 메타데이터 (데이터 타입, 테이블 타입, 스토리지 포맷, 기능)
   ├── 기본 역할 (admin, superuser, user)
   └── 기본 설정 (S3, 임베딩, LLM, 인증, CORS)
6. 설정 로드 (DB → 메모리)
   ├── Object Storage (S3/MinIO)
   ├── Embedding Provider (local/openai/ollama)
   ├── LLM Provider (openai/ollama/anthropic)
   ├── Auth (Keycloak/Local)
   └── CORS Origins
7. S3 버킷 확인/생성
8. Uvicorn 서버 시작 (0.0.0.0:4600)
```

---

## 15. 라이선스

Apache License 2.0
