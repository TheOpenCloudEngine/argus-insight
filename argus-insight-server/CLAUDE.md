# Argus Insight Server

Argus Insight 플랫폼의 **중앙 관리 서버**입니다. React UI와 통신하여 사용자 인터페이스를 제공하고, 원격 서버에 설치된 argus-insight-agent를 통해 서버를 제어합니다.

## 핵심 기능

- **에이전트 관리** (`agent`): 에이전트 등록/해제, 목록 조회, 상태 확인(헬스체크), 태그 기반 그룹핑
- **프록시** (`proxy`): React UI의 요청을 대상 에이전트로 전달하고 응답을 반환. 커맨드 실행, 모니터링, 패키지 관리 등 에이전트의 모든 API를 중계
- **인증** (`auth`): UI 사용자 인증 (로그인, 토큰 발급/검증)
- **대시보드** (`dashboard`): 등록된 에이전트들의 상태를 집계하여 대시보드 데이터 제공

## 아키텍처

```
React UI  <──HTTP/WS──>  Argus Insight Server  <──HTTP/WS──>  Argus Insight Agent(s)
(Frontend)                (이 프로젝트)                         (원격 서버)
```

- **React UI → Server**: REST API + WebSocket (포트 4500)
- **Server → Agent**: HTTP 클라이언트 (httpx)로 Agent API 호출 (포트 4501)

## 운영 환경

- systemd 서비스로 동작 (`argus-insight-server.service`)
- 일반 사용자 권한으로 실행 (argus 계정)
- 기본 포트: **4500**
- 디렉토리 구조:
  - `/etc/argus-insight-server/` - 설정 파일 (`config.yml`, `config.properties`)
  - `/var/log/argus-insight-server/` - 로그 파일 (`server.log`)
  - `/var/lib/argus-insight-server/` - 데이터 디렉토리
  - `/opt/argus-insight-server/` - 애플리케이션 코드
  - `/opt/argus-insight-server/bin/argus-insight-server` - 엔트리포인트
- 장애 시 자동 재시작 (`Restart=on-failure`, 5초 간격)

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn (비동기 HTTP/WebSocket 서버)
- Pydantic v2 (스키마 검증)
- httpx (에이전트 통신용 비동기 HTTP 클라이언트)
- PyYAML (설정 파일 파싱)
- 빌드: setuptools
- 린터: ruff
- 테스트: pytest + pytest-asyncio + httpx

## 프로젝트 구조

```
argus-insight-server/
├── app/
│   ├── __init__.py          # 버전 정의 (__version__)
│   ├── main.py              # FastAPI 앱 엔트리포인트, lifespan 관리, CORS 설정
│   ├── core/
│   │   ├── config.py        # Settings 클래스 (config.yml + config.properties 기반)
│   │   ├── config_loader.py # properties 파싱 + YAML ${var} 변수 치환 로더
│   │   ├── logging.py       # 일별 롤링 파일 로깅 설정
│   │   └── security.py      # SecurityHeadersMiddleware
│   ├── agent/               # 에이전트 관리 모듈
│   │   ├── router.py        # /api/v1/agent/* API 엔드포인트
│   │   ├── schemas.py       # AgentInfo, AgentRegisterRequest, AgentHealthResponse
│   │   └── service.py       # 에이전트 등록/해제/조회/헬스체크
│   ├── proxy/               # 에이전트 프록시 모듈
│   │   ├── router.py        # /api/v1/proxy/{agent_id}/* API 엔드포인트
│   │   ├── schemas.py       # ProxyCommandRequest, ProxyCommandResponse
│   │   └── service.py       # httpx 기반 에이전트 API 호출 전달
│   ├── auth/                # 인증 모듈
│   │   ├── router.py        # /api/v1/auth/* API 엔드포인트
│   │   ├── schemas.py       # LoginRequest, LoginResponse, UserInfo
│   │   └── service.py       # 사용자 인증, 토큰 생성/검증
│   └── dashboard/           # 대시보드 모듈
│       ├── router.py        # /api/v1/dashboard/* API 엔드포인트
│       ├── schemas.py       # DashboardOverview, AgentSummary
│       └── service.py       # 에이전트 상태 집계
├── tests/
│   ├── conftest.py          # 공통 fixtures (httpx AsyncClient)
│   ├── test_agent/          # 에이전트 관리 테스트
│   ├── test_proxy/          # 프록시 테스트
│   ├── test_auth/           # 인증 테스트
│   └── test_dashboard/      # 대시보드 테스트
├── packaging/
│   ├── config/
│   │   ├── config.yml         # YAML 설정 파일 (${var} 변수 사용)
│   │   └── config.properties  # Java-style 변수 정의 파일
│   ├── debian/              # Debian 패키지 빌드 설정
│   └── systemd/             # argus-insight-server.service 유닛 파일
├── scripts/argus-insight-server  # 시스템 설치 시 엔트리포인트
├── requirements.txt         # Python 의존성 (pip install -r)
├── pyproject.toml           # 프로젝트 설정 및 의존성
└── Makefile                 # 빌드/실행/테스트 명령
```

