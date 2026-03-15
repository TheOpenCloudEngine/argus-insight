# Argus Insight Agent

관리 대상 서버에 설치되어 **root 권한**으로 동작하는 서버 관리 에이전트입니다. Argus Insight 플랫폼의 중앙 관리 서버와 연동하여 원격으로 서버를 제어하는 역할을 합니다.

## 핵심 기능

- **커맨드 실행** (`command`): 원격 셸 명령 실행, 타임아웃 관리, 위험 명령 차단
- **서버 자원 모니터링** (`monitor`): CPU, 메모리, 디스크, 네트워크 상태를 REST 및 WebSocket 실시간 스트리밍으로 제공
- **애플리케이션 설치 및 관리** (`package`): dnf/yum/apt 패키지 매니저 자동 감지 후 패키지 설치, 삭제, 업데이트 수행
- **원격 터미널** (`terminal`): PTY 기반 WebSocket 터미널 세션으로 서버에 직접 접속하는 것과 동일한 경험 제공
- **Yum 리포지토리 및 패키지 관리** (`yum`): yum repo 파일 CRUD, 백업, 패키지 설치/삭제/업그레이드, 패키지 정보 조회. API와 CLI 모두 지원
- **시스템 모니터링** (`sysmon`): dmesg, CPU(top/htop 스타일), 네트워크(인터페이스별 트래픽/에러), 프로세스(VSS/RSS/PSS/USS/SWAP), 디스크 파티션. React UI용 JSON 구조화. API와 CLI 모두 지원
- **호스트 관리** (`hostmgr`): hostname 조회/변경/검증, /etc/hosts CRUD/백업, /etc/resolv.conf CRUD/백업/네임서버 관리. API와 CLI 모두 지원

## 운영 환경

- systemd 서비스로 동작 (`argus-agent.service`)
- **root 권한**으로 실행 (서버 관리 작업에 필요)
- 기본 포트: **8600**
- 디렉토리 구조:
  - `/etc/argus-insight-agent/` - 설정 파일 (`config.yml`, `config.properties`)
  - `/var/log/argus-insight-agent/` - 로그 파일 (`agent.log`)
  - `/var/lib/argus-insight-agent/` - 데이터 디렉토리
  - `/opt/argus-insight/agent/backups/` - 백업 디렉토리 (yum repo 백업 등)
  - `/usr/lib/argus-agent/` - 애플리케이션 코드
- 장애 시 자동 재시작 (`Restart=on-failure`, 5초 간격)

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn (비동기 HTTP/WebSocket 서버)
- Pydantic v2 (스키마 검증)
- PyYAML (설정 파일 파싱)
- psutil (시스템 리소스 수집)
- asyncio subprocess (비동기 명령 실행)
- PTY (os.fork + pty.openpty 기반 터미널 세션)
- 빌드: setuptools
- 린터: ruff
- 테스트: pytest + pytest-asyncio + httpx

## 프로젝트 구조

