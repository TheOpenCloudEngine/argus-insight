# Hive Query Audit Hook

## Requirement

* Hive 3.1.3 (Cloudera CDP 7.1.9 SP1)
* JDK 8

## Build

```
# mvn -Dmaven.test.skip=true clean package
```

## Configuration

### `hive-site.xml`

```xml
<property>
  <name>hive.exec.pre.hooks</name>
  <value>io.datadynamics.hive.hook.QueryAuditHook</value> 
</property>

<property>
  <name>hive.exec.post.hooks</name>
  <value>io.datadynamics.hive.hook.QueryAuditHook</value>
</property>

<property>
  <name>hive.exec.failure.hooks</name>
  <value>io.datadynamics.hive.hook.QueryAuditHook</value>
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

### Cloudera Manager

"Cloudera > Hive On Tez > Configuration > Hive Service Advanced Configuration Snippet (Safety Valve) for hive-site.xml"에 다음을 추가합니다.

* Pre Hooks
  * Name : `hive.exec.pre.hooks`
  * Value : `io.datadynamics.hive.hook.QueryAuditHook`
* Post Hooks
  * Name : `hive.exec.post.hooks`
  * Value : `io.datadynamics.hive.hook.QueryAuditHook`
* Failure Hooks
  * Name : `hive.exec.failure.hooks`
  * Value : `io.datadynamics.hive.hook.QueryAuditHook`
* Enable
  * Name : `QueryAuditHook.enabled`
  * Value : `true`
* Target URL
  * Name : `QueryAuditHook.target.url` 
  * Value : `http://10.10.10.10/api/hive/audit`

## Deployment

* 빌드한 JAR 파일은 `hive-site.xml` 파일에  `hive.aux.jars.path` 설정을 통해 지정 가능합니다.
* Comma Separated로 N개 JAR 파일을 지정할 수 있습니다.
* Hook에서 외부 라이브러리를 사용하는 경우 Maven dependency plugin을 통해 함께 패키징하도록 합니다.
* JAR 파일 지정시 경로는 로컬 파일 시스템 또는 HDFS 지정할 수 있습니다.
* 로컬 파일 시스템을 지정하는 경우 모든 노드에 배포하도록 하도록 합니다.

### Valina Hadoop

`hive-site.xml` 파일에 다음을 추가합니다.

```xml
<property>
  <name>hive.aux.jars.path</name>
  <value>/opt/lib-ext/</value>
  <description>HDFS 및 로컬 파일 시스템의 보조 JAR 경로</description>
</property>
```

### Cloudera CDP

"Cloudera Manager > Hive On Tez > Configuration > Hive Auxiliary JARs Directory"를 찾아서 경로를 지정하도록 합니다.
