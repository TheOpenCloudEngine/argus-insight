# Multi-Cluster Support Design

## 1. Current State Analysis

현재 argus-insight는 **단일 K8s 클러스터**만 지원합니다.

### 현재 구조의 한계

| 구성 요소 | 현재 상태 | 한계 |
|-----------|----------|------|
| `argus_configuration` (k8s) | kubeconfig_path 1개, context 1개 | 글로벌 싱글톤 설정 |
| `kubernetes/client.py` | 모든 kubectl 호출이 동일한 kubeconfig 사용 | 클러스터 구분 불가 |
| `argus_workspaces.k8s_cluster` | 컬럼은 존재하나 실제 클러스터 연결에 미사용 | 단순 문자열 레이블 |
| Settings UI | kubeconfig path + context 입력 필드 1세트 | 다중 클러스터 등록 UI 없음 |
| Workspace 생성 API | `k8s_cluster` 파라미터를 받지만 무시 | 항상 글로벌 설정 사용 |

### 현재 데이터 흐름

```
Settings UI → argus_configuration (k8s_kubeconfig_path, k8s_context) → 글로벌 1개
                                        ↓
Workspace 생성 → WorkflowContext.k8s_kubeconfig = 글로벌 설정값
                                        ↓
kubectl_apply(manifest, kubeconfig=글로벌경로)  ← 모든 워크스페이스 동일 클러스터
```

---

## 2. Multi-Cluster Target Architecture

```
                    ┌─────────────────────────┐
                    │   argus-insight-server   │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │ argus_k8s_clusters │  │  ← NEW: 클러스터 레지스트리
                    │  │  - cluster-alpha   │  │
                    │  │  - cluster-beta    │  │
                    │  │  - cluster-gpu     │  │
                    │  └───────────────────┘  │
                    │           │              │
                    │  ┌────────┴──────────┐  │
                    │  │ ClusterResolver    │  │  ← NEW: workspace → cluster 매핑
                    │  └────────┬──────────┘  │
                    └───────────┼──────────────┘
                       ┌────────┼────────┐
                       ▼        ▼        ▼
                  ┌────────┐┌────────┐┌────────┐
                  │Cluster ││Cluster ││Cluster │
                  │ Alpha  ││ Beta   ││  GPU   │
                  │(dev)   ││(prod)  ││(train) │
                  └────────┘└────────┘└────────┘
```

---

## 3. Changes Required

### 3.1 Database: New `argus_k8s_clusters` Table

**File**: `argus-insight-server/packaging/config/argus-db-schema-postgresql.sql`
**File**: `argus-insight-workspace-provisioner/scripts/argus-insight-provisioner-postgresql.sql`

```sql
CREATE TABLE IF NOT EXISTS argus_k8s_clusters (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,       -- "cluster-alpha"
    display_name    VARCHAR(255)    NOT NULL,              -- "Alpha Development Cluster"
    description     TEXT,
    -- Connection
    kubeconfig_path VARCHAR(500),                          -- "/etc/kubeconfigs/alpha.yaml"
    kubeconfig_data TEXT,                                  -- inline kubeconfig (encrypted)
    context         VARCHAR(255),                          -- kubeconfig context name
    api_server_url  VARCHAR(500),                          -- "https://10.0.1.10:6443"
    -- Metadata
    environment     VARCHAR(50)     DEFAULT 'development', -- development, staging, production
    region          VARCHAR(100),                          -- "ap-northeast-2"
    tags            JSONB           DEFAULT '{}',          -- {"gpu": true, "tier": "high"}
    -- Capacity / status
    is_default      BOOLEAN         NOT NULL DEFAULT FALSE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',  -- active, unreachable, disabled
    last_health_at  TIMESTAMPTZ,
    -- Audit
    created_by      INTEGER         REFERENCES argus_users(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Ensure only one default cluster
CREATE UNIQUE INDEX IF NOT EXISTS idx_k8s_clusters_default
    ON argus_k8s_clusters (is_default) WHERE is_default = TRUE;
```

**기존 테이블 변경**: `argus_workspaces.k8s_cluster` → FK로 전환

