# Argus Catalog — AWS SaaS 서비스 가이드

AWS에서 argus-catalog-server + argus-catalog-ui를 SaaS로 서비스하기 위한 전반적인 설계 및 운영 가이드입니다.
비용 최소화를 전제로 설계하되, 트래픽 증가에 따라 단계적으로 확장할 수 있는 구조를 목표로 합니다.

---

## 1. 아키텍처 개요

### 1.1 시스템 구성도

```
                    ┌──────────────┐
                    │  Route 53    │
                    │  (도메인 DNS) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  CloudFront  │──── S3 (UI 정적 빌드)
                    │  (CDN + TLS) │
                    └──────┬───────┘
                           │ /api/*
                    ┌──────▼──────────────────────────────────┐
                    │  EC2 (t3.medium, Reserved Instance)     │
                    │                                         │
                    │  ┌───────────────────────────────────┐  │
                    │  │  Docker Compose                   │  │
                    │  │                                   │  │
                    │  │  ┌─────────┐  ┌────────────────┐  │  │
                    │  │  │  Caddy  │  │ catalog-server │  │  │
                    │  │  │  :80    ├─►│ (FastAPI)      │  │  │
                    │  │  │  :443   │  │ :4600          │  │  │
                    │  │  └─────────┘  └───────┬────────┘  │  │
                    │  │                       │           │  │
                    │  │               ┌───────▼────────┐  │  │
                    │  │               │  PostgreSQL    │  │  │
                    │  │               │  + pgvector    │  │  │
                    │  │               │  :5432         │  │  │
                    │  │               └────────────────┘  │  │
                    │  └───────────────────────────────────┘  │
                    │                                         │
                    │  EBS gp3 (50GB)                         │
                    └─────────────────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  S3          │
                    │  (모델 아티팩트,│
                    │   DB 백업)    │
                    └──────────────┘
```

### 1.2 핵심 설계 원칙

- **매니지드 서비스 최소화**: RDS, ALB, ECS 등 고비용 서비스 대신 EC2 직접 운영
- **Docker Compose 통합**: 단일 EC2에 모든 컴포넌트 컨테이너화
- **Caddy 활용**: ALB + ACM 대신 무료 Let's Encrypt 자동 TLS
- **S3만 활용**: 정적 UI 호스팅 + 모델 아티팩트 + DB 백업
- **단계적 확장**: 트래픽 증가 시 컴포넌트를 분리하여 스케일 아웃

### 1.3 AWS 서비스 매핑

| 기존 구성요소 | AWS 서비스 | 비용 | 비고 |
|---|---|---|---|
| FastAPI 서버 | EC2 t3.medium (RI 1yr) | ~$30/월 | 2 vCPU, 4GB RAM |
| PostgreSQL + pgvector | EC2 내 Docker 컨테이너 | $0 (EC2에 포함) | RDS 대비 $50+/월 절감 |
| Next.js UI | S3 + CloudFront | ~$1/월 | 정적 빌드, 프리티어 내 |
| MinIO (S3 호환) | Amazon S3 | ~$0.25/월 | 기존 aioboto3 코드 호환 |
| 리버스 프록시 + TLS | Caddy (Docker) | $0 | ALB $16/월 절감 |
| 도메인 | Route 53 | ~$0.5/월 | Hosted zone 1개 |
| DB 스토리지 | EBS gp3 50GB | ~$4/월 | |
| DB 백업 | S3 (pg_dump 크론) | ~$0.25/월 | |

---

## 2. 비용 산정

### 2.1 Phase별 월 비용 (서울 리전 기준, USD)

| 항목 | Phase 1 (단일 EC2) | Phase 2 (EC2 2대) | Phase 3 (매니지드) |
|---|---|---|---|
| EC2 | $30 (t3.medium RI) | $60 (t3.medium × 2) | - |
| ECS Fargate | - | - | $50 |
| RDS PostgreSQL | - | - | $50+ |
| ALB | - | - | $16 |
| EBS | $4 | $8 | - |
| S3 + CloudFront | $1.5 | $1.5 | $1.5 |
| Route 53 | $0.5 | $0.5 | $0.5 |
| Stripe 수수료 | 매출의 2.9%+$0.30 | 매출의 2.9%+$0.30 | 매출의 2.9%+$0.30 |
| **합계** | **~$36** | **~$70** | **~$120+** |

