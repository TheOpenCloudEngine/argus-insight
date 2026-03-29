# Workspace Provisioner — Plugin Architecture

## 개요

Workspace Provisioner의 플러그인 아키텍처는 **메타데이터 기반, 버전 인식** 플러그인 시스템입니다. 각 소프트웨어(MinIO, Airflow, VS Code Server 등)가 하나의 플러그인이 되며, 플러그인 내부에 여러 버전을 포함할 수 있습니다. 관리자는 UI에서 플러그인의 활성화/비활성화, 실행 순서, 버전 선택을 관리합니다.

### 설계 원칙

1. **plugin.yaml이 단일 진실 공급원** — 메타데이터, 의존성, 설정 스키마를 하나의 파일에 선언
2. **Self-describing** — UI가 plugin.yaml만 읽으면 설정 폼, 순서 제약, 의존성 그래프를 자동으로 구성
3. **의존성 기반 순서 제약** — 관리자가 순서를 바꿀 수 있되, 의존성 위반은 불가
4. **버전별 배포 전략** — 같은 소프트웨어의 버전마다 다른 K8s 매니페스트, 설정 스키마, 배포 로직 지원
5. **기존 코드 100% 호환** — 기존 WorkflowStep/WorkflowExecutor 엔진 변경 없이 동작

---

## 디렉토리 구조

```
workspace_provisioner/
├── plugins/
│   ├── __init__.py
│   ├── base.py                  # PluginMeta, PluginVersionMeta 데이터클래스
│   ├── registry.py              # PluginRegistry — 발견, 로딩, 검증, 의존성 해석
│   ├── models.py                # ArgusPluginConfig DB 모델
│   ├── schemas.py               # API 요청/응답 Pydantic 스키마
│   ├── router.py                # FastAPI 라우터 (/api/v1/plugins/*)
│   │
│   ├── builtin/                 # 내장 플러그인 (코드와 함께 배포)
│   │   ├── gitlab/
│   │   │   ├── plugin.yaml      # 소프트웨어 레벨 메타데이터
│   │   │   └── v1.0/
│   │   │       └── version.yaml # 버전 레벨 메타데이터
│   │   ├── minio_deploy/
│   │   │   ├── plugin.yaml
│   │   │   └── v1.0/
│   │   │       └── version.yaml
│   │   ├── minio_setup/
│   │   │   ├── plugin.yaml
│   │   │   └── v1.0/
│   │   │       └── version.yaml
│   │   ├── airflow/
│   │   │   ├── plugin.yaml
│   │   │   └── v1.0/
│   │   │       └── version.yaml
│   │   ├── mlflow/
│   │   │   ├── plugin.yaml
│   │   │   └── v1.0/
│   │   │       └── version.yaml
│   │   ├── kserve/
│   │   │   ├── plugin.yaml
│   │   │   └── v1.0/
│   │   │       └── version.yaml
│   │   └── vscode_server/
│   │       ├── plugin.yaml
│   │       ├── v1.0/
│   │       │   └── version.yaml
│   │       └── v1.1/
│   │           └── version.yaml
│   │
│   └── external/                # 외부 플러그인 (사용자가 추가)
│       └── .gitkeep
│
├── workflow/
│   ├── engine.py                # WorkflowStep ABC, WorkflowExecutor (변경 없음)
│   ├── models.py                # Workflow/Step execution DB 모델
│   └── steps/                   # 기존 Step 구현체 (그대로 유지)
│       ├── gitlab_create_project.py
│       ├── minio_deploy.py
│       ├── minio_setup.py
│       ├── airflow_deploy.py
│       ├── mlflow_deploy.py
│       ├── kserve_deploy.py
│       └── custom_hook.py
│
├── kubernetes/
│   └── templates/               # K8s 매니페스트 템플릿
│       ├── airflow/
│       ├── minio/
│       ├── mlflow/
│       ├── kserve/
│       └── vscode/
│
├── config.py                    # ProvisioningConfig (레거시 호환)
├── models.py                    # Workspace/Member/Credential DB 모델
├── schemas.py                   # Workspace API 스키마
├── service.py                   # 비즈니스 로직 (플러그인 + 레거시 지원)
└── router.py                    # Workspace API 라우터
```

---

## 핵심 개념

### Plugin = Software (What)

하나의 플러그인은 하나의 소프트웨어를 나타냅니다. `plugin.yaml`에 소프트웨어 레벨의 메타데이터를 선언합니다.

### Version = 배포 전략 (How)

