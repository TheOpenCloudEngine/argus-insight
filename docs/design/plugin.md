# Plugin - Docker Image - Kubernetes 배포

이 문서는 Argus Insight의 Plugin이 Docker Image를 Kubernetes 클러스터에 배포하는 구조와 개념을 상세히 설명합니다. Deployment-Pipeline-Plugin의 전체 구조는 [deployment.md](deployment.md)를 참고하세요.

## 개요

Plugin의 핵심 역할은 **Docker Image를 Kubernetes 리소스로 변환하여 배포**하는 것입니다:

```
Plugin
  │
  ├── Config (Pydantic 모델)      ── 어떤 이미지를, 어떤 리소스로
  ├── Template (K8s YAML)          ── 어떤 K8s 리소스 형태로
  └── Step (WorkflowStep)          ── 어떻게 배포할 것인가
  
  ↓
  
Docker Image  →  K8s Manifest  →  kubectl apply  →  Running Pod
```

## Plugin의 3-Layer 구조

### Layer 1: Config (설정 모델)

Pydantic v2 모델로 정의되며, Docker Image 이름, 리소스 제한, 스토리지 크기 등 배포에 필요한 모든 파라미터를 관리합니다.

```python
class MinioConfig(BaseModel):
    image: str = Field(
        default="minio/minio:RELEASE.2025-02-28T09-55-16Z",
        description="MinIO server container image",
    )
    storage_size: str = Field(
        default="50Gi",
        description="PVC size for MinIO data volume",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory resource configuration",
    )

class ResourceConfig(BaseModel):
    cpu_request: str = "250m"
    cpu_limit: str = "2"
    memory_request: str = "512Mi"
    memory_limit: str = "2Gi"
```

**Config의 역할:**
- Docker Image 태그 관리 (버전 고정)
- K8s 리소스 requests/limits 정의
- PVC 스토리지 크기 지정
- 서비스별 고유 설정 (포트, 동기화 주기, 인증 정보 등)
- JSON Schema 자동 생성 → UI 동적 폼 렌더링

**Config 계층 구조:**

```
ResourceConfig (공통)
    ↑ 포함
MinioConfig
AirflowConfig
MlflowConfig
KServeConfig
JupyterLabConfig
    ↑ 상속
    ├── JupyterTensorFlowConfig  (GPU 이미지, 메모리 증가)
    └── JupyterPySparkConfig     (Spark 이미지, 메모리 증가)
MilvusConfig
MindsdbConfig
Neo4jConfig
VScodeServerConfig
MinioWorkspaceConfig
    ↑ 집합
ProvisioningConfig (최상위)
```

### Layer 2: Template (K8s 매니페스트 템플릿)

`kubernetes/templates/{component}/` 디렉토리에 YAML 파일로 정의됩니다. `${VAR}` 플레이스홀더를 사용하여 런타임에 실제 값으로 치환합니다.

```
kubernetes/templates/
├── minio/
│   ├── secret.yaml          # Root credentials
│   ├── pvc.yaml             # 데이터 볼륨
│   ├── statefulset.yaml     # MinIO 서버 Pod
│   └── service.yaml         # ClusterIP + Ingress
├── airflow/
│   ├── secret.yaml          # DB 비밀번호, Fernet key
│   ├── configmap.yaml       # Airflow 설정
│   ├── pvc.yaml             # DAGs, Logs, DB 볼륨
│   ├── statefulset.yaml     # PostgreSQL
│   ├── deployment.yaml      # Webserver + Scheduler
│   └── service.yaml         # ClusterIP + Ingress
├── mlflow/
│   └── ...
└── kserve/
    └── ...
```

#### 템플릿 변수 치환

```yaml
# 템플릿 원본 (statefulset.yaml)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: argus-minio-${WORKSPACE_NAME}
  namespace: ${K8S_NAMESPACE}
  labels:
    app.kubernetes.io/name: minio
    app.kubernetes.io/instance: ${WORKSPACE_NAME}
    app.kubernetes.io/part-of: argus-insight
    argus-insight/workspace: ${WORKSPACE_NAME}
spec:
  containers:
    - name: minio
      image: ${MINIO_IMAGE}
      resources:
        requests:
          cpu: "${MINIO_CPU_REQUEST}"
          memory: "${MINIO_MEMORY_REQUEST}"
        limits:
          cpu: "${MINIO_CPU_LIMIT}"
          memory: "${MINIO_MEMORY_LIMIT}"
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: argus-minio-${WORKSPACE_NAME}-data
```

