# RAG 제품 로드맵 — 프로덕션 기능 설계

현재 argus-rag-server가 갖춘 기능을 기준으로, 프로덕션 RAG 제품이 되기 위해 필요한 전체 기능을 정리합니다.

---

## 현재 구현 상태 vs 프로덕션 제품 Gap

| 영역 | 현재 (argus-rag-server) | 프로덕션 제품에 필요한 것 |
|------|------------------------|------------------------|
| **데이터 수집** | 3종 (Catalog API, DB Query, HTTP) | +파일 업로드, Git, S3, Confluence, Slack, Email |
| **청킹** | 4전략 (single/paragraph/fixed/sliding) | +Semantic chunking, 코드 청킹, 테이블 청킹 |
| **임베딩** | 3 Provider (Local/OpenAI/Ollama) | +배치 큐, 증분 임베딩, 멀티 모델 |
| **검색** | 하이브리드 (keyword + semantic) | +Reranker, 필터링, 멀티 테넌시 |
| **저장** | pgvector only | +Qdrant, Milvus, Pinecone 백엔드 교체 |
| **관리** | 기본 CRUD + 동기화 | +스케줄러, 버저닝, 접근 제어 |
| **품질** | 없음 | 검색 품질 평가, A/B 테스트 |
| **운영** | 기본 로그 | 모니터링, 알림, 사용량 추적 |

---

## 1. Data Ingestion (데이터 수집)

### 커넥터 전체 목록

| 카테고리 | 커넥터 | 설명 |
|----------|--------|------|
| **Database** | MySQL, PostgreSQL, Oracle, MSSQL, MongoDB | SQL 쿼리 기반, 증분 sync (`WHERE updated_at > ?`) |
| **API** | REST API (JSON), GraphQL, gRPC | Pagination 자동 처리, 인증 (OAuth, API Key) |
| **File** | PDF, DOCX, PPTX, XLSX, CSV, TXT, Markdown | 파일 업로드, S3/MinIO/GCS 경로 스캔 |
| **Code** | Git Repository (Python, Java, SQL, YAML) | 파일별 청킹, 함수/클래스 단위 분할 |
| **Collaboration** | Confluence, Notion, Google Docs | 페이지별 수집, 첨부파일 포함 |
| **Messaging** | Slack, Microsoft Teams | 채널별 수집, 스레드 단위 문서화 |
| **Catalog** | argus-catalog-server, DataHub, OpenMetadata | 메타데이터 + 스키마 + 리니지 정보 |

### 핵심 기능

| 기능 | 설명 |
|------|------|
| **증분 동기화** | `last_modified > last_sync_at` 조건으로 변경분만 수집 |
| **변경 감지** | 소스 텍스트 해시 비교 → 변경된 문서만 재청킹/재임베딩 |
| **스케줄러** | Cron 기반 자동 동기화 (매시간, 매일, 매주) |
| **Webhook** | 소스 시스템에서 변경 시 실시간 트리거 |
| **Dead Letter Queue** | 수집 실패 항목을 DLQ에 저장, 재시도 관리 |
| **파일 파서** | PDF (OCR 포함), DOCX, PPTX, XLSX → 텍스트 추출 |
| **멀티 소스 매핑** | 하나의 Collection에 여러 소스를 동시에 연결 |

---

## 2. Chunking (청킹 — 문서 분할)

### 전략별 적합한 데이터 유형

| Strategy | Best For | 현재 상태 |
|----------|----------|----------|
| Single | 짧은 메타데이터 (제목+설명, < 500자) | ✅ 구현됨 |
| Paragraph | 일반 문서, 기술 문서 | ✅ 구현됨 |
| Fixed Size | 로그, 코드, 균일한 길이 필요 시 | ✅ 구현됨 |
| Sliding Window | 긴 문서에서 맥락 손실 방지 | ✅ 구현됨 |
| **Semantic** | 의미 단위로 분할 (문단 경계 + 유사도) | ❌ 미구현 |
| **Sentence** | FAQ, QA 데이터 | ❌ 미구현 |
| **Recursive** | Markdown/HTML 구조 기반 | ❌ 미구현 |
| **Code** | 함수/클래스/메서드 단위 | ❌ 미구현 |
| **Table** | CSV, XLSX → 행 단위 또는 셀 단위 | ❌ 미구현 |
| **Parent-Child** | 작은 청크로 검색 + 큰 청크로 컨텍스트 | ❌ 미구현 |