```sql
ALTER TABLE argus_workspaces
    ADD COLUMN k8s_cluster_id INTEGER REFERENCES argus_k8s_clusters(id);
```

**기존 `argus_configuration` k8s 설정**: default cluster 마이그레이션 후 유지 (하위 호환)

---

### 3.2 ORM Models

**New file**: `argus-insight-server/app/clusters/models.py`

```python
class ArgusK8sCluster(Base):
    __tablename__ = "argus_k8s_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    kubeconfig_path = Column(String(500))
    kubeconfig_data = Column(Text)           # encrypted inline kubeconfig
    context = Column(String(255))
    api_server_url = Column(String(500))
    environment = Column(String(50), default="development")
    region = Column(String(100))
    tags = Column(JSON, default=dict)
    is_default = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="active")
    last_health_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("argus_users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Modified**: `workspace_provisioner/models.py` - ArgusWorkspace

```python
# ADD:
k8s_cluster_id = Column(Integer, ForeignKey("argus_k8s_clusters.id"))

# KEEP for backward compat (deprecated):
k8s_cluster = Column(String(255))  # legacy, to be migrated
```

---

### 3.3 Cluster Management API

**New module**: `argus-insight-server/app/clusters/`

```
app/clusters/
├── __init__.py
├── router.py      # /api/v1/clusters/*
├── schemas.py     # Pydantic request/response models
└── service.py     # CRUD + health check logic
```

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/clusters` | Register a new cluster |
| GET | `/api/v1/clusters` | List all clusters |
| GET | `/api/v1/clusters/{id}` | Get cluster details |
| PUT | `/api/v1/clusters/{id}` | Update cluster config |
| DELETE | `/api/v1/clusters/{id}` | Deregister cluster |
| POST | `/api/v1/clusters/{id}/test` | Test connectivity |
| GET | `/api/v1/clusters/{id}/health` | Health check |
| POST | `/api/v1/clusters/health/all` | Health check all clusters |
| GET | `/api/v1/clusters/{id}/resources` | Get cluster resource usage (nodes, CPU, memory) |
| PUT | `/api/v1/clusters/{id}/default` | Set as default cluster |

#### Request/Response Schemas

```python
class ClusterCreateRequest(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    kubeconfig_path: str | None = None
    kubeconfig_data: str | None = None  # base64-encoded
    context: str | None = None
    api_server_url: str | None = None
    environment: str = "development"
    region: str | None = None
    tags: dict = {}
    is_default: bool = False

class ClusterResponse(BaseModel):
    id: int
    name: str
    display_name: str
    environment: str
    region: str | None
    status: str
    is_default: bool
    workspace_count: int          # number of workspaces using this cluster
    last_health_at: datetime | None

class ClusterDetailResponse(ClusterResponse):
    kubeconfig_path: str | None
    context: str | None
    api_server_url: str | None
    tags: dict
    node_count: int | None        # from live K8s API
    total_cpu: str | None
    total_memory: str | None
```

---

### 3.4 Kubernetes Client: Multi-Cluster Support

**Modified file**: `workspace_provisioner/kubernetes/client.py`

현재 모든 kubectl 함수가 `kubeconfig: str | None`을 받지만, 이를 **클러스터 객체 기반**으로 확장합니다.

```python
# NEW: Cluster connection resolver
class ClusterConnection:
    """Resolved connection parameters for a K8s cluster."""
    def __init__(self, kubeconfig_path: str | None, context: str | None):
        self.kubeconfig_path = kubeconfig_path
        self.context = context

    def kubectl_args(self) -> list[str]:
        """Return kubectl CLI flags for this cluster."""
        args = []
        if self.kubeconfig_path:
            args.append(f"--kubeconfig={self.kubeconfig_path}")
        if self.context:
            args.append(f"--context={self.context}")
        return args


async def resolve_cluster(cluster_id: int | None, session) -> ClusterConnection:
    """Resolve a cluster ID to connection parameters.
    Falls back to default cluster if cluster_id is None.
    """
    ...
```

**변경 포인트**: 모든 kubectl 함수의 시그니처 변경