### 2.2 확장 트리거 기준

```
Phase 1 → Phase 2: 사용자 50+ 또는 DB 부하로 응답 지연 발생
Phase 2 → Phase 3: 사용자 200+ 또는 고가용성(HA) SLA 필요
```

---

## 3. 인프라 구성 상세

### 3.1 Docker Compose

```yaml
# docker-compose.yml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    restart: unless-stopped

  catalog-server:
    build: ./argus-catalog-server
    environment:
      - ARGUS_CATALOG_SERVER_CONFIG_DIR=/config
    volumes:
      - ./config:/config
      - data_dir:/var/lib/argus-catalog-server
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: argus_catalog
      POSTGRES_USER: argus
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    secrets:
      - db_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U argus"]
      interval: 10s
      retries: 5
    restart: unless-stopped

secrets:
  db_password:
    file: ./secrets/db_password.txt

volumes:
  pg_data:
  data_dir:
  caddy_data:
```

### 3.2 Caddy 설정 (리버스 프록시 + 자동 TLS)

```
# Caddyfile
catalog.example.com {
    handle /api/* {
        reverse_proxy catalog-server:4600
    }
    handle {
        # SSR 필요 시 catalog-ui:3000으로 프록시
        # 정적 빌드 시 S3/CloudFront에서 직접 서빙하므로 이 블록 불필요
        respond "Not Found" 404
    }
}
```

### 3.3 UI 배포 (S3 + CloudFront)

Next.js를 정적 빌드(`output: 'export'`)하여 S3에 업로드하고 CloudFront로 서빙합니다.

```bash
# 빌드 및 배포
cd argus-catalog-ui
pnpm build                          # 정적 빌드 (out/ 디렉토리 생성)
aws s3 sync out/ s3://catalog-ui-bucket --delete
aws cloudfront create-invalidation --distribution-id EXXXXX --paths "/*"
```

CloudFront 설정:
- Origin: S3 버킷 (OAC 접근)
- Behavior: `/api/*` → EC2 origin (catalog-server)
- Default: S3 origin (정적 UI)
- TLS: CloudFront 기본 인증서 또는 ACM

### 3.4 S3 버킷 구성

| 버킷 | 용도 | 수명주기 정책 |
|---|---|---|
| `catalog-ui-{env}` | UI 정적 빌드 | 없음 (배포 시 덮어쓰기) |
| `catalog-artifacts-{env}` | ML 모델 아티팩트 | 없음 |
| `catalog-backup-{env}` | DB 백업 (pg_dump) | 30일 후 Glacier, 90일 후 삭제 |

### 3.5 DB 백업

```bash
# crontab (EC2 내부)
# 매일 03:00 KST DB 덤프 → S3 업로드
0 18 * * * docker exec postgres pg_dump -U argus argus_catalog | \
  gzip | aws s3 cp - s3://catalog-backup-prod/$(date +\%Y\%m\%d).sql.gz

# 복원 시
aws s3 cp s3://catalog-backup-prod/20260325.sql.gz - | \
  gunzip | docker exec -i postgres psql -U argus argus_catalog
```

### 3.6 모니터링

| 항목 | 도구 | 비용 |
|---|---|---|
| EC2 시스템 메트릭 | CloudWatch 기본 (5분 간격) | $0 |
| 앱 로그 | Docker 로그 + logrotate | $0 |
| 알림 | CloudWatch Alarm (무료 10개) | $0 |
| 외부 상태 체크 | UptimeRobot (무료 50개) | $0 |
| 디스크/메모리 | CloudWatch Agent (커스텀 메트릭) | ~$0.30/메트릭/월 |

### 3.7 보안

| 항목 | 적용 방법 |
|---|---|
| TLS | Caddy 자동 Let's Encrypt |
| DB 자격증명 | Docker secrets + 환경변수 (Secrets Manager 불필요) |
| JWT secret | 환경변수로 주입 (하드코딩 제거) |
| 네트워크 | EC2 Security Group: 80, 443만 공개, 5432 내부만 |
| SSH 접근 | EC2 Instance Connect 또는 SSM Session Manager |
| S3 | 퍼블릭 접근 차단, OAC로 CloudFront만 허용 |
| 업데이트 | EC2 내부에서 `docker compose pull && docker compose up -d` |