### Parent-Child Chunking (가장 중요한 고급 전략)

```
문서: "제1장: 데이터 파이프라인 설계\n1.1 ETL vs ELT\n..."
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  [Parent Chunk]   [Parent Chunk]   [Parent Chunk]
  "제1장 전체"     "제2장 전체"     "제3장 전체"
        │               │
   ┌────┼────┐     ┌────┼────┐
   ▼    ▼    ▼     ▼    ▼    ▼
 [Child] [Child] [Child] ...
 "1.1"  "1.2"   "1.3"

검색: Child 청크로 정밀 매칭 → Parent 청크를 LLM에 전달 (넓은 컨텍스트)
```

---

## 3. Embedding (임베딩)

| 기능 | 설명 | 현재 상태 |
|------|------|----------|
| 멀티 모델 | Collection별 다른 임베딩 모델 사용 가능 | ✅ 구현됨 |
| 3 Provider | Local SentenceTransformer, OpenAI, Ollama | ✅ 구현됨 |
| **배치 큐** | 대량 임베딩 작업을 백그라운드 큐로 처리 (Celery/RQ) | ❌ 미구현 |
| **증분 임베딩** | 변경된 청크만 재임베딩 (소스 텍스트 해시 비교) | ❌ 미구현 |
| **차원 정규화** | 다른 차원의 임베딩을 같은 인덱스에서 검색 (Matryoshka) | ❌ 미구현 |
| **캐싱** | 동일 텍스트 재임베딩 방지 (해시 → 벡터 캐시) | ❌ 미구현 |
| **토큰 추적** | OpenAI 등 유료 API 사용량 추적 및 비용 계산 | ❌ 미구현 |
| **Rate Limiting** | API 호출 제한 관리 (OpenAI RPM/TPM) | ❌ 미구현 |
| **Sparse Embedding** | BM25/SPLADE 기반 희소 벡터 (하이브리드 정밀도 향상) | ❌ 미구현 |

### Embedding Pipeline

```
Document → [Changed?] → [Chunk] → [Token Count] → [Rate Limit Check]
                                        ↓
                              [Batch Queue (64 at a time)]
                                        ↓
                              [Provider API / Local Model]
                                        ↓
                              [Vector Store (upsert)]
                                        ↓
                              [Usage Tracking (tokens, cost)]
```

---

## 4. Vector Storage (벡터 저장)

### 벡터 DB 백엔드 옵션

| Backend | 적합 규모 | 특징 | 현재 상태 |
|---------|----------|------|----------|
| **pgvector** | ~100만 | HNSW 인덱스, PostgreSQL 내장 | ✅ 기본 |
| **Qdrant** | 100만+ | 전용 벡터 DB, 필터링 우수 | ❌ 미구현 |
| **Milvus** | 10억+ | GPU 가속, 분산 클러스터 | ❌ 미구현 |
| **Weaviate** | 100만+ | 멀티 모달 (텍스트 + 이미지) | ❌ 미구현 |
| **Pinecone** | 서버리스 | 관리형, 클라우드 전용 | ❌ 미구현 |
| **Elasticsearch** | 100만+ | 기존 ELK 인프라 활용 (kNN) | ❌ 미구현 |

### 추상화 인터페이스

```python
class VectorStore(ABC):
    async def upsert(self, collection: str, vectors: list[VectorRecord])
    async def search(self, collection: str, query_vec: list[float],
                     filters: dict, top_k: int) -> list[SearchResult]
    async def delete(self, collection: str, ids: list[str])
    async def count(self, collection: str) -> int
```

---

## 5. Search & Retrieval (검색)

### 검색 기능 전체 목록

