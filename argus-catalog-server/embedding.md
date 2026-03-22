# Semantic Search — Embedding 기반 카탈로그 검색

## 개요

Argus Catalog의 시맨틱 검색은 데이터셋 메타데이터(이름, 설명, 플랫폼, 태그, 소유자)를
벡터 임베딩으로 변환하고, pgvector를 이용한 코사인 유사도 검색을 수행합니다.

**기존 키워드 검색과의 차이:**

| 검색 방식 | 쿼리 예시 | 동작 |
|-----------|----------|------|
| 키워드 (LIKE) | `customer` | `customer`가 포함된 이름/설명만 매칭 |
| 시맨틱 | `고객 구매 이력` | 의미적으로 유사한 `fact_purchases`, `order_history` 등도 매칭 |
| 하이브리드 | `customer purchase` | 키워드 매칭 + 시맨틱 유사도를 가중 합산하여 최적 결과 |

---

## pgvector와 Embedding Provider의 관계

pgvector와 Embedding Provider는 **독립적인 역할**을 담당합니다.

| 구성 요소 | 역할 | 의존 관계 |
|-----------|------|-----------|
| **pgvector** | 벡터 **저장 + 검색** (PostgreSQL 확장) | 필수 — 어떤 프로바이더를 쓰든 벡터를 저장할 곳이 필요 |
| **Embedding Provider** | 텍스트 → 벡터 **생성** | 3개 중 택 1 — Local, OpenAI, Ollama |

```
텍스트 "고객 구매 테이블"
    ↓
[Embedding Provider]  ← 여기가 교체 가능한 부분
    ├─ Local (sentence-transformers)
    ├─ OpenAI API
    └─ Ollama
    ↓
벡터 [0.012, -0.034, ...]  (384 또는 1536차원)
    ↓
[pgvector]  ← 여기는 항상 고정
    ├─ 저장: INSERT INTO catalog_dataset_embeddings
    └─ 검색: ORDER BY embedding <=> query_vec (코사인 유사도)
```

- **pgvector 없이** → 벡터를 저장/검색할 수 없으므로 시맨틱 검색 자체가 불가
- **Local embedding 없이** → OpenAI나 Ollama로 벡터를 생성하면 되므로 `sentence-transformers` 설치 불필요

즉, **pgvector는 필수**, Embedding Provider는 **3개 중 1개를 선택**합니다.

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  Settings (catalog_configuration)                       │
│  category = "embedding"                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │ embedding_enabled  = true                        │   │
│  │ embedding_provider = local | openai | ollama     │   │
│  │ embedding_model    = all-MiniLM-L6-v2            │   │
│  │ embedding_api_key  = (OpenAI 전용)               │   │
│  │ embedding_api_url  = (커스텀 엔드포인트)          │   │
│  │ embedding_dimension = 384                        │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  Embedding Provider Registry (singleton)                 │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │
│  │ LocalProvider   │ │ OpenAIProvider │ │ OllamaProvider│ │
│  │ sentence-       │ │ text-embedding │ │ all-minilm   │ │
│  │ transformers    │ │ -3-small       │ │ nomic-embed  │ │
│  │ (로컬 GPU/CPU)  │ │ (API 호출)     │ │ (로컬 API)   │ │
│  └────────────────┘ └────────────────┘ └──────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector                                   │
│  ┌────────────────────────────────────────────────────┐  │
│  │ catalog_dataset_embeddings                         │  │
│  │ ├─ dataset_id (FK, UNIQUE)                         │  │
│  │ ├─ embedding vector(384)  ← pgvector 타입          │  │
│  │ ├─ source_text            ← 임베딩 원본 텍스트     │  │
│  │ ├─ model_name             ← 사용된 모델            │  │
│  │ └─ provider               ← 사용된 프로바이더      │  │
│  └────────────────────────────────────────────────────┘  │
│  IVFFlat 인덱스 (코사인 유사도)                          │
└──────────────────────────────────────────────────────────┘
```

---

## 모듈 구조

```
app/
├── embedding/                     # 임베딩 프로바이더 시스템
│   ├── base.py                    # EmbeddingProvider 추상 클래스
│   ├── providers/
│   │   ├── local.py               # sentence-transformers (기본값)
│   │   ├── openai.py              # OpenAI API
│   │   └── ollama.py              # Ollama API
│   ├── registry.py                # 프로바이더 싱글톤 관리
│   ├── models.py                  # DatasetEmbedding ORM (pgvector)
│   └── service.py                 # 임베딩 생성/저장/백필/통계
├── search/
│   ├── schemas.py                 # 검색 API Pydantic 스키마
│   ├── service.py                 # 시맨틱/하이브리드 검색 로직
│   └── router.py                  # 검색 API 엔드포인트
└── settings/
    ├── service.py                 # 임베딩 설정 로드/시드
    └── router.py                  # 임베딩 설정 CRUD 엔드포인트
