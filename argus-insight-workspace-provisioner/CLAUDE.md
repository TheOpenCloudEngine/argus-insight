# Argus Insight Workspace Provisioner

Workspace 생명주기를 관리하는 Step-based Workflow Engine 라이브러리입니다. `argus-insight-server`에서 import하여 사용합니다.

## 핵심 개념

### Workspace
- 독립된 작업 환경 단위. 각 Workspace에는 Airflow, MLflow, VS Code, Jupyter, Trino, MinIO 등이 배포됩니다.
- K8s 클러스터와 네임스페이스가 지정되며, GitLab 프로젝트가 연결됩니다.
- 사용자는 여러 Workspace에 참여할 수 있고, WorkspaceAdmin 또는 User 역할을 가집니다.

### Workflow Engine
- 워크스페이스 생성/삭제 시 실행되는 Step 기반 파이프라인입니다.
- 각 Step은 `WorkflowStep` ABC를 상속하여 `execute()`와 선택적으로 `rollback()`을 구현합니다.
- 모든 Step의 실행 상태는 DB에 기록되어 UI에서 진행 상황을 모니터링할 수 있습니다.
- Step 실패 시 완료된 Step들의 rollback이 역순으로 실행됩니다.

## 프로젝트 구조

```
argus-insight-workspace-provisioner/
├── CLAUDE.md
├── pyproject.toml
├── scripts/
│   ├── argus-insight-provisioner-mariadb.sql
│   └── argus-insight-provisioner-postgresql.sql
└── workspace_provisioner/
    ├── __init__.py
    ├── config.py              # ProvisioningConfig (UI에서 넘겨받는 설정 모델)
    ├── models.py              # ArgusWorkspace, ArgusWorkspaceMember ORM 모델
    ├── schemas.py             # Pydantic 요청/응답 스키마
    ├── service.py             # 비즈니스 로직 (CRUD + 워크플로우 실행)
    ├── router.py              # FastAPI 라우터 (/api/v1/workspace/*)
    ├── gitlab/
    │   ├── __init__.py
    │   └── client.py          # python-gitlab 래퍼 (비동기)
    ├── minio/
    │   ├── __init__.py
    │   └── client.py          # MinIO admin 래퍼 (버킷/사용자/정책)
    ├── kubernetes/
    │   ├── __init__.py
    │   ├── client.py          # kubectl async wrapper + 템플릿 렌더링
    │   └── templates/
    │       ├── minio/         # MinIO K8s 매니페스트 템플릿
    │       ├── airflow/       # Airflow K8s 매니페스트 템플릿
    │       └── mlflow/        # MLflow K8s 매니페스트 템플릿
    └── workflow/
        ├── __init__.py
        ├── engine.py          # WorkflowStep ABC, WorkflowContext, WorkflowExecutor
        ├── models.py          # ArgusWorkflowExecution, ArgusWorkflowStepExecution ORM
        └── steps/
            ├── __init__.py
            ├── gitlab_create_project.py  # Step 1: GitLab 프로젝트 생성
            ├── minio_deploy.py           # Step 2: MinIO K8s 배포
            ├── minio_setup.py            # Step 3: 버킷 + 사용자 생성
            ├── airflow_deploy.py         # Step 4: Airflow K8s 배포
            └── mlflow_deploy.py          # Step 5: MLflow K8s 배포
```

## 아키텍처

```
WorkspaceCreateRequest (+ provisioning_config)
    │
    ▼
WorkspaceService.create_workspace()
    ├── DB에 workspace 레코드 생성 (status: provisioning)
    ├── 생성자를 WorkspaceAdmin으로 추가
    └── Background Task: WorkflowExecutor.run()
         ├── Step 1: GitLabCreateProjectStep
         │    ├── workspaces 그룹 확인/생성
         │    ├── 프로젝트 생성
         │    └── 초기 디렉토리 구조 커밋 (airflow/dags, notebooks, vscode, mlflow)
         ├── Step 2: MinioDeployStep
         │    ├── K8s 매니페스트 렌더링 (config에서 이미지/리소스/스토리지 주입)
         │    ├── kubectl apply (Secret, PVC, StatefulSet, Service, Ingress)
         │    └── rollout 완료 대기
         ├── Step 3: MinioSetupStep
         │    ├── 기본 버킷 생성 (workspace 이름 = 버킷 이름)
         │    ├── WorkspaceAdmin 전용 사용자 생성
         │    └── read-write 정책 할당
         ├── Step 4: AirflowDeployStep
         │    ├── PostgreSQL + Airflow StatefulSet (webserver + scheduler)
         │    ├── git-sync sidecar → GitLab repo에서 DAG 자동 동기화
         │    └── init container: db migrate + admin 사용자 생성
         ├── Step 5: MlflowDeployStep
         │    ├── PostgreSQL + MLflow Tracking Server
         │    └── MinIO를 artifact store로 사용
         └── 완료 → workspace.status = active
```

