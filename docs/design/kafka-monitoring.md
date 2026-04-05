# Kafka Monitoring — Design Document

## Overview

Argus Insight에 Cloudera SMM(Streams Messaging Manager) 수준의 Kafka 모니터링 UI를 내장한다.
sidebar에 "Kafka Monitor" 메뉴를 추가하여, workspace에 배포된 Kafka 클러스터의 상태를 실시간으로 모니터링한다.

## 기존 인프라

- Kafka plugin: `argus-kafka` (KRaft mode, ZooKeeper-free)
- K8s StatefulSet: `argus-kafka-{workspace_name}`
- Bootstrap: `argus-kafka-{ws}-headless.{ns}.svc.cluster.local:9092`
- 설정: 환경변수 기반 (`KAFKA_*`)
- Configure dialog: broker/retention/performance/buffer 설정 가능
- Python package: `kafka-python` 또는 `confluent-kafka` 사용 예정

## 구현 Phase

### Phase 1: Topic & Consumer (Kafka Admin API only — JMX 불필요)

**서버 API**: `app/kafka_monitor/` 신규 모듈

```
GET  /api/v1/kafka-monitor/clusters                    # workspace의 Kafka 서비스 목록
GET  /api/v1/kafka-monitor/{cluster_id}/overview       # 브로커 수, 토픽 수, 파티션 수, consumer group 수
GET  /api/v1/kafka-monitor/{cluster_id}/topics          # 토픽 목록 (이름, 파티션 수, 복제 수, config)
POST /api/v1/kafka-monitor/{cluster_id}/topics          # 토픽 생성 (이름, 파티션, 복제, config)
DELETE /api/v1/kafka-monitor/{cluster_id}/topics/{name}  # 토픽 삭제
GET  /api/v1/kafka-monitor/{cluster_id}/topics/{name}/partitions  # 파티션 상세 (리더, ISR, offset)
GET  /api/v1/kafka-monitor/{cluster_id}/consumers       # Consumer Group 목록
GET  /api/v1/kafka-monitor/{cluster_id}/consumers/{group}/lag  # 파티션별 lag (latest - committed)
```

**cluster_id**: workspace_services의 `argus-kafka` 서비스 ID (음수 = workspace service)

**서버 구현 방법**:
- `confluent-kafka` 또는 `kafka-python` 패키지의 `AdminClient` 사용
- workspace service metadata에서 bootstrap_servers 추출
- `AdminClient.list_topics()` → 토픽 목록
- `AdminClient.list_consumer_groups()` → consumer group 목록
- `AdminClient.list_consumer_group_offsets()` → committed offset
- `Consumer.get_watermark_offsets()` → latest offset
- Lag = latest - committed (파티션별)

**프론트엔드**: `features/kafka-monitor/`

```
sidebar 메뉴: "Kafka Monitor" (Kafka 서비스가 있을 때만 표시 — SQL과 동일 패턴)
라우트: /dashboard/kafka-monitor

탭 구성:
  ├── Overview: 클러스터 상태 카드 (브로커, 토픽, 파티션, consumer group 수)
  ├── Topics: AG Grid 테이블 + 생성/삭제 버튼
  │     클릭 → 파티션 상세 (리더, ISR, offset 테이블)
  ├── Consumers: AG Grid 테이블 (group, state, members, lag 합계)
  │     클릭 → 파티션별 lag 바 차트
  └── (Phase 2에서 확장)
```

**UI 참고**: SQL Editor와 동일한 패턴
- workspace 선택 가드 (SQL page와 동일)
- AG Grid (Roboto Condensed, text-sm)
- DashboardHeader

**필요 패키지**: `pip install confluent-kafka` (서버)

**예상 소요**: 3-4시간

---

### Phase 2: Data Explorer & Consumer Lag 심화

