# argus-catalog-python-source-analyzer

Python 소스코드를 정적 분석하여 ORM/DB 프레임워크에서 사용하는 **데이터베이스 테이블 매핑 정보**를 자동으로 추출하는 도구입니다.

## 지원 프레임워크

| 프레임워크 | 분석 대상 | 인식 패턴 |
|-----------|----------|----------|
| **SQLAlchemy ORM** | Python 소스 | `__tablename__`, `class(Base)`, `mapped_column()`, `session.add/query/delete/merge/execute()` |
| **SQLAlchemy Core** | Python 소스 | `Table("name", metadata)`, `select()`, `insert()`, `update()`, `delete()`, `text("SQL")` |
| **Django ORM** | Python 소스 | `class Meta: db_table`, 모델 클래스명 자동 매핑, `objects.raw("SQL")`, `cursor.execute("SQL")` |
| **DB-API (psycopg2)** | Python 소스 | `cursor.execute("SQL")`, `cursor.executemany()` |
| **DB-API (sqlite3)** | Python 소스 | `connection.execute("SQL")`, `cursor.execute()` |
| **DB-API (기타)** | Python 소스 | pymysql, cx_Oracle, oracledb, pyodbc, pymssql, asyncpg, aiomysql, aiosqlite |

## 분석 방식

모든 Python 파일에 대해 **AST 분석 + Regex 분석**을 동시에 수행하고 결과를 병합합니다:

```
Python Source ─┬─▶ AST Analyzer (ast 모듈)  ──┐
               │                                ├─▶ Merger ─▶ 최종 결과
               └─▶ Regex Analyzer (re)  ───────┘
```

- **AST**: Python 표준 `ast` 모듈로 정확한 구조 분석 (클래스 정의, 메서드 호출, 변수 할당)
- **Regex**: AST 실패 시 fallback + 문자열 리터럴 보완
- **SQL Parser**: 추출된 SQL 문자열을 sqlglot으로 파싱하여 테이블명과 R/W 판별

## 설치

```bash
pip install -e ".[dev]"
```

### 의존성

- `sqlglot>=26.0` — SQL 문자열 파싱 (외부 파서 불필요: Python AST는 표준 라이브러리)

## 사용법

### 1. 소스코드 분석 (`analyze`)

Python 프로젝트 디렉토리를 스캔하여 TSV 리포트를 생성합니다.

```bash
# 결과를 stdout으로 출력
python-source-analyzer analyze /path/to/python/project -p "MyProject"

# TSV 파일로 저장
python-source-analyzer analyze /path/to/python/project -p "MyProject" -o result.tsv

# JSON 형식으로 출력
python-source-analyzer analyze /path/to/python/project -p "MyProject" -f json

# TSV + JSON 동시 생성
python-source-analyzer analyze /path/to/python/project -p "MyProject" -f both -o result
# → result.tsv, result.json 생성
```

### 2. TSV 리포트 테이블 표시 (`show`)

생성된 TSV 파일을 터미널에서 포맷팅된 테이블로 확인합니다.

```bash
python-source-analyzer show result.tsv
```

출력 예시:
```
+-------------+-------------------+------------------+---------------------+----------------+-------------------+-----------+----------+
| 프로젝트명  | 소스파일          | 모듈경로         | 클래스/함수         | Python Version | 프레임워크        | 테이블명  | 사용방식 |
+-------------+-------------------+------------------+---------------------+----------------+-------------------+-----------+----------+
| MyProject   | models.py         | myapp.models     | User                | 3.11           | SQLAlchemy        | users     | RW       |
| MyProject   | models.py         | myapp.models     | Author              | 3.11           | Django ORM        | authors   | RW       |
| MyProject   | repo.py           | myapp.repo       | find_all_users      | 3.11           | DB-API (psycopg2) | users     | R        |
+-------------+-------------------+------------------+---------------------+----------------+-------------------+-----------+----------+

Total: 3 records
```

### 3. Catalog API 서버로 업로드 (`upload`)

TSV 리포트를 Argus Catalog API 서버로 전송하여 적재합니다.

```bash
python-source-analyzer upload result.tsv --api-url http://localhost:8080

# API 키 인증
python-source-analyzer upload result.tsv --api-url http://catalog.example.com --api-key "my-secret-key"

# 타임아웃 설정
python-source-analyzer upload result.tsv --api-url http://catalog.example.com --timeout 60
```

API 엔드포인트: `POST {api-url}/api/v1/source-analysis/tables`