## Provisioning Config (UI 설정)

워크스페이스 생성 시 `provisioning_config` 필드를 통해 각 서비스의 배포 설정을 지정할 수 있습니다.
모든 필드는 optional이며, 지정하지 않으면 기본값이 사용됩니다.

### 설정 모델 (`config.py`)

#### ResourceConfig (공통 리소스 설정)

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `cpu_request` | string | `"250m"` | K8s CPU request |
| `cpu_limit` | string | `"2"` | K8s CPU limit |
| `memory_request` | string | `"512Mi"` | K8s Memory request |
| `memory_limit` | string | `"2Gi"` | K8s Memory limit |

#### MinioConfig

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `image` | string | `"minio/minio:RELEASE.2025-02-28T09-55-16Z"` | MinIO 컨테이너 이미지 |
| `storage_size` | string | `"50Gi"` | 데이터 볼륨 PVC 크기 |
| `resources` | ResourceConfig | (기본값) | CPU/Memory 리소스 |

#### AirflowConfig

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `image` | string | `"apache/airflow:2.10.4-python3.11"` | Airflow 컨테이너 이미지 |
| `postgres_image` | string | `"postgres:16-alpine"` | 메타데이터 DB PostgreSQL 이미지 |
| `git_sync_image` | string | `"alpine/git:latest"` | DAG 동기화 sidecar 이미지 |
| `git_sync_interval` | int | `60` | DAG 동기화 주기 (초) |
| `dags_storage_size` | string | `"10Gi"` | DAGs 볼륨 PVC 크기 |
| `logs_storage_size` | string | `"20Gi"` | Logs 볼륨 PVC 크기 |
| `db_storage_size` | string | `"10Gi"` | PostgreSQL 데이터 볼륨 PVC 크기 |
| `webserver_resources` | ResourceConfig | (기본값) | Webserver CPU/Memory 리소스 |
| `scheduler_resources` | ResourceConfig | (기본값) | Scheduler CPU/Memory 리소스 |

#### MlflowConfig

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `image` | string | `"ghcr.io/mlflow/mlflow:v2.19.0"` | MLflow 컨테이너 이미지 |
| `postgres_image` | string | `"postgres:16-alpine"` | Backend store PostgreSQL 이미지 |
| `db_storage_size` | string | `"10Gi"` | PostgreSQL 데이터 볼륨 PVC 크기 |
| `resources` | ResourceConfig | (기본값) | CPU/Memory 리소스 |

### API 요청 예시

#### 모든 기본값 사용 (설정 생략 가능)

```json
POST /api/v1/workspace/workspaces
{
  "name": "ml-team-dev",
  "display_name": "ML Team Dev",
  "domain": "dev.net",
  "admin_user_id": 1
}
```

#### 일부 설정만 오버라이드

```json
POST /api/v1/workspace/workspaces
{
  "name": "ml-team-dev",
  "display_name": "ML Team Dev",
  "domain": "dev.net",
  "k8s_cluster": "prod-cluster",
  "k8s_namespace": "ml-team",
  "admin_user_id": 1,
  "provisioning_config": {
    "minio": {
      "image": "minio/minio:RELEASE.2025-03-01T00-00-00Z",
      "storage_size": "200Gi",
      "resources": {
        "cpu_request": "500m",
        "cpu_limit": "4",
        "memory_request": "1Gi",
        "memory_limit": "4Gi"
      }
    },
    "airflow": {
      "image": "apache/airflow:2.10.4-python3.11",
      "git_sync_interval": 30,
      "dags_storage_size": "20Gi",
      "logs_storage_size": "50Gi",
      "webserver_resources": {
        "cpu_limit": "4",
        "memory_limit": "4Gi"
      },
      "scheduler_resources": {
        "cpu_limit": "4",
        "memory_limit": "4Gi"
      }
    },
    "mlflow": {
      "db_storage_size": "20Gi",
      "resources": {
        "cpu_limit": "4",
        "memory_limit": "4Gi"
      }
    }
  }
}
```

#### 특정 서비스만 설정

```json
POST /api/v1/workspace/workspaces
{
  "name": "data-team",
  "display_name": "Data Team",
  "domain": "dev.net",
  "admin_user_id": 2,
  "provisioning_config": {
    "minio": {
      "storage_size": "500Gi"
    }
  }
}
```

### 설정 데이터 흐름