## 설정 시스템

Spring Boot 스타일의 `${변수:기본값}` 문법을 사용합니다. argus-insight-agent와 동일한 설정 로더를 사용합니다.

### config.properties (변수 정의)

```properties
# 서버 설정
server.host=0.0.0.0
server.port=4500

# 로깅
log.level=INFO
log.dir=/var/log/argus-insight-server
log.filename=server.log

# CORS
cors.origins=*

# 에이전트 통신
agent.timeout=30
agent.health_interval=60
```

### config.yml (메인 설정)

```yaml
server:
  host: ${server.host:0.0.0.0}
  port: ${server.port:4500}

logging:
  level: ${log.level:INFO}
  dir: ${log.dir:/var/log/argus-insight-server}
  filename: ${log.filename:server.log}

cors:
  origins: ${cors.origins:*}

agent:
  timeout: ${agent.timeout:30}
  health_interval: ${agent.health_interval:60}
```

### 설정 파일 위치

| 환경 | config.yml | config.properties |
|------|-----------|-------------------|
| 패키지 설치 (rpm/deb) | `/etc/argus-insight-server/config.yml` | `/etc/argus-insight-server/config.properties` |
| 개발 환경 | `ARGUS_SERVER_CONFIG_DIR` 환경변수로 지정 | 동일 디렉토리 |

### 설정 항목 전체 목록

| 섹션 | YAML 키 | properties 변수 | 기본값 | 설명 |
|------|---------|----------------|--------|------|
| server | host | server.host | 0.0.0.0 | 바인드 주소 |
| server | port | server.port | 4500 | 바인드 포트 |
| app | debug | - | false | 디버그 모드 |
| logging | level | log.level | INFO | 로그 레벨 |
| logging | dir | log.dir | /var/log/argus-insight-server (패키지), logs (직접 실행) | 로그 디렉토리 |
| logging | filename | log.filename | server.log | 로그 파일명 |
| logging | rolling.type | log.rolling.type | daily | 롤링 방식 |
| logging | rolling.backup_count | log.rolling.backup_count | 30 | 롤링 파일 보관 개수 |
| data | dir | data.dir | /var/lib/argus-insight-server | 데이터 디렉토리 |
| cors | origins | cors.origins | * | 허용할 CORS origin (쉼표 구분) |
| agent | timeout | agent.timeout | 30 | 에이전트 통신 타임아웃 (초) |
| agent | health_interval | agent.health_interval | 60 | 헬스체크 주기 (초) |

## CLI 실행 및 옵션

### 서버 실행

```bash
# 개발 모드 (uvicorn --reload)
make run

# python -m 모듈 실행
cd argus-insight-server
python -m app.main

# 설정 파일 경로 지정
python -m app.main --config-yaml /path/to/config.yml --config-properties /path/to/config.properties

# pip install 후 명령어 실행
argus-insight-server
argus-insight-server --config-yaml /path/to/config.yml
argus-insight-server --config-yaml /path/to/config.yml --config-properties /path/to/config.properties
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `--help` | 도움말 출력 |
| `--config-yaml PATH` | YAML 설정 파일(config.yml) 경로 지정. 미지정 시 `/etc/argus-insight-server/config.yml` |
| `--config-properties PATH` | Properties 변수 파일(config.properties) 경로 지정. 미지정 시 `/etc/argus-insight-server/config.properties` |

- 옵션을 지정하지 않으면 기본 디렉토리(`/etc/argus-insight-server/`)에서 설정 파일을 읽습니다.
- `ARGUS_SERVER_CONFIG_DIR` 환경변수로 기본 디렉토리를 변경할 수 있습니다.
- `--config-yaml`과 `--config-properties`는 개별적으로 지정 가능하며, 지정하지 않은 파일은 기본 디렉토리에서 읽습니다.

## 주요 명령어

```bash
# 작업 디렉토리
cd argus-insight-server

# 의존성 설치 (개발용)
make dev            # pip install -e ".[dev]"

# 서버 실행 (개발 모드, --reload 포함)
make run            # uvicorn app.main:app --host 0.0.0.0 --port 4500 --reload