| 기능 | 설명 | 중요도 | 현재 상태 |
|------|------|--------|----------|
| Semantic Search | 벡터 유사도 검색 (cosine) | 기본 | ✅ 구현됨 |
| Keyword Search | BM25 / ILIKE 전문 검색 | 기본 | ✅ 구현됨 |
| Hybrid Search | 키워드 + 시맨틱 가중치 합산 | 기본 | ✅ 구현됨 |
| Multi-Collection | 여러 Collection 동시 검색 | 기본 | ✅ 구현됨 |
| **Reranker** | 1차 검색 결과를 Cross-Encoder로 재정렬 | **핵심** | ❌ 미구현 |
| **Metadata Filter** | `platform_type=mysql AND status=active` 필터 | **핵심** | ❌ 미구현 |
| **MMR** | Maximal Marginal Relevance — 결과 다양성 보장 | 중요 | ❌ 미구현 |
| **Query Expansion** | 사용자 쿼리를 LLM으로 확장/변환 | 중요 | ❌ 미구현 |
| **Query Routing** | 쿼리 유형에 따라 다른 Collection으로 라우팅 | 중요 | ❌ 미구현 |
| **Contextual Compression** | 검색 결과에서 쿼리 관련 부분만 추출 | 고급 | ❌ 미구현 |
| **Self-Query** | 자연어 → 메타데이터 필터 자동 변환 | 고급 | ❌ 미구현 |
| **Time Decay** | 최신 문서에 가중치 부여 | 고급 | ❌ 미구현 |

### Reranker가 핵심인 이유

```
Without Reranker:
  Query: "고객 주문 취소 프로세스"
  Top 3: [주문(0.56), 발주(0.53), 매출(0.49)]  ← 관련도 낮은 결과 포함

With Reranker (Cross-Encoder):
  1차 검색: Top 20 후보
  2차 재정렬: Cross-Encoder가 (query, document) 쌍을 직접 비교
  Top 3: [주문취소정책(0.92), 환불프로세스(0.87), 주문상태변경(0.83)]  ← 정밀
```

### Metadata Filter 구조

```json
{
  "query": "고객 매출 집계",
  "filters": {
    "collection": ["catalog_datasets", "glossary_terms"],
    "metadata": {
      "platform_type": {"$in": ["mysql", "postgresql"]},
      "status": {"$eq": "active"},
      "created_at": {"$gte": "2026-01-01"}
    }
  },
  "top_k": 10,
  "rerank": true,
  "mmr_lambda": 0.7
}
```

---

## 6. Document Management (문서 관리)

| 기능 | 설명 |
|------|------|
| **버저닝** | 문서 변경 이력 추적, 이전 버전 롤백 |
| **태깅** | 문서에 태그 부여 → 필터 검색에 활용 |
| **만료(TTL)** | 일정 기간 후 자동 삭제 (로그, 임시 데이터) |
| **중복 탐지** | 유사도 기반 중복 문서 감지 → 경고 또는 자동 병합 |
| **문서 상태** | draft → active → archived → deleted 라이프사이클 |
| **접근 제어** | Collection/Document 단위 RBAC (읽기/쓰기/관리) |
| **감사 로그** | 누가 언제 어떤 문서를 수정했는지 추적 |

---

## 7. API & Integration (API 및 통합)

### API 레이어

```
REST API (현재)
├── /collections — CRUD
├── /documents — Ingest, bulk, CRUD
├── /search — semantic, keyword, hybrid
├── /sync — trigger, preview
└── /settings — embedding, chunking

SDK (Python) ★
├── rag_client = RagClient("http://rag:4800")
├── results = rag_client.search("고객 주문", top_k=5)
└── rag_client.ingest(collection="docs", text="...", ...)

SDK (TypeScript) ★
├── const rag = new RagClient("http://rag:4800")
└── const results = await rag.search("query")

LangChain Integration ★
├── from argus_rag import ArgusRetriever
└── retriever = ArgusRetriever(base_url="http://rag:4800")

LlamaIndex Integration ★
└── vector_store = ArgusVectorStore(...)

OpenAI-Compatible API ★
└── /v1/embeddings — OpenAI 호환 임베딩 API

Webhook Outbound ★
└── 문서 변경/동기화 완료 시 외부 시스템에 알림
```

---

## 8. Quality & Evaluation (품질 평가)

