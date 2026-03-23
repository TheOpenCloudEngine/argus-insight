# argus-catalog-java-source-analyzer

Java 소스코드를 정적 분석하여 ORM/DB 프레임워크에서 사용하는 **데이터베이스 테이블 매핑 정보**를 자동으로 추출하는 도구입니다.

## 지원 프레임워크

| 프레임워크 | 분석 대상 | 인식 패턴 |
|-----------|----------|----------|
| **JPA / Hibernate** | Java 소스 | `@Entity`, `@Table`, `@SecondaryTable`, `@JoinTable`, `@CollectionTable`, `@NamedQuery`, `@NamedNativeQuery`, `createQuery()`, `createNativeQuery()`, `EntityManager.persist/merge/remove/find` |
| **MyBatis (XML)** | XML Mapper | `<select>`, `<insert>`, `<update>`, `<delete>`, 동적 SQL(`<if>`, `<where>`, `<foreach>`), `<sql>` / `<include>` fragment |
| **MyBatis (Annotation)** | Java 소스 | `@Select`, `@Insert`, `@Update`, `@Delete`, 멀티라인 `@Select({"...", "..."})` |
| **Spring JDBC** | Java 소스 | `JdbcTemplate.query()`, `queryForObject()`, `queryForList()`, `update()`, `batchUpdate()`, `execute()` |
| **JDBC** | Java 소스 | `Statement.executeQuery()`, `executeUpdate()`, `PreparedStatement`, `Connection.prepareStatement()`, SQL 문자열 변수 |

## 분석 방식

모든 Java 파일에 대해 **AST 분석 + Regex 분석**을 동시에 수행하고 결과를 병합합니다:

```
Java Source ─┬─▶ AST Analyzer (javalang)  ──┐
             │                                ├─▶ Merger ─▶ 최종 결과
             └─▶ Regex Analyzer (re)  ───────┘
```

- **AST**: javalang 라이브러리로 정확한 구조 분석 (어노테이션 소속 클래스/필드, 파라미터 파싱)
- **Regex**: AST 실패 시 fallback + AST가 놓치는 문자열 리터럴 보완
- **SQL Parser**: 추출된 SQL 문자열을 sqlglot으로 파싱하여 테이블명과 R/W 판별

## 설치

```bash
pip install -e ".[dev]"
```

### 의존성

- `javalang>=0.13.0` — Java AST 파싱
- `sqlglot>=26.0` — SQL 문자열 파싱

## 사용법

### 1. 소스코드 분석 (`analyze`)

Java 프로젝트 디렉토리를 스캔하여 TSV 리포트를 생성합니다.

```bash
# 결과를 stdout으로 출력
java-source-analyzer analyze /path/to/java/project -p "MyProject"

# TSV 파일로 저장
java-source-analyzer analyze /path/to/java/project -p "MyProject" -o result.tsv

# JSON 형식으로 출력
java-source-analyzer analyze /path/to/java/project -p "MyProject" -f json

# TSV + JSON 동시 생성
java-source-analyzer analyze /path/to/java/project -p "MyProject" -f both -o result
# → result.tsv, result.json 생성
```

### 2. TSV 리포트 테이블 표시 (`show`)

생성된 TSV 파일을 터미널에서 포맷팅된 테이블로 확인합니다.

```bash
java-source-analyzer show result.tsv
```

출력 예시:
```
+-------------+------------------+---------------------+----------------------------+--------------+-------------------+-------------+-----------+----------+
| 프로젝트명  | 소스파일         | 패키지명            | 클래스/함수                | Java Version | Java EE Version   | 프레임워크  | 테이블명  | 사용방식 |
+-------------+------------------+---------------------+----------------------------+--------------+-------------------+-------------+-----------+----------+
| MyProject   | User.java        | com.example.domain  | User                       | 17           | Jakarta EE (JPA…) | JPA         | users     | RW       |
| MyProject   | UserMapper.xml   | com.example.mapper  | UserMapper.findById        | 17           | unknown           | MyBatis     | users     | R        |
| MyProject   | UserDao.java     | com.example.dao     | UserDao.findAll            | 17           | unknown           | Spring JDBC | users     | R        |
+-------------+------------------+---------------------+----------------------------+--------------+-------------------+-------------+-----------+----------+

Total: 3 records
```

### 3. Catalog API 서버로 업로드 (`upload`)

TSV 리포트를 Argus Catalog API 서버로 전송하여 적재합니다.