---

## 4. 멀티테넌시

### 4.1 격리 전략

비용 최소화를 위해 **Row-level 격리**를 사용합니다.

| 전략 | 격리 수준 | 비용 | 적합 시점 |
|---|---|---|---|
| **Row-level (채택)** | 논리적 | 최저 | Phase 1~2 |
| Schema-per-tenant | 중간 | 중간 | Phase 2~3 |
| DB-per-tenant | 물리적 | 최고 | Enterprise 전용 |

### 4.2 DB 스키마 추가

```sql
-- 테넌트 마스터
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(50) UNIQUE NOT NULL,
    plan            VARCHAR(20) NOT NULL DEFAULT 'starter',
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,
    -- Stripe 연동
    stripe_customer_id    VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    -- 플랜별 한도
    max_users       INT NOT NULL DEFAULT 5,
    max_platforms   INT NOT NULL DEFAULT 3,
    max_datasets    INT NOT NULL DEFAULT 500,
    max_ai_calls    INT NOT NULL DEFAULT 100,
    max_models      INT NOT NULL DEFAULT 10,
    max_storage_mb  INT NOT NULL DEFAULT 5120
);

-- 사용량 추적 (월별 집계)
CREATE TABLE tenant_usage (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID REFERENCES tenants(id),
    month       DATE NOT NULL,
    users       INT DEFAULT 0,
    platforms   INT DEFAULT 0,
    datasets    INT DEFAULT 0,
    ai_calls    INT DEFAULT 0,
    models      INT DEFAULT 0,
    storage_mb  INT DEFAULT 0,
    UNIQUE(tenant_id, month)
);

-- 과금 이력
CREATE TABLE billing_history (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID REFERENCES tenants(id),
    month       DATE NOT NULL,
    plan        VARCHAR(20),
    base_amount DECIMAL(10,2),
    overage     DECIMAL(10,2) DEFAULT 0,
    total       DECIMAL(10,2),
    status      VARCHAR(20) DEFAULT 'pending',
    paid_at     TIMESTAMP,
    invoice_url TEXT
);
```

기존 주요 테이블에 `tenant_id` 컬럼 추가:

```sql
ALTER TABLE catalog_datasets ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE catalog_platforms ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE catalog_tags ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE catalog_glossary_terms ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE registered_models ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE alert_rules ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE catalog_users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
-- ... 기타 모든 테넌트 소유 테이블

-- 인덱스 추가
CREATE INDEX idx_datasets_tenant ON catalog_datasets(tenant_id);
CREATE INDEX idx_platforms_tenant ON catalog_platforms(tenant_id);
CREATE INDEX idx_models_tenant ON registered_models(tenant_id);
```

### 4.3 테넌트 미들웨어 (자동 격리)

```python
# app/core/tenant.py
from contextvars import ContextVar
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

current_tenant_id: ContextVar[str] = ContextVar("current_tenant_id")

class TenantMiddleware(BaseHTTPMiddleware):
    """요청마다 JWT에서 tenant_id를 추출하여 ContextVar에 설정"""

    async def dispatch(self, request: Request, call_next):
        # 인증 불필요 경로 스킵
        if request.url.path in ("/health", "/api/v1/auth/login"):
            return await call_next(request)

        token_user = request.state.user  # auth 미들웨어에서 설정됨
        if not token_user or not token_user.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant not found")

        current_tenant_id.set(token_user.tenant_id)
        response = await call_next(request)
        return response
```

```python
# app/core/database.py - SQLAlchemy 이벤트로 자동 tenant 필터링
from sqlalchemy import event
from app.core.tenant import current_tenant_id

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state):
    """모든 SELECT 쿼리에 tenant_id 조건을 자동 추가"""
    tenant_id = current_tenant_id.get(None)
    if tenant_id and execute_state.is_select:
        execute_state.statement = execute_state.statement.filter_by(
            tenant_id=tenant_id
        )
```

### 4.4 테넌트 상태 라이프사이클

```
가입 완료 ──► active ──┬──► suspended ──┬──► active (결제 복구)
                       │   (결제 실패)   │
                       │                └──► cancelled ──► deleted
                       │                       (30일 유예)   (데이터 삭제)
                       └──► cancelled ──► deleted
```