# 테스트
make test           # pytest tests/ -v

# 린트
make lint           # ruff check app/ tests/ && ruff format --check app/ tests/

# 포맷팅
make format         # ruff format app/ tests/ && ruff check --fix app/ tests/

# Debian 패키지 빌드
make deb            # dpkg-buildpackage -us -uc -b

# 빌드 아티팩트 정리
make clean
```

## Swagger / OpenAPI

| UI | URL | 설명 |
|----|-----|------|
| Swagger UI | `http://<host>:4500/docs` | 대화형 API 테스트 가능 (Try it out) |
| ReDoc | `http://<host>:4500/redoc` | 읽기 전용 API 문서 |
| OpenAPI JSON | `http://<host>:4500/openapi.json` | OpenAPI 3.x 스펙 (JSON) |

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 (status, version 반환) |
| POST | /api/v1/auth/login | 로그인 (username, password → access_token) |
| GET | /api/v1/auth/me | 현재 사용자 정보 조회 |
| POST | /api/v1/agent/register | 에이전트 등록 (host, port, name, tags) |
| GET | /api/v1/agent/list | 등록된 에이전트 목록 조회 |
| GET | /api/v1/agent/{id} | 에이전트 상세 정보 조회 |
| PUT | /api/v1/agent/{id} | 에이전트 정보 수정 (name, port, tags) |
| DELETE | /api/v1/agent/{id} | 에이전트 등록 해제 |
| GET | /api/v1/agent/{id}/health | 특정 에이전트 헬스체크 |
| POST | /api/v1/agent/health/all | 전체 에이전트 헬스체크 |
| POST | /api/v1/proxy/{id}/command/execute | 에이전트에 명령 실행 요청 전달 |
| GET | /api/v1/proxy/{id}/monitor/system | 에이전트 시스템 모니터 조회 |
| POST | /api/v1/proxy/{id}/package/manage | 에이전트에 패키지 관리 요청 전달 |
| GET | /api/v1/proxy/{id}/package/list | 에이전트 패키지 목록 조회 |
| * | /api/v1/proxy/{id}/{path} | 범용 에이전트 API 프록시 |
| GET | /api/v1/dashboard/overview | 대시보드 전체 현황 |
| GET | /api/v1/dashboard/agents/summary | 에이전트 상태 요약 |

## 로깅

### 로그 포맷

```
LEVEL yyyy-MM-dd HH:mm:ss.SSS PID 프로그램명 소스파일:함수명:라인 - 메시지
```

예시:
```
INFO 2026-03-15 14:30:45.123 12345 argus-insight-server main.py:lifespan:25 - Argus Insight Server 0.1.0 starting
```

### 파일 롤링

- 기본 로그 파일: `server.log`
- 일 단위로 자동 롤링
- 롤링된 파일명: `server_20260315.log` (날짜 suffix)
- 기본 보관 개수: 30일 (`log.rolling.backup_count`)

### 로그 디렉토리

| 실행 환경 | 로그 디렉토리 |
|----------|-------------|
| rpm/deb 패키지 설치 | `/var/log/argus-insight-server/` |
| 터미널 직접 실행 (개발) | `argus-insight-server/logs/` (설정 파일 없을 시 기본값) |

## 보안 고려사항

- **CORS**: `CORSMiddleware`로 React UI의 cross-origin 요청 허용. 프로덕션에서는 `cors.origins`를 특정 도메인으로 제한 필요
- **보안 헤더**: `SecurityHeadersMiddleware`가 모든 응답에 `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection` 헤더 추가
- **인증**: 토큰 기반 인증. 프로덕션에서는 JWT 라이브러리(python-jose, PyJWT) 사용 권장
- **에이전트 통신**: 에이전트와의 통신은 현재 HTTP. 프로덕션에서는 mTLS(상호 TLS) 인증 적용 권장
- **새 기능 추가 시**: 입력 검증 철저히, 에이전트 프록시 시 경로 탈출(path traversal) 방어 필수

## 코딩 규칙

- ruff 린터: `target-version = "py311"`, `line-length = 100`, 규칙 `E, F, I, N, W`
- 테스트: `asyncio_mode = "auto"`, httpx `AsyncClient`로 ASGI 앱 직접 테스트
- 모듈 패턴: 각 기능 모듈은 `router.py` (API 라우트), `schemas.py` (Pydantic 모델), `service.py` (비즈니스 로직) 3파일로 구성
- 새 모듈 추가 시: 위 패턴을 따르고, `app/main.py`에 라우터 등록, `tests/` 디렉토리에 테스트 추가
