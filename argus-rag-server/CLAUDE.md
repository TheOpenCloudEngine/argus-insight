# RAG Server

Argus 플랫폼의 **임베딩, 인덱싱, 시맨틱 검색 서비스**입니다. 여러 종류의 데이터를 Collection 단위로 관리하며, 다양한 소비자(DE Agent, Catalog UI, 통합 검색)에게 벡터 검색 API를 제공합니다.

## 핵심 기능

- **Collection 관리**: 데이터 그룹 단위 CRUD, Collection별 임베딩 모델/청킹 설정
- **Document Ingest**: 단일/벌크 문서 수집, 자동 청킹 (paragraph/fixed/sliding)
- **임베딩**: SentenceTransformer(로컬), OpenAI, Ollama 지원, 배치 처리
- **시맨틱 검색**: pgvector cosine similarity, 멀티 Collection 검색
- **하이브리드 검색**: 키워드 + 시맨틱 가중치 합산
- **데이터 소스**: Catalog API 커넥터 (datasets, models, glossary, standards)
- **동기화**: 수동 트리거, 소스별/Collection별 sync + 자동 임베딩

## 기술 스택

- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy 2.0 (async), PostgreSQL + pgvector
- SentenceTransformer / OpenAI / Ollama 임베딩
- httpx (외부 API 호출)

## 프로젝트 구조

```
argus-rag-server/
├── app/
│   ├── main.py                  # FastAPI 엔트리포인트 (port 4800)
│   ├── core/                    # 공통 인프라 (config, database, auth, logging)
│   ├── collection/              # Collection + Document CRUD
│   │   ├── router.py            # REST API
│   │   ├── service.py           # 비즈니스 로직
│   │   ├── schemas.py           # Pydantic 모델
│   │   └── chunker.py           # 청킹 전략 (paragraph/fixed/sliding)
│   ├── embedding/               # 임베딩 서비스
│   │   ├── base.py              # EmbeddingProvider ABC
│   │   ├── registry.py          # 싱글톤 관리
│   │   ├── service.py           # embed_collection, clear, stats
│   │   └── providers/           # Local, OpenAI, Ollama
│   ├── search/                  # 검색 서비스
│   │   ├── router.py            # /semantic, /keyword, /hybrid
│   │   └── service.py           # 멀티 Collection 검색
│   ├── source/                  # 데이터 소스 커넥터
│   │   ├── base.py              # SourceConnector ABC
│   │   ├── catalog_connector.py # Catalog API 연동
│   │   ├── sync_service.py      # 동기화 오케스트레이터
│   │   └── router.py            # Sync 트리거 API
│   ├── models/                  # ORM (Collection, Document, Chunk, DataSource, SyncJob)
│   └── settings/                # 설정 API (Embedding, Chunking)
├── packaging/config/
└── pyproject.toml
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 (임베딩 상태 포함) |
| GET | /api/v1/stats | 전체 대시보드 통계 |
| GET | /api/v1/collections | Collection 목록 |
| POST | /api/v1/collections | Collection 생성 |
| GET | /api/v1/collections/{id} | Collection 상세 |
| PUT | /api/v1/collections/{id} | Collection 수정 |
| DELETE | /api/v1/collections/{id} | Collection 삭제 |
| GET | /api/v1/collections/{id}/documents | Document 목록 |
| POST | /api/v1/collections/{id}/documents | Document 수집 (단일) |
| POST | /api/v1/collections/{id}/documents/bulk | Document 벌크 수집 |
| GET | /api/v1/collections/{id}/sources | DataSource 목록 |
| POST | /api/v1/collections/{id}/sources | DataSource 등록 |
| GET | /api/v1/collections/{id}/jobs | SyncJob 이력 |
| GET | /api/v1/search/semantic | 시맨틱 검색 |
| GET | /api/v1/search/keyword | 키워드 검색 |
| GET | /api/v1/search/hybrid | 하이브리드 검색 |
| POST | /api/v1/search/collections/{id}/embed | 임베딩 생성 |
| DELETE | /api/v1/search/collections/{id}/embeddings | 임베딩 초기화 |
| GET | /api/v1/search/collections/{id}/stats | 임베딩 통계 |
| POST | /api/v1/sync/sources/{id} | DataSource 동기화 |
| POST | /api/v1/sync/collections/{id} | Collection 전체 동기화 |
| GET | /api/v1/settings/embedding | 임베딩 설정 조회 |
| PUT | /api/v1/settings/embedding | 임베딩 설정 변경 |
| GET | /api/v1/settings/chunking | 청킹 설정 조회 |
| PUT | /api/v1/settings/chunking | 청킹 설정 변경 |

## 주요 명령어

```bash
make dev    # pip install -e ".[dev]"
make run    # uvicorn (port 4800)
make lint   # ruff check
make format # ruff format
```

## 코딩 규칙

- ruff: `target-version = "py311"`, `line-length = 100`
- 기본 포트: **4800**