| 상태 | API 접근 | 로그인 | 데이터 보존 | 트리거 |
|---|---|---|---|---|
| `active` | O | O | O | 결제 성공 |
| `suspended` | X | O (안내 페이지) | O | 결제 실패 |
| `cancelled` | X | X | O (30일) | 구독 해지 |
| `deleted` | X | X | X | 유예 기간 만료 |

---

## 5. 과금 체계

### 5.1 요금제

| | Starter | Pro | Enterprise |
|---|---|---|---|
| **월 요금** | $99 | $299 | 별도 협의 |
| 사용자 | 5명 | 20명 | 무제한 |
| 플랫폼 | 3개 | 10개 | 무제한 |
| 데이터셋 | 500개 | 5,000개 | 무제한 |
| AI 생성 (설명/태그/PII) | 100회/월 | 1,000회/월 | 무제한 |
| ML 모델 | 10개 | 100개 | 무제한 |
| 스토리지 | 5GB | 50GB | 별도 협의 |
| 지원 | 이메일 | 이메일 + 채팅 | 전담 담당자 |
| 초과 과금 | 불가 (업그레이드 필요) | 건당 과금 | N/A |

### 5.2 Pro 플랜 초과 요금

| 리소스 | 초과 단가 |
|---|---|
| 데이터셋 | $0.02/건 |
| AI 생성 | $0.05/건 |
| ML 모델 | $0.50/건 |
| 스토리지 | $0.01/MB |

### 5.3 사용량 추적 및 한도 적용

```python
# app/core/quota.py
from cachetools import TTLCache
from fastapi import HTTPException

# 메모리 캐시 (DB 조회 최소화, 5분 TTL)
_usage_cache = TTLCache(maxsize=500, ttl=300)

async def check_quota(tenant_id: str, resource: str, db: AsyncSession) -> bool:
    """한도 초과 여부 확인"""
    cache_key = f"{tenant_id}:{resource}"

    if cache_key not in _usage_cache:
        tenant = await db.get(Tenant, tenant_id)
        usage = await get_current_usage(tenant_id, resource, db)
        limit = getattr(tenant, f"max_{resource}")
        _usage_cache[cache_key] = (usage, limit)

    usage, limit = _usage_cache[cache_key]
    return usage < limit


async def increment_usage(tenant_id: str, resource: str, db: AsyncSession):
    """사용량 1 증가 (UPSERT)"""
    month = date.today().replace(day=1)
    await db.execute(
        text("""
            INSERT INTO tenant_usage (tenant_id, month, {resource})
            VALUES (:tid, :month, 1)
            ON CONFLICT (tenant_id, month)
            DO UPDATE SET {resource} = tenant_usage.{resource} + 1
        """.format(resource=resource)),
        {"tid": tenant_id, "month": month}
    )
    _usage_cache.pop(f"{tenant_id}:{resource}", None)


def require_quota(resource: str):
    """API 엔드포인트에 한도를 적용하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tenant_id = current_tenant_id.get()
            db = kwargs.get("db")

            if not await check_quota(tenant_id, resource, db):
                raise HTTPException(
                    status_code=429,
                    detail=f"Plan limit exceeded for {resource}. "
                           f"Please upgrade your plan."
                )

            result = await func(*args, **kwargs)
            await increment_usage(tenant_id, resource, db)
            return result
        return wrapper
    return decorator
```

적용 예시:

```python
# app/catalog/router.py
@router.post("/datasets")
@require_quota("datasets")
async def create_dataset(body: DatasetCreate, db: AsyncSession = Depends(get_db)):
    ...

# app/ai/router.py
@router.post("/generate")
@require_quota("ai_calls")
async def generate_description(...):
    ...
```

---

## 6. 결제 연동 (Stripe)

### 6.1 결제 흐름

```
고객 가입 ──► Stripe Checkout ──► 구독 생성 ──► Webhook ──► 테넌트 활성화
                                                  │
                    매월 자동 결제 ◄────────────────┘
                                                  │
                    결제 실패 ──► Webhook ──► 서비스 일시 중지 (suspended)
                                                  │
                    월말 ──► 초과 사용량 정산 ──► 추가 Invoice 발행
```

### 6.2 구독 관리