```yaml
# 렌더링 결과 (실제 배포되는 매니페스트)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: argus-minio-ml-team-dev
  namespace: argus-workspace-ml-team-dev
  labels:
    app.kubernetes.io/name: minio
    app.kubernetes.io/instance: ml-team-dev
    app.kubernetes.io/part-of: argus-insight
    argus-insight/workspace: ml-team-dev
spec:
  containers:
    - name: minio
      image: minio/minio:RELEASE.2025-02-28T09-55-16Z
      resources:
        requests:
          cpu: "250m"
          memory: "512Mi"
        limits:
          cpu: "2"
          memory: "2Gi"
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: argus-minio-ml-team-dev-data
```

#### 매니페스트 렌더링 순서

파일 이름 기반으로 결정적(deterministic) 순서가 보장됩니다:

```
1. secret*.yaml        → K8s Secret (인증 정보, 비밀번호)
2. pvc*.yaml           → PersistentVolumeClaim (스토리지)
3. statefulset*.yaml   → StatefulSet (상태 있는 워크로드)
4. deployment*.yaml    → Deployment (상태 없는 워크로드)
5. service*.yaml       → Service + Ingress (네트워크)
```

이 순서는 K8s 리소스 간 참조 관계를 반영합니다:
- Pod는 Secret과 PVC를 마운트하므로, Secret/PVC가 먼저 생성되어야 합니다
- Service는 Pod를 선택하므로, Pod가 먼저 생성되어야 합니다

### Layer 3: Step (배포 실행 로직)

`WorkflowStep`을 구현하여 실제 배포를 수행합니다. Config에서 설정을 읽고, Template를 렌더링하고, kubectl로 배포합니다.

```python
class MinioDeployStep(WorkflowStep):
    @property
    def name(self) -> str:
        return "minio-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        # 1. Config 읽기
        config: MinioConfig = ctx.get("minio_config", MinioConfig())
        
        # 2. 템플릿 변수 구성
        variables = {
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": ctx.get("k8s_namespace"),
            "MINIO_IMAGE": config.image,
            "MINIO_STORAGE_SIZE": config.storage_size,
            "MINIO_CPU_REQUEST": config.resources.cpu_request,
            "MINIO_CPU_LIMIT": config.resources.cpu_limit,
            "MINIO_MEMORY_REQUEST": config.resources.memory_request,
            "MINIO_MEMORY_LIMIT": config.resources.memory_limit,
            "MINIO_ROOT_USER": root_user,
            "MINIO_ROOT_PASSWORD": root_password,
        }
        
        # 3. 매니페스트 렌더링
        manifests = render_manifests("minio", variables)
        
        # 4. K8s에 배포
        await kubectl_apply(manifests)
        
        # 5. 배포 완료 대기
        await kubectl_rollout_status(
            f"statefulset/argus-minio-{ctx.workspace_name}",
            namespace=ctx.get("k8s_namespace"),
        )
        
        # 6. 결과를 Context에 저장 (다음 Step에서 참조)
        ctx.set("minio_endpoint", f"https://argus-minio-{ctx.workspace_name}....")
        ctx.set("minio_manifests", manifests)
        
        return {"status": "deployed"}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("minio_manifests")
        if manifests:
            await kubectl_delete(manifests)

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        # teardown 시에는 manifests가 없을 수 있으므로 re-render
        manifests = ctx.get("minio_manifests")
        if not manifests:
            manifests = render_manifests("minio", self._build_variables(ctx))
        await kubectl_delete(manifests)
        return None
```

## Docker Image 관리 전략

### Image 버전 고정

모든 Plugin의 Config에는 Docker Image 태그가 **버전 고정(pinned)** 되어 있습니다:

```python
# Good: 특정 버전 고정
image: str = "minio/minio:RELEASE.2025-02-28T09-55-16Z"
image: str = "apache/airflow:2.10.4-python3.11"
image: str = "ghcr.io/mlflow/mlflow:v2.19.0"
image: str = "neo4j:5.26-community"

# Bad: latest 태그 사용 (비결정적)
image: str = "minio/minio:latest"  # 지양
```