```
argus-insight-agent/
├── app/
│   ├── __init__.py          # 버전 정의 (__version__)
│   ├── main.py              # FastAPI 앱 엔트리포인트, lifespan 관리
│   ├── core/
│   │   ├── config.py        # Settings 클래스 (config.yml + config.properties 기반)
│   │   ├── config_loader.py # properties 파싱 + YAML ${var} 변수 치환 로더
│   │   ├── logging.py       # 일별 롤링 파일 로깅 설정
│   │   └── security.py      # SecurityHeadersMiddleware, BLOCKED_COMMANDS
│   ├── command/             # 셸 명령 실행 모듈
│   │   ├── router.py        # POST /api/v1/command/execute
│   │   ├── schemas.py       # CommandRequest, CommandResponse
│   │   └── service.py       # asyncio.create_subprocess_shell 기반 실행
│   ├── monitor/             # 시스템 리소스 모니터링 모듈
│   │   ├── router.py        # GET /api/v1/monitor/system, WS /api/v1/monitor/ws
│   │   ├── schemas.py       # SystemInfo, CpuInfo, MemoryInfo, DiskInfo, NetworkInfo
│   │   └── service.py       # psutil 기반 CPU/메모리/디스크/네트워크 수집
│   ├── sysmon/              # 시스템 모니터링 모듈 (고급)
│   │   ├── router.py        # /api/v1/sysmon/* API 엔드포인트
│   │   ├── schemas.py       # React UI용 JSON 모델 (CPU/네트워크/프로세스/디스크)
│   │   ├── service.py       # psutil/dmesg/ethtool 기반 메트릭 수집
│   │   └── cli.py           # 커맨드라인 인터페이스 (argus-sysmon)
│   ├── package/             # 패키지(애플리케이션) 관리 모듈
│   │   ├── router.py        # POST /api/v1/package/manage, GET /api/v1/package/list
│   │   ├── schemas.py       # PackageRequest, PackageInfo, PackageActionResult
│   │   └── service.py       # dnf/yum/apt 자동 감지 및 패키지 관리
│   ├── terminal/            # 원격 터미널 모듈
│   │   ├── router.py        # WS /api/v1/terminal/ws
│   │   └── service.py       # TerminalManager: PTY fork, 세션 관리, resize 지원
│   ├── yum/                 # Yum 리포지토리 & 패키지 관리 모듈
│   │   ├── router.py        # /api/v1/yum/* API 엔드포인트
│   │   ├── schemas.py       # Repo/Package 요청/응답 모델
│   │   ├── service.py       # 리포지토리 CRUD, 백업, 패키지 관리
│   │   └── cli.py           # 커맨드라인 인터페이스 (argus-yum)
│   └── hostmgr/             # 호스트 관리 모듈
│       ├── router.py        # /api/v1/host/* API 엔드포인트
│       ├── schemas.py       # Hostname/Hosts/Resolv 요청/응답 모델
│       ├── service.py       # hostname 변경, /etc/hosts·resolv.conf 관리
│       └── cli.py           # 커맨드라인 인터페이스 (argus-host)
├── tests/
│   ├── conftest.py          # 공통 fixtures (httpx AsyncClient)
│   ├── test_config_loader.py # config loader 테스트
│   ├── test_command/        # 명령 실행 테스트
│   ├── test_monitor/        # 모니터링 테스트
│   ├── test_package/        # 패키지 관리 테스트 (미작성)
│   ├── test_sysmon/         # 시스템 모니터링 테스트
│   ├── test_terminal/       # 터미널 테스트 (미작성)
│   ├── test_yum/            # yum 모듈 테스트
│   └── test_hostmgr/        # 호스트 관리 테스트
├── packaging/
│   ├── config/
│   │   ├── config.yml         # YAML 설정 파일 (${var} 변수 사용)
│   │   └── config.properties  # Java-style 변수 정의 파일
│   ├── debian/              # Debian 패키지 빌드 설정
│   └── systemd/             # argus-agent.service 유닛 파일
├── scripts/argus-agent      # 시스템 설치 시 엔트리포인트 (/usr/bin/argus-agent)
├── pyproject.toml           # 프로젝트 설정 및 의존성
└── Makefile                 # 빌드/실행/테스트 명령
```

## 설정 시스템

Spring Boot 스타일의 `${변수:기본값}` 문법을 사용합니다. 설정은 두 개의 파일로 구성됩니다:

### config.properties (변수 정의)

Java-style `key=value` 형식으로 변수를 정의합니다. `#`으로 시작하는 줄은 주석입니다. 이 파일의 값은 `config.yml`에서 참조됩니다.

```properties
# 서버 설정
server.host=0.0.0.0
server.port=8600

# 로깅
log.level=INFO
log.dir=/var/log/argus-insight-agent
log.filename=agent.log
log.rolling.type=daily
log.rolling.backup_count=30

# 명령 실행
command.timeout=300
```

### config.yml (메인 설정)

