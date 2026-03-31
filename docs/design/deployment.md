# Deployment - Pipeline - Plugin Architecture

Argus Insight의 소프트웨어 배포 시스템은 **Deployment**, **Pipeline**, **Plugin** 세 가지 핵심 개념으로 구성됩니다. 이 문서는 각 개념의 정의와 관계, 전체 아키텍처를 설명합니다.

## 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Software Deployment                         │
│                                                                    │
│   사용자가 Workspace에 소프트웨어를 배포하는 전체 프로세스           │
│                                                                    │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                      Pipeline                                │  │
│   │                                                              │  │
│   │   Plugin들의 실행 순서와 설정을 정의한 배포 템플릿            │  │
│   │                                                              │  │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │  │
│   │   │ Plugin A │→ │ Plugin B │→ │ Plugin C │→ │ Plugin D │   │  │
│   │   │ (GitLab) │  │ (MinIO)  │  │(Airflow) │  │ (MLflow) │   │  │
│   │   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│   WorkflowExecutor가 Pipeline의 Step들을 순차 실행                 │
│   → 각 Plugin이 Docker Image를 K8s 클러스터에 배포                 │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## 핵심 개념

### 1. Plugin (소프트웨어 컴포넌트)

Plugin은 배포 가능한 **소프트웨어 단위**입니다. 하나의 Plugin은 하나의 소프트웨어(예: Apache Airflow, MinIO, MLflow)를 나타내며, 해당 소프트웨어를 Kubernetes 클러스터에 배포하는 데 필요한 모든 정보를 포함합니다.

**Plugin이 가진 정보:**
- **메타데이터**: 이름, 설명, 카테고리, 아이콘, 태그
- **의존성**: 이 Plugin이 실행되기 전에 먼저 배포되어야 하는 다른 Plugin 목록
- **계약 (Contract)**: `provides` (제공하는 값)와 `requires` (필요한 값)
- **버전**: 동일 소프트웨어의 서로 다른 배포 전략 (예: Airflow v1.0, v2.0)

**Plugin 종류:**

| 카테고리 | Plugin | 설명 |
|----------|--------|------|
| VCS | argus-gitlab | GitLab 프로젝트 생성 |
| Storage | argus-minio | MinIO 오브젝트 스토리지 배포 |
| Storage | argus-minio-setup | MinIO 버킷/사용자 설정 |
| Storage | argus-minio-workspace | Workspace 전용 MinIO 설정 |
| Orchestration | argus-airflow | Apache Airflow 워크플로우 엔진 |
| ML | argus-mlflow | MLflow 트래킹 서버 |
| ML | argus-kserve | KServe 모델 서빙 |
| IDE | argus-vscode-server | VS Code Server |
| Notebook | argus-jupyter | Jupyter Lab |
| Notebook | argus-jupyter-pyspark | Jupyter + PySpark |
| Notebook | argus-jupyter-tensorflow | Jupyter + TensorFlow |
| Database | argus-neo4j | Neo4j 그래프 DB |
| Database | argus-milvus | Milvus 벡터 DB |
| AI | argus-mindsdb | MindsDB AI 엔진 |

### 2. Pipeline (배포 파이프라인)

Pipeline은 **Plugin들의 실행 순서와 설정을 정의한 재사용 가능한 배포 템플릿**입니다. 관리자가 UI에서 Pipeline을 구성하면, 이를 여러 Workspace에 반복적으로 적용할 수 있습니다.

**Pipeline이 정의하는 것:**
- 어떤 Plugin을 포함할 것인가 (enabled/disabled)
- 각 Plugin의 실행 순서 (display_order)
- 각 Plugin의 버전 선택 (selected_version)
- 각 Plugin의 기본 설정 오버라이드 (default_config)

```
Pipeline: "ML Team Standard"
├── [1] argus-gitlab       (v1.0, enabled)
├── [2] argus-minio        (v1.0, enabled, storage_size: 200Gi)
├── [3] argus-minio-setup  (v1.0, enabled)
├── [4] argus-airflow      (v1.0, enabled, dags_storage_size: 20Gi)
├── [5] argus-mlflow       (v1.0, enabled)
├── [6] argus-kserve       (v1.0, enabled)
└── [7] argus-jupyter      (v1.0, disabled)
```

### 3. Deployment (배포 실행)