```python
# app/billing/service.py
import stripe

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

PLAN_PRICES = {
    "starter": "price_xxxxx",   # Stripe Dashboard에서 생성한 Price ID
    "pro": "price_yyyyy",
}


async def create_subscription(tenant_id: str, plan: str, email: str) -> str:
    """Stripe Checkout 세션 생성 → 결제 URL 반환"""
    customer = stripe.Customer.create(
        email=email,
        metadata={"tenant_id": tenant_id}
    )

    checkout = stripe.checkout.Session.create(
        customer=customer.id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICES[plan], "quantity": 1}],
        success_url="https://catalog.example.com/billing/success",
        cancel_url="https://catalog.example.com/billing/cancel",
    )
    return checkout.url


async def cancel_subscription(tenant_id: str):
    """구독 해지 (기간 만료 시 종료)"""
    tenant = await get_tenant(tenant_id)
    stripe.Subscription.modify(
        tenant.stripe_subscription_id,
        cancel_at_period_end=True
    )
```

### 6.3 Webhook 처리

```python
# app/billing/router.py
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_id = data["customer"]["metadata"]["tenant_id"]
        await activate_tenant(tenant_id, db)

    elif event_type == "invoice.payment_failed":
        customer_id = data["customer"]
        tenant = await get_tenant_by_stripe_customer(customer_id, db)
        await suspend_tenant(tenant.id, db)

    elif event_type == "customer.subscription.deleted":
        customer_id = data["customer"]
        tenant = await get_tenant_by_stripe_customer(customer_id, db)
        await cancel_tenant(tenant.id, db)

    return {"ok": True}
```

### 6.4 월말 초과 사용량 정산

```python
# billing_cron.py (매월 1일 실행)
OVERAGE_RATES = {
    "datasets": 0.02,     # 건당 $0.02
    "ai_calls": 0.05,     # 건당 $0.05
    "models": 0.50,       # 건당 $0.50
    "storage_mb": 0.01,   # MB당 $0.01
}

async def bill_overage():
    """Pro 플랜 초과 사용량을 Stripe Invoice로 청구"""
    last_month = date.today().replace(day=1) - timedelta(days=1)
    month = last_month.replace(day=1)

    tenants = await get_tenants_by_plan("pro")
    for tenant in tenants:
        usage = await get_usage(tenant.id, month)
        overage_total = Decimal("0")

        for resource, rate in OVERAGE_RATES.items():
            used = getattr(usage, resource, 0)
            limit = getattr(tenant, f"max_{resource}", 0)
            if used > limit:
                overage_total += Decimal(str((used - limit) * rate))

        if overage_total > 0:
            stripe.InvoiceItem.create(
                customer=tenant.stripe_customer_id,
                amount=int(overage_total * 100),  # cents
                currency="usd",
                description=f"Overage charges for {month.strftime('%Y-%m')}",
            )
            await record_billing(tenant.id, month, overage=overage_total)
```

---

## 7. 서비스 관리 (어드민)

### 7.1 관리자 API

```python
# app/admin/router.py
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/tenants")
async def list_tenants(status: str = None, db: AsyncSession = Depends(get_db)):
    """전체 테넌트 목록 + 사용량 요약"""
    ...

@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """특정 테넌트 상세 사용량 (월별 추이)"""
    ...

@router.put("/tenants/{tenant_id}/plan")
async def change_plan(tenant_id: str, body: PlanUpdate, db: AsyncSession = Depends(get_db)):
    """플랜 변경 (한도 즉시 반영, Stripe 구독 업데이트)"""
    ...

@router.put("/tenants/{tenant_id}/suspend")
async def suspend_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """서비스 일시 중지"""
    ...

@router.put("/tenants/{tenant_id}/activate")
async def activate_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """서비스 재활성화"""
    ...

@router.get("/revenue")
async def revenue_summary(period: str = "monthly", db: AsyncSession = Depends(get_db)):
    """매출 요약 (MRR, 테넌트별 매출, 이탈률)"""
    ...

@router.get("/system/health")
async def system_health():
    """시스템 상태 (DB 연결, 디스크, 메모리, 컨테이너 상태)"""
    ...
```

### 7.2 관리 대시보드 지표

| 카테고리 | 지표 |
|---|---|
| **매출** | MRR (Monthly Recurring Revenue), ARR, 테넌트별 매출 |
| **성장** | 신규 가입 수, 이탈률 (churn rate), 플랜별 분포 |
| **사용량** | 전체 데이터셋 수, API 호출량, 스토리지 사용량 |
| **시스템** | CPU/메모리 사용률, DB 커넥션 수, 응답 시간 (p95) |