YAML 형식의 메인 설정 파일입니다. `${변수명:기본값}` 문법으로 변수를 참조합니다.

변수 해석 규칙 (Spring Boot 스타일):
- `${변수명:기본값}` : `config.properties`에서 변수를 찾고, 없으면 기본값 사용
- `${변수명}` : `config.properties`에서 변수를 찾고, 없으면 placeholder 그대로 유지

```yaml
server:
  host: ${server.host:0.0.0.0}
  port: ${server.port:8600}

logging:
  level: ${log.level:INFO}
  dir: ${log.dir:/var/log/argus-insight-agent}
  filename: ${log.filename:agent.log}
  rolling:
    type: ${log.rolling.type:daily}
    backup_count: ${log.rolling.backup_count:30}

command:
  timeout: ${command.timeout:300}
```

### 설정 로드 흐름

1. `config.properties` 파일을 파싱하여 변수 맵 생성
2. `config.yml` 파일을 로드
3. `${변수:기본값}` 패턴을 해석: properties에 값이 있으면 사용, 없으면 기본값 사용
4. 치환된 결과를 `Settings` 클래스로 매핑

### 설정 파일 위치

| 환경 | config.yml | config.properties |
|------|-----------|-------------------|
| 패키지 설치 (rpm/deb) | `/etc/argus-insight-agent/config.yml` | `/etc/argus-insight-agent/config.properties` |
| 개발 환경 | `ARGUS_CONFIG_DIR` 환경변수로 지정 | 동일 디렉토리 |

### 설정 항목 전체 목록

| 섹션 | YAML 키 | properties 변수 | 기본값 | 설명 |
|------|---------|----------------|--------|------|
| server | host | server.host | 0.0.0.0 | 바인드 주소 |
| server | port | server.port | 8600 | 바인드 포트 |
| app | debug | - | false | 디버그 모드 |
| logging | level | log.level | INFO | 로그 레벨 |
| logging | dir | log.dir | /var/log/argus-insight-agent (패키지), logs (직접 실행) | 로그 디렉토리 |
| logging | filename | log.filename | agent.log | 로그 파일명 |
| logging | rolling.type | log.rolling.type | daily | 롤링 방식 (일 단위) |
| logging | rolling.backup_count | log.rolling.backup_count | 30 | 롤링 파일 보관 개수 |
| backup | dir | backup.dir | /opt/argus-insight/agent/backups (패키지), backups (직접 실행) | 백업 디렉토리 |
| data | dir | data.dir | /var/lib/argus-insight-agent | 데이터 디렉토리 |
| command | timeout | command.timeout | 300 | 명령 실행 타임아웃 (초) |
| command | max_output | command.max_output | 1048576 | 명령 출력 최대 크기 (1MB) |
| monitor | interval | monitor.interval | 5 | 모니터링 WebSocket 전송 주기 (초) |
| terminal | shell | terminal.shell | /bin/bash | 터미널 셸 |
| terminal | max_sessions | terminal.max_sessions | 10 | 최대 동시 터미널 세션 수 |

## 주요 명령어