같은 소프트웨어라도 버전마다 배포 방식이 다를 수 있습니다. 각 버전은 독립된 디렉토리에 `version.yaml`, `step.py`, `config.py`, `templates/`를 가집니다.

```
Plugin (vscode-server)
├── v1.0 — code-server 기본, ephemeral 스토리지
├── v1.1 — code-server + s3fs sidecar, S3 기반 영구 스토리지
└── v1.2 — OpenVSCode Server, StatefulSet + PVC 기반 (향후)
```

---

## 메타데이터 파일 형식

### plugin.yaml — 소프트웨어 레벨

```yaml
# 필수 필드
name: airflow-deploy                    # 고유 식별자 (step name과 동일)
display_name: Apache Airflow            # UI 표시명
description: DAG 기반 워크플로우 오케스트레이션 엔진
icon: airflow                           # UI 아이콘 매핑 키
category: orchestration                 # UI 그룹핑용 카테고리

# 의존성 그래프
depends_on:                             # 이 플러그인 전에 실행되어야 하는 플러그인
  - gitlab-create-project
  - minio-deploy
provides:                               # context에 쓰는 키 (다른 플러그인이 참조)
  - airflow_endpoint
  - airflow_admin_password
requires:                               # context에서 읽는 키 (depends_on이 제공)
  - gitlab_http_url
  - gitlab_token
  - minio_endpoint

# 버전
versions:                               # 사용 가능한 버전 목록
  - "1.0"
default_version: "1.0"                  # 기본 버전

# 메타데이터
tags:                                   # UI 필터링/검색용
  - workflow
  - scheduler
```

### version.yaml — 버전 레벨

```yaml
# 필수 필드
version: "1.0"                          # 버전 문자열
display_name: "v1.0 (Airflow 2.10)"    # UI 표시명
description: Airflow 2.10 with PostgreSQL and git-sync
status: stable                          # stable | beta | deprecated

# Step 구현
step_class: workspace_provisioner.workflow.steps.airflow_deploy.AirflowDeployStep

# 설정 모델 (Pydantic class → JSON Schema로 변환하여 UI 폼 자동 생성)
config_class: workspace_provisioner.config.AirflowConfig

# K8s 매니페스트 템플릿 디렉토리
template_dir: airflow

# 선택적 필드
release_date: "2026-01-15"             # 릴리스 날짜
min_k8s_version: "1.28"                # 최소 K8s 버전 요구사항

# 버전별 의존성 변경 (plugin.yaml의 depends_on에 merge)
depends_on_override:
  add:                                  # 이 버전에서 추가된 의존성
    - some-new-dependency
  remove:                               # 이 버전에서 제거된 의존성
    - old-dependency

# 업그레이드 호환성
upgradeable_from:                       # 이 버전으로 업그레이드 가능한 이전 버전
  - "0.9"

# 변경 이력
changelog: |
  - Airflow 2.10.4 with Python 3.11
  - PostgreSQL 16 for metadata store
  - Git-sync sidecar for DAG auto-loading
```

---

## 핵심 클래스

### PluginMeta (base.py)

`plugin.yaml`을 파싱한 데이터클래스입니다.

```python
@dataclass
class PluginMeta:
    name: str                               # "airflow-deploy"
    display_name: str                       # "Apache Airflow"
    description: str
    icon: str
    category: str
    depends_on: list[str]                   # ["gitlab-create-project", "minio-deploy"]
    provides: list[str]                     # ["airflow_endpoint", ...]
    requires: list[str]                     # ["gitlab_http_url", ...]
    tags: list[str]
    source: str                             # "builtin" | "external"
    plugin_dir: Path                        # 플러그인 디렉토리 절대경로
    versions: dict[str, PluginVersionMeta]  # "1.0" → VersionMeta
    default_version: str                    # "1.0"
```

주요 메서드:

- `get_version(version: str | None) -> PluginVersionMeta` — 지정된 버전 또는 기본 버전 반환
- `get_effective_depends_on(version: str) -> list[str]` — 플러그인 레벨 + 버전 오버라이드 병합

### PluginVersionMeta (base.py)

`version.yaml`을 파싱한 데이터클래스입니다.

```python
@dataclass
class PluginVersionMeta:
    version: str                    # "1.0"
    display_name: str               # "v1.0 (Airflow 2.10)"
    description: str
    status: str                     # stable | beta | deprecated
    step_class: str                 # Python import path
    config_class: str | None        # Python import path (optional)
    template_dir: str | None
    changelog: str | None
    upgradeable_from: list[str]
    release_date: str | None
    min_k8s_version: str | None
    depends_on_override: dict       # {"add": [...], "remove": [...]}
```