| 기능 | 설명 |
|------|------|
| **Ground Truth 관리** | 질문-정답 쌍 데이터셋 관리 |
| **자동 평가** | Recall@K, MRR, NDCG 메트릭 자동 계산 |
| **A/B 테스트** | 임베딩 모델 / 청킹 전략 / 검색 파라미터 비교 |
| **사용자 피드백** | 검색 결과에 대한 thumbs up/down |
| **피드백 루프** | 부정 피드백 → 자동으로 검색 품질 개선 |
| **검색 로그 분석** | 자주 검색되는 쿼리, 결과 없는 쿼리 분석 |
| **청킹 시뮬레이터** | 동일 문서를 다른 전략으로 청킹 → 결과 비교 |

### Evaluation Dashboard

```
┌─────────────────────────────────────────────────────┐
│  Search Quality Report                               │
│                                                       │
│  Dataset: "qa_golden_set" (150 Q&A pairs)            │
│                                                       │
│  ┌─────────────────────────────────┐                 │
│  │ Configuration A (current)       │                 │
│  │ Model: multilingual-MiniLM      │                 │
│  │ Chunk: paragraph (512)          │                 │
│  │ Recall@5: 78.2%                 │                 │
│  │ MRR: 0.692                      │                 │
│  └─────────────────────────────────┘                 │
│           vs                                          │
│  ┌─────────────────────────────────┐                 │
│  │ Configuration B (candidate)     │                 │
│  │ Model: bge-m3 + Reranker       │                 │
│  │ Chunk: semantic (512)           │                 │
│  │ Recall@5: 91.4% (+13.2%)       │                 │
│  │ MRR: 0.847 (+22.4%)            │                 │
│  └─────────────────────────────────┘                 │
│                                                       │
│  [Apply Configuration B to Production]               │
└─────────────────────────────────────────────────────┘
```

---

## 9. Operations & Monitoring (운영)

| 기능 | 설명 | 현재 상태 |
|------|------|----------|
| 대시보드 | 전체 통계, 검색 성능, 임베딩 커버리지 | ✅ 기본 구현 |
| 작업 이력 | 동기화/임베딩 작업 로그 | ✅ 기본 구현 |
| **알림** | 동기화 실패, 임베딩 오류, 저장소 부족 시 알림 | ❌ 미구현 |
| **검색 성능** | p50/p95/p99 응답 시간, QPS 추적 | ❌ 미구현 |
| **사용량** | 일별 검색 횟수, 임베딩 토큰 사용량, API 비용 | ❌ 미구현 |
| **인덱스 상태** | 벡터 인덱스 크기, 메모리 사용, fragmentation | ❌ 미구현 |
| **백업/복원** | Collection 단위 export/import (벡터 포함) | ❌ 미구현 |
| **Health Check** | 임베딩 모델, 벡터 DB, 소스 연결 상태 점검 | ✅ 기본 구현 |

---

## 10. Security & Multi-tenancy (보안)

| 기능 | 설명 |
|------|------|
| **인증** | JWT, API Key, OAuth2, Keycloak OIDC |
| **RBAC** | Collection 단위 역할 기반 접근 제어 |
| **멀티 테넌시** | 조직/팀별 격리된 Collection 관리 |
| **데이터 암호화** | 벡터 저장 시 암호화 (at rest) |
| **PII 탐지** | 임베딩 전 개인정보 자동 감지/마스킹 |
| **감사 로그** | 모든 API 호출 기록 |
| **Rate Limiting** | 사용자/API Key별 요청 제한 |

---

## 11. Advanced RAG Patterns (고급 RAG 패턴)

| 패턴 | 설명 | 복잡도 |
|------|------|--------|
| **Naive RAG** | 단순 검색 → LLM에 전달 | 현재 수준 |
| **Advanced RAG** | Reranker + Metadata Filter + Query Expansion | 중 |
| **Modular RAG** | 검색/생성/피드백 모듈을 조합하여 파이프라인 구성 | 중 |
| **Agentic RAG** | Agent가 검색 전략을 동적으로 결정 | 상 |
| **Graph RAG** | 지식 그래프 + 벡터 검색 결합 | 상 |
| **Multi-Modal RAG** | 텍스트 + 이미지 + 테이블을 동시에 검색 | 상 |
| **Corrective RAG** | 검색 결과가 부적절하면 자동으로 재검색 | 상 |