```python
# BEFORE:
async def kubectl_apply(manifest_yaml: str, kubeconfig: str | None = None) -> str:

# AFTER:
async def kubectl_apply(manifest_yaml: str, cluster: ClusterConnection | None = None) -> str:
    cmd = ["kubectl", "apply", "-f", "-"]
    if cluster:
        cmd[1:1] = cluster.kubectl_args()  # inject --kubeconfig and --context
```

같은 패턴으로 `kubectl_delete`, `kubectl_wait`, `kubectl_rollout_status` 모두 변경.

---

### 3.5 Workflow Context: Cluster Binding

**Modified file**: `workspace_provisioner/workflow/engine.py`

```python
class WorkflowContext:
    # EXISTING fields...

    # ADD:
    cluster_id: int | None = None
    cluster_connection: ClusterConnection | None = None
```

**Modified file**: `workspace_provisioner/service.py` - `_run_provisioning_workflow()`

```python
# BEFORE: kubeconfig from global config
ctx.set("k8s_kubeconfig", global_kubeconfig_path)

# AFTER: resolve from cluster registry
cluster = await resolve_cluster(workspace.k8s_cluster_id, session)
ctx.cluster_connection = cluster
ctx.set("k8s_kubeconfig", cluster.kubeconfig_path)  # backward compat
ctx.set("k8s_context", cluster.context)
```

---

### 3.6 Workflow Steps: Cluster-Aware Deployment

모든 deploy step에서 `kubeconfig` 대신 `cluster_connection` 사용.

**Files to modify**:
- `workflow/steps/minio_deploy.py`
- `workflow/steps/airflow_deploy.py`
- `workflow/steps/mlflow_deploy.py`
- `workflow/steps/kserve_deploy.py`
- `workflow/steps/app_deploy.py`

**Example change** (minio_deploy.py):

```python
# BEFORE:
kubeconfig = ctx.get("k8s_kubeconfig")
await kubectl_apply(manifests, kubeconfig=kubeconfig)

# AFTER:
cluster = ctx.cluster_connection
await kubectl_apply(manifests, cluster=cluster)
```

---

### 3.7 Workspace Creation: Cluster Selection

**Modified file**: `workspace_provisioner/schemas.py`

```python
class WorkspaceCreateRequest(BaseModel):
    name: str
    display_name: str
    domain: str
    admin_user_id: int
    k8s_cluster_id: int | None = None   # ADD: None → use default cluster
    k8s_namespace: str | None = None
    provisioning_config: ProvisioningConfig | None = None
    steps: list[str] | None = None
```

**Modified file**: `workspace_provisioner/service.py`

```python
async def create_workspace(self, req: WorkspaceCreateRequest, ...):
    # Resolve cluster
    cluster_id = req.k8s_cluster_id
    if cluster_id is None:
        cluster_id = await get_default_cluster_id(session)

    workspace = ArgusWorkspace(
        name=req.name,
        k8s_cluster_id=cluster_id,
        k8s_namespace=req.k8s_namespace or f"{ns_prefix}{req.name}",
        ...
    )
```

---

### 3.8 Frontend UI Changes

#### 3.8.1 New: Cluster Management Page

**New files**:
```
argus-insight-ui/apps/web/
├── app/dashboard/clusters/
│   └── page.tsx                           # Cluster list page
├── features/clusters/
│   ├── types.ts                           # Cluster types
│   ├── api.ts                             # API calls
│   └── components/
│       ├── clusters-table.tsx             # Cluster list table
│       ├── cluster-register-dialog.tsx    # Register new cluster form
│       ├── cluster-detail-dialog.tsx      # Cluster detail view
│       └── cluster-health-badge.tsx       # Health status badge
```

**Menu entry** (`data/menu.json`):

```json
{
  "id": "clusters",
  "title": "Kubernetes Clusters",
  "url": "/dashboard/clusters",
  "icon": "Container"
}
```

#### 3.8.2 Modified: Settings Page

**File**: `features/settings/components/argus-settings.tsx`

현재의 K8s 단일 설정 섹션을 **Legacy/Migration 알림**으로 교체하고, 새 Cluster 관리 페이지로 링크.

```
기존: kubeconfig_path + namespace_prefix + context 입력폼
변경: "클러스터는 Kubernetes Clusters 메뉴에서 관리합니다" + 마이그레이션 버튼
```