```bash
java-source-analyzer upload result.tsv --api-url http://localhost:8080

# API 키 인증
java-source-analyzer upload result.tsv --api-url http://catalog.example.com --api-key "my-secret-key"

# 타임아웃 설정
java-source-analyzer upload result.tsv --api-url http://catalog.example.com --timeout 60
```

API 엔드포인트: `POST {api-url}/api/v1/source-analysis/tables`

요청 바디:
```json
{
  "source": "java-source-analyzer",
  "record_count": 42,
  "records": [
    {
      "프로젝트명": "MyProject",
      "소스파일": "User.java",
      "패키지명": "com.example.domain",
      "클래스/함수": "User",
      "Java Version": "17",
      "Java EE Version": "Jakarta EE (JPA 3.x+)",
      "프레임워크": "JPA",
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
| 소스파일 | 분석된 소스 파일의 상대 경로 | `src/main/java/com/example/User.java` |
| 패키지명 | Java 패키지 | `com.example.domain` |
| 클래스/함수 | 테이블이 참조된 클래스 또는 메서드 | `User`, `UserMapper.findById` |
| Java Version | pom.xml/build.gradle에서 감지한 Java 버전 | `17`, `11` |
| Java EE Version | javax/jakarta 패키지로 감지한 EE 버전 | `Java EE (JPA 2.x)`, `Jakarta EE (JPA 3.x+)` |
| 프레임워크 | 사용된 ORM/DB 프레임워크 | `JPA`, `JPA/Hibernate`, `MyBatis`, `Spring JDBC`, `JDBC` |
| 테이블명 | 추출된 데이터베이스 테이블 이름 | `users`, `orders` |
| 사용방식 | 테이블 접근 유형 | `R` (읽기), `W` (쓰기), `RW` (읽기/쓰기) |

## 사용방식(R/W) 판별 기준

| 접근 유형 | 판별 기준 |
|----------|----------|
| **R** (Read) | `SELECT`, `@NamedQuery(SELECT...)`, `EntityManager.find()`, `<select>`, `@Select`, `JdbcTemplate.query*()`, `Statement.executeQuery()` |
| **W** (Write) | `INSERT`, `UPDATE`, `DELETE`, `EntityManager.persist/merge/remove()`, `<insert>/<update>/<delete>`, `@Insert/@Update/@Delete`, `JdbcTemplate.update()`, `Statement.executeUpdate()` |
| **RW** (Read/Write) | `@Entity`/`@Table` 매핑 (엔티티는 읽기/쓰기 모두 가능), `JdbcTemplate.execute()` |

## Java/EE 버전 감지

- **pom.xml**: `maven.compiler.source`, `maven.compiler.target`, `java.version`, compiler plugin 설정
- **build.gradle**: `sourceCompatibility`, `JavaVersion.VERSION_*`, `languageVersion`
- **Java EE**: `javax.persistence.*` → Java EE (JPA 2.x), `jakarta.persistence.*` → Jakarta EE (JPA 3.x+)
- **Hibernate**: 의존성에서 `org.hibernate` 감지 → `JPA/Hibernate` 프레임워크 표시

## 프로젝트 구조

```
src/java_source_analyzer/
├── cli.py                    # CLI (analyze, show, upload)
├── models.py                 # 데이터 모델 (TableMapping, RawMapping 등)
├── scanner.py                # 디렉토리 스캔 오케스트레이터
├── build_detector.py         # Java/EE 버전 감지
├── jpa/                      # JPA/Hibernate 분석기
│   ├── ast_analyzer.py       # javalang AST 기반
│   ├── regex_analyzer.py     # 정규식 기반 보조
│   ├── sql_parser.py         # SQL 문자열 파싱 (sqlglot)
│   └── merger.py             # 결과 병합
├── mybatis/                  # MyBatis 분석기
│   ├── xml_analyzer.py       # XML Mapper 파서
│   ├── annotation_analyzer.py # @Select 등 어노테이션
│   └── merger.py
├── jdbc/                     # Spring JDBC / JDBC 분석기
│   ├── ast_analyzer.py
│   ├── regex_analyzer.py
│   └── merger.py
└── output/
    ├── tsv_writer.py         # TSV 출력
    ├── json_writer.py        # JSON 출력
    ├── table_display.py      # 터미널 테이블 표시
    └── catalog_uploader.py   # Catalog API 업로드
```

## 테스트

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 라이선스

Apache License 2.0
