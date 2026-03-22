# Alert System — 리니지 변경 알림

## 개요

Argus Catalog의 Alert 시스템은 **이기종 시스템 간 데이터셋 스키마 변경**이 리니지 관계에 미치는 영향을 자동으로 감지하고, 관련 담당자에게 알림을 전달하는 시스템이다.

예를 들어 PostgreSQL의 `employees` 테이블에서 `salary` 컬럼이 삭제되면, 이 컬럼이 Impala의 `emp_fact.salary_amt`에 매핑되어 있다면 **BREAKING** 알림을 생성하여 ETL 파이프라인 담당자에게 즉시 통보한다.

## 아키텍처

```
Sync 실행 → 스키마 변경 감지 → save_schema_snapshot()
                                      │
                                      ▼ changes가 있으면
                            evaluate_rules_and_create_alerts()
                                      │
                            ┌─────────┴──────────┐
                            ▼                    ▼
                      활성 Rule 조회         변경된 데이터셋 정보 조회
                            │                (태그, 플랫폼, 리니지)
                            ▼
                      각 Rule에 대해:
                      1. Scope 매칭 (이 변경이 이 Rule의 감시 범위인가?)
                      2. Trigger 매칭 (트리거 조건에 부합하는가?)
                      3. Alert 생성 + 알림 전달
```

## Alert Rule 정의

Alert Rule은 **"무엇을 감시하고, 언제 알림을 만들고, 누구에게 어떻게 전달하는가"**를 하나로 정의한다.

```
Alert Rule = 감시 대상 (Scope) + 트리거 조건 (Trigger) + 알림 설정 (Notify)
```

### Scope (감시 대상)

| scope_type | scope_id | 설명 | 예시 |
|-----------|----------|------|------|
| `DATASET` | dataset_id | 특정 데이터셋 하나 | `payment_transactions` 테이블 |
| `TAG` | tag_id | 태그가 붙은 모든 데이터셋 | `PII` 태그 → 50개 테이블 자동 포함 |
| `LINEAGE` | lineage_id | 특정 리니지 관계 (A→B) | `employees → emp_fact` 연결 |
| `PLATFORM` | platform_id | 특정 플랫폼의 모든 데이터셋 | PostgreSQL 인스턴스 전체 |
| `ALL` | NULL | 카탈로그 내 모든 데이터셋 | 전체 감시 |

**TAG scope의 장점:**
- 새 테이블에 태그만 붙이면 자동으로 감시 대상에 포함
- 태그를 떼면 자동으로 제외
- Rule 수정 없이 **태그 관리만으로 감시 범위 조절**

**LINEAGE scope의 동작:**
- 리니지의 source 또는 target 중 하나가 변경되면 발동
- 컬럼 매핑이 있으면 매핑 기반 정밀 분석

### Trigger (트리거 조건)

| trigger_type | trigger_config | 설명 |
|-------------|----------------|------|
| `ANY` | `{}` | 모든 스키마 변경 시 발동 |
| `SCHEMA_CHANGE` | `{"change_types": ["DROP","MODIFY"]}` | 특정 변경 유형만 감시 |
| `COLUMN_WATCH` | `{"columns": ["salary","emp_id"], "change_types": ["DROP"]}` | 특정 컬럼만 감시 |
| `MAPPING_BROKEN` | `{}` | 컬럼 매핑된 컬럼이 변경될 때만 발동 |
| `SYNC_STALE` | `{"stale_hours": 24}` | N시간 이상 sync 안 됨 (예약) |

### Severity (심각도)

| 설정 | 동작 |
|------|------|
| `null` (Auto) | 변경 유형에 따라 자동 판정 (DROP=BREAKING, 타입변경=WARNING, 나머지=INFO) |
| `BREAKING` | 강제로 BREAKING 지정 |
| `WARNING` | 강제로 WARNING 지정 |
| `INFO` | 강제로 INFO 지정 |

