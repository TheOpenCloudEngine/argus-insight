# Argus Insight

Argus Insight는 '백 개의 눈'을 가진 신화 속 수호자처럼, 방대한 데이터를 빈틈없이 관측하여 숨겨진 가치를 찾아내는 지능형 Data + AI Platform입니다. 데이터의 전 생명주기 동안 활용할 수 있는 소프트웨어 스택과 관리 방법을 제공합니다.

## 프로젝트 구조

```
argus-insight/
├── CLAUDE.md                        # 이 파일 (루트 가이드)
├── argus-insight-server/            # 중앙 관리 서버 (Python/FastAPI)
├── argus-insight-agent/             # 서버 관리 에이전트 (Python/FastAPI)
├── argus-insight-ui/                # 프론트엔드 웹 UI (Next.js/React)
├── argus-insight-docs/              # 기술 문서 (AsciiDoc + Antora)
├── argus-data-engineer-ai-agent/    # DE AI 에이전트 (Python/FastAPI)
├── argus-rag-server/                # RAG 서버 (Python/FastAPI)
├── argus-rag-ui/                    # RAG 프론트엔드 (Next.js/React)
└── README.md
```

## 서브 프로젝트

### argus-insight-server
Argus Insight 플랫폼의 중앙 관리 서버입니다. React UI와 통신하여 사용자 인터페이스를 제공하고, 원격 서버에 설치된 argus-insight-agent를 통해 서버를 제어합니다.

주요 기능:
- **에이전트 관리**: 에이전트 등록/해제, 목록 조회, 헬스체크, 태그 기반 그룹핑
- **프록시**: React UI의 요청을 대상 에이전트로 전달하고 응답을 반환
- **인증**: UI 사용자 인증 (로그인, 토큰 발급/검증)
- **대시보드**: 등록된 에이전트들의 상태를 집계하여 대시보드 데이터 제공

자세한 내용은 `argus-insight-server/CLAUDE.md`를 참고하세요.

### argus-insight-agent
관리 대상 서버에 설치되어 root 권한으로 동작하는 서버 관리 에이전트입니다. Argus Insight 플랫폼의 중앙 관리 서버(argus-insight-server)가 이 에이전트를 통해 원격 서버를 제어합니다.

주요 기능:
- **커맨드 실행**: 원격 서버에서 셸 명령을 실행하고 결과를 반환
- **서버 자원 모니터링**: CPU, 메모리, 디스크, 네트워크 상태를 실시간 수집 및 스트리밍
- **애플리케이션 설치 및 관리**: dnf/yum/apt를 통한 패키지 설치, 삭제, 업데이트
- **원격 터미널**: PTY 기반 WebSocket 터미널 세션 제공

자세한 내용은 `argus-insight-agent/CLAUDE.md`를 참고하세요.

### argus-insight-ui
Argus Insight 플랫폼의 프론트엔드 웹 애플리케이션입니다. shadcn-admin을 기반으로 구성된 Next.js + React 모노레포입니다.

주요 기능:
- **대시보드**: 서버 상태 통계, 알림, 서버 현황 요약
- **사용자 관리**: 사용자 CRUD, 역할/상태 관리, 일괄 작업
- **서비스 설정**: 서비스별 설정 폼 빌더
- **사이드바 네비게이션**: 동적 메뉴 로딩, 아이콘 매핑

자세한 내용은 `argus-insight-ui/CLAUDE.md`를 참고하세요.

### argus-insight-docs
Argus Insight 플랫폼의 기술 문서 프로젝트입니다. AsciiDoc + Antora를 사용하여 HTML 웹 사이트와 PDF 문서를 생성합니다.

주요 기능:
- **HTML 사이트**: Antora 기반 정적 문서 사이트 빌드 (웹 publish용)
- **PDF 문서**: asciidoctor-pdf를 사용한 인쇄용 문서 생성 (고객 전달용)
- **모듈화**: Server, Agent 별 독립 문서 모듈 관리

자세한 내용은 `argus-insight-docs/CLAUDE.md`를 참고하세요.

### argus-data-engineer-ai-agent
Data Engineer의 업무를 도와주는 AI Agent입니다. 자연어 프롬프트를 입력하면 argus-catalog의 메타데이터를 활용하여 데이터 엔지니어링 작업을 자율적으로 수행합니다.

주요 기능:
- **ReAct Agent**: Reason → Act → Observe 루프 기반 자율형 에이전트
- **Catalog 연동**: argus-catalog-server API를 통해 데이터셋, 스키마, 리니지, 품질 정보 활용
- **도구 호출**: LLM native tool_use를 활용한 15개 도구 (검색, 상세조회, 리니지, 품질, 파이프라인 등)
- **승인 플로우**: 읽기는 자동 실행, 쓰기/실행은 사용자 승인 후 처리
- **코드 생성**: SQL, PySpark, DDL 등 플랫폼별 코드 생성 (계획)

자세한 내용은 `argus-data-engineer-ai-agent/CLAUDE.md`를 참고하세요.

### argus-rag-server
임베딩, 인덱싱, 시맨틱 검색을 담당하는 전용 RAG 서비스입니다. 여러 종류의 데이터를 Collection 단위로 관리하며, 다양한 소비자(DE Agent, Catalog UI)에게 벡터 검색 API를 제공합니다.

주요 기능:
- **Collection 관리**: 데이터 그룹 단위 CRUD, 임베딩 모델/청킹 설정
- **시맨틱 검색**: pgvector 기반 멀티 Collection 하이브리드 검색
- **데이터 소스 커넥터**: Catalog API에서 datasets, models, glossary, standards 자동 수집
- **청킹 전략**: paragraph, fixed, sliding window 지원

자세한 내용은 `argus-rag-server/CLAUDE.md`를 참고하세요.

### argus-rag-ui
RAG Server의 프론트엔드 웹 애플리케이션입니다. Collection 관리, 검색 Playground, 데이터 소스 관리, 설정을 제공합니다.

자세한 내용은 `argus-rag-ui/CLAUDE.md`를 참고하세요.

## 공통 규칙

- 백엔드 언어: Python 3.11+
- 프론트엔드: TypeScript 5.9+, React 19, Next.js 16
- 라이선스: Apache License 2.0
- 커밋 메시지: 영문으로 작성, 간결하고 명확하게
- 코드 스타일: 각 서브 프로젝트의 lint 설정을 따름
