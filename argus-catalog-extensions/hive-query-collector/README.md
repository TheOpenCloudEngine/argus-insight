# Hive Query Hook

Hive의 `ExecuteWithHookContext` 인터페이스를 구현하여 쿼리 실행 이벤트(시작, 성공, 실패)를 수집하고 외부 REST API로 전송하는 Hook입니다.

## Requirement

* Hive 3.1.3 (Cloudera CDP 7.1.9 SP1)
* JDK 11+

> 이 프로젝트는 `java.net.http.HttpClient`, `Map.of()` 등 JDK 11 이상의 API를 사용합니다.

## Build

```
# mvn -Dmaven.test.skip=true clean package
```

빌드 결과물:
* `target/hive-query-hook-1.0.1.jar` — Hook 클래스만 포함
* `target/hive-query-hook-1.0.1-jar-with-dependencies.jar` — Jackson 등 외부 의존성 포함 (배포용)

## Hive Query 수집 메커니즘

### Hook 동작 원리

Hive는 쿼리 실행 과정에서 특정 시점에 등록된 Hook을 호출합니다. `QueryAuditHook`은 `ExecuteWithHookContext` 인터페이스를 구현하며, Hive가 `run(HookContext context)` 메소드를 호출할 때 실행됩니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hive Query 실행 흐름                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client ──▶ HiveServer2 ──▶ Query Parse ──▶ Query Plan 생성     │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ PRE_EXEC_HOOK    │ ◀── 쿼리 실행 직전 호출                    │
│  │ status: RUNNING  │     시작 시각, 쿼리, 사용자 정보 전송       │
│  └────────┬─────────┘                                           │
│           ▼                                                     │
│  ┌──────────────────┐                                           │
│  │   Query 실행      │                                           │
│  └────────┬─────────┘                                           │
│           ▼                                                     │
│  ┌──────────────────┐    ┌───────────────────┐                  │
│  │ POST_EXEC_HOOK   │    │ ON_FAILURE_HOOK    │                  │
│  │ status: SUCCESS   │    │ status: FAILED     │                  │
│  │ 종료시각, 소요시간 │    │ 종료시각, 에러메시지 │                  │
│  └──────────────────┘    └───────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### HookContext 주요 필드

`HookContext`는 Hive가 Hook에 전달하는 컨텍스트 객체로, 쿼리 실행에 관한 모든 정보를 포함합니다.

| 메소드 | 반환 타입 | 설명 |
|--------|-----------|------|
| `getHookType()` | `HookContext.HookType` | Hook 유형 (`PRE_EXEC_HOOK`, `POST_EXEC_HOOK`, `ON_FAILURE_HOOK`) |
| `getConf()` | `HiveConf` | Hive 설정 (`hive-site.xml`의 모든 속성 접근 가능) |
| `getQueryPlan()` | `QueryPlan` | 쿼리 실행 계획 (쿼리 ID, 쿼리 문자열, 시작 시각 등) |
| `getUgi()` | `UserGroupInformation` | Kerberos/OS 사용자 정보 (`getShortUserName()` → `alice`) |
| `getUserName()` | `String` | 세션 사용자명 (Kerberos의 경우 `alice@REALM.COM`) |
| `getOperationName()` | `String` | 실행 작업 유형 (`QUERY`, `CREATETABLE`, `ALTERTABLE_ADDCOLS` 등) |
| `getException()` | `Exception` | 실패 시 예외 객체 (`ON_FAILURE_HOOK`에서만 유효) |
| `getInputs()` | `Set<ReadEntity>` | 쿼리가 읽는 테이블/파티션 목록 |
| `getOutputs()` | `Set<WriteEntity>` | 쿼리가 쓰는 테이블/파티션 목록 |
| `getQueryState()` | `QueryState` | 쿼리 상태 및 진행 정보 |

### QueryPlan 주요 필드

| 메소드 | 반환 타입 | 설명 |
|--------|-----------|------|
| `getQueryId()` | `String` | 쿼리 고유 ID (예: `hive_20260321143012_abcd1234`) |
| `getQueryString()` | `String` | 실행된 쿼리 원문 |
| `getQueryStartTime()` | `long` | 쿼리 시작 시각 (epoch millis) |
| `getOperationName()` | `String` | 실행 작업 유형 |

### HookType 종류

| Hook Type | 설정 키 | 호출 시점 | 용도 |
|-----------|---------|-----------|------|
| `PRE_EXEC_HOOK` | `hive.exec.pre.hooks` | 쿼리 실행 직전 | 쿼리 시작 기록, 실행 중 상태 전송 |
| `POST_EXEC_HOOK` | `hive.exec.post.hooks` | 쿼리 성공 완료 후 | 소요 시간, 성공 상태 전송 |
| `ON_FAILURE_HOOK` | `hive.exec.failure.hooks` | 쿼리 실패 시 | 에러 메시지, 실패 상태 전송 |

