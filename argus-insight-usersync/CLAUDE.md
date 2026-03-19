# Argus Insight UserSync

Apache Ranger UserSync의 Python 구현체입니다. 외부 소스(LDAP/AD, Unix, 파일)에서 사용자와 그룹 정보를 읽어 Apache Ranger Admin에 동기화하는 배치 작업입니다.

## 핵심 기능

- **사용자/그룹 동기화**: 외부 소스에서 사용자/그룹을 가져와 Ranger Admin에 생성/업데이트
- **다중 소스 지원**: LDAP/Active Directory, Unix (/etc/passwd, /etc/group), 파일(CSV/JSON)
- **그룹 멤버십 동기화**: 사용자-그룹 매핑을 Ranger에 반영
- **변경 감지**: 기존 Ranger 데이터와 비교하여 변경된 항목만 업데이트
- **드라이런 모드**: Ranger를 수정하지 않고 동기화 대상을 미리 확인

## 아키텍처

```
External Source (LDAP/Unix/File)  →  SyncEngine  →  Ranger Admin REST API
                                         ↑
                                    config.yml
```

- **SyncSource**: 소스별 사용자/그룹 조회 추상화 (LDAP, Unix, File)
- **RangerClient**: Ranger Admin XUser REST API 클라이언트
- **SyncEngine**: 소스 → Ranger 동기화 오케스트레이터

## 운영 환경

- systemd timer로 하루 1회 실행 (`argus-insight-usersync.timer`)
- oneshot 서비스로 동작 (`argus-insight-usersync.service`)
- 일반 사용자 권한으로 실행 (argus 계정)
- 디렉토리 구조:
  - `/etc/argus-insight-usersync/` - 설정 파일 (`config.yml`, `config.properties`)
  - `/var/log/argus-insight-usersync/` - 로그 파일 (`usersync.log`)
  - `/opt/argus-insight-usersync/` - 애플리케이션 코드
  - `/opt/argus-insight-usersync/bin/argus-insight-usersync` - 엔트리포인트

## 기술 스택

- Python 3.11+
- httpx (Ranger Admin REST API 통신)
- python-ldap (LDAP/AD 소스)
- PyYAML (설정 파일 파싱)
- 빌드: setuptools
- 린터: ruff
- 테스트: pytest

## 프로젝트 구조

```
argus-insight-usersync/
├── app/
│   ├── __init__.py          # 버전 정의 (__version__)
│   ├── main.py              # 배치 작업 엔트리포인트, CLI 인자 파싱
│   ├── core/
│   │   ├── config.py        # Settings 클래스 (config.yml + config.properties 기반)
│   │   ├── config_loader.py # properties 파싱 + YAML ${var} 변수 치환 로더
│   │   ├── logging.py       # 일별 롤링 파일 + 콘솔 로깅 설정
│   │   └── models.py        # UserInfo, GroupInfo, SyncResult 데이터 모델
│   ├── source/              # 동기화 소스 모듈
│   │   ├── base.py          # SyncSource 추상 기본 클래스
│   │   ├── ldap_source.py   # LDAP/AD 소스 (python-ldap, 페이지 검색)
│   │   ├── unix_source.py   # Unix 소스 (/etc/passwd, /etc/group)
│   │   └── file_source.py   # 파일 소스 (CSV, JSON)
│   ├── ranger/              # Ranger Admin 클라이언트
│   │   └── client.py        # XUser REST API 클라이언트 (사용자/그룹/멤버십 CRUD)
│   └── sync/                # 동기화 엔진
│       └── engine.py        # SyncEngine (소스 → Ranger 오케스트레이션)
├── tests/
│   ├── conftest.py          # 공통 fixtures
│   ├── test_models.py       # 데이터 모델 테스트
│   ├── test_file_source.py  # 파일 소스 테스트
│   ├── test_ranger_client.py # Ranger 클라이언트 테스트
│   └── test_sync_engine.py  # 동기화 엔진 테스트
├── packaging/
│   ├── config/
│   │   ├── config.yml         # YAML 설정 파일 (${var} 변수 사용)
│   │   └── config.properties  # Java-style 변수 정의 파일
│   └── systemd/
│       ├── argus-insight-usersync.service  # oneshot 서비스 유닛
│       └── argus-insight-usersync.timer    # 일일 타이머 유닛
├── scripts/argus-insight-usersync  # 시스템 설치 시 엔트리포인트
├── requirements.txt         # Python 의존성
├── pyproject.toml           # 프로젝트 설정 및 의존성
└── Makefile                 # 빌드/실행/테스트 명령
```