```

---

## 임베딩 프로바이더

### 1. Local (기본값)

로컬에서 sentence-transformers 모델을 실행합니다. 인터넷 불필요 (에어갭 환경 지원).

| 항목 | 값 |
|------|-----|
| 라이브러리 | `sentence-transformers` |
| 기본 모델 | `all-MiniLM-L6-v2` |
| 차원 | 384 |
| 크기 | ~80MB |
| 한국어 | `paraphrase-multilingual-MiniLM-L12-v2` 사용 시 지원 (~470MB) |
| 동작 방식 | `asyncio.run_in_executor`로 스레드 풀에서 실행 (이벤트 루프 비차단) |

**설정 예시:**
```json
{
  "embedding_enabled": "true",
  "embedding_provider": "local",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

**에어갭 배포:**
모델 파일을 서버에 미리 다운로드한 후 로컬 경로를 `embedding_model`에 지정:
```json
{
  "embedding_model": "/opt/models/all-MiniLM-L6-v2"
}
```

### 2. OpenAI API

OpenAI의 임베딩 API를 호출합니다. Azure OpenAI도 `api_url` 변경으로 지원.

| 항목 | 값 |
|------|-----|
| 기본 모델 | `text-embedding-3-small` |
| 차원 | 1536 |
| 요금 | ~$0.02 / 1M tokens |
| 한국어 | 지원 |

**설정 예시:**
```json
{
  "embedding_enabled": "true",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "embedding_api_key": "sk-...",
  "embedding_dimension": "1536"
}
```

**Azure OpenAI:**
```json
{
  "embedding_api_url": "https://my-resource.openai.azure.com/openai/deployments/my-embedding"
}
```

### 3. Ollama

로컬에서 실행되는 Ollama 인스턴스를 사용합니다.

| 항목 | 값 |
|------|-----|
| 기본 엔드포인트 | `http://localhost:11434` |
| 기본 모델 | `all-minilm` |
| 차원 | 모델에 따라 다름 (자동 감지) |
| 한국어 | `nomic-embed-text` 사용 시 지원 |

**설정 예시:**
```json
{
  "embedding_enabled": "true",
  "embedding_provider": "ollama",
  "embedding_model": "nomic-embed-text",
  "embedding_api_url": "http://localhost:11434"
}
```

---

## 임베딩 프로바이더별 검색 품질

카탈로그 메타데이터 검색은 비교적 단순한 의미 매칭이므로 프로바이더 간 체감 차이가 크지 않습니다.

| 모델 | MTEB 벤치마크 | 차원 | 한국어 | 에어갭 | 비용 |
|------|-------------|------|--------|--------|------|
| `all-MiniLM-L6-v2` | 56.3 | 384 | X | O | 무료 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 53.8 | 384 | O | O | 무료 |
| `bge-small-en-v1.5` | 62.2 | 384 | X | O | 무료 |
| `text-embedding-3-small` (OpenAI) | 62.3 | 1536 | O | X | $0.02/1M |
| `text-embedding-3-large` (OpenAI) | 64.6 | 3072 | O | X | $0.13/1M |
| `nomic-embed-text` (Ollama) | 62.4 | 768 | O | O | 무료 |

**권장:**
- 영문 위주 + 에어갭: `all-MiniLM-L6-v2` (기본값)
- 한국어 필요 + 에어갭: `paraphrase-multilingual-MiniLM-L12-v2`
- 최고 품질: `text-embedding-3-small` (OpenAI)
- 한국어 + 로컬 + 고품질: `nomic-embed-text` (Ollama)

---

## API 엔드포인트

### 검색 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/catalog/search/semantic?q=...` | 시맨틱 검색 |
| GET | `/api/v1/catalog/search/hybrid?q=...` | 하이브리드 검색 |

**시맨틱 검색:**
```
GET /api/v1/catalog/search/semantic?q=고객 구매 이력&limit=10&threshold=0.3
```

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `q` | (필수) | 검색 쿼리 (1~500자) |
| `limit` | 20 | 최대 결과 수 (1~100) |
| `threshold` | 0.3 | 최소 코사인 유사도 (0.0~1.0) |

**하이브리드 검색:**
```
GET /api/v1/catalog/search/hybrid?q=customer purchase&keyword_weight=0.3&semantic_weight=0.7
```

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `keyword_weight` | 0.3 | 키워드 매칭 가중치 |
| `semantic_weight` | 0.7 | 시맨틱 유사도 가중치 |

**응답 형식:**
```json
{
  "items": [
    {
      "dataset": {
        "id": 42,
        "name": "warehouse.fact_purchases",
        "platform_name": "MySQL",
        "description": "고객 구매 트랜잭션 테이블",
        "origin": "PROD",
        "tag_count": 3,
        "owner_count": 2
      },
      "score": 0.8234,
      "match_type": "semantic"
    }
  ],
  "total": 5,
  "query": "고객 구매 이력",
  "provider": "local",
  "model": "all-MiniLM-L6-v2"
}
```

### 임베딩 관리 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/catalog/search/embeddings/stats` | 임베딩 커버리지 통계 |
| POST | `/api/v1/catalog/search/embeddings/backfill` | 전체 데이터셋 일괄 임베딩 |
| DELETE | `/api/v1/catalog/search/embeddings` | 모든 임베딩 삭제 |

**커버리지 통계 응답:**
```json
{
  "total_datasets": 135,
  "embedded_datasets": 120,
  "coverage_pct": 88.9,
  "provider": "local",
  "model": "all-MiniLM-L6-v2",
  "dimension": 384
}
```

### 설정 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/settings/embedding` | 임베딩 설정 조회 |
| PUT | `/api/v1/settings/embedding` | 임베딩 설정 변경 + 프로바이더 재초기화 |
| POST | `/api/v1/settings/embedding/test` | 프로바이더 연결 테스트 |

**설정 조회/변경 스키마:**
```json
{
  "enabled": true,
  "provider": "local",
  "model": "all-MiniLM-L6-v2",
  "api_key": "",
  "api_url": "",
  "dimension": 384
}
```

---

## 임베딩 생성 흐름

### 자동 임베딩 (데이터셋 생성/수정 시)

```
POST /api/v1/catalog/datasets (데이터셋 생성)
    ↓
catalog/service.py create_dataset()
    ↓ DB 커밋 후
embedding/service.py embed_dataset_background(dataset_id)
    ↓ asyncio.create_task (비차단)
    ├─ build_source_text()  → "테이블명 | 설명 | 플랫폼 | 태그들 | 소유자들"
    ├─ provider.embed()     → [0.012, -0.034, ...]  (384차원 벡터)
    └─ UPSERT into catalog_dataset_embeddings
```

- API 응답은 즉시 반환 (임베딩은 백그라운드)
- 임베딩 실패 시 WARNING 로그만 남기고, 데이터셋 생성/수정에는 영향 없음
- `source_text`가 변경되지 않았으면 재임베딩 건너뜀 (중복 방지)

### 일괄 백필 (기존 데이터셋)

```
POST /api/v1/catalog/search/embeddings/backfill
    ↓
모든 active 데이터셋 순회
    ↓ 각 데이터셋마다
    ├─ source_text 생성 → 변경 여부 확인
    ├─ 변경 시 임베딩 생성 + UPSERT
    └─ 미변경 시 skip
    ↓
결과: {"total": 135, "embedded": 120, "skipped": 10, "errors": 5}
```

### 임베딩 소스 텍스트 구성

데이터셋의 다양한 메타데이터를 `|` 구분자로 결합:

```
{name} | {description} | {qualified_name} | {platform_name} | {platform_type} | {tag1} | {tag2} | {owner1}
```

예시:
```
fact_daily_sales | 일별 매출 집계 테이블 | warehouse.fact_daily_sales | Sakila MySQL | mysql | sales | analytics | data-team
```

---

## 프로바이더 전환

프로바이더를 변경하면 벡터 공간이 달라지므로 기존 임베딩을 재생성해야 합니다.

**전환 절차:**
1. `PUT /api/v1/settings/embedding` → 새 프로바이더 설정 저장 + 재초기화
2. `DELETE /api/v1/catalog/search/embeddings` → 기존 임베딩 삭제
3. `POST /api/v1/catalog/search/embeddings/backfill` → 새 프로바이더로 전체 재임베딩

**차원이 다를 경우** (예: local 384 → OpenAI 1536):
pgvector 컬럼의 차원을 변경해야 합니다:
```sql
ALTER TABLE catalog_dataset_embeddings
ALTER COLUMN embedding TYPE vector(1536);
```

---

## DB 스키마

### catalog_dataset_embeddings

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE catalog_dataset_embeddings (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL UNIQUE
        REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    source_text TEXT NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    dimension INT NOT NULL DEFAULT 384,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- IVFFlat 인덱스 (코사인 유사도 검색 최적화)
CREATE INDEX idx_dataset_embeddings_ivfflat
    ON catalog_dataset_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### catalog_configuration (embedding 카테고리)

| config_key | 기본값 | 설명 |
|-----------|--------|------|
| `embedding_enabled` | `false` | 시맨틱 검색 활성화 |
| `embedding_provider` | `local` | 프로바이더: `local`, `openai`, `ollama` |
| `embedding_model` | `all-MiniLM-L6-v2` | 모델 식별자 |
| `embedding_api_key` | (빈 값) | API 키 (OpenAI 전용) |
| `embedding_api_url` | (빈 값) | API URL 오버라이드 |
| `embedding_dimension` | `384` | 벡터 차원 |

---

## 의존성 및 설치

### 필수 의존성

```bash
pip install pgvector>=0.3.0      # SQLAlchemy pgvector 타입 (필수)
```

PostgreSQL에 pgvector 확장이 필요합니다:
```bash
# Ubuntu/Debian
sudo apt install postgresql-16-pgvector

# RHEL/Rocky Linux
sudo dnf install pgvector_16

# macOS (Homebrew)
brew install pgvector

# Docker (postgres 이미지에 포함된 pgvector 이미지 사용)
docker run -d pgvector/pgvector:pg16
```

설치 후 SQL에서 확장을 활성화합니다 (서버 시작 시 자동 실행됨):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### sentence-transformers 설치 (Local 프로바이더)

Local 프로바이더 사용 시에만 필요합니다. PyTorch를 포함하여 용량이 큽니다.

```bash
# 기본 설치 (CPU, ~2GB)
pip install sentence-transformers>=3.0.0

# GPU 지원 (CUDA 12.x)
pip install sentence-transformers>=3.0.0 torch --index-url https://download.pytorch.org/whl/cu121

# GPU 지원 (CUDA 11.8)
pip install sentence-transformers>=3.0.0 torch --index-url https://download.pytorch.org/whl/cu118
```

> OpenAI나 Ollama 프로바이더만 사용하는 경우 `sentence-transformers`를 설치하지 않아도 됩니다.
> 코드에서 lazy import를 사용하므로 설치되지 않은 상태에서도 서버가 정상 시작됩니다.

### 모델 다운로드

#### 온라인 환경

첫 임베딩 요청 시 모델이 자동으로 HuggingFace Hub에서 다운로드됩니다.
캐시 위치: `~/.cache/huggingface/hub/`

수동으로 미리 다운로드하려면:
```bash
# Python으로 다운로드
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# 한국어 모델
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
```

#### 에어갭 (오프라인) 환경

인터넷이 없는 환경에서는 모델 파일을 미리 다운로드하여 서버에 배포합니다.

**Step 1: 인터넷이 되는 머신에서 모델 다운로드**

```bash
# 방법 1: sentence-transformers로 다운로드
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
model.save('/tmp/all-MiniLM-L6-v2')
"

# 방법 2: huggingface-cli로 다운로드
pip install huggingface_hub
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir /tmp/all-MiniLM-L6-v2
```

**Step 2: 에어갭 서버로 전송**

```bash
# 압축
tar -czf all-MiniLM-L6-v2.tar.gz -C /tmp all-MiniLM-L6-v2

# USB/SCP 등으로 전송 후 압축 해제
tar -xzf all-MiniLM-L6-v2.tar.gz -C /opt/models/
```

**Step 3: 설정에서 로컬 경로 지정**

Settings > Embedding에서 Model 필드에 로컬 경로를 입력:
```
/opt/models/all-MiniLM-L6-v2
```

또는 API로 설정:
```bash
curl -X PUT http://localhost:4600/api/v1/settings/embedding \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "provider": "local",
    "model": "/opt/models/all-MiniLM-L6-v2",
    "dimension": 384
  }'
```

#### 모델별 다운로드 명령어

| 모델 | 용도 | 크기 | 다운로드 |
|------|------|------|---------|
| `all-MiniLM-L6-v2` | 영문 기본 | ~80MB | `SentenceTransformer('all-MiniLM-L6-v2')` |
| `paraphrase-multilingual-MiniLM-L12-v2` | 한국어+영문 | ~470MB | `SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')` |
| `bge-small-en-v1.5` | 영문 고품질 | ~130MB | `SentenceTransformer('BAAI/bge-small-en-v1.5')` |
| `bge-m3` | 다국어 고품질 | ~2.2GB | `SentenceTransformer('BAAI/bge-m3')` |

#### Ollama 모델 설치

Ollama 프로바이더 사용 시 모델을 미리 pull 해야 합니다:
```bash
# Ollama 설치 (https://ollama.com)
curl -fsSL https://ollama.com/install.sh | sh

# 모델 pull
ollama pull all-minilm           # 384d, ~23MB
ollama pull nomic-embed-text     # 768d, ~274MB
ollama pull mxbai-embed-large    # 1024d, ~670MB

# 동작 확인
curl http://localhost:11434/api/embeddings -d '{"model": "all-minilm", "prompt": "test"}'
```

에어갭 환경에서는 [Ollama 모델 파일을 수동으로 복사](https://github.com/ollama/ollama/blob/main/docs/import.md)하여 배포합니다.

---

## 서버 시작 시 동작

```python
# app/main.py lifespan 내:

# 1. pgvector 확장 활성화 (PostgreSQL)
#    CREATE EXTENSION IF NOT EXISTS vector

# 2. embedding 설정 시드 (최초 1회)
#    catalog_configuration에 embedding_* 키가 없으면 기본값 삽입

# 3. 임베딩 프로바이더 초기화
#    embedding_enabled=true인 경우에만 모델 로드
#    false이면 "Embedding is disabled" 로그 출력 후 건너뜀

# 4. 서버 종료 시 프로바이더 정리
#    shutdown_provider() 호출
```

---

## 커스텀 프로바이더 추가

`EmbeddingProvider` 추상 클래스를 구현하면 새로운 프로바이더를 추가할 수 있습니다.

```python
# app/embedding/providers/my_provider.py
from app.embedding.base import EmbeddingProvider

class MyProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 벡터 생성 로직
        ...

    def dimension(self) -> int:
        return 768

    def model_name(self) -> str:
        return "my-custom-model"

    def provider_name(self) -> str:
        return "custom"
```

그 후 `app/embedding/registry.py`의 `initialize_provider()`에 분기를 추가합니다.

---

## 문제 해결

### 임베딩이 생성되지 않음
- `GET /api/v1/settings/embedding` → `enabled`가 `true`인지 확인
- `GET /api/v1/catalog/search/embeddings/stats` → `provider`가 `null`이면 프로바이더 미초기화

### 검색 결과가 없음
- `embeddings/stats`에서 `embedded_datasets`가 0이면 → `POST /embeddings/backfill` 실행
- `threshold`를 낮추기 (기본 0.3 → 0.1)

### 로컬 프로바이더 로드 실패

**`RuntimeError: sentence-transformers is required`**
```bash
pip install sentence-transformers>=3.0.0
```

**`OSError: Can't load model 'all-MiniLM-L6-v2'` (에어갭 환경)**
```bash
# 온라인 머신에서 다운로드 후 전송
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2').save('/tmp/all-MiniLM-L6-v2')"
# 서버에 복사 후 Settings에서 모델 경로를 /opt/models/all-MiniLM-L6-v2 로 변경
```

**`torch.cuda.OutOfMemoryError` (GPU 메모리 부족)**
```bash
# CPU 모드로 강제 전환
export CUDA_VISIBLE_DEVICES=""
# 또는 더 작은 모델 사용 (all-MiniLM-L6-v2 → 80MB)
```

### pgvector 확장 미설치

**`ERROR: type "vector" does not exist`**
```bash
# PostgreSQL 버전에 맞는 pgvector 설치
sudo apt install postgresql-16-pgvector    # Debian/Ubuntu
sudo dnf install pgvector_16               # RHEL/Rocky
```

설치 후 슈퍼유저로 확장을 활성화해야 합니다:
```bash
sudo -u postgres psql -d argus_catalog -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
> 일반 DB 사용자(`argus`)로는 `CREATE EXTENSION`을 실행할 수 없습니다.
> `InsufficientPrivilegeError: 확장 모듈을 만들 권한이 없습니다` 에러가 발생하면
> 반드시 `postgres` 슈퍼유저로 실행하세요.

### embedding 컬럼이 text 타입으로 생성됨

pgvector 확장을 설치하기 **전에** 서버가 시작되면 SQLAlchemy `create_all()`이
`vector(384)` 타입을 인식하지 못하고 `text` 타입으로 fallback하여 테이블을 생성합니다.
이 경우 검색 시 다음 에러가 발생합니다:

**`ERROR: 연산자 없음: text <=> vector`**

해결 방법:
```bash
# 1. pgvector 확장 설치 (위 참고)

# 2. 기존 데이터 삭제 후 컬럼 타입 변경
sudo -u postgres psql -d argus_catalog -c "
DELETE FROM catalog_dataset_embeddings;
ALTER TABLE catalog_dataset_embeddings
  ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384);
"

# 3. 백필로 임베딩 재생성
curl -X POST http://localhost:4600/api/v1/catalog/search/embeddings/backfill
```

> **권장 설치 순서:** pgvector 확장 설치 → 서버 시작 (테이블 자동 생성)
> 이 순서를 따르면 이 문제가 발생하지 않습니다.

### SQLAlchemy text()에서 ::vector 캐스트 구문 에러

**`PostgresSyntaxError: 구문 오류, ":" 부근`**

SQLAlchemy `text()` 안에서 PostgreSQL의 `::vector` 타입 캐스트를 사용하면,
`::`가 바인드 파라미터 `:param`의 `:`와 충돌합니다.

```python
# 잘못된 예 — :: 가 파라미터 구문과 충돌
text("e.embedding <=> :query_vec::vector")

# 올바른 예 — CAST() 함수 사용
text("e.embedding <=> CAST(:query_vec AS vector)")
```

### 프로바이더 변경 후 검색 품질 저하
- 기존 임베딩 삭제 → 백필 필요 (다른 벡터 공간)
- 차원이 다르면 pgvector 컬럼 ALTER 필요:
  ```sql
  ALTER TABLE catalog_dataset_embeddings ALTER COLUMN embedding TYPE vector(1536);
  ```