### PluginRegistry (registry.py)

플러그인의 발견, 로딩, 검증, 인스턴스화를 담당하는 싱글턴입니다.

```python
class PluginRegistry:
    _instance: "PluginRegistry | None" = None

    @classmethod
    def get_instance(cls) -> "PluginRegistry": ...

    def discover(self, dirs: list[Path]) -> int: ...
    def register(self, meta: PluginMeta) -> None: ...
    def get_all(self) -> list[PluginMeta]: ...
    def get(self, name: str) -> PluginMeta | None: ...
    def resolve_order(self, selected: list[str], versions: dict[str, str] | None = None) -> list[str]: ...
    def validate_order(self, ordered: list[str], versions: dict[str, str] | None = None) -> list[str]: ...
    def instantiate_step(self, name: str, version: str | None = None, **kwargs) -> WorkflowStep: ...
    def get_config_schema(self, name: str, version: str | None = None) -> dict | None: ...
    def get_config_class(self, name: str, version: str | None = None) -> type | None: ...
    def rescan(self) -> None: ...
```

주요 동작:

| 메서드 | 설명 |
|--------|------|
| `discover(dirs)` | 디렉토리에서 `*/plugin.yaml`을 찾아 등록 |
| `resolve_order(selected)` | 위상 정렬(Kahn's algorithm)로 의존성 존중 순서 반환 |
| `validate_order(ordered)` | 관리자 지정 순서가 의존성을 위반하는지 검증 |
| `instantiate_step(name, version)` | Step 클래스를 동적 import하여 인스턴스 생성 |
| `get_config_schema(name, version)` | Pydantic 모델 → JSON Schema 반환 (UI 폼 생성용) |
| `rescan()` | builtin + external 디렉토리 재스캔 |

---

## DB 모델

### argus_plugin_configs

관리자가 UI에서 설정한 플러그인 구성을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | 자동 증가 ID |
| plugin_name | VARCHAR(100) UNIQUE | 플러그인 식별자 (예: `airflow-deploy`) |
| enabled | BOOLEAN | 활성화 여부 (UI 토글) |
| display_order | INTEGER | 관리자가 지정한 실행 순서 |
| selected_version | VARCHAR(50) | 선택된 버전 (null이면 default_version 사용) |
| default_config | JSON | 기본 설정 오버라이드 (JSON) |
| created_at | TIMESTAMP | 생성 시간 |
| updated_at | TIMESTAMP | 수정 시간 |

---

## API 엔드포인트

### 플러그인 관리 (`/api/v1/plugins`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/plugins` | 전체 플러그인 목록 (메타 + DB 설정 병합) |
| GET | `/plugins/{name}` | 플러그인 상세 (전체 버전 + config schema) |
| GET | `/plugins/{name}/versions/{ver}/schema` | 해당 버전의 JSON Schema |
| PUT | `/plugins/order` | 전체 순서/활성화/버전 일괄 업데이트 |
| POST | `/plugins/validate-order` | 순서 검증 dry-run |
| POST | `/plugins/rescan` | 외부 디렉토리 재스캔 |

### 워크스페이스 생성 (기존 API 확장)

`POST /workspace/workspaces` 요청에 `plugins` 필드가 추가됩니다:

```json
{
  "name": "ml-team",
  "domain": "dev.net",
  "admin_user_id": 1,
  "plugins": {
    "airflow-deploy": {
      "version": "1.0",
      "config": {
        "image": "apache/airflow:2.10.4-python3.11",
        "dags_storage_size": "20Gi"
      }
    },
    "vscode-server": {
      "version": "1.1"
    },
    "minio-deploy": {
      "config": {
        "storage_size": "100Gi"
      }
    }
  }
}
```

- `plugins` 필드를 생략하면 관리자가 설정한 전체 플러그인 세트 사용
- `plugins`를 지정하면 해당 플러그인만 실행 (의존성은 자동 해석)
- `version`을 생략하면: 요청 > DB selected_version > plugin default_version 순으로 결정
- `config`를 생략하면: DB default_config > 플러그인 기본값 사용

### 레거시 호환

`plugins` 필드가 `null`이고 `provisioning_config`가 설정되어 있으면 기존 하드코딩 방식으로 동작합니다:

```json
{
  "name": "ml-team",
  "domain": "dev.net",
  "admin_user_id": 1,
  "provisioning_config": {
    "minio": { "storage_size": "50Gi" },
    "airflow": { "image": "apache/airflow:2.10.4-python3.11" }
  }
}
```

---

## 의존성 관리

### 의존성 그래프

플러그인 간 의존성은 `depends_on`과 `provides/requires`로 선언됩니다.

```
gitlab-create-project     (depends: 없음)
    ├── minio-deploy      (depends: 없음)
    │   └── minio-setup   (depends: minio-deploy)
    │   └── vscode-server (depends: minio-deploy)
    ├── airflow-deploy    (depends: gitlab, minio-deploy)
    ├── mlflow-deploy     (depends: minio-deploy)
    └── kserve-deploy     (depends: 없음)
```

### 순서 검증 규칙

1. 모든 `depends_on` 플러그인이 활성화되어 있어야 함
2. 의존하는 플러그인이 항상 먼저 실행되어야 함
3. 순환 의존성 불가

### 관리자 순서 변경 예시

**허용되는 변경:**
```
1. gitlab-create-project
2. minio-deploy
3. airflow-deploy        ← mlflow보다 먼저 (상호 의존 없음, OK)
4. minio-setup
5. mlflow-deploy
6. kserve-deploy
```

**거부되는 변경:**
```
1. minio-setup           ← minio-deploy가 아직 실행되지 않음!
2. minio-deploy
→ API 응답: 400 Bad Request
  "minio-setup depends on minio-deploy, but minio-deploy is at position 2"
```

### 위상 정렬 알고리즘

`PluginRegistry.resolve_order()`는 Kahn's algorithm을 사용합니다:

1. 각 플러그인의 in-degree(들어오는 의존성 수) 계산
2. in-degree가 0인 플러그인을 큐에 추가 (관리자 순서 우선)
3. 큐에서 하나씩 꺼내며 결과에 추가, 의존하는 플러그인의 in-degree 감소
4. 모든 플러그인이 처리되면 완료, 아니면 순환 의존성 에러

---

## 버전별 배포 전략

### 같은 소프트웨어, 다른 배포 방식

VS Code Server를 예로 들면:

| 버전 | 베이스 이미지 | 스토리지 | K8s 리소스 | 설정 |
|------|-------------|---------|-----------|------|
| v1.0 | codercom/code-server:4.96.4 | ephemeral (emptyDir) | Deployment | VScodeV10Config |
| v1.1 | codercom/code-server:4.96.4 | S3 (s3fs sidecar) | Deployment | VScodeV11Config |
| v1.2 (향후) | gitpod/openvscode-server | PVC (persistent) | StatefulSet | VScodeV12Config |

각 버전은 독립된 디렉토리에 위치합니다:

```
plugins/builtin/vscode_server/
├── plugin.yaml              # 소프트웨어 메타데이터
├── common/
│   └── config.py            # 전 버전 공통 설정 (VScodeBaseConfig)
├── v1.0/
│   ├── version.yaml         # 버전 메타데이터
│   ├── step.py              # 배포 로직 (선택적, 공통 step 참조 가능)
│   └── templates/           # K8s 매니페스트 (선택적, 공통 템플릿 참조 가능)
├── v1.1/
│   ├── version.yaml
│   ├── step.py              # s3fs sidecar 로직 추가
│   ├── config.py            # VScodeV11Config (BaseConfig 상속 + s3fs 설정)
│   └── templates/
│       └── deployment.yaml  # s3fs sidecar 포함된 다른 매니페스트
└── v1.2/                    # 향후 추가
    ├── version.yaml
    ├── step.py              # 완전히 다른 배포 로직 (StatefulSet)
    ├── config.py            # VScodeV12Config (storage_size, PVC 설정)
    └── templates/
        ├── statefulset.yaml # Deployment → StatefulSet 변경
        └── pvc.yaml         # PVC 추가
```

### 버전별 Config 상속

```python
# common/config.py — 전 버전 공통
class VScodeBaseConfig(BaseModel):
    cpu_request: str = "500m"
    cpu_limit: str = "2"
    memory_request: str = "512Mi"
    memory_limit: str = "4Gi"

# v1.0/config.py
class VScodeV10Config(VScodeBaseConfig):
    image: str = "codercom/code-server:4.96.4"

# v1.1/config.py
class VScodeV11Config(VScodeV10Config):
    s3fs_image: str = "efrecon/s3fs:1.94"
    s3_bucket_pattern: str = "user-{username}"

# v1.2/config.py — 다른 베이스
class VScodeV12Config(VScodeBaseConfig):
    image: str = "gitpod/openvscode-server:1.96.2"
    storage_size: str = "20Gi"
    storage_class: str = "local-path"
```

### 버전별 의존성 변경

`version.yaml`의 `depends_on_override`로 버전 특화 의존성을 추가/제거할 수 있습니다:

```yaml
# v1.2/version.yaml
depends_on_override:
  add:
    - gitlab-create-project    # v1.2부터 GitLab 연동 추가
  remove: []
```

최종 의존성 = `plugin.yaml.depends_on` + `version.yaml.depends_on_override.add` - `version.yaml.depends_on_override.remove`

---

## UI 통합

### 플러그인 관리 화면

관리자가 플러그인 순서, 활성화, 버전을 관리하는 화면입니다.

```
┌─────────────────────────────────────────────────────────┐
│ ☰  Plugin Name          Version       Category  Status  │
├─────────────────────────────────────────────────────────┤
│ 1. ✅ GitLab Project     —             infra     ●      │
│ 2. ✅ MinIO Storage      —             storage   ●      │
│ 3. ✅ MinIO Setup        —             storage   ●      │
│ 4. ✅ Apache Airflow     —             orch.     ●      │
│ 5. ✅ VS Code Server    [v1.1 ▾]      dev       ●      │
│ 6. ☐ MLflow Tracking    —             mlops     ○      │
│ 7. ☐ KServe             —             serving   ○      │
│ 8. ✅ JupyterHub        [v2.0 ▾]      dev       ●      │ ← 외부 플러그인
└─────────────────────────────────────────────────────────┘

[↕ 드래그로 순서 변경]    [저장]
```

### 버전 선택 시 동작

버전 드롭다운을 변경하면:

1. `GET /api/v1/plugins/{name}/versions/{ver}/schema` 호출
2. JSON Schema를 기반으로 설정 폼을 동적으로 다시 렌더링
3. 이전 버전의 설정값 중 호환되는 필드는 자동 유지

### 순서 저장 시 동작

1. `POST /api/v1/plugins/validate-order` (dry-run)
2. 의존성 위반이 있으면 에러 메시지 + 추천 순서 표시
3. 검증 통과 시 `PUT /api/v1/plugins/order` 호출

---

## 외부 플러그인 개발 가이드

### 최소 요구사항

외부 개발자가 새 플러그인을 만들려면 **3개 파일**만 필요합니다:

```
/etc/argus-insight-server/plugins/
└── my-jupyter/
    ├── plugin.yaml          # 메타데이터
    └── v1.0/
        ├── version.yaml     # 버전 메타데이터
        └── step.py          # WorkflowStep 구현
```

### Step 1: plugin.yaml 작성

```yaml
name: jupyter-deploy
display_name: JupyterHub
description: 멀티유저 Jupyter 노트북 환경
icon: jupyter
category: development
depends_on:
  - minio-deploy
provides:
  - jupyter_endpoint
requires:
  - minio_endpoint
  - minio_root_user
tags:
  - notebook
  - ide
versions:
  - "1.0"
default_version: "1.0"
```

### Step 2: version.yaml 작성

```yaml
version: "1.0"
display_name: "v1.0 (JupyterHub 4.x)"
description: JupyterHub with S3 storage backend
status: stable
step_class: step.JupyterDeployStep        # 상대 경로 (version 디렉토리 기준)
config_class: null                         # 설정 모델이 없으면 null
template_dir: null                         # 자체 템플릿이 없으면 null
changelog: |
  - Initial version
  - JupyterHub 4.x with S3 storage
upgradeable_from: []
```

### Step 3: step.py 작성

기존 `WorkflowStep` ABC를 상속하면 됩니다:

```python
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowStep
from workspace_provisioner.kubernetes.client import (
    kubectl_apply,
    kubectl_delete,
    render_manifests,
)


class JupyterDeployStep(WorkflowStep):
    @property
    def name(self) -> str:
        return "jupyter-deploy"

    async def execute(self, ctx: WorkflowContext) -> dict | None:
        workspace_name = ctx.workspace_name
        namespace = ctx.get("k8s_namespace", f"argus-ws-{workspace_name}")

        variables = {
            "WORKSPACE_NAME": workspace_name,
            "K8S_NAMESPACE": namespace,
            "DOMAIN": ctx.domain,
            "MINIO_ENDPOINT": ctx.get("minio_endpoint"),
        }

        # 자체 템플릿이 있으면 render_manifests 사용
        # manifests = render_manifests("jupyter", variables)
        # await kubectl_apply(manifests)

        endpoint = f"jupyter-{workspace_name}.argus-insight.{ctx.domain}"
        ctx.set("jupyter_endpoint", endpoint)
        return {"endpoint": endpoint}

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        # 리소스 삭제 로직
        return {"deleted": True}
```

### Step 4: 배포

```bash
# 1. 플러그인 디렉토리에 파일 복사
cp -r my-jupyter/ /etc/argus-insight-server/plugins/

# 2. 서버 재시작 또는 API로 재스캔
curl -X POST http://localhost:4500/api/v1/plugins/rescan

# 3. UI에서 플러그인 활성화 및 순서 지정
```

### 설정 모델 추가 (선택)

UI에서 설정 폼을 자동 생성하려면 Pydantic 모델을 추가합니다:

```python
# v1.0/config.py
from pydantic import BaseModel, Field

class JupyterConfig(BaseModel):
    image: str = Field(
        default="jupyterhub/jupyterhub:4.1.5",
        description="JupyterHub container image",
    )
    storage_size: str = Field(
        default="10Gi",
        description="PVC size for user notebooks",
    )
    max_users: int = Field(
        default=50,
        description="Maximum concurrent users",
    )
```

```yaml
# v1.0/version.yaml에 추가
config_class: config.JupyterConfig    # 상대 경로
```

`config_class`를 지정하면 `GET /api/v1/plugins/jupyter-deploy/versions/1.0/schema`에서 JSON Schema가 반환되고, UI가 이를 기반으로 설정 폼을 자동으로 렌더링합니다.

---

## 설정 우선순위

플러그인 설정값은 다음 우선순위로 결정됩니다 (높은 것이 우선):

```
1. 워크스페이스 생성 요청의 plugins[name].config      ← 가장 높음
2. DB argus_plugin_configs.default_config              ← 관리자 기본값
3. Pydantic config 모델의 Field(default=...)           ← 코드 기본값
```

### 버전 결정 우선순위

```
1. 워크스페이스 생성 요청의 plugins[name].version      ← 가장 높음
2. DB argus_plugin_configs.selected_version            ← 관리자 선택
3. plugin.yaml의 default_version                       ← 플러그인 기본값
```

---

## 전체 흐름

### 서버 시작

```
1. PluginRegistry.discover([builtin/, external/])
2. plugin.yaml 파싱 → PluginMeta 객체 생성
3. version.yaml 파싱 → PluginVersionMeta 객체 생성
4. DB(argus_plugin_configs)와 동기화
   - 새 플러그인: 자동 등록 (enabled=true, 순서=마지막)
   - 삭제된 플러그인: enabled=false 처리
```

### 워크스페이스 생성 요청

```
1. POST /workspace/workspaces (plugins 필드 포함)
2. DB에서 enabled + ordered 플러그인 목록 조회
3. 요청의 plugins와 DB 설정 병합 (버전, 설정값)
4. PluginRegistry.resolve_order()로 의존성 검증 + 위상 정렬
5. 각 플러그인의 Step 인스턴스 생성 (instantiate_step)
6. WorkflowExecutor에 순서대로 add_step()
7. executor.run() 실행 — 기존 엔진 그대로 사용
```

### 워크스페이스 삭제

```
1. DELETE /workspace/workspaces/{id}
2. DB에서 enabled 플러그인 목록 조회
3. 같은 Step 인스턴스를 역순으로 teardown 실행
4. executor.run_teardown() — 기존 best-effort 삭제 엔진 사용
```

---

## 기존 코드와의 호환성

| 구성 요소 | 변경 내용 |
|-----------|----------|
| `workflow/engine.py` | **변경 없음** — WorkflowStep ABC와 WorkflowExecutor 그대로 사용 |
| `workflow/steps/*.py` | **변경 없음** — 기존 Step 구현체는 builtin 플러그인의 step_class로 참조 |
| `kubernetes/templates/` | **변경 없음** — 기존 템플릿 디렉토리 그대로 사용 |
| `config.py` | **변경 없음** — ProvisioningConfig와 하위 모델 유지 (레거시 호환) |
| `service.py` | 수정 — plugins 필드 존재 시 플러그인 기반, 없으면 레거시 방식 |
| `schemas.py` | 확장 — WorkspaceCreateRequest에 `plugins` 필드 추가 |

레거시 요청 (`plugins` 필드 없음)은 기존과 완전히 동일하게 동작합니다. 기존 API 클라이언트는 코드 변경 없이 계속 사용할 수 있습니다.