버전 고정의 이점:
- **재현 가능한 배포**: 동일 설정이면 항상 동일한 결과
- **롤백 안전성**: 이전 버전으로 즉시 되돌릴 수 있음
- **감사 추적**: 어떤 이미지가 배포되었는지 정확히 기록

### Image 오버라이드 계층

```
1순위: Workspace 생성 요청       "plugins.argus-minio.config.image"
2순위: Pipeline 기본 설정        DB argus_plugin_configs.default_config.image
3순위: Plugin Config 기본값       MinioConfig.image (Pydantic default)
```

사용자는 원하는 계층에서 Image를 오버라이드할 수 있습니다:

```json
POST /workspace/workspaces
{
  "name": "ml-team-dev",
  "plugins": {
    "argus-minio": {
      "config": {
        "image": "minio/minio:RELEASE.2025-03-15T00-00-00Z"
      }
    }
  }
}
```

### Image 레지스트리 지원

Plugin Config의 image 필드는 어떤 레지스트리든 지원합니다:

```
Docker Hub:     minio/minio:RELEASE.2025-02-28T09-55-16Z
GitHub CR:      ghcr.io/mlflow/mlflow:v2.19.0
Quay.io:        quay.io/jupyter/scipy-notebook:2025-03-17
Private:        registry.internal.example.com/airflow:2.10.4
```

## Kubernetes 배포 패턴

### 리소스 명명 규칙

모든 K8s 리소스는 `argus-{component}-{workspace_name}` 패턴으로 명명됩니다:

```
Namespace:    argus-workspace-{workspace_name}
StatefulSet:  argus-minio-{workspace_name}
Service:      argus-minio-{workspace_name}
PVC:          argus-minio-{workspace_name}-data
Secret:       argus-minio-{workspace_name}
Ingress:      argus-minio-{workspace_name}
```

### K8s 레이블 표준

모든 리소스에 일관된 레이블이 적용됩니다:

```yaml
labels:
  app.kubernetes.io/name: minio                    # 소프트웨어 이름
  app.kubernetes.io/instance: ml-team-dev           # Workspace 이름
  app.kubernetes.io/part-of: argus-insight          # 플랫폼 이름
  argus-insight/workspace: ml-team-dev              # Workspace 식별자
```

### 배포 유형별 K8s 리소스 매핑

| Plugin | 주요 워크로드 | 스토리지 | 네트워크 |
|--------|-------------|---------|---------|
| MinIO | StatefulSet (1 replica) | PVC 50Gi | Service + Ingress (API:9000, Console:9001) |
| Airflow | StatefulSet (PostgreSQL) + Deployment (Webserver+Scheduler) | PVC x3 (DAGs, Logs, DB) | Service + Ingress (Webserver:8080) |
| MLflow | StatefulSet (PostgreSQL) + Deployment (Tracking Server) | PVC (DB) | Service + Ingress (Server:5000) |
| KServe | Deployment (Controller) | - | Service (Controller) |
| Jupyter | Deployment (1 replica) | s3fs sidecar mount | Service + Ingress (Lab:8888) |
| VS Code | Deployment (1 replica) | s3fs sidecar mount | Service + Ingress (Server:8080) |
| Neo4j | StatefulSet (1 replica) | PVC 20Gi | Service + Ingress (HTTP:7474, Bolt:7687) |
| Milvus | StatefulSet (1 replica) | PVC 30Gi | Service + Ingress (gRPC:19530) |
| MindsDB | StatefulSet (1 replica) | PVC 20Gi | Service + Ingress (HTTP:47334) |

### Health Check 패턴

모든 Pod에 liveness/readiness probe가 설정됩니다:

```yaml
livenessProbe:
  httpGet:
    path: /minio/health/live      # 서비스별 헬스체크 경로
    port: api
  initialDelaySeconds: 30          # 컨테이너 시작 대기
  periodSeconds: 20                # 체크 주기
  timeoutSeconds: 5
  failureThreshold: 3              # 실패 허용 횟수

readinessProbe:
  httpGet:
    path: /minio/health/ready
    port: api
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### 인증 정보 관리

각 Plugin은 K8s Secret을 통해 인증 정보를 관리합니다:

```
1. Step에서 비밀번호 생성 (랜덤 또는 설정값)
2. Secret 매니페스트에 주입
3. Pod에서 secretKeyRef로 환경변수 마운트
4. WorkflowContext에 저장 → DB credentials 테이블에 기록
```

```yaml
# Secret 템플릿
apiVersion: v1
kind: Secret
metadata:
  name: argus-minio-${WORKSPACE_NAME}
  namespace: ${K8S_NAMESPACE}