자동 판정 기준:
- **BREAKING**: 매핑된 컬럼이 삭제됨 → 파이프라인 깨짐
- **WARNING**: 매핑된 컬럼의 데이터 타입이 변경됨 → 타입 불일치 가능
- **INFO**: 매핑되지 않은 컬럼 변경, 컬럼 추가

### Notify (알림 설정)

| 필드 | 설명 |
|------|------|
| `channels` | 알림 채널 (콤마 구분): `IN_APP`, `WEBHOOK`, `EMAIL` |
| `webhook_url` | WEBHOOK 채널일 때 전송 URL (Slack, Teams 등) |
| `subscribers` | 구독자 목록 (콤마 구분): `"team@co.com,user@co.com"` |
| `notify_owners` | `true`이면 데이터셋 Owner에게도 IN_APP 알림 |

## Rule 정의 예시

### 1. PII 태그 테이블 컬럼 삭제 감시

```json
{
    "rule_name": "PII 데이터 컬럼 삭제 감시",
    "scope_type": "TAG",
    "scope_id": 5,
    "trigger_type": "SCHEMA_CHANGE",
    "trigger_config": "{\"change_types\": [\"DROP\"]}",
    "severity_override": "BREAKING",
    "channels": "IN_APP,WEBHOOK",
    "webhook_url": "https://hooks.slack.com/xxx",
    "subscribers": "security-team@co.com,dpo@co.com",
    "notify_owners": "true"
}
```

### 2. 특정 리니지 매핑 컬럼 감시

```json
{
    "rule_name": "HR 파이프라인 매핑 감시",
    "scope_type": "LINEAGE",
    "scope_id": 7,
    "trigger_type": "MAPPING_BROKEN",
    "trigger_config": "{}",
    "severity_override": null,
    "channels": "IN_APP",
    "subscribers": "etl-team@co.com",
    "notify_owners": "true"
}
```

### 3. 결제 테이블 핵심 컬럼 감시

```json
{
    "rule_name": "결제 핵심 컬럼 감시",
    "scope_type": "DATASET",
    "scope_id": 42,
    "trigger_type": "COLUMN_WATCH",
    "trigger_config": "{\"columns\": [\"amount\",\"currency\",\"status\"], \"change_types\": [\"DROP\",\"MODIFY\"]}",
    "severity_override": "BREAKING",
    "channels": "IN_APP,WEBHOOK",
    "webhook_url": "https://hooks.teams.com/xxx",
    "subscribers": "payment-team@co.com"
}
```

## Alert 생명주기

```
OPEN → ACKNOWLEDGED → RESOLVED
                   → DISMISSED
```

| 상태 | 설명 |
|------|------|
| `OPEN` | 새로 생성된 알림 |
| `ACKNOWLEDGED` | 담당자가 확인함 (아직 미해결) |
| `RESOLVED` | 문제 해결 완료 |
| `DISMISSED` | 조치 불필요로 판단 |

## API 엔드포인트

### Alert Rule 관리

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/alerts/rules` | Rule 생성 |
| GET | `/api/v1/alerts/rules` | Rule 목록 |
| GET | `/api/v1/alerts/rules/{id}` | Rule 상세 |
| PUT | `/api/v1/alerts/rules/{id}` | Rule 수정 |
| DELETE | `/api/v1/alerts/rules/{id}` | Rule 삭제 |

### Alert 조회/관리

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/alerts/summary` | 미해결 알림 건수 (벨 배지용) |
| GET | `/api/v1/alerts` | 알림 목록 (필터: status, severity, dataset_id) |
| GET | `/api/v1/alerts/{id}` | 알림 상세 |
| PUT | `/api/v1/alerts/{id}/status` | 상태 변경 (확인/해결/무시) |

### Alert Notification (알림 전달)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/alerts/notifications` | 전달 기록 (예정) |

## Webhook Payload 예시

