# Data Engineer AI Agent

Data Engineer의 업무를 도와주는 AI Agent입니다. 자연어 프롬프트를 입력하면 Argus Data Catalog의 메타데이터를 활용하여 데이터 엔지니어링 작업을 수행합니다.

## 핵심 기능

- **ReAct Agent**: Reason → Act → Observe 루프 기반 자율형 에이전트
- **Catalog 연동**: argus-catalog-server API를 통해 데이터셋, 스키마, 리니지, 품질 정보 활용
- **Tool-use**: LLM의 native tool_use를 활용한 안정적인 도구 호출
- **코드 생성**: SQL, PySpark, DDL 등 플랫폼별 코드 생성 (Phase 2)
- **승인 플로우**: 읽기는 자동, 쓰기/실행은 사용자 승인 필요

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async)
- httpx (Catalog API 클라이언트, LLM API 클라이언트)
- Pydantic v2

## 프로젝트 구조

```
argus-data-engineer-ai-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 엔트리포인트
│   ├── core/                    # 공통 인프라 (config, database, auth, logging)
│   ├── agent/                   # ★ Agent 엔진
│   │   ├── engine.py            # ReAct 루프 (핵심)
│   │   ├── session.py           # 대화 세션 관리
│   │   └── prompts/             # 시스템 프롬프트
│   ├── llm/                     # LLM Provider (tool_use 지원)
│   │   ├── base.py              # AgentLLMProvider ABC
│   │   ├── registry.py          # 싱글톤 관리
│   │   └── providers/           # Anthropic, OpenAI, Ollama
│   ├── tools/                   # Agent 도구 (31개)
│   │   ├── base.py              # BaseTool ABC, SafetyLevel (6단계)
│   │   ├── registry.py          # ToolRegistry (승인 판단)
│   │   ├── setup.py             # 전체 도구 등록
│   │   ├── catalog/             # Catalog API 연동 도구 (21개)
│   │   ├── codegen/             # 코드 생성 도구 (4개: SQL, PySpark, DDL, Pipeline)
│   │   ├── execution/           # 실행 도구 (6개: SQL실행, 미리보기, 검증, 파일관리)
│   │   └── analysis/            # 분석 도구 (Phase 4)
│   ├── connectors/              # DB 커넥터 프레임워크
│   │   ├── base.py              # DBConnector ABC, QueryResult
│   │   ├── mysql.py             # MySQL/MariaDB (aiomysql, read-only)
│   │   ├── postgresql.py        # PostgreSQL (asyncpg, read-only)
│   │   └── factory.py           # 플랫폼 → 커넥터 팩토리
│   ├── catalog_client/          # argus-catalog-server HTTP 클라이언트
│   ├── models/                  # ORM 모델 (대화 이력)
│   └── router/                  # API 라우터 (chat, settings)
├── packaging/config/
│   ├── config.yml
│   └── config.properties
├── pyproject.toml
└── Makefile
```

## 주요 명령어

```bash
cd argus-data-engineer-ai-agent
make dev      # pip install -e ".[dev]"
make run      # uvicorn --reload (port 4700)
make test     # pytest
make lint     # ruff check
make format   # ruff format
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 (LLM 상태 포함) |
| POST | /api/v1/chat | 메인 대화 API |
| POST | /api/v1/chat/{session_id}/approve | 도구 실행 승인/거부 |
| GET | /api/v1/chat/sessions | 세션 목록 |
| GET | /api/v1/chat/sessions/{session_id} | 세션 상세 |
| DELETE | /api/v1/chat/sessions/{session_id} | 세션 삭제 |
| WS | /api/v1/chat/ws | WebSocket 스트리밍 |
| GET | /api/v1/settings/llm | LLM 설정 조회 |
| PUT | /api/v1/settings/llm | LLM 설정 변경 |
| GET | /api/v1/settings/agent | Agent 설정 조회 |
| PUT | /api/v1/settings/agent | Agent 설정 변경 |

## Agent Tools (21개)

### Catalog 조회 (Auto — 자동 실행)
- `search_datasets` — 하이브리드 검색 (키워드 + 시맨틱)
- `get_dataset_detail` — 데이터셋 상세 정보
- `get_dataset_schema` — 컬럼/필드 스키마
- `get_dataset_lineage` — 리니지 그래프
- `get_platform_config` — 플랫폼 연결 설정
- `get_platform_metadata` — 플랫폼 기능/데이터타입
- `list_pipelines` — 파이프라인 목록
- `get_quality_profile` — 품질 프로파일
- `get_quality_score` — 품질 점수
- `get_catalog_stats` — 카탈로그 통계
- `search_glossary` — 비즈니스 용어 검색

### 데이터 표준 준수 검사 (Auto / Approve Write)
- `list_standard_dictionaries` — 표준 사전 목록 조회 (Auto)
- `search_standard_terms` — 표준 용어 검색 (Auto)
- `analyze_standard_term` — 용어 형태소 분석 및 표준 물리명 생성 (Auto)
- `check_dataset_compliance` — 데이터셋 표준 준수율 확인 (Auto)
- `get_dataset_term_mapping` — 컬럼별 표준 용어 매핑 상세 조회 (Auto)
- `auto_map_dataset` — 데이터셋 컬럼-표준 용어 자동 매핑 (Approve Write)

### 코드 생성 (Auto — 자동 실행, 컨텍스트 수집만)
- `generate_sql` — SQL 쿼리 생성 (SELECT, JOIN, MERGE 등 + 플랫폼별 방언)
- `generate_pyspark` — PySpark ETL 코드 생성 (JDBC 드라이버/URL 포함)
- `generate_ddl` — CREATE TABLE DDL 생성 (플랫폼 간 타입 변환)
- `generate_pipeline_config` — Airflow DAG / Kestra Flow 생성

### 데이터 미리보기 (Auto Read)
- `preview_data` — 소스 DB에서 샘플 데이터 조회 (LIMIT 10)

### 품질/검증 실행 (Approve — 승인 필요)
- `run_profiling` — 소스 DB 프로파일링 실행
- `run_quality_check` — 품질 규칙 검사 실행
- `validate_sql` — SQL 구문 검증 (EXPLAIN)

### SQL 실행 (Approve Exec — 승인 필요)
- `execute_sql` — 소스 DB에 SELECT 쿼리 실행 (DML/DDL 차단, 최대 500행)

### 파일 관리
- `write_file` — 생성된 코드를 워크스페이스에 저장 (Approve Write)
- `read_file` — 워크스페이스 파일 읽기 (Auto)
- `list_files` — 워크스페이스 파일 목록 (Auto)

### 카탈로그 쓰기 (Approve Write — 승인 필요)
- `register_pipeline` — 파이프라인 등록
- `register_lineage` — 리니지 등록

## 코딩 규칙

- ruff: `target-version = "py311"`, `line-length = 100`
- 모듈 패턴: `router.py`, `schemas.py`, `service.py`, `models.py`
- 기본 포트: **4700**
- Catalog 서버 연동: `http://localhost:4600`

## Safety Levels

```
Level 0 (AUTO)         : 카탈로그 조회, 검색
Level 1 (AUTO_READ)    : 데이터 미리보기
Level 2 (APPROVE)      : 프로파일링, 품질검사
Level 3 (APPROVE_WRITE): 파일 쓰기, 파이프라인/리니지 등록
Level 4 (APPROVE_EXEC) : SQL 실행 (SELECT만)
Level 5 (BLOCKED)      : DDL/DML 직접 실행 — 코드 생성만 가능
```