#### 3.8.3 Modified: Workspace Creation Dialog

**File**: `features/workspaces/components/workspace-create-dialog.tsx` (or equivalent)

워크스페이스 생성 폼에 **Cluster 선택 드롭다운** 추가:

```typescript
// Cluster selector in workspace creation form
<Select value={selectedClusterId} onValueChange={setSelectedClusterId}>
  <SelectTrigger>
    <SelectValue placeholder="Select cluster (default if empty)" />
  </SelectTrigger>
  <SelectContent>
    {clusters.map(c => (
      <SelectItem key={c.id} value={c.id}>
        {c.display_name} ({c.environment}) {c.is_default && "★"}
      </SelectItem>
    ))}
  </SelectContent>
</Select>
```

#### 3.8.4 Modified: Workspace Detail

**File**: `features/workspaces/components/workspace-detail.tsx`

워크스페이스 상세에 **클러스터 정보** 표시 추가:

```
Cluster: cluster-alpha (Development, ap-northeast-2)
Namespace: argus-ws-ml-team-dev
```

#### 3.8.5 Modified: Workspace Types

**File**: `features/workspaces/types.ts`

```typescript
interface WorkspaceResponse {
  // ADD:
  k8s_cluster_id: number | null
  k8s_cluster_name: string | null
  k8s_cluster_display_name: string | null
  k8s_cluster_environment: string | null
  // EXISTING:
  k8s_namespace: string | null
  ...
}
```

---

### 3.9 Cluster Health Monitoring

**New**: Background task for periodic cluster health checks.

**File**: `argus-insight-server/app/clusters/health.py`

```python
async def cluster_health_loop(interval: int = 60):
    """Periodically check connectivity to all registered clusters."""
    while True:
        clusters = await get_all_active_clusters()
        for cluster in clusters:
            try:
                conn = ClusterConnection(cluster.kubeconfig_path, cluster.context)
                reachable = await kubectl_cluster_info(conn, timeout=10)
                cluster.status = "active" if reachable else "unreachable"
                cluster.last_health_at = utcnow()
            except Exception:
                cluster.status = "unreachable"
        await asyncio.sleep(interval)
```

Register in `app/main.py` lifespan.

---

### 3.10 Migration Strategy

기존 단일 클러스터 환경에서의 무중단 마이그레이션:

```sql
-- Step 1: Create default cluster from existing config
INSERT INTO argus_k8s_clusters (name, display_name, kubeconfig_path, context, is_default)
SELECT
    'default',
    'Default Cluster',
    (SELECT config_value FROM argus_configuration WHERE config_key = 'k8s_kubeconfig_path'),
    (SELECT config_value FROM argus_configuration WHERE config_key = 'k8s_context'),
    TRUE;

-- Step 2: Link existing workspaces to default cluster
UPDATE argus_workspaces
SET k8s_cluster_id = (SELECT id FROM argus_k8s_clusters WHERE name = 'default')
WHERE k8s_cluster_id IS NULL;
```

---

## 4. Files to Change (Summary)

### New Files

| File | Description |
|------|-------------|
| `argus-insight-server/app/clusters/__init__.py` | Module init |
| `argus-insight-server/app/clusters/models.py` | ArgusK8sCluster ORM |
| `argus-insight-server/app/clusters/schemas.py` | Pydantic schemas |
| `argus-insight-server/app/clusters/router.py` | REST API endpoints |
| `argus-insight-server/app/clusters/service.py` | Business logic |
| `argus-insight-server/app/clusters/health.py` | Health monitoring |
| `argus-insight-ui/apps/web/app/dashboard/clusters/page.tsx` | Cluster list page |
| `argus-insight-ui/apps/web/features/clusters/types.ts` | TypeScript types |
| `argus-insight-ui/apps/web/features/clusters/api.ts` | API client |
| `argus-insight-ui/apps/web/features/clusters/components/*.tsx` | UI components |

### Modified Files

