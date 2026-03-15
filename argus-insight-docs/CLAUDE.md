# Argus Insight Docs

Argus Insight 플랫폼의 **기술 문서** 프로젝트입니다. AsciiDoc + Antora를 사용하여 HTML 웹 사이트와 PDF 문서를 생성합니다.

## 핵심 기능

- **HTML 사이트 생성**: Antora 기반 정적 문서 사이트 빌드
- **PDF 생성**: asciidoctor-pdf를 사용한 인쇄용 PDF 문서 생성
- **모듈화된 문서 구조**: 컴포넌트별(Server, Agent) 독립 모듈로 관리
- **재사용 가능한 콘텐츠**: AsciiDoc partials를 통한 공통 콘텐츠 공유

## 출력 형식

| 형식 | 용도 | 빌드 명령 |
|------|------|-----------|
| HTML | 웹 사이트 publish | `make build` |
| PDF | 고객 전달 문서 | `make pdf` |

## 기술 스택

- AsciiDoc (문서 마크업 언어)
- Antora 3.x (정적 문서 사이트 생성기)
- asciidoctor-pdf (PDF 변환기)
- Node.js + npm (빌드 도구)

## 프로젝트 구조

```
argus-insight-docs/
├── antora-playbook.yml        # HTML 사이트 생성 playbook
├── antora-playbook-pdf.yml    # PDF 생성 playbook
├── package.json               # Node.js 의존성 및 스크립트
├── Makefile                   # 빌드 명령어
├── docs/                      # 문서 콘텐츠 소스
│   ├── antora.yml             # Antora 컴포넌트 설정 (버전, 속성, 네비게이션)
│   └── modules/
│       ├── ROOT/              # 메인 모듈 (소개, 아키텍처, 시작하기)
│       │   ├── nav.adoc       # 네비게이션 정의
│       │   ├── pages/         # 페이지 (.adoc 파일)
│       │   ├── partials/      # 재사용 가능한 콘텐츠 조각
│       │   ├── images/        # 이미지 파일
│       │   └── examples/      # 예제 코드/설정 파일
│       ├── server/            # Server 문서 모듈
│       │   ├── nav.adoc
│       │   ├── pages/         # 개요, 설치, 설정, API 레퍼런스
│       │   ├── partials/
│       │   ├── images/
│       │   └── examples/
│       └── agent/             # Agent 문서 모듈
│           ├── nav.adoc
│           ├── pages/         # 개요, 설치, 설정, API, CLI 레퍼런스
│           ├── partials/
│           ├── images/
│           └── examples/
├── pdf/                       # PDF 테마 설정
│   └── argus-insight-theme.yml  # asciidoctor-pdf 테마 (A4, 폰트, 색상)
├── ui-supplemental/           # Antora UI 커스터마이징
│   ├── css/custom.css         # 커스텀 CSS
│   ├── partials/              # 커스텀 Handlebars 템플릿
│   └── img/                   # 로고 등 커스텀 이미지
└── build/                     # 빌드 출력 (gitignore)
    ├── site/                  # HTML 사이트 출력
    └── pdf/                   # PDF 문서 출력
```

## 문서 모듈 구성

| 모듈 | 경로 | 내용 |
|------|------|------|
| ROOT | `docs/modules/ROOT/` | 플랫폼 소개, 아키텍처, 시작하기 |
| server | `docs/modules/server/` | Server 개요, 설치, 설정, API 레퍼런스 |
| agent | `docs/modules/agent/` | Agent 개요, 설치, 설정, API, CLI 레퍼런스 |

## 주요 명령어

```bash
# 작업 디렉토리
cd argus-insight-docs

# 의존성 설치
make install        # npm install

# HTML 사이트 빌드
make build          # npx antora antora-playbook.yml
                    # 출력: build/site/

# PDF 빌드
make pdf            # npx antora antora-playbook-pdf.yml
                    # 출력: build/pdf/

# HTML 미리보기 (브라우저에서 열기)
make preview        # npm run preview (http://localhost:8888)

# 빌드 아티팩트 정리
make clean          # rm -rf build .antora-cache
```

## 설정 파일

### antora.yml (컴포넌트 설정)

컴포넌트 이름, 버전, 공통 AsciiDoc 속성, 네비게이션 파일 목록을 정의합니다.

주요 속성:
- `product-name`: 제품명 (Argus Insight)
- `product-version`: 제품 버전
- `server-port`: Server 기본 포트 (8080)
- `agent-port`: Agent 기본 포트 (8600)

### antora-playbook.yml (HTML 사이트)

사이트 전체 설정: URL, 콘텐츠 소스, UI 번들, 출력 디렉토리를 정의합니다.

### antora-playbook-pdf.yml (PDF)

PDF 생성용 playbook. `@antora/pdf-extension`을 사용합니다.

### pdf/argus-insight-theme.yml (PDF 테마)

asciidoctor-pdf의 스타일 설정: A4 용지, 폰트, 색상, 헤더/푸터, 제목 페이지, 코드 블록, 테이블 스타일 등.

## AsciiDoc 작성 규칙

- **페이지 파일**: `docs/modules/{모듈}/pages/` 디렉토리에 `.adoc` 확장자로 생성
- **재사용 콘텐츠**: `docs/modules/{모듈}/partials/` 디렉토리에 `_` 접두사로 생성 (예: `_common-requirements.adoc`)
- **이미지**: `docs/modules/{모듈}/images/` 디렉토리에 저장
- **예제 코드**: `docs/modules/{모듈}/examples/` 디렉토리에 저장
- **크로스 참조**: `xref:모듈:페이지.adoc[표시텍스트]` 형식 사용
- **속성 참조**: `{product-name}`, `{server-port}` 등 antora.yml에 정의된 속성 사용
- **네비게이션**: 새 페이지 추가 시 해당 모듈의 `nav.adoc`에 항목 추가 필수

## 새 문서 페이지 추가 방법

1. `docs/modules/{모듈}/pages/` 에 `.adoc` 파일 생성
2. 해당 모듈의 `nav.adoc`에 `* xref:파일명.adoc[제목]` 추가
3. `make build`로 빌드 확인
4. `make preview`로 브라우저에서 확인

## 새 문서 모듈 추가 방법

1. `docs/modules/{새모듈}/` 디렉토리 생성 (`pages/`, `partials/`, `images/`, `examples/` 포함)
2. `docs/modules/{새모듈}/nav.adoc` 생성
3. `docs/antora.yml`의 `nav:` 섹션에 `- modules/{새모듈}/nav.adoc` 추가
4. `docs/modules/{새모듈}/pages/index.adoc` 생성 (모듈 메인 페이지)