**서버 API 추가**:
```
POST /api/v1/kafka-monitor/{cluster_id}/topics/{name}/messages  # 메시지 조회
  Body: { partition: 0, offset: "earliest|latest|12345", limit: 50 }
  Response: { messages: [{ partition, offset, key, value, timestamp, headers }] }

GET /api/v1/kafka-monitor/{cluster_id}/consumers/{group}/lag/history  # lag 시계열
  Query: ?minutes=30
  Response: { timestamps: [...], partitions: { "0": [...], "1": [...] } }
```

**메시지 조회 구현**:
- `Consumer.assign([TopicPartition(topic, partition, offset)])` → `Consumer.poll()` 반복
- key/value 역직렬화: bytes → UTF-8 시도 → 실패 시 hex 표시
- Avro/JSON Schema Registry 연동은 선택적

**Consumer Lag 시계열**:
- 서버에서 주기적(10초) polling → 메모리 또는 DB에 저장 (최근 1시간)
- 또는 프론트에서 polling (단순하지만 탭 닫으면 데이터 유실)

**프론트엔드 추가**:
```
Topics 탭:
  └── 토픽 클릭 → Data Explorer 슬라이드 패널
        파티션 선택 → offset 입력 → 메시지 테이블 (AG Grid)

Consumers 탭:
  └── Consumer Group 클릭 → Lag Detail
        파티션별 lag 바 차트 (recharts BarChart)
        시간별 lag 추이 LineChart (최근 30분)
```

**예상 소요**: 1일

---

### Phase 3: Broker 메트릭 (JMX Exporter 필요)

**인프라 변경**:
1. Kafka StatefulSet에 JMX Exporter sidecar 추가
   ```yaml
   - name: jmx-exporter
     image: bitnami/jmx-exporter:latest
     ports:
       - containerPort: 9404
     args: ["9404", "/etc/jmx-exporter/config.yaml"]
   ```
2. 또는 Kafka 내장 JMX 포트 노출 (`KAFKA_JMX_PORT=9999`)
3. Prometheus scrape config 추가 (Prometheus가 없으면 서버에서 직접 JMX HTTP scrape)

**핵심 JMX 메트릭**:
```
# Broker
kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec          # 초당 메시지 수
kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec             # 초당 입력 바이트
kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec            # 초당 출력 바이트
kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions     # 복제 부족 파티션
kafka.server:type=ReplicaManager,name=PartitionCount                # 파티션 수
kafka.server:type=ReplicaManager,name=LeaderCount                   # 리더 파티션 수
kafka.controller:type=KafkaController,name=ActiveControllerCount    # 활성 컨트롤러

# Request
kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Produce  # Produce 요청 지연
kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Fetch    # Fetch 요청 지연

# Log
kafka.log:type=LogFlushStats,name=LogFlushRateAndTimeMs             # 로그 플러시 지연
```

**서버 API 추가**:
```
GET /api/v1/kafka-monitor/{cluster_id}/brokers                      # 브로커 목록 + 메트릭
GET /api/v1/kafka-monitor/{cluster_id}/brokers/{id}/metrics         # 개별 브로커 메트릭
GET /api/v1/kafka-monitor/{cluster_id}/topics/{name}/metrics        # 토픽별 처리량
```

**프론트엔드 추가**:
```
Brokers 탭:
  ├── 브로커 카드 (host, port, controller 여부, 파티션 수, 리더 수)
  └── 클릭 → 메트릭 차트 (messages/sec, bytes in/out, request latency)
        recharts LineChart (실시간 10초 갱신)

Topics 탭 확장:
  └── 토픽별 처리량 컬럼 추가 (bytes in/sec, messages/sec)
```

**kafka_deploy.py 변경**: JMX Exporter sidecar를 StatefulSet에 추가
**statefulset.yaml 변경**: JMX 포트 + exporter 컨테이너

**예상 소요**: 1-2일

---

### Phase 4: E2E Flow 시각화 & Alerting

**End-to-End Flow**:
- React Flow (이미 ML Studio Modeler에서 사용 중)로 구현
- 노드: Producer (client.id) → Topic → Consumer Group
- 엣지: 처리량(messages/sec) 표시
- 데이터 소스: broker의 client metrics + consumer group metadata 조합