```bash
# 작업 디렉토리
cd argus-insight-agent

# 의존성 설치 (개발용)
make dev            # pip install -e ".[dev]"

# 서버 실행 (개발 모드, --reload 포함)
make run            # uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload

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

# Sysmon CLI (커맨드라인에서 직접 실행)
python -m app.sysmon.cli dmesg --lines 100 --level err
python -m app.sysmon.cli cpu --interval 1.0
python -m app.sysmon.cli cores --interval 1.0
python -m app.sysmon.cli network
python -m app.sysmon.cli network-errors
python -m app.sysmon.cli processes --sort cpu_percent --limit 20
python -m app.sysmon.cli disk

# Yum CLI (커맨드라인에서 직접 실행)
python -m app.yum.cli repo list
python -m app.yum.cli repo read base.repo
python -m app.yum.cli repo create myrepo.repo /path/to/content.repo
python -m app.yum.cli repo backup
python -m app.yum.cli package list
python -m app.yum.cli package search httpd
python -m app.yum.cli package install nginx
python -m app.yum.cli package remove nginx
python -m app.yum.cli package upgrade nginx
python -m app.yum.cli package info nginx
python -m app.yum.cli package files nginx

# Host CLI (커맨드라인에서 직접 실행)
python -m app.hostmgr.cli hostname get
python -m app.hostmgr.cli hostname set myhost
python -m app.hostmgr.cli hostname validate
python -m app.hostmgr.cli hosts read
python -m app.hostmgr.cli hosts update /path/to/hosts
python -m app.hostmgr.cli hosts backup
python -m app.hostmgr.cli resolv read
python -m app.hostmgr.cli resolv update /path/to/resolv.conf
python -m app.hostmgr.cli resolv backup
python -m app.hostmgr.cli resolv nameservers
python -m app.hostmgr.cli resolv set-nameservers 8.8.8.8 8.8.4.4
```

## Swagger / OpenAPI

FastAPI가 자동으로 제공하는 API 문서입니다. 별도 설정 없이 서버 시작 시 바로 사용할 수 있습니다.

| UI | URL | 설명 |
|----|-----|------|
| Swagger UI | `http://<host>:8600/docs` | 대화형 API 테스트 가능 (Try it out) |
| ReDoc | `http://<host>:8600/redoc` | 읽기 전용 API 문서 |
| OpenAPI JSON | `http://<host>:8600/openapi.json` | OpenAPI 3.x 스펙 (JSON) |

개발 환경 예시:
- Swagger UI: http://localhost:8600/docs
- ReDoc: http://localhost:8600/redoc

## API 엔드포인트

| Method    | Path                        | 설명                                        |
|-----------|-----------------------------|---------------------------------------------|
| GET       | /health                     | 헬스체크 (status, version 반환)                |
| POST      | /api/v1/command/execute     | 셸 명령 실행 (command, timeout, cwd 지정 가능)   |
| GET       | /api/v1/monitor/system      | 시스템 리소스 정보 일회 조회                       |
| WebSocket | /api/v1/monitor/ws          | 시스템 리소스 실시간 스트리밍 (주기: monitor.interval) |
| POST      | /api/v1/package/manage      | 패키지 설치/삭제/업데이트 (dnf/yum/apt 자동 감지)    |
| GET       | /api/v1/package/list        | 설치된 패키지 전체 목록 조회                        |
| WebSocket | /api/v1/terminal/ws         | PTY 기반 원격 터미널 세션 (resize 지원)            |
| GET       | /api/v1/sysmon/dmesg         | dmesg 커널 로그 캡처 (?lines=200&level=err)       |
| GET       | /api/v1/sysmon/cpu           | CPU 사용량 (top 스타일, user/system/iowait 등)     |
| GET       | /api/v1/sysmon/cpu/cores     | 코어별 CPU 사용량 (htop 스타일)                    |
| GET       | /api/v1/sysmon/network       | 네트워크 인터페이스별 트래픽 + 전체 합산               |
| GET       | /api/v1/sysmon/network/errors | 네트워크 인터페이스별 에러/드롭 카운터               |
| GET       | /api/v1/sysmon/processes     | 프로세스별 리소스 점유율 (CPU/RSS/VSS/PSS/USS/SWAP)  |
| GET       | /api/v1/sysmon/disk/partitions | 디스크 파티션 현황                                |
| GET       | /api/v1/yum/repo             | yum repo 파일 목록 조회                          |
| POST      | /api/v1/yum/repo             | yum repo 파일 생성                              |
| PUT       | /api/v1/yum/repo             | yum repo 파일 수정                              |
| GET       | /api/v1/yum/repo/{filename}  | yum repo 파일 내용 읽기                          |
| POST      | /api/v1/yum/repo/backup      | yum repo 파일 전체 백업 (zip)                     |
| POST      | /api/v1/yum/package          | yum 패키지 설치/삭제/업그레이드                     |
| GET       | /api/v1/yum/package          | 설치된 RPM 패키지 전체 목록                         |
| GET       | /api/v1/yum/package/search   | 설치된 패키지 검색                                 |
| GET       | /api/v1/yum/package/{name}/info  | 패키지 상세 메타데이터 조회                       |
| GET       | /api/v1/yum/package/{name}/files | 패키지 소유 파일 목록                            |
| GET       | /api/v1/host/hostname            | 현재 hostname 및 FQDN 조회                      |
| PUT       | /api/v1/host/hostname            | hostname 변경                                   |
| GET       | /api/v1/host/hostname/validate   | hostname 일관성 검증                              |
| GET       | /api/v1/host/hosts               | /etc/hosts 파일 읽기                              |
| PUT       | /api/v1/host/hosts               | /etc/hosts 파일 수정                              |
| POST      | /api/v1/host/hosts/backup        | /etc/hosts 백업 (hosts_YYYYMMDDHHmmss.zip)              |
| GET       | /api/v1/host/resolv              | /etc/resolv.conf 파일 읽기                        |
| PUT       | /api/v1/host/resolv              | /etc/resolv.conf 파일 수정                        |
| POST      | /api/v1/host/resolv/backup       | /etc/resolv.conf 백업 (resolv_YYYYMMDDHHmmss.zip)       |
| GET       | /api/v1/host/resolv/nameservers  | 네임서버 목록 파싱 조회                             |
| PUT       | /api/v1/host/resolv/nameservers  | 네임서버 엔트리 수정                                |

