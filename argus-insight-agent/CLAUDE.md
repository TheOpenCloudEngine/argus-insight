# Argus Insight Agent

서버에 설치되어 원격으로 서버를 관리하는 에이전트. root 권한으로 동작하며 셸 명령 실행, 시스템 리소스 모니터링, 패키지 관리, 원격 터미널 기능을 제공합니다.

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2 / Pydantic Settings
- psutil (시스템 모니터링)
- 빌드: setuptools
- 린터: ruff
- 테스트: pytest + pytest-asyncio + httpx

## 프로젝트 구조

```
argus-insight-agent/
├── app/
│   ├── __init__.py          # 버전 정의 (__version__)
│   ├── main.py              # FastAPI 앱 엔트리포인트
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings, ARGUS_ 환경변수 prefix)
│   │   ├── logging.py       # 로깅 설정
│   │   └── security.py      # 보안 미들웨어, 차단 명령어 목록
│   ├── command/             # 셸 명령 실행 모듈
│   │   ├── router.py        # POST /api/v1/command/execute
│   │   ├── schemas.py       # CommandRequest, CommandResponse
│   │   └── service.py       # asyncio subprocess 기반 명령 실행
│   ├── monitor/             # 시스템 리소스 모니터링 모듈
│   │   ├── router.py        # GET /api/v1/monitor/system, WS /api/v1/monitor/ws
│   │   ├── schemas.py       # SystemInfo, CpuInfo, MemoryInfo, DiskInfo, NetworkInfo
│   │   └── service.py       # psutil 기반 시스템 정보 수집
│   ├── package/             # 패키지 관리 모듈
│   │   ├── router.py        # POST /api/v1/package/manage, GET /api/v1/package/list
│   │   ├── schemas.py       # PackageRequest, PackageInfo, PackageActionResult
│   │   └── service.py       # dnf/yum/apt 패키지 관리
│   └── terminal/            # 원격 터미널 모듈
│       ├── router.py        # WS /api/v1/terminal/ws
│       └── service.py       # PTY 기반 터미널 세션 관리
├── tests/
│   ├── conftest.py          # 공통 fixtures (AsyncClient)
│   ├── test_command/        # 명령 실행 테스트
│   ├── test_monitor/        # 모니터링 테스트
│   ├── test_package/        # 패키지 관리 테스트
│   └── test_terminal/       # 터미널 테스트
├── packaging/               # 시스템 패키징 (Debian, systemd)
├── scripts/argus-agent      # 시스템 설치 시 엔트리포인트
├── pyproject.toml           # 프로젝트 설정 및 의존성
└── Makefile                 # 빌드/실행/테스트 명령
```

## 주요 명령어

```bash
# 작업 디렉토리
cd argus-insight-agent

# 의존성 설치 (개발용)
make dev            # pip install -e ".[dev]"

# 서버 실행
make run            # uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload

# 테스트
make test           # pytest tests/ -v

# 린트
make lint           # ruff check app/ tests/ && ruff format --check app/ tests/

# 포맷팅
make format         # ruff format app/ tests/ && ruff check --fix app/ tests/

# 빌드 아티팩트 정리
make clean
```

## API 엔드포인트

| Method    | Path                        | 설명                           |
|-----------|-----------------------------|-------------------------------|
| GET       | /health                     | 헬스체크                        |
| POST      | /api/v1/command/execute     | 셸 명령 실행                     |
| GET       | /api/v1/monitor/system      | 시스템 리소스 정보 조회             |
| WebSocket | /api/v1/monitor/ws          | 시스템 리소스 실시간 스트리밍         |
| POST      | /api/v1/package/manage      | 패키지 설치/삭제/업데이트            |
| GET       | /api/v1/package/list        | 설치된 패키지 목록                  |
| WebSocket | /api/v1/terminal/ws         | 원격 터미널 세션                   |

## 설정

환경변수 prefix: `ARGUS_` (예: `ARGUS_PORT=8600`, `ARGUS_LOG_LEVEL=DEBUG`)

설정 파일 위치: `/etc/argus/agent.env`

주요 설정값:
- `ARGUS_HOST` / `ARGUS_PORT`: 서버 바인드 주소 (기본 0.0.0.0:8600)
- `ARGUS_LOG_LEVEL`: 로그 레벨 (기본 INFO)
- `ARGUS_COMMAND_TIMEOUT`: 명령 실행 타임아웃 초 (기본 300)
- `ARGUS_TERMINAL_MAX_SESSIONS`: 최대 터미널 세션 수 (기본 10)

## 코딩 규칙

- ruff 린터 설정: `target-version = "py311"`, `line-length = 100`
- ruff lint 규칙: E, F, I, N, W
- 테스트: `asyncio_mode = "auto"`, httpx AsyncClient 사용
- 모듈 패턴: 각 모듈은 `router.py` (API), `schemas.py` (Pydantic 모델), `service.py` (비즈니스 로직)로 구성
- 보안: `BLOCKED_COMMANDS` 목록으로 위험 명령 차단, SecurityHeadersMiddleware로 보안 헤더 추가