type: Opaque
data:
  root-user: ${MINIO_ROOT_USER_B64}
  root-password: ${MINIO_ROOT_PASSWORD_B64}

# Pod에서 참조
env:
  - name: MINIO_ROOT_USER
    valueFrom:
      secretKeyRef:
        name: argus-minio-${WORKSPACE_NAME}
        key: root-user
```

## kubectl 래퍼

`kubernetes/client.py`는 kubectl 명령을 비동기로 실행하는 래퍼를 제공합니다:

| 함수 | 설명 |
|------|------|
| `render_template(path, vars)` | 단일 YAML 파일의 `${VAR}` 치환 |
| `render_manifests(component, vars)` | 컴포넌트의 모든 YAML을 결정적 순서로 렌더링 후 결합 |
| `kubectl_apply(yaml)` | `kubectl apply -f -` (stdin으로 YAML 전달) |
| `kubectl_delete(yaml)` | `kubectl delete -f - --ignore-not-found` |
| `kubectl_rollout_status(resource, ns)` | 배포 완료 대기 (StatefulSet/Deployment) |
| `kubectl_wait(resource, ns, condition)` | 커스텀 조건 대기 (예: Ready) |

모든 kubectl 호출은:
- `asyncio.create_subprocess_exec`로 비동기 실행
- stdin으로 매니페스트 YAML 전달 (임시 파일 미사용)
- kubeconfig 경로를 선택적으로 지정 가능 (멀티 클러스터 지원)

## Sidecar 패턴

일부 Plugin은 메인 컨테이너 외에 sidecar 컨테이너를 함께 배포합니다:

### git-sync Sidecar (Airflow)

GitLab 리포지토리에서 DAG 파일을 주기적으로 동기화합니다:

```
┌──────────────────────────────────────┐
│ Airflow Pod                          │
│                                      │
│ ┌──────────────┐  ┌──────────────┐  │
│ │  Webserver   │  │  git-sync    │  │
│ │              │  │              │  │
│ │  DAGs 실행   │←─│  GitLab에서   │  │
│ │              │  │  DAG 동기화   │  │
│ └──────────────┘  └──────────────┘  │
│        │                   │         │
│        └───── /dags ───────┘         │
│         (SharedVolume)               │
└──────────────────────────────────────┘
```

### s3fs Sidecar (Jupyter, VS Code)

MinIO 버킷을 FUSE 파일시스템으로 마운트합니다:

```
┌──────────────────────────────────────┐
│ Jupyter Pod                          │
│                                      │
│ ┌──────────────┐  ┌──────────────┐  │
│ │  Jupyter Lab │  │    s3fs      │  │
│ │              │  │              │  │
│ │  /workspace  │←─│  MinIO 버킷  │  │
│ │  /data       │  │  FUSE 마운트  │  │
│ └──────────────┘  └──────────────┘  │
│        │                   │         │
│        └── mount point ────┘         │
│         (shared mount)               │
└──────────────────────────────────────┘
```

## Plugin 간 데이터 흐름

Plugin들은 `WorkflowContext`를 통해 데이터를 주고받습니다. `provides`/`requires` 계약이 이를 보장합니다:

```
[argus-gitlab]
  ctx.set("gitlab_http_url", ...)     ──provides──→ gitlab_http_url
  ctx.set("gitlab_token", ...)        ──provides──→ gitlab_token

[argus-minio]
  ctx.set("minio_endpoint", ...)      ──provides──→ minio_endpoint
  ctx.set("minio_root_user", ...)     ──provides──→ minio_root_user
  ctx.set("minio_root_password", ...) ──provides──→ minio_root_password

[argus-airflow]                       ──requires──← gitlab_http_url
  git_url = ctx.get("gitlab_http_url")
  minio_url = ctx.get("minio_endpoint")  ←requires── minio_endpoint
  │
  ├── git-sync sidecar: GitLab → DAGs 동기화
  └── Airflow connections: MinIO를 remote log storage로 설정

[argus-mlflow]                        ──requires──← minio_endpoint
  minio_url = ctx.get("minio_endpoint")
  │
  └── MLflow: MinIO를 artifact store로 설정