## 로깅

### 로그 포맷

```
LEVEL yyyy-MM-dd HH:mm:ss.SSS PID 프로그램명 소스파일:함수명:라인 - 메시지
```

예시:
```
INFO 2025-03-15 14:30:45.123 12345 argus-insight-agent main.py:lifespan:25 - Argus Insight Agent 0.1.0 starting
```

### 파일 롤링

- 기본 로그 파일: `agent.log`
- 일 단위로 자동 롤링
- 롤링된 파일명: `agent_20260315.log` (날짜 suffix)
- 기본 보관 개수: 30일 (`log.rolling.backup_count`)

### 로그 디렉토리

| 실행 환경 | 로그 디렉토리 |
|----------|-------------|
| rpm/deb 패키지 설치 | `/var/log/argus-insight-agent/` |
| 터미널 직접 실행 (개발) | `argus-insight-agent/logs/` (설정 파일 없을 시 기본값) |

## 보안 고려사항

이 에이전트는 root 권한으로 동작하므로 보안에 특별히 주의해야 합니다:

- **위험 명령 차단**: `BLOCKED_COMMANDS` 목록(`rm -rf /`, `mkfs`, `dd if=/dev/zero`, fork bomb)으로 치명적 명령 사전 차단
- **보안 헤더**: `SecurityHeadersMiddleware`가 모든 응답에 `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection` 헤더 추가
- **출력 크기 제한**: 명령 출력은 `command.max_output`(기본 1MB)으로 제한
- **터미널 세션 제한**: 최대 동시 세션 수 제한 (`terminal.max_sessions`)
- **새 기능 추가 시**: 입력 검증 철저히, 명령 인젝션 방지, 경로 탈출(path traversal) 방어 필수

## 코딩 규칙

- ruff 린터: `target-version = "py311"`, `line-length = 100`, 규칙 `E, F, I, N, W`
- 테스트: `asyncio_mode = "auto"`, httpx `AsyncClient`로 ASGI 앱 직접 테스트
- 모듈 패턴: 각 기능 모듈은 `router.py` (API 라우트), `schemas.py` (Pydantic 모델), `service.py` (비즈니스 로직) 3파일로 구성
- 새 모듈 추가 시: 위 패턴을 따르고, `app/main.py`에 라우터 등록, `tests/` 디렉토리에 테스트 추가