**Alerting**:
```
규칙 예시:
  - Consumer lag > 10000 for 5 minutes → Warning
  - Under-replicated partitions > 0 → Critical
  - Broker offline → Critical
  - Produce latency p99 > 500ms → Warning

저장: argus_kafka_alert_rules (DB 테이블)
실행: 서버 백그라운드 태스크 (10초 주기 체크)
알림: Argus Alerts 시스템 연동 (기존 alerts 모듈)
```

**예상 소요**: 2-3일

---

## 파일 구조

```
argus-insight-server/
  app/kafka_monitor/
    __init__.py
    router.py          # API 엔드포인트
    service.py          # Kafka AdminClient 래퍼, 메트릭 수집
    schemas.py          # Pydantic 모델
    metrics.py          # JMX 메트릭 수집 (Phase 3)
    alerts.py           # 알림 규칙 엔진 (Phase 4)

argus-insight-ui/
  apps/web/
    app/dashboard/kafka-monitor/page.tsx     # 라우트 페이지
    features/kafka-monitor/
      components/
        kafka-overview.tsx      # Overview 탭 (카드)
        kafka-topics.tsx        # Topics 탭 (AG Grid + CRUD)
        kafka-consumers.tsx     # Consumers 탭 (AG Grid + lag)
        kafka-data-explorer.tsx # Data Explorer (Phase 2)
        kafka-brokers.tsx       # Brokers 탭 (Phase 3)
        kafka-flow.tsx          # E2E Flow (Phase 4, React Flow)
      api.ts                    # API 호출 함수
      types.ts                  # TypeScript 타입
```

## sidebar 메뉴 동적 표시

SQL 메뉴와 동일한 패턴:
- workspace에 `argus-kafka` 서비스가 배포되어 있을 때만 sidebar에 "Kafka Monitor" 표시
- `data/menu.json`에 정적 등록 후, 서비스 유무에 따라 visibility 제어
- 또는 동적 메뉴 시스템으로 확장 (Jupyter Notebook 메뉴와 같은 패턴)

## 기술 스택

| 항목 | 선택 |
|------|------|
| Kafka 클라이언트 (서버) | `confluent-kafka` Python 패키지 (AdminClient, Consumer) |
| 메트릭 수집 | Phase 1-2: Admin API only / Phase 3: JMX Exporter + HTTP scrape |
| 시계열 저장 | 메모리 (최근 1시간) 또는 PostgreSQL (장기) |
| 차트 | recharts (LineChart, BarChart) — 이미 admin dashboard에서 사용 중 |
| 데이터 그리드 | AG Grid (Roboto Condensed) — SQL Editor와 동일 |
| 플로우 시각화 | React Flow (@xyflow/react) — ML Studio Modeler와 동일 |

## 주의사항

1. **confluent-kafka 설치**: `pip install confluent-kafka` (librdkafka C 라이브러리 의존)
   - 또는 순수 Python: `pip install kafka-python-ng` (성능 낮지만 설치 쉬움)
2. **Consumer Lag 계산 시 주의**: rebalancing 중 lag 급증은 false positive → 상태(Stable/Rebalancing) 함께 표시
3. **JMX 메트릭 고카디널리티**: 토픽×파티션×브로커 조합이 폭발적 → 집계 주기 10초 권장
4. **K8s 내부 접근**: Admin API는 bootstrap_servers로 접근 → DNS 해석 필요 (이미 CoreDNS 설정됨)
5. **인증**: Kafka SASL 인증이 있으면 AdminClient에도 동일 설정 필요 (현재 PLAINTEXT)

## 참고 오픈소스

- [AKHQ](https://github.com/tchiotludo/akhq) — 가장 완성도 높은 Kafka UI OSS
- [Kafka-UI (kafbat)](https://github.com/kafbat/kafka-ui) — 또 다른 인기 Kafka UI
- [Burrow](https://github.com/linkedin/Burrow) — LinkedIn의 Consumer Lag 모니터링 (sliding window 방식)
- [Kafka Exporter](https://github.com/danielqsj/kafka_exporter) — Prometheus 메트릭 exporter
