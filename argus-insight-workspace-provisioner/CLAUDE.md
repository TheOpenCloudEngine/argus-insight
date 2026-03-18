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
└── workspace_provisioner/
    ├── __init__.py
    ├── models.py              # ArgusWorkspace, ArgusWorkspaceMember ORM 모델
    ├── schemas.py             # Pydantic 요청/응답 스키마
    ├── service.py             # 비즈니스 로직 (CRUD + 워크플로우 실행)
    ├── router.py              # FastAPI 라우터 (/api/v1/workspace/*)
    ├── gitlab/
    │   ├── __init__.py
    │   └── client.py          # python-gitlab 래퍼 (비동기)
    └── workflow/
        ├── __init__.py
        ├── engine.py          # WorkflowStep ABC, WorkflowContext, WorkflowExecutor
        ├── models.py          # ArgusWorkflowExecution, ArgusWorkflowStepExecution ORM
        └── steps/
            ├── __init__.py
            └── gitlab_create_project.py  # GitLab 프로젝트 생성 Step
```

## 아키텍처

```
WorkspaceCreateRequest
    │
    ▼
WorkspaceService.create_workspace()
    ├── DB에 workspace 레코드 생성 (status: provisioning)
    ├── 생성자를 WorkspaceAdmin으로 추가
    └── Background Task: WorkflowExecutor.run()
         ├── Step 1: GitLabCreateProjectStep
         │    ├── workspaces 그룹 확인/생성
         │    ├── 프로젝트 생성
         │    └── 초기 디렉토리 구조 커밋
         ├── Step 2: (향후) MinIO 버킷 생성
         ├── Step 3: (향후) Airflow 배포
         ├── Step 4: (향후) DNS 레코드 등록
         └── 완료 → workspace.status = active
```

## 새 Step 추가 방법

1. `workspace_provisioner/workflow/steps/` 에 새 파일 생성
2. `WorkflowStep`을 상속하고 `name`, `execute()` 구현
3. 필요시 `rollback()` 구현
4. `workspace_provisioner/service.py`의 `_run_provisioning_workflow()`에 Step 등록

```python
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep

class MinioCreateBucketStep(WorkflowStep):
    @property
    def name(self) -> str:
        return "minio-create-bucket"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        bucket_name = f"ws-{ctx.workspace_name}"
        # ... MinIO 버킷 생성 로직
        ctx.set("minio_bucket", bucket_name)
        return {"bucket": bucket_name}

    async def rollback(self, ctx: WorkflowContext) -> None:
        bucket_name = ctx.get("minio_bucket")
        if bucket_name:
            # ... MinIO 버킷 삭제 로직
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
| `argus_workspaces` | Workspace 정의 (이름, 도메인, K8s, GitLab 정보, 상태) |
| `argus_workspace_members` | Workspace 멤버십 (user_id, workspace_id, role) |
| `argus_workflow_executions` | 워크플로우 실행 이력 (workspace_id, status) |
| `argus_workflow_step_executions` | Step별 실행 상태 (step_name, status, error, result) |

## 기술 스택

- Python 3.11+
- FastAPI (라우터)
- SQLAlchemy async (ORM)
- Pydantic v2 (스키마)
- python-gitlab (GitLab API 클라이언트)
- ruff (린터)

## 코딩 규칙

- argus-insight-server와 동일한 3-layer 패턴 (router → schemas → service)
- ruff: `target-version = "py311"`, `line-length = 100`
- 커밋 메시지: 영문, 간결하게