```
argus-insight-ui (Settings 페이지)
    │
    │  POST /api/v1/workspace/workspaces
    │  { ..., "provisioning_config": { "minio": {...}, "airflow": {...}, "mlflow": {...} } }
    │
    ▼
router.py → WorkspaceCreateRequest.provisioning_config (Pydantic 검증 + 기본값 채움)
    │
    ▼
service.py → WorkflowContext에 config 주입
    │         ctx.data["minio_config"] = provisioning_config.minio
    │         ctx.data["airflow_config"] = provisioning_config.airflow
    │         ctx.data["mlflow_config"] = provisioning_config.mlflow
    │
    ▼
각 Deploy Step에서 config 읽기
    │  config: MinioConfig = ctx.get("minio_config", MinioConfig())
    │
    ▼
K8s 매니페스트 템플릿 변수로 주입
    │  variables = {
    │      "MINIO_IMAGE": config.image,
    │      "MINIO_STORAGE_SIZE": config.storage_size,
    │      "MINIO_CPU_REQUEST": config.resources.cpu_request,
    │      ...
    │  }
    │
    ▼
kubernetes/client.py → render_manifests() → kubectl apply
```

## 서비스 접근 URL

워크스페이스 이름이 `{ws}`, 도메인이 `{domain}`일 때:

| 서비스 | URL |
|--------|-----|
| GitLab 프로젝트 | `https://gitlab-global.argus-insight.{domain}/workspaces/{ws}` |
| MinIO API | `https://minio-{ws}.argus-insight.{domain}` |
| MinIO Console | `https://minio-console-{ws}.argus-insight.{domain}` |
| Airflow | `https://airflow-{ws}.argus-insight.{domain}` |
| MLflow | `https://mlflow-{ws}.argus-insight.{domain}` |

## 새 Step 추가 방법

1. `workspace_provisioner/workflow/steps/` 에 새 파일 생성
2. `WorkflowStep`을 상속하고 `name`, `execute()` 구현
3. 필요시 `rollback()` 구현
4. 설정이 필요하면 `config.py`에 새 Config 모델 추가 후 `ProvisioningConfig`에 등록
5. `workspace_provisioner/service.py`의 `_run_provisioning_workflow()`에 Step 등록

```python
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

class DnsRegisterStep(WorkflowStep):
    @property
    def name(self) -> str:
        return "dns-register"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        domain = ctx.domain
        # config = ctx.get("dns_config", DnsConfig())
        # ... DNS 레코드 등록 로직
        return {"records_created": 5}

    async def rollback(self, ctx: WorkflowContext) -> None:
        # ... DNS 레코드 삭제 로직
        pass
```

## argus-insight-server 연동

### 의존성 추가

`argus-insight-server/pyproject.toml`:
```toml
dependencies = [
    ...,
    "argus-insight-workspace-provisioner",
]
```

### 라우터 등록

`argus-insight-server/app/main.py`:
```python
from workspace_provisioner.router import router as workspace_router, init_gitlab_client

# In lifespan:
init_gitlab_client(
    url=settings.gitlab_url,
    private_token=settings.gitlab_token,
)

# Router registration:
app.include_router(workspace_router, prefix="/api/v1")
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /workspace/workspaces | Workspace 생성 + 프로비저닝 시작 |
| GET | /workspace/workspaces | Workspace 목록 (페이지네이션) |
| GET | /workspace/workspaces/{id} | Workspace 상세 조회 |
| DELETE | /workspace/workspaces/{id} | Workspace 삭제 |
| POST | /workspace/workspaces/{id}/members | 멤버 추가 |
| GET | /workspace/workspaces/{id}/members | 멤버 목록 |
| DELETE | /workspace/workspaces/{id}/members/{mid} | 멤버 제거 |
| GET | /workspace/workspaces/{id}/workflow | 프로비저닝 워크플로우 상태 조회 |

## DB 테이블

| 테이블 | 설명 |
|--------|------|
| `argus_workspaces` | Workspace 정의 (이름, 도메인, K8s, GitLab, MinIO, Airflow, MLflow 정보, 상태) |
| `argus_workspace_members` | Workspace 멤버십 (user_id, workspace_id, role) |
| `argus_workflow_executions` | 워크플로우 실행 이력 (workspace_id, status) |
| `argus_workflow_step_executions` | Step별 실행 상태 (step_name, status, error, result) |

## 기술 스택

- Python 3.11+
- FastAPI (라우터)
- SQLAlchemy async (ORM)
- Pydantic v2 (스키마, 설정 모델)
- python-gitlab (GitLab API 클라이언트)
- minio (MinIO SDK)
- cryptography (Airflow Fernet key 생성)
- ruff (린터)

## 코딩 규칙

- argus-insight-server와 동일한 3-layer 패턴 (router → schemas → service)
- 모든 배포 설정은 `config.py`의 Pydantic 모델로 관리, Step에 상수 하드코딩 금지
- K8s 매니페스트 템플릿에서 이미지, 스토리지 크기, 리소스는 반드시 `${VAR}` 변수 사용
- ruff: `target-version = "py311"`, `line-length = 100`
- 커밋 메시지: 영문, 간결하게