---

## 8. 고객 온보딩

### 8.1 가입 흐름

```
1. 가입 페이지 접속
   └─ 이메일, 회사명, 플랜 선택, 비밀번호 설정

2. Stripe Checkout으로 리다이렉트
   └─ 카드 정보 입력 → 결제 완료

3. Stripe Webhook → 자동 프로비저닝
   ├─ tenants 레코드 생성 (status: active)
   ├─ 관리자 계정 생성 (catalog_users + tenant_id)
   ├─ 기본 설정 초기화 (catalog_configuration)
   └─ 환영 이메일 발송 (SES)

4. 로그인 → 초기 설정 위저드
   ├─ 데이터 플랫폼 등록
   ├─ 메타데이터 동기화 실행
   └─ 팀원 초대
```

### 8.2 이메일 발송 (Amazon SES)

| 이벤트 | 이메일 내용 |
|---|---|
| 가입 완료 | 환영 + 시작 가이드 링크 |
| 결제 성공 | 월별 청구서 (Stripe 자동) |
| 결제 실패 | 카드 업데이트 요청 |
| 한도 80% 도달 | 업그레이드 안내 |
| 서비스 중지 예정 | 최종 결제 안내 (해지 30일 전) |

비용: SES $0.10/1,000건 (사실상 무료)

---

## 9. 인증 설정

### 9.1 SaaS 환경 권장 설정

```yaml
# config.yml
auth:
  type: local          # SaaS에서는 local JWT 권장 (Keycloak 불필요)
  jwt:
    secret_key: ${JWT_SECRET_KEY}   # 환경변수에서 주입
    algorithm: HS256
    expiry_minutes: 480
```

### 9.2 JWT 클레임 확장

기존 JWT에 `tenant_id` 추가:

```python
# JWT payload
{
    "sub": "user-uuid",
    "username": "admin",
    "email": "admin@company.com",
    "tenant_id": "tenant-uuid",      # 추가
    "roles": ["admin"],
    "exp": 1711382400
}
```

---

## 10. CI/CD 파이프라인

### 10.1 GitHub Actions 배포

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy-ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build UI
        working-directory: argus-catalog-ui
        run: |
          pnpm install
          pnpm build

      - name: Deploy to S3
        run: |
          aws s3 sync argus-catalog-ui/apps/web/out/ s3://${{ vars.UI_BUCKET }} --delete
          aws cloudfront create-invalidation \
            --distribution-id ${{ vars.CF_DISTRIBUTION_ID }} \
            --paths "/*"

  deploy-server:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t catalog-server:${{ github.sha }} ./argus-catalog-server

      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ vars.ECR_REGISTRY }}
          docker tag catalog-server:${{ github.sha }} ${{ vars.ECR_REGISTRY }}/catalog-server:latest
          docker push ${{ vars.ECR_REGISTRY }}/catalog-server:latest

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /opt/argus-catalog
            aws ecr get-login-password | docker login --username AWS --password-stdin ${{ vars.ECR_REGISTRY }}
            docker compose pull catalog-server
            docker compose up -d catalog-server