### Agentic RAG 흐름

```
User: "지난달 매출 상위 10개 제품의 ETL 파이프라인 상태는?"
                │
                ▼
        [Query Analyzer]
         "복합 질의 감지 — 2단계 검색 필요"
                │
         ┌──────┴──────┐
         ▼             ▼
  [1차: 제품 검색]  [2차: 파이프라인 검색]
  Collection:       Collection:
  catalog_datasets  pipeline_docs
  Filter:           Filter:
  tag=매출          status=active
         │             │
         └──────┬──────┘
                ▼
         [Reranker]
                ▼
         [Contextual Compression]
                ▼
         [LLM Response]
```

---

## 구현 우선순위 로드맵

| Phase | 기능 | 가치 | 예상 규모 |
|-------|------|------|----------|
| **Phase 1** ✅ | Collection CRUD, 3종 커넥터, 4종 청킹, 하이브리드 검색 | MVP | 완료 |
| **Phase 2** | Reranker, Metadata Filter, 파일 업로드 (PDF/DOCX) | **검색 품질 대폭 향상** | 중 |
| **Phase 3** | 스케줄러, 증분 동기화, 변경 감지, Webhook | 자동화 | 중 |
| **Phase 4** | Semantic Chunking, Parent-Child, Query Expansion | 고급 검색 | 중 |
| **Phase 5** | 벡터 DB 추상화 (Qdrant/Milvus), Python/TS SDK | 확장성 | 대 |
| **Phase 6** | 품질 평가 (Ground Truth, Recall@K, A/B), 피드백 루프 | 지속 개선 | 대 |
| **Phase 7** | 멀티 테넌시, RBAC, PII 탐지, 감사 로그 | 엔터프라이즈 | 대 |
| **Phase 8** | Graph RAG, Agentic RAG, Multi-Modal | 차별화 | 대 |

### 가장 ROI가 높은 다음 단계

**Phase 2 (Reranker + Metadata Filter + 파일 업로드)** — 검색 정확도를 ~30% 향상시키면서 사용자가 바로 체감할 수 있는 기능들입니다.

- **Reranker**: Cross-Encoder 모델(`cross-encoder/ms-marco-MiniLM-L-6-v2`)로 2차 재정렬 → 정밀도 대폭 향상
- **Metadata Filter**: 검색 시 `platform_type`, `status`, `created_at` 등으로 필터링 → 불필요한 결과 제거
- **파일 업로드**: PDF/DOCX/XLSX 직접 업로드 → 가장 많이 요청되는 사용자 기능

---

## 경쟁 제품 참고

| 제품 | 특징 | 참고할 점 |
|------|------|----------|
| **LangChain** | RAG 파이프라인 프레임워크 | 모듈 조합 패턴, Retriever 추상화 |
| **LlamaIndex** | 데이터 프레임워크 | 인덱싱 전략, Query Engine |
| **Pinecone** | 관리형 벡터 DB | Serverless, Metadata Filter UX |
| **Weaviate** | 오픈소스 벡터 DB | 멀티 모달, GraphQL API |
| **Qdrant** | 오픈소스 벡터 DB | 필터링 성능, Rust 기반 속도 |
| **Vectara** | RAG-as-a-Service | End-to-end RAG API, 품질 평가 |
| **Cohere** | RAG + Reranker | Rerank API, 다국어 임베딩 |

### 차별화 포인트

1. **Data Catalog 네이티브 통합**: argus-catalog-server와의 긴밀한 연동으로 데이터 메타데이터를 자동으로 RAG에 활용
2. **DB Query 직접 임베딩**: SQL 쿼리 결과를 직접 임베딩하는 기능은 대부분의 RAG 제품에 없음
3. **Data Engineer 특화**: ETL 코드, 파이프라인 설정, 데이터 품질 정보 등 DE 도메인에 최적화된 검색
4. **Airgap 지원**: 로컬 SentenceTransformer + pgvector로 완전 오프라인 운영 가능