```json
{
    "alert_type": "SCHEMA_CHANGE",
    "severity": "BREAKING",
    "rule_name": "PII 데이터 컬럼 삭제 감시",
    "source": {
        "dataset": "employees",
        "platform": "PostgreSQL"
    },
    "affected": {
        "dataset": "emp_fact",
        "platform": "Impala"
    },
    "change_summary": "'salary' dropped (mapped to salary_amt)",
    "changes": [
        {
            "changed_column": "salary",
            "mapped_to": "salary_amt",
            "change_type": "DROP",
            "severity": "BREAKING"
        }
    ],
    "timestamp": "2026-03-23T14:30:00Z"
}
```

## UI

### Alerts 페이지 (`/dashboard/alerts`)

두 개의 탭으로 구성:

- **Alerts 탭**: 알림 목록. 상태/심각도 필터, 확인/해결/무시 액션, 상세 다이얼로그
- **Rules 탭**: 알림 규칙 카드 목록. 활성/비활성 토글, 생성/삭제

### 헤더 알림 벨

- 30초 주기로 `/alerts/summary` polling
- 미해결 알림 건수를 배지로 표시 (BREAKING=빨강, WARNING=주황)
- 클릭 시 최근 5개 알림 팝오버

### Lineage 탭 연동

- 리니지 엣지 상세 패널에서 해당 리니지에 적용된 Rule 확인
- "Add Rule" 버튼으로 LINEAGE scope가 사전 설정된 Rule 생성 다이얼로그 진입

## 데이터 모델

### argus_alert_rule

```sql
CREATE TABLE argus_alert_rule (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,        -- 규칙 이름
    description TEXT,                       -- 설명
    scope_type VARCHAR(32) NOT NULL,        -- DATASET, TAG, LINEAGE, PLATFORM, ALL
    scope_id INT,                           -- 대상 ID (ALL이면 NULL)
    trigger_type VARCHAR(64) NOT NULL,      -- ANY, SCHEMA_CHANGE, COLUMN_WATCH, MAPPING_BROKEN
    trigger_config TEXT DEFAULT '{}',       -- 조건 상세 (JSON)
    severity_override VARCHAR(16),          -- 강제 심각도 (NULL이면 자동 판정)
    channels VARCHAR(200) DEFAULT 'IN_APP', -- 알림 채널 (콤마 구분)
    notify_owners VARCHAR(5) DEFAULT 'true',-- Owner 알림 여부
    webhook_url VARCHAR(500),               -- Webhook URL
    subscribers VARCHAR(2000),              -- 구독자 (콤마 구분)
    is_active VARCHAR(5) DEFAULT 'true',    -- 활성화 여부
    created_by VARCHAR(200),                -- 생성자
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### argus_lineage_alert

```sql
CREATE TABLE argus_lineage_alert (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL,        -- SCHEMA_CHANGE
    severity VARCHAR(16) NOT NULL,          -- INFO, WARNING, BREAKING
    source_dataset_id INT NOT NULL,         -- 변경 발생 데이터셋
    affected_dataset_id INT,                -- 영향받는 데이터셋
    lineage_id INT,                         -- 관련 리니지 관계
    rule_id INT,                            -- 이 알림을 생성한 Rule
    change_summary VARCHAR(500) NOT NULL,   -- 변경 요약
    change_detail TEXT,                     -- 변경 상세 (JSON)
    status VARCHAR(20) DEFAULT 'OPEN',      -- OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED
    resolved_by VARCHAR(200),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### argus_alert_notification

```sql
CREATE TABLE argus_alert_notification (
    id SERIAL PRIMARY KEY,
    alert_id INT NOT NULL,                  -- 알림 참조
    channel VARCHAR(32) NOT NULL,           -- IN_APP, WEBHOOK, EMAIL
    recipient VARCHAR(200) NOT NULL,        -- 수신자
    sent_at TIMESTAMPTZ DEFAULT now(),
    status VARCHAR(20) DEFAULT 'SENT'       -- SENT, FAILED, READ
);
```