```

### 10.2 배포 전략

- **Blue/Green 불필요** (Phase 1): 단일 EC2이므로 rolling restart로 충분
- 다운타임: Docker Compose `up -d`로 교체 시 수 초 이내
- 롤백: ECR에서 이전 이미지 태그로 `docker compose up -d`

---

## 11. 운영 체크리스트

### 11.1 서비스 출시 전

- [ ] Dockerfile 작성 (catalog-server, catalog-ui)
- [ ] Docker Compose 구성 + 로컬 테스트
- [ ] EC2 인스턴스 프로비저닝 (t3.medium, RI 구매)
- [ ] S3 버킷 생성 (UI, artifacts, backup)
- [ ] CloudFront 배포 설정
- [ ] Route 53 도메인 연결
- [ ] Caddy TLS 설정 확인
- [ ] Security Group 설정 (80, 443만 공개)
- [ ] DB 초기 스키마 적용 (DDL + 테넌트 테이블)
- [ ] Stripe 계정 생성 + Product/Price 설정
- [ ] Stripe Webhook 엔드포인트 등록
- [ ] SES 이메일 발신 도메인 인증
- [ ] DB 백업 크론 설정 + 복원 테스트
- [ ] CloudWatch Alarm 설정 (CPU > 80%, 디스크 > 85%)
- [ ] 외부 모니터링 설정 (UptimeRobot)

### 11.2 정기 운영

| 주기 | 작업 |
|---|---|
| 매일 | DB 백업 확인, CloudWatch 알람 확인 |
| 매주 | 디스크 사용량 확인, Docker 이미지 정리 |
| 매월 | 초과 사용량 정산, 비용 리포트 확인, 보안 패치 |
| 분기 | RI 갱신 검토, 확장 필요성 평가, 성능 테스트 |

### 11.3 장애 대응

| 장애 유형 | 대응 |
|---|---|
| EC2 다운 | CloudWatch 알람 → 자동 재시작 (EC2 Auto Recovery) |
| DB 손상 | S3 백업에서 복원 |
| 디스크 풀 | EBS 볼륨 온라인 확장 (`aws ec2 modify-volume`) |
| 배포 실패 | ECR에서 이전 이미지로 롤백 |
| DDoS | CloudFront + AWS Shield Standard (무료) |

---

## 12. 확장 로드맵

```
Phase 1: EC2 1대 통합                        ~$36/월
  │      (사용자 ~50명, 테넌트 ~10개)
  │
  ▼
Phase 2: EC2 2대 분리                        ~$70/월
  │      EC2-A: catalog-server + Caddy
  │      EC2-B: PostgreSQL + pgvector
  │      (사용자 ~200명, 테넌트 ~30개)
  │
  ▼
Phase 3: 부분 매니지드                        ~$150/월
  │      ECS Fargate (서버 오토스케일링)
  │      RDS PostgreSQL (고가용성)
  │      ALB (로드밸런싱 + TLS)
  │      (사용자 ~1,000명, 테넌트 ~100개)
  │
  ▼
Phase 4: 풀 매니지드                          ~$500+/월
         EKS (컨테이너 오케스트레이션)
         Aurora PostgreSQL (글로벌 복제)
         ElastiCache (세션/캐시)
         (사용자 ~10,000명, 테넌트 ~500개)
```

---

## 13. AWS Marketplace 등록 (선택)

Marketplace를 통해 판매하려면 추가로 필요한 사항:

### 13.1 판매 모델

| 모델 | 설명 | 권장 시점 |
|---|---|---|
| **SaaS** | 우리 AWS 계정에서 호스팅 | Phase 1부터 가능 |
| Container | 고객 계정에 컨테이너 배포 | Enterprise 고객용 |
| AMI | 고객 계정에 EC2 이미지 배포 | On-premise 대안 |

### 13.2 등록 절차

1. AWS Partner Network (APN) 가입
2. Marketplace Management Portal에서 제품 등록
3. 제품 리스팅 작성 (설명, 가격, EULA, 아키텍처 다이어그램)
4. Marketplace Metering API 연동 (사용량 보고)
5. AWS 팀 기술 검증 (보안/아키텍처 리뷰)
6. 승인 후 퍼블리시

### 13.3 Metering API 연동

```python
# AWS Marketplace에 시간당 사용량 보고
import boto3

metering = boto3.client("meteringmarketplace")

metering.meter_usage(
    ProductCode="prod-xxxxxxxxx",
    Timestamp=datetime.utcnow(),
    UsageDimension="datasets",
    UsageQuantity=150,
)
```

---

## 부록: 설정 변경 요약

기존 argus-catalog-server 코드에서 SaaS 전환 시 변경이 필요한 영역:

| 영역 | 현재 | SaaS 전환 후 |
|---|---|---|
| 인증 | Local JWT (단일 테넌트) | Local JWT + tenant_id 클레임 |
| DB | 단일 DB | tenant_id 컬럼 추가 (row-level) |
| 설정 | 파일 기반 (config.yml) | 환경변수 + DB 동적 설정 |
| S3 | MinIO (자체 호스팅) | Amazon S3 (엔드포인트만 변경) |
| 로그 | 파일 롤링 | stdout 출력 (Docker 로그 수집) |
| JWT secret | 하드코딩 | 환경변수로 주입 |
| CORS | `*` (전체 허용) | 테넌트 도메인만 허용 |