Deployment는 Pipeline을 기반으로 **실제 Kubernetes 클러스터에 소프트웨어를 배포하는 실행 프로세스**입니다. `WorkflowExecutor`가 Pipeline의 각 Plugin을 순서대로 실행하며, 각 Plugin의 `WorkflowStep`이 K8s 매니페스트를 렌더링하고 `kubectl apply`로 배포합니다.

## 세 개념의 관계

```
                    ┌──────────────┐
                    │    Plugin    │   소프트웨어 정의 + 배포 방법
                    │  (What/How)  │   plugin.yaml + version.yaml
                    └──────┬───────┘
                           │  N개의 Plugin으로 구성
                           ▼
                    ┌──────────────┐
                    │   Pipeline   │   순서 + 설정 + 활성화 여부
                    │  (Template)  │   DB: argus_pipelines + argus_plugin_configs
                    └──────┬───────┘
                           │  Workspace 생성 시 적용
                           ▼
                    ┌──────────────┐
                    │  Deployment  │   실행 + 결과 + 상태 관리
                    │ (Execution)  │   WorkflowExecutor → kubectl apply
                    └──────────────┘
```

**비유하면:**
- **Plugin** = 레시피 (재료와 만드는 법)
- **Pipeline** = 코스 요리 메뉴 (어떤 레시피를 어떤 순서로 제공할지)
- **Deployment** = 실제 조리 과정 (메뉴에 따라 요리를 만들어 서빙)

## 아키텍처 상세

### Plugin 시스템 구조

```
plugins/
├── builtin/                        # 기본 제공 Plugin
│   ├── airflow/
│   │   ├── plugin.yaml             # Plugin 메타데이터
│   │   └── v1.0/
│   │       ├── version.yaml        # 버전별 배포 전략
│   │       ├── step.py             # WorkflowStep 구현 (선택)
│   │       └── config.py           # Pydantic 설정 모델 (선택)
│   ├── minio_deploy/
│   ├── mlflow/
│   └── ...
└── external/                       # 외부 Plugin (사용자 확장)
    └── .gitkeep
```

#### plugin.yaml (소프트웨어 정의)

```yaml
name: argus-airflow
display_name: Apache Airflow
description: Deploy Airflow workflow orchestration engine
icon: airflow
category: orchestration
depends_on: []                      # 의존하는 다른 Plugin 이름
provides:                           # 이 Plugin이 제공하는 값
  - airflow_endpoint
  - airflow_admin_password
  - airflow_manifests
requires:                           # 이 Plugin이 필요로 하는 값
  - gitlab_http_url
  - gitlab_token
  - minio_endpoint
tags:
  - workflow
  - scheduler
versions:
  - "1.0"
default_version: "1.0"
```

#### version.yaml (배포 전략)

```yaml
version: "1.0"
display_name: "v1.0 (Airflow 2.10)"
description: Airflow 2.10 with PostgreSQL metadata DB, git-sync DAG sidecar
status: stable                      # stable | beta | deprecated
step_class: workspace_provisioner.workflow.steps.airflow_deploy.AirflowDeployStep
config_class: workspace_provisioner.config.AirflowConfig
template_dir: airflow               # K8s 매니페스트 템플릿 디렉토리
changelog: |
  - Airflow 2.10.4 with Python 3.11
  - PostgreSQL 16 for metadata store
  - Git-sync sidecar for automatic DAG loading from GitLab
upgradeable_from: []                # 업그레이드 가능한 이전 버전
```

### Plugin 의존성 그래프

Plugin 간에는 `depends_on`과 `provides`/`requires`로 정의되는 의존성 관계가 있습니다.

```
argus-gitlab ──provides──→ gitlab_http_url, gitlab_token
      │
      ▼ (no explicit dep, but provides required values)
argus-minio ──provides──→ minio_endpoint, minio_root_user, minio_root_password
      │
      ▼ (depends_on: argus-minio)
argus-minio-setup ──provides──→ minio_workspace_user, minio_workspace_password
      │
      ├──→ argus-airflow ──requires──→ gitlab_http_url, minio_endpoint
      ├──→ argus-mlflow  ──requires──→ minio_endpoint
      └──→ argus-kserve  ──requires──→ minio_endpoint
```