### 전송 JSON 포맷

**PRE_EXEC_HOOK (RUNNING)**

```json
{
  "queryId": "hive_20260321143012_abcd1234",
  "shortUsername": "alice",
  "username": "alice@REALM.COM",
  "operationName": "QUERY",
  "startTime": "1742536212000",
  "query": "SELECT * FROM db.table WHERE dt = '2026-03-21'",
  "status": "RUNNING"
}
```

**POST_EXEC_HOOK (SUCCESS)**

```json
{
  "queryId": "hive_20260321143012_abcd1234",
  "shortUsername": "alice",
  "username": "alice@REALM.COM",
  "operationName": "QUERY",
  "startTime": "1742536212000",
  "endTime": "1742536215000",
  "durationMs": "3000",
  "query": "SELECT * FROM db.table WHERE dt = '2026-03-21'",
  "status": "SUCCESS"
}
```

**ON_FAILURE_HOOK (FAILED)**

```json
{
  "queryId": "hive_20260321143012_abcd1234",
  "shortUsername": "alice",
  "username": "alice@REALM.COM",
  "operationName": "QUERY",
  "startTime": "1742536212000",
  "endTime": "1742536214000",
  "durationMs": "2000",
  "errorMsg": "SemanticException [Error 10001]: Table not found 'db.unknown_table'",
  "query": "SELECT * FROM db.unknown_table",
  "status": "FAILED"
}
```

### operationName 주요 값

| 값 | 설명 |
|----|------|
| `QUERY` | SELECT, INSERT, CTAS 등 일반 쿼리 |
| `CREATETABLE` | 테이블 생성 |
| `DROPTABLE` | 테이블 삭제 |
| `ALTERTABLE_ADDCOLS` | 컬럼 추가 |
| `ALTERTABLE_RENAME` | 테이블명 변경 |
| `CREATEDATABASE` | 데이터베이스 생성 |
| `DROPDATABASE` | 데이터베이스 삭제 |
| `LOAD` | LOAD DATA 실행 |
| `EXPORT` | EXPORT TABLE 실행 |
| `IMPORT` | IMPORT TABLE 실행 |

## Configuration

### `hive-site.xml`

```xml
<property>
  <name>hive.exec.pre.hooks</name>
  <value>org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook</value>
</property>

<property>
  <name>hive.exec.post.hooks</name>
  <value>org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook</value>
</property>

<property>
  <name>hive.exec.failure.hooks</name>
  <value>org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook</value>
</property>

<property>
  <name>QueryAuditHook.enabled</name>
  <value>true</value>
</property>

<property>
  <name>QueryAuditHook.target.url</name>
  <value>http://10.10.10.10/api/hive/audit</value>
</property>
```

> **기존 Hook이 있는 경우**: 기존 값에 콤마로 추가합니다.
> 예: `org.apache.atlas.hive.hook.HiveHook,org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook`

### Cloudera Manager

"Cloudera > Hive On Tez > Configuration > Hive Service Advanced Configuration Snippet (Safety Valve) for hive-site.xml"에 다음을 추가합니다.

* Pre Hooks
  * Name : `hive.exec.pre.hooks`
  * Value : `org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook`
* Post Hooks
  * Name : `hive.exec.post.hooks`
  * Value : `org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook`
* Failure Hooks
  * Name : `hive.exec.failure.hooks`
  * Value : `org.opencloudengine.argus.catalog.collector.hql.hook.QueryAuditHook`
* Enable
  * Name : `QueryAuditHook.enabled`
  * Value : `true`
* Target URL
  * Name : `QueryAuditHook.target.url`
  * Value : `http://10.10.10.10/api/hive/audit`

## Deployment

* 빌드한 `hive-query-hook-1.0.1-jar-with-dependencies.jar` 파일을 배포합니다.
* `hive-site.xml`의 `hive.aux.jars.path` 설정을 통해 JAR 경로를 지정합니다.
* Comma Separated로 N개 JAR 파일을 지정할 수 있습니다.
* JAR 파일 경로는 로컬 파일 시스템 또는 HDFS를 지정할 수 있습니다.
* 로컬 파일 시스템을 지정하는 경우 **모든 HiveServer2 노드**에 동일하게 배포해야 합니다.

### Vanilla Hadoop

`hive-site.xml` 파일에 다음을 추가합니다.

```xml
<property>
  <name>hive.aux.jars.path</name>
  <value>/opt/lib-ext/</value>
  <description>HDFS 및 로컬 파일 시스템의 보조 JAR 경로</description>
</property>
```

### Cloudera CDP

"Cloudera Manager > Hive On Tez > Configuration > Hive Auxiliary JARs Directory"를 찾아서 경로를 지정합니다.