요청 바디:
```json
{
  "source": "python-source-analyzer",
  "record_count": 15,
  "records": [
    {
      "프로젝트명": "MyProject",
      "소스파일": "models.py",
      "모듈경로": "myapp.models",
      "클래스/함수": "User",
      "Python Version": "3.11",
      "프레임워크": "SQLAlchemy",
      "테이블명": "users",
      "사용방식": "RW"
    }
  ]
}
```

## 출력 필드

| 필드 | 설명 | 예시 |
|------|------|------|
| 프로젝트명 | 사용자가 지정한 프로젝트 이름 | `MyProject` |
| 소스파일 | 분석된 소스 파일의 상대 경로 | `myapp/models.py` |
| 모듈경로 | Python 모듈 경로 | `myapp.models` |
| 클래스/함수 | 테이블이 참조된 클래스 또는 함수 | `User`, `UserRepo.find_all` |
| Python Version | pyproject.toml/setup.py에서 감지한 Python 버전 | `3.11`, `3.12` |
| 프레임워크 | 사용된 ORM/DB 프레임워크 | `SQLAlchemy`, `Django ORM`, `DB-API (psycopg2)` |
| 테이블명 | 추출된 데이터베이스 테이블 이름 | `users`, `orders` |
| 사용방식 | 테이블 접근 유형 | `R`, `W`, `RW` |

## 프레임워크별 인식 패턴 상세

### SQLAlchemy ORM (Declarative)
```python
class User(Base):
    __tablename__ = "users"          # → 테이블 "users", RW
    id = mapped_column(Integer, primary_key=True)
```

### SQLAlchemy Core
```python
users = Table("users", metadata,    # → 테이블 "users", RW
    Column("id", Integer, primary_key=True),
)

stmt = select(users)                 # → 테이블 "users", R
stmt = insert(users)                 # → 테이블 "users", W
conn.execute(text("SELECT * FROM orders"))  # → 테이블 "orders", R
```

### Django ORM
```python
class Author(models.Model):
    class Meta:
        db_table = "authors"         # → 테이블 "authors", RW

class Book(models.Model):           # → 테이블 "book" (자동), RW
    pass

# Raw SQL
cursor.execute("SELECT * FROM books") # → 테이블 "books", R
Author.objects.raw("SELECT * FROM authors WHERE ...") # → 테이블 "authors", R
```

### DB-API (psycopg2 / sqlite3 / 기타)
```python
cursor.execute("SELECT * FROM users")           # → 테이블 "users", R
cursor.execute("INSERT INTO orders ...")         # → 테이블 "orders", W
cursor.executemany("INSERT INTO logs ...", data) # → 테이블 "logs", W
conn.execute("DELETE FROM old_records")          # → 테이블 "old_records", W
```

## 사용방식(R/W) 판별 기준

| 접근 유형 | 판별 기준 |
|----------|----------|
| **R** (Read) | `SELECT` SQL, `session.query()`, `select()`, `cursor.execute("SELECT...")`, `objects.filter()` |
| **W** (Write) | `INSERT/UPDATE/DELETE` SQL, `session.add/delete()`, `insert()/update()/delete()`, `cursor.executemany()` |
| **RW** (Read/Write) | `__tablename__`/`Table()` 정의 (모델 자체는 R/W 모두 가능), `session.execute()` |

## Python 버전 감지

- **pyproject.toml**: `requires-python = ">=3.11"` → `3.11`
- **setup.py**: `python_requires=">=3.10"` → `3.10`
- **setup.cfg**: `python_requires` 설정
- **Classifiers**: `Programming Language :: Python :: 3.12` → `3.12`

## 프로젝트 구조

```
src/python_source_analyzer/
├── cli.py                      # CLI (analyze, show, upload)
├── models.py                   # 데이터 모델
├── scanner.py                  # 디렉토리 스캔 오케스트레이터
├── sql_parser.py               # SQL 문자열 파싱 (sqlglot)
├── merger.py                   # 결과 병합
├── project_detector.py         # Python 버전 감지
├── sqlalchemy_analyzer/        # SQLAlchemy 분석기
│   ├── ast_analyzer.py         # ast 모듈 기반
│   └── regex_analyzer.py       # 정규식 기반 보조
├── django_analyzer/            # Django ORM 분석기
│   ├── ast_analyzer.py
│   └── regex_analyzer.py
├── dbapi_analyzer/             # DB-API 분석기
│   ├── ast_analyzer.py
│   └── regex_analyzer.py
└── output/
    ├── tsv_writer.py           # TSV 출력
    ├── json_writer.py          # JSON 출력
    ├── table_display.py        # 터미널 테이블 표시
    └── catalog_uploader.py     # Catalog API 업로드
```

## 테스트

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 라이선스

Apache License 2.0