의존성 해결은 **Kahn's Algorithm** (위상 정렬)을 사용합니다:
1. 모든 Plugin의 in-degree(선행 의존성 수)를 계산
2. in-degree가 0인 Plugin부터 실행 대기열에 추가
3. 관리자가 지정한 순서를 최대한 존중하며 정렬
4. 순환 의존성이 감지되면 오류 반환

### Pipeline 데이터 모델

Pipeline은 두 개의 DB 테이블로 관리됩니다:

```
argus_pipelines (파이프라인 정의)
├── id: 1
├── name: "ml-standard"
├── display_name: "ML Team Standard"
├── description: "ML 팀 표준 배포 파이프라인"
├── version: 1
└── created_by: "admin"

argus_plugin_configs (파이프라인별 Plugin 설정)
├── pipeline_id: 1, plugin_name: "argus-gitlab",      enabled: true,  display_order: 1
├── pipeline_id: 1, plugin_name: "argus-minio",       enabled: true,  display_order: 2
├── pipeline_id: 1, plugin_name: "argus-minio-setup",  enabled: true,  display_order: 3
├── pipeline_id: 1, plugin_name: "argus-airflow",      enabled: true,  display_order: 4
├── pipeline_id: 1, plugin_name: "argus-mlflow",       enabled: true,  display_order: 5
└── pipeline_id: 1, plugin_name: "argus-kserve",       enabled: true,  display_order: 6
```

### Deployment 실행 흐름

```
                    Workspace 생성 요청
                           │
                           ▼
                ┌─────────────────────┐
                │  Pipeline 조회       │  DB에서 Pipeline + PluginConfig 로드
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  의존성 검증 + 정렬  │  PluginRegistry.resolve_order()
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  Step 인스턴스 생성   │  PluginRegistry.instantiate_step()
                │  (동적 import)       │  version.yaml의 step_class 로드
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  WorkflowExecutor   │
                │  .run()             │
                │                     │
                │  Step 1: execute()  │──→ K8s 배포
                │  Step 2: execute()  │──→ K8s 배포
                │  Step 3: execute()  │──→ K8s 배포
                │  ...                │
                │                     │
                │  실패 시 → rollback  │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  Workspace 상태 갱신 │  provisioning → active (또는 failed)
                └─────────────────────┘
```

### 설정 우선순위

Plugin의 설정값은 3단계 우선순위로 결정됩니다:

```
1순위: Workspace 생성 요청의 plugins[name].config    (사용자가 직접 지정)
          │
          ▼ (지정 안 된 필드)
2순위: DB argus_plugin_configs.default_config          (관리자 기본값)
          │
          ▼ (DB에도 없는 필드)
3순위: Pydantic Config 모델의 Field default            (코드 기본값)
```

### WorkflowStep 인터페이스

모든 Plugin의 실행 로직은 `WorkflowStep` ABC를 구현합니다:

```python
class WorkflowStep(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """고유 Step 식별자 (예: 'minio-deploy')"""

    @abstractmethod
    async def execute(self, ctx: WorkflowContext) -> dict | None:
        """Step 실행. K8s 매니페스트 렌더링 → kubectl apply"""

    async def rollback(self, ctx: WorkflowContext) -> None:
        """실패 시 역순 롤백. 생성된 리소스 삭제"""

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Workspace 삭제 시 리소스 정리"""
```

### WorkflowContext (공유 상태)

Step 간 데이터 전달은 `WorkflowContext`를 통해 이루어집니다:

```
Step 1 (GitLab)
  ctx.set("gitlab_http_url", "https://...")
  ctx.set("gitlab_token", "glpat-xxx")
      │
      ▼
Step 2 (MinIO Deploy)
  ctx.set("minio_endpoint", "https://...")
  ctx.set("minio_root_password", "xxx")
      │
      ▼
Step 3 (Airflow Deploy)
  gitlab_url = ctx.get("gitlab_http_url")    ← Step 1의 결과 참조
  minio_url = ctx.get("minio_endpoint")      ← Step 2의 결과 참조
```

### Kubernetes 배포 방식

각 Plugin의 Step은 K8s 매니페스트 템플릿을 사용하여 배포합니다:

```
1. 템플릿 로드       kubernetes/templates/{component}/*.yaml
2. 변수 치환         ${WORKSPACE_NAME}, ${IMAGE}, ${STORAGE_SIZE} 등
3. 매니페스트 결합    secret → pvc → statefulset/deployment → service (결정적 순서)
4. kubectl apply     렌더링된 YAML을 stdin으로 전달
5. rollout 대기      StatefulSet/Deployment 준비 완료까지 대기
```