[argus-kserve]                        ──requires──← minio_endpoint
  minio_url = ctx.get("minio_endpoint")
  │
  └── KServe: MinIO에서 모델 파일 로드
```

## 새 Plugin 작성 가이드

### 1. Plugin 디렉토리 생성

```
plugins/builtin/my-software/
├── plugin.yaml
└── v1.0/
    └── version.yaml
```

### 2. plugin.yaml 작성

```yaml
name: argus-my-software
display_name: My Software
description: Deploy My Software to Kubernetes
icon: my-software
category: analytics
depends_on:
  - argus-minio           # MinIO가 먼저 배포되어야 함
provides:
  - my_software_endpoint
  - my_software_password
requires:
  - minio_endpoint        # MinIO의 provides에서 제공
tags:
  - analytics
versions:
  - "1.0"
default_version: "1.0"
```

### 3. version.yaml 작성

```yaml
version: "1.0"
display_name: "v1.0 (My Software 3.2)"
description: My Software 3.2 with persistent storage
status: stable
step_class: workspace_provisioner.workflow.steps.my_software_deploy.MySoftwareDeployStep
config_class: workspace_provisioner.config.MySoftwareConfig
template_dir: my-software
changelog: |
  - Initial version
  - My Software 3.2 with PostgreSQL backend
upgradeable_from: []
```

### 4. Config 모델 작성 (`config.py`에 추가)

```python
class MySoftwareConfig(BaseModel):
    image: str = Field(
        default="my-org/my-software:3.2.0",
        description="My Software container image",
    )
    storage_size: str = Field(
        default="20Gi",
        description="PVC size for data volume",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory resource configuration",
    )
```

### 5. K8s 매니페스트 템플릿 작성

```
kubernetes/templates/my-software/
├── secret.yaml
├── pvc.yaml
├── statefulset.yaml
└── service.yaml
```

### 6. WorkflowStep 구현

```python
class MySoftwareDeployStep(WorkflowStep):
    @property
    def name(self) -> str:
        return "my-software-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        config = ctx.get("my_software_config", MySoftwareConfig())
        minio_endpoint = ctx.get("minio_endpoint")  # requires에서 선언
        
        variables = {
            "WORKSPACE_NAME": ctx.workspace_name,
            "K8S_NAMESPACE": ctx.get("k8s_namespace"),
            "MY_SOFTWARE_IMAGE": config.image,
            "STORAGE_SIZE": config.storage_size,
            "MINIO_ENDPOINT": minio_endpoint,
            # ...
        }
        
        manifests = render_manifests("my-software", variables)
        ctx.set("my_software_manifests", manifests)
        
        await kubectl_apply(manifests)
        await kubectl_rollout_status(
            f"statefulset/argus-my-software-{ctx.workspace_name}",
            namespace=ctx.get("k8s_namespace"),
        )
        
        ctx.set("my_software_endpoint", f"https://...")  # provides 계약 이행
        return {"status": "deployed"}

    async def rollback(self, ctx: WorkflowContext) -> None:
        manifests = ctx.get("my_software_manifests")
        if manifests:
            await kubectl_delete(manifests)
```

### 7. 검증 및 배포

```bash
# 플러그인 재탐색
POST /plugins/rescan

# 매니페스트 렌더링 확인 (dry-run)
python bin/provisioner-cli.py render -f workspace.json -s my-software

# kubectl dry-run 검증
python bin/provisioner-cli.py render -f workspace.json -s my-software \
  | kubectl apply --dry-run=client -f -
```

## 주요 설계 원칙

1. **선언적 메타데이터**: `plugin.yaml`과 `version.yaml`로 Plugin의 모든 메타데이터를 선언적으로 관리
2. **관심사 분리**: Config(무엇을) / Template(어떤 형태로) / Step(어떻게) 3계층 분리
3. **계약 기반 연동**: `provides`/`requires`로 Plugin 간 데이터 의존성을 명시적으로 선언
4. **동적 로딩**: `importlib`를 통한 Step/Config 클래스 동적 임포트로 코드 수정 없이 Plugin 추가 가능
5. **Schema-Driven UI**: Pydantic 모델 → JSON Schema → UI 폼 자동 생성
6. **멱등성**: `kubectl apply`는 멱등적이므로 동일 매니페스트를 반복 적용해도 안전
7. **결정적 순서**: 매니페스트 렌더링과 적용 순서가 파일 이름 기반으로 항상 동일