| File | Change |
|------|--------|
| `packaging/config/argus-db-schema-postgresql.sql` | Add `argus_k8s_clusters` table, alter `argus_workspaces` |
| `provisioner/scripts/argus-insight-provisioner-postgresql.sql` | Same schema changes |
| `workspace_provisioner/models.py` | Add `k8s_cluster_id` FK to ArgusWorkspace |
| `workspace_provisioner/kubernetes/client.py` | Add `ClusterConnection`, change kubectl functions |
| `workspace_provisioner/workflow/engine.py` | Add cluster_connection to WorkflowContext |
| `workspace_provisioner/service.py` | Cluster resolution in create/delete workflows |
| `workspace_provisioner/schemas.py` | Add `k8s_cluster_id` to create request |
| `workflow/steps/minio_deploy.py` | Use ClusterConnection |
| `workflow/steps/airflow_deploy.py` | Use ClusterConnection |
| `workflow/steps/mlflow_deploy.py` | Use ClusterConnection |
| `workflow/steps/kserve_deploy.py` | Use ClusterConnection |
| `workflow/steps/app_deploy.py` | Use ClusterConnection |
| `argus-insight-server/app/main.py` | Register cluster router + health task |
| `argus-insight-server/app/settings/router.py` | K8s settings → cluster migration |
| `argus-insight-ui/.../settings/components/argus-settings.tsx` | Replace K8s section |
| `argus-insight-ui/.../workspaces/types.ts` | Add cluster fields |
| `argus-insight-ui/.../workspaces/components/workspace-detail.tsx` | Show cluster info |
| `argus-insight-ui/apps/web/data/menu.json` | Add clusters menu entry |
| `argus-insight-ui/apps/web/lib/icon-map.ts` | Add cluster icon |

---

## 5. Implementation Order

```
Phase 1: Foundation (Backend)
├── 1-1. DB schema: argus_k8s_clusters table
├── 1-2. ORM: ArgusK8sCluster model
├── 1-3. Cluster CRUD API (router/schemas/service)
└── 1-4. Migration script (existing config → default cluster)

Phase 2: Core (Provisioner)
├── 2-1. ClusterConnection class in kubernetes/client.py
├── 2-2. Modify kubectl_* functions to accept ClusterConnection
├── 2-3. WorkflowContext: add cluster_connection
├── 2-4. Service: resolve cluster on workspace create/delete
└── 2-5. All deploy steps: use ClusterConnection

Phase 3: Frontend
├── 3-1. Cluster management page (list/register/edit/delete)
├── 3-2. Workspace creation: cluster selector dropdown
├── 3-3. Workspace detail: show cluster info
└── 3-4. Settings page: replace K8s section

Phase 4: Operations
├── 4-1. Cluster health monitoring background task
├── 4-2. Dashboard: per-cluster resource usage
└── 4-3. Cross-cluster workspace migration (future)
```

---

## 6. Key Design Decisions

### Q1: kubeconfig file vs inline data?

**Both**. `kubeconfig_path`는 서버 로컬 파일, `kubeconfig_data`는 API로 전달된 인라인 kubeconfig.
인라인 데이터는 암호화하여 DB 저장. 사용 시 임시 파일로 쓰고 kubectl 실행 후 삭제.

### Q2: kubectl subprocess vs kubernetes python client?

**kubectl subprocess 유지**. 현재 아키텍처와의 일관성. `--kubeconfig` + `--context` 플래그로
멀티 클러스터 전환이 간단. Python kubernetes client 전환은 별도 리팩토링으로 진행 가능.

### Q3: Workspace를 다른 cluster로 이동(migration) 지원?

**Phase 4에서 검토**. 실행 중인 서비스의 cross-cluster migration은 복잡도가 높음.
초기에는 workspace 생성 시 cluster 선택만 지원, 이동은 재생성으로 대체.

### Q4: Namespace prefix를 cluster별로 다르게?

**Global prefix 유지**. `argus_configuration`의 `k8s_namespace_prefix`는 글로벌로 유지.
클러스터별 prefix가 필요하면 `argus_k8s_clusters.tags`에 override 가능.

### Q5: 하위 호환성?

**`k8s_cluster` string 컬럼 유지**. `k8s_cluster_id` FK 추가 후 migration 완료 시까지
기존 코드가 string 컬럼도 참조 가능. 마이그레이션 완료 후 deprecated 처리.
