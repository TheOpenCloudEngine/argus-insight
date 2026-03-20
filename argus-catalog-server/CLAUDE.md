# Catalog Server

Argus 플랫폼의 **데이터 카탈로그 관리 서버**입니다. DataHub 스타일의 데이터 카탈로그 기능을 제공합니다.

## 핵심 기능

- **데이터셋 관리** (`catalog`): 데이터셋 등록/조회/검색/수정/삭제
- **플랫폼 관리**: 데이터 플랫폼 등록 (Hive, MySQL, Kafka, S3 등)
- **태그 관리**: 데이터셋 분류를 위한 태그 CRUD
- **용어집 관리**: 비즈니스 용어집(Glossary) CRUD
- **스키마 관리**: 데이터셋의 필드/컬럼 스키마 관리
- **소유자 관리**: 데이터셋 소유자 (Technical Owner, Business Owner, Data Steward)
- **검색**: 이름, 설명, URN, 플랫폼, 태그 기반 검색

## 기술 스택

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async)
- Pydantic v2
- PostgreSQL / MariaDB

## 프로젝트 구조

```
argus-catalog-server/
├── app/
│   ├── __init__.py          # 버전 정의
│   ├── main.py              # FastAPI 엔트리포인트
│   ├── core/
│   │   ├── config.py        # Settings 클래스
│   │   ├── config_loader.py # properties + YAML 로더
│   │   ├── database.py      # SQLAlchemy 비동기 엔진
│   │   ├── logging.py       # 일별 롤링 로깅
│   │   └── security.py      # 보안 헤더 미들웨어
│   └── catalog/
│       ├── router.py        # API 엔드포인트
│       ├── schemas.py       # Pydantic 모델
│       ├── service.py       # 비즈니스 로직
│       └── models.py        # SQLAlchemy ORM 모델
├── tests/
├── packaging/config/
│   ├── config.yml
│   └── config.properties
├── pyproject.toml
└── Makefile
```

## 주요 명령어

```bash
cd argus-catalog-server
make dev      # pip install -e ".[dev]"
make run      # uvicorn --reload (port 4600)
make test     # pytest
make lint     # ruff check
make format   # ruff format
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 |
| GET | /api/v1/catalog/stats | 카탈로그 통계 |
| GET | /api/v1/catalog/platforms | 플랫폼 목록 |
| POST | /api/v1/catalog/platforms | 플랫폼 등록 |
| GET | /api/v1/catalog/tags | 태그 목록 |
| POST | /api/v1/catalog/tags | 태그 생성 |
| GET | /api/v1/catalog/glossary | 용어집 목록 |
| POST | /api/v1/catalog/glossary | 용어 생성 |
| GET | /api/v1/catalog/datasets | 데이터셋 검색/목록 |
| POST | /api/v1/catalog/datasets | 데이터셋 등록 |
| GET | /api/v1/catalog/datasets/{id} | 데이터셋 상세 |
| PUT | /api/v1/catalog/datasets/{id} | 데이터셋 수정 |
| DELETE | /api/v1/catalog/datasets/{id} | 데이터셋 삭제 |
| POST | /api/v1/catalog/datasets/{id}/tags/{tag_id} | 태그 연결 |
| POST | /api/v1/catalog/datasets/{id}/owners | 소유자 추가 |
| PUT | /api/v1/catalog/datasets/{id}/schema | 스키마 업데이트 |

## 코딩 규칙

- ruff: `target-version = "py311"`, `line-length = 100`
- 모듈 패턴: `router.py`, `schemas.py`, `service.py`, `models.py`
- 기본 포트: **4600**