## 설정 시스템

Spring Boot 스타일의 `${변수:기본값}` 문법을 사용합니다.

### 설정 항목 전체 목록

| 섹션 | YAML 키 | properties 변수 | 기본값 | 설명 |
|------|---------|----------------|--------|------|
| logging | level | log.level | INFO | 로그 레벨 |
| logging | dir | log.dir | /var/log/argus-insight-usersync | 로그 디렉토리 |
| logging | filename | log.filename | usersync.log | 로그 파일명 |
| sync | source | sync.source | unix | 동기화 소스 타입 (unix/ldap/file) |
| sync | user_filter | sync.user_filter | (비어있음) | 동기화할 사용자 필터 (쉼표 구분) |
| sync | group_filter | sync.group_filter | (비어있음) | 동기화할 그룹 필터 (쉼표 구분) |
| sync | min_uid | sync.min_uid | 500 | Unix 소스 최소 UID |
| sync | min_gid | sync.min_gid | 500 | Unix 소스 최소 GID |
| ldap | url | ldap.url | ldap://localhost:389 | LDAP 서버 URL |
| ldap | bind_dn | ldap.bind_dn | (비어있음) | LDAP 바인드 DN |
| ldap | bind_password | ldap.bind_password | (비어있음) | LDAP 바인드 비밀번호 |
| ldap | user_search_base | ldap.user_search_base | (비어있음) | 사용자 검색 기본 DN |
| ldap | user_search_filter | ldap.user_search_filter | (objectClass=person) | 사용자 검색 필터 |
| ldap | group_search_base | ldap.group_search_base | (비어있음) | 그룹 검색 기본 DN |
| ldap | group_search_filter | ldap.group_search_filter | (objectClass=groupOfNames) | 그룹 검색 필터 |
| file | users_path | file.users_path | (비어있음) | 사용자 파일 경로 |
| file | groups_path | file.groups_path | (비어있음) | 그룹 파일 경로 |
| file | format | file.format | csv | 파일 형식 (csv/json) |
| ranger | url | ranger.url | http://localhost:6080 | Ranger Admin URL |
| ranger | username | ranger.username | admin | Ranger Admin 사용자명 |
| ranger | password | ranger.password | admin | Ranger Admin 비밀번호 |
| ranger | timeout | ranger.timeout | 30 | Ranger API 타임아웃 (초) |

## CLI 실행 및 옵션

```bash
# 개발 모드 실행
cd argus-insight-usersync
python -m app.main

# 설정 파일 지정
python -m app.main --config-yaml /path/to/config.yml --config-properties /path/to/config.properties

# 드라이런 (Ranger 수정 없이 소스 데이터만 확인)
python -m app.main --dry-run

# pip install 후 명령어 실행
argus-insight-usersync
argus-insight-usersync --dry-run
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `--help` | 도움말 출력 |
| `--config-yaml PATH` | YAML 설정 파일 경로 지정 |
| `--config-properties PATH` | Properties 변수 파일 경로 지정 |
| `--dry-run` | Ranger를 수정하지 않고 소스 데이터만 출력 |

## 주요 명령어

```bash
cd argus-insight-usersync

# 의존성 설치 (개발용)
make dev

# 실행 (배치 작업)
make run

# 드라이런
make dry-run

# 테스트
make test

# 린트
make lint

# 포맷팅
make format
```

## Ranger Admin REST API

UserSync가 사용하는 Ranger XUser API:

| Method | Path | 설명 |
|--------|------|------|
| GET | /service/xusers/users | 사용자 목록 (페이지네이션) |
| GET | /service/xusers/users/userName/{name} | 사용자명으로 조회 |
| POST | /service/xusers/secure/users | 사용자 생성 |
| PUT | /service/xusers/secure/users/{id} | 사용자 수정 |
| GET | /service/xusers/groups | 그룹 목록 (페이지네이션) |
| GET | /service/xusers/groups/groupName/{name} | 그룹명으로 조회 |
| POST | /service/xusers/secure/groups | 그룹 생성 |
| PUT | /service/xusers/secure/groups/{id} | 그룹 수정 |
| POST | /service/xusers/groupusers | 그룹-사용자 매핑 생성 |

## 코딩 규칙

- ruff 린터: `target-version = "py311"`, `line-length = 100`, 규칙 `E, F, I, N, W`
- 테스트: pytest, httpx mock (respx)
- 모듈 패턴: source/ (소스 추상화), ranger/ (API 클라이언트), sync/ (오케스트레이션)
