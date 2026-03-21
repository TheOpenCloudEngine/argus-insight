# Argus Catalog Metadata Sync

외부 데이터 플랫폼(Hive Metastore 등)에서 메타데이터를 수집하여 Argus Catalog Server에 동기화하는 배치/서비스입니다.

## 기술 스택

- Python 3.11+
- FastAPI (원격 제어 API)
- hmsclient (Hive Metastore Thrift)
- requests (Cloudera Manager API 통신)
- sqlglot (SQL lineage 파싱)
- schedule (주기적 동기화)
- Pydantic v2

## 프로젝트 구조

```
argus-catalog-metadata-sync/
├── src/sync/
│   ├── main.py              # CLI 엔트리포인트 (server/batch 모드)
│   ├── api.py               # FastAPI REST API (원격 제어)
│   ├── core/
│   │   ├── base.py          # BasePlatformSync 추상 클래스
│   │   ├── catalog_client.py # Argus Catalog Server REST 클라이언트
│   │   ├── config.py        # YAML 설정 로더
│   │   ├── database.py      # SQLAlchemy 엔진/세션 관리
│   │   └── scheduler.py     # 주기적 동기화 스케줄러
│   └── platforms/
│       ├── hive/
│       │   ├── sync.py           # Hive Metastore 동기화 구현
│       │   ├── models.py         # ORM 모델 (쿼리 이력, lineage)
│       │   ├── query_history.py  # 쿼리 이벤트 수신/저장
│       │   ├── lineage_parser.py # SQLGlot 기반 Hive SQL lineage 파서
│       │   └── lineage_service.py # Lineage 저장 로직
│       └── impala/
│           ├── models.py          # ImpalaQueryHistory ORM 모델
│           ├── collector.py       # Cloudera Manager API 쿼리 수집기
│           ├── scheduler.py       # 주기적 수집 스케줄러
│           └── lineage_service.py # Impala lineage 파싱/저장
├── config/
│   └── sync.yml             # 설정 파일
├── tests/
├── pyproject.toml
└── Makefile
```

## 실행 방법

```bash
# 개발 환경 설치
make dev

# API 서버 모드 (port 4610, 스케줄러 포함)
make server
# 또는
metadata-sync --mode server

# 배치 모드 (1회 실행 후 종료)
metadata-sync --mode batch
metadata-sync --mode batch --platform hive
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 |
| GET | /sync/status | 전체 플랫폼 동기화 상태 |
| GET | /sync/{platform}/status | 특정 플랫폼 동기화 상태 |
| POST | /sync/{platform}/run | 즉시 동기화 실행 |
| GET | /sync/{platform}/discover | 테이블 목록 미리보기 |
| PUT | /sync/{platform}/schedule | 동기화 주기 설정 |
| GET | /sync/{platform}/schedule | 동기화 주기 조회 |
| PUT | /sync/hive/connection | Hive 연결 설정 변경 |
| POST | /sync/hive/test | Hive 연결 테스트 |
| POST | /collector/hive/query | Hive 쿼리 이벤트 수집 (Hook → lineage 파싱 포함) |

## 새 플랫폼 추가 방법

1. `src/sync/platforms/{platform_name}/sync.py` 생성
2. `BasePlatformSync`를 상속하여 `connect()`, `disconnect()`, `discover()`, `sync()` 구현
3. `config.py`에 플랫폼 설정 모델 추가
4. `api.py`에 플랫폼 등록 로직 추가