## 삭제 (Teardown) 워크플로우

Workspace 삭제 시 배포의 역순으로 리소스를 정리합니다:

```
WorkflowExecutor.run_teardown()
    │  (역순 실행, best-effort: 한 Step 실패해도 나머지 계속)
    │
    ├── Step N: Plugin D.teardown()    ← kubectl delete
    ├── Step 3: Plugin C.teardown()    ← kubectl delete
    ├── Step 2: Plugin B.teardown()    ← kubectl delete + 데이터 정리
    └── Step 1: Plugin A.teardown()    ← 프로젝트 삭제
```

| | rollback() | teardown() |
|---|---|---|
| **호출 시점** | 프로비저닝 중 Step 실패 | 운영 중 Workspace 삭제 |
| **에러 처리** | 전체 중단 + 역순 롤백 | Best-effort (실패해도 계속) |
| **데이터** | 빈 리소스 삭제 | 운영 데이터 포함 정리 |

## API 엔드포인트

### Plugin 관리

| Method | Path | 설명 |
|--------|------|------|
| GET | /plugins | 전체 Plugin 목록 (메타데이터 + 관리자 설정 포함) |
| GET | /plugins/{name} | Plugin 상세 (모든 버전 + 설정 스키마) |
| GET | /plugins/{name}/versions/{ver}/schema | 특정 버전의 JSON Schema (UI 폼 생성용) |
| PUT | /plugins/order | Plugin 순서/활성화/버전 일괄 업데이트 |
| POST | /plugins/validate-order | 순서 검증 (dry-run) |
| POST | /plugins/rescan | 외부 Plugin 재탐색 |

### Pipeline 관리

| Method | Path | 설명 |
|--------|------|------|
| GET | /pipelines | Pipeline 목록 |
| POST | /pipelines | Pipeline 생성 |
| GET | /pipelines/{id} | Pipeline 상세 |
| PUT | /pipelines/{id} | Pipeline 수정 |
| DELETE | /pipelines/{id} | Pipeline 삭제 |

### Workspace (Deployment 실행)

| Method | Path | 설명 |
|--------|------|------|
| POST | /workspace/workspaces | Workspace 생성 + 배포 실행 |
| GET | /workspace/workspaces/{id}/workflow | 배포 워크플로우 상태 조회 |
| DELETE | /workspace/workspaces/{id} | Workspace 삭제 (teardown 실행) |

## UI 연동

```
┌──────────────────────────────────────────────────────────────┐
│  Software Deployment Dashboard (argus-insight-ui)            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Catalog Tab  │  │ Pipeline Tab │  │ Workspace    │       │
│  │              │  │              │  │              │       │
│  │ Plugin 목록   │  │ Pipeline 편집 │  │ 배포 상태     │       │
│  │ 버전 정보     │  │ 순서 조정     │  │ 로그 모니터링  │       │
│  │ JSON Schema  │  │ 설정 오버라이드│  │ 자격증명 조회  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  Dynamic Config Form: Pydantic → JSON Schema → React Form   │
└──────────────────────────────────────────────────────────────┘
```

UI는 Plugin의 Pydantic 설정 모델에서 자동 생성된 JSON Schema를 기반으로 동적 폼을 렌더링합니다. 관리자가 별도로 UI 폼을 만들 필요 없이, Python 모델만 정의하면 UI가 자동으로 생성됩니다.

## Plugin 확장

### Builtin Plugin 추가

1. `plugins/builtin/my-plugin/` 디렉토리 생성
2. `plugin.yaml` 작성 (메타데이터, 의존성, provides/requires)
3. `v1.0/` 디렉토리 생성
4. `version.yaml` 작성 (step_class, config_class, template_dir)
5. WorkflowStep 구현
6. (선택) Pydantic Config 모델 작성
7. (선택) K8s 매니페스트 템플릿 작성

### External Plugin 추가

1. `plugins/external/my-plugin/` 디렉토리에 동일한 구조로 작성
2. 서버 재시작 또는 `POST /plugins/rescan` 호출
3. 동일 이름의 builtin Plugin이 있으면 external이 우선

## 관련 문서

- [Plugin 상세 설계 (Docker Image / K8s 배포)](plugin.md)
