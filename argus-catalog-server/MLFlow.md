# MLflow 연동 가이드

Argus Catalog Server는 Unity Catalog OSS 호환 API를 제공하여,
MLflow에서 직접 모델을 등록하고 관리할 수 있습니다.

## 개요

```
┌──────────────┐     ┌───────────────────────────┐     ┌──────────────────┐
│ MLflow Client │────▶│ Catalog Server (:4600)      │     │ 로컬 디스크        │
│               │     │                             │     │                    │
│ log_model()   │     │ /api/2.1/unity-catalog/*    │────▶│ data_dir/          │
│ load_model()  │     │ (UC 호환 API)               │     │  model-artifacts/  │
│               │     │                             │     │   {name}/          │
│               │     │ /api/v1/models/*            │     │    versions/{N}/   │
│               │     │ (네이티브 API)              │     │     MLmodel, ...   │
└──────────────┘     └───────────────────────────┘     └──────────────────┘
```

## 사전 요구사항

```bash
pip install mlflow[skinny]>=3.0
pip install mlflow-unity-catalog>=0.1.0
```

## 기본 사용법

### 모델 등록

```python
import mlflow

# Argus Catalog를 Model Registry로 설정
mlflow.set_registry_uri("uc:http://<catalog-server>:4600")

# 모델 학습
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris

X, y = load_iris(return_X_y=True)
model = RandomForestClassifier(n_estimators=100, max_depth=5)
model.fit(X, y)

# 모델 등록 (한 줄)
mlflow.sklearn.log_model(
    model, "model",
    registered_model_name="argus.ml.iris_classifier",
)
```

### 모델 로딩 (추론)

```python
import mlflow

mlflow.set_registry_uri("uc:http://<catalog-server>:4600")

# 특정 버전 로드
model = mlflow.pyfunc.load_model("models:/argus.ml.iris_classifier/1")
predictions = model.predict(X_test)

# 최신 버전 로드
model = mlflow.pyfunc.load_model("models:/argus.ml.iris_classifier/latest")
```

## 네이밍 규칙

MLflow UC 플러그인은 **반드시 3-part name** (`catalog.schema.model`)을 요구합니다:

```python
# ✅ 올바른 예시
"argus.ml.iris_classifier"      # catalog=argus, schema=ml, model=iris_classifier
"prod.recommendation.user_sim"  # catalog=prod, schema=recommendation, model=user_sim
"datateam.fraud.detector_v2"    # catalog=datateam, schema=fraud, model=detector_v2

# ❌ 잘못된 예시 (에러 발생)
"iris_classifier"               # 1-part → ValueError
"ml.iris_classifier"            # 2-part → ValueError
```

## 내부 동작 흐름

`mlflow.sklearn.log_model(model, "model", registered_model_name="a.b.c")` 실행 시:

```
Step 1: POST /api/2.1/unity-catalog/models
        → RegisteredModel 생성 (또는 기존 모델 조회)
        → DB: catalog_registered_models 행 생성

Step 2: POST /api/2.1/unity-catalog/models/versions
        → ModelVersion 생성 (status=PENDING_REGISTRATION)
        → DB: catalog_model_versions 행 생성
        → 서버가 storage_location 반환 (file:///var/lib/.../versions/N/)

Step 3: MLflow가 storage_location에 아티팩트 파일 직접 복사
        → model.pkl, MLmodel, conda.yaml, requirements.txt, python_env.yaml
        → file:// 접두사이므로 로컬 파일시스템에 직접 쓰기

Step 4: PATCH /api/2.1/unity-catalog/models/{name}/versions/{ver}/finalize
        → status: PENDING_REGISTRATION → READY
        → 서버가 아티팩트 디렉토리 스캔 (artifact_count, artifact_size 기록)
        → catalog_models 테이블에 파싱된 메타데이터 저장
```

## 아티팩트 저장 경로

```
{data_dir}/model-artifacts/
  argus.ml.iris_classifier/              ← RegisteredModel
    versions/
      1/                                 ← ModelVersion v1
        MLmodel                          ← 모델 메타데이터 (YAML)
        model.pkl                        ← 직렬화된 모델
        conda.yaml                       ← Conda 환경 정의
        requirements.txt                 ← pip 의존성
        python_env.yaml                  ← Python 가상환경 정의
      2/                                 ← ModelVersion v2
        MLmodel
        model.pkl
        ...
```

### MLmodel 파일 구조

```yaml
artifact_path: /path/to/artifacts
flavors:
  python_function:
    env:
      conda: conda.yaml
      virtualenv: python_env.yaml
    loader_module: mlflow.sklearn
    model_path: model.pkl
    predict_fn: predict
    python_version: 3.12.3
  sklearn:
    code: null
    pickled_model: model.pkl
    serialization_format: cloudpickle
    sklearn_version: 1.8.0
mlflow_version: 3.10.1
model_id: m-77fbac52087046ca95d7db71252da1da
model_size_bytes: 177230
model_uuid: m-77fbac52087046ca95d7db71252da1da
utc_time_created: '2026-03-20 19:40:55.665301'
```

## 모델 버전 상태 (Status Lifecycle)

```
create_model_version()
    ↓
PENDING_REGISTRATION ──── 아티팩트 업로드 중
    ↓
finalize_model_version()
    ↓
 ┌──┴──┐
 ▼     ▼
READY  FAILED_REGISTRATION
```

| 상태 | 의미 |
|------|------|
| `PENDING_REGISTRATION` | 버전 생성됨, MLflow가 아티팩트 업로드 중 |
| `READY` | 아티팩트 업로드 완료, 사용 가능 |
| `FAILED_REGISTRATION` | 업로드 실패 또는 모델 삭제 중 실패 |

### 정상/비정상 판단 기준

```
status=READY, artifact_count>0, finished_at≠NULL       → 정상
status=FAILED_REGISTRATION, status_message="..."        → 실패 (원인 확인)
status=PENDING_REGISTRATION, finished_at=NULL, 1시간 경과 → stuck (비정상)
```

## DB 테이블 구조

### catalog_registered_models

모델 등록 정보. 버전과 무관한 상위 엔티티.

| 컬럼 | 설명 |
|------|------|
| `name` | 3-part 모델 이름 (e.g. `argus.ml.iris_classifier`) |
| `urn` | `{name}.PROD.model` |
| `storage_type` | `local` (file://) 또는 `s3` |
| `storage_location` | 아티팩트 저장 경로 |
| `max_version_number` | 최대 버전 번호 (자동 증가) |
| `status` | `active` / `deleted` |

### catalog_model_versions

버전별 상태 및 아티팩트 정보.

| 컬럼 | 설명 |
|------|------|
| `version` | 버전 번호 (1, 2, 3, ...) |
| `status` | `PENDING_REGISTRATION` / `READY` / `FAILED_REGISTRATION` |
| `status_message` | 실패 사유 |
| `storage_location` | 버전별 아티팩트 경로 (`file:///.../{name}/versions/{N}/`) |
| `artifact_count` | finalize 시 파일 수 |
| `artifact_size` | finalize 시 총 바이트 |
| `finished_at` | finalize 완료 시각 (NULL이면 미완료) |
| `source` | MLflow 아티팩트 소스 URI |
| `run_id` | MLflow run ID |

### catalog_models

finalize 시 아티팩트 파일에서 파싱한 상세 메타데이터.

| 컬럼 | 소스 | 설명 |
|------|------|------|
| `predict_fn` | `MLmodel` → `flavors.python_function.predict_fn` | 예측 함수명 |
| `python_version` | `MLmodel` → `flavors.python_function.python_version` | Python 버전 |
| `serialization_format` | `MLmodel` → `flavors.sklearn.serialization_format` | 직렬화 형식 |
| `sklearn_version` | `MLmodel` → `flavors.sklearn.sklearn_version` | sklearn 버전 |
| `mlflow_version` | `MLmodel` → `mlflow_version` | MLflow 버전 |
| `mlflow_model_id` | `MLmodel` → `model_uuid` | 모델 UUID |
| `model_size_bytes` | `MLmodel` → `model_size_bytes` | 모델 크기 (bytes) |
| `utc_time_created` | `MLmodel` → `utc_time_created` | 생성 시각 (UTC 문자열) |
| `time_created` | 위 값을 로컬 timezone 변환 | 생성 시각 (datetime) |
| `requirements` | `requirements.txt` 파일 내용 | pip 의존성 |
| `conda` | `conda.yaml` 파일 내용 | Conda 환경 |
| `python_env` | `python_env.yaml` 파일 내용 | Python 환경 |
| `source_type` | 자동 설정 | `mlflow` / `huggingface` / `local` |

## API 엔드포인트

### Unity Catalog 호환 API

MLflow 클라이언트가 직접 호출하는 API. 사용자가 직접 호출할 필요 없음.

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/2.1/unity-catalog/models` | 모델 등록 |
| GET | `/api/2.1/unity-catalog/models` | 모델 목록 |
| GET | `/api/2.1/unity-catalog/models/{name}` | 모델 조회 |
| POST | `/api/2.1/unity-catalog/models/versions` | 버전 생성 |
| GET | `/api/2.1/unity-catalog/models/{name}/versions/{ver}` | 버전 조회 |
| PATCH | `/api/2.1/unity-catalog/models/{name}/versions/{ver}/finalize` | 버전 확정 |

### 네이티브 모델 API

웹 UI 및 관리 도구에서 사용하는 API.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/models` | 모델 목록 (검색, 필터, 페이지네이션) |
| POST | `/api/v1/models` | 모델 등록 |
| GET | `/api/v1/models/{name}` | 모델 조회 |
| PATCH | `/api/v1/models/{name}` | 모델 수정 |
| DELETE | `/api/v1/models/{name}` | 모델 삭제 (soft delete) |
| POST | `/api/v1/models/hard-delete` | 모델 영구 삭제 (DB + 디스크) |
| POST | `/api/v1/models/{name}/versions` | 버전 생성 |
| GET | `/api/v1/models/{name}/versions` | 버전 목록 |
| GET | `/api/v1/models/{name}/versions/{ver}` | 버전 조회 |
| PATCH | `/api/v1/models/{name}/versions/{ver}/finalize` | 버전 확정 |

### 목록 API 필터 파라미터

`GET /api/v1/models`:

| 파라미터 | 설명 |
|---------|------|
| `search` | 모델 이름 검색 (LIKE) |
| `status` | 최신 버전 상태 필터 (`READY`, `PENDING_REGISTRATION`, `FAILED_REGISTRATION`) |
| `python_version` | Python 버전 필터 (e.g. `3.12.3`) |
| `sklearn_version` | sklearn 버전 필터 (e.g. `1.8.0`) |
| `page` | 페이지 번호 (기본: 1) |
| `page_size` | 페이지 크기 (기본: 20, 최대: 100) |

## 지원 프레임워크

MLflow flavor를 통해 다양한 프레임워크를 지원합니다:

| 프레임워크 | MLflow Flavor | 사용 예시 |
|-----------|--------------|----------|
| scikit-learn | `mlflow.sklearn` | `mlflow.sklearn.log_model(model, "model")` |
| PyTorch | `mlflow.pytorch` | `mlflow.pytorch.log_model(model, "model")` |
| TensorFlow | `mlflow.tensorflow` | `mlflow.tensorflow.log_model(model, "model")` |
| XGBoost | `mlflow.xgboost` | `mlflow.xgboost.log_model(model, "model")` |
| LightGBM | `mlflow.lightgbm` | `mlflow.lightgbm.log_model(model, "model")` |
| HuggingFace | `mlflow.transformers` | `mlflow.transformers.log_model(pipe, "model")` |
| ONNX | `mlflow.onnx` | `mlflow.onnx.log_model(onnx_model, "model")` |
| SparkML | `mlflow.spark` | `mlflow.spark.log_model(model, "model")` |
| Custom | `mlflow.pyfunc` | `mlflow.pyfunc.log_model("model", python_model=MyModel())` |

## 전체 예제

```python
import mlflow
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. Registry 설정
mlflow.set_registry_uri("uc:http://catalog-server:4600")

# 2. 데이터 준비
X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# 3. 학습
model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
model.fit(X_train, y_train)
accuracy = accuracy_score(y_test, model.predict(X_test))
print(f"Accuracy: {accuracy:.4f}")

# 4. 모델 등록 (Catalog Server에 자동 저장)
mlflow.sklearn.log_model(
    model, "model",
    registered_model_name="argus.ml.iris_classifier",
)
print("Model registered successfully!")

# 5. 등록된 모델로 추론
loaded_model = mlflow.pyfunc.load_model("models:/argus.ml.iris_classifier/1")
predictions = loaded_model.predict(X_test)
print(f"Predictions: {predictions[:5]}")
```

## 소스 코드 구조

```
app/models/
├── router.py        ← 네이티브 모델 API (/api/v1/models)
├── schemas.py       ← Pydantic 요청/응답 모델
├── service.py       ← 모델/버전 CRUD + finalize + 메타데이터 파싱
├── models.py        ← RegisteredModel, ModelVersion, CatalogModel ORM
└── uc_compat.py     ← Unity Catalog OSS 호환 API (/api/2.1/unity-catalog)
```

## 확장 기능

### Stage 관리 (버전 승인 워크플로우)

모델 버전의 배포 단계를 관리합니다. 각 단계 전환 시 변경자와 시각이 기록됩니다.

```
NONE → STAGING → PRODUCTION → ARCHIVED
```

```bash
# 버전을 Staging으로 전환
PUT /api/v1/models/{name}/versions/{ver}/stage
{ "stage": "STAGING", "changed_by": "ml-team" }

# Production으로 승격
PUT /api/v1/models/{name}/versions/{ver}/stage
{ "stage": "PRODUCTION", "changed_by": "ops-team" }
```

| Stage | 의미 |
|-------|------|
| NONE | 초기 상태 (등록 직후) |
| STAGING | 검증 중 (테스트 환경 배포) |
| PRODUCTION | 운영 환경 배포 중 |
| ARCHIVED | 이전 버전 (보관) |

### 모델-데이터셋 리니지

모델이 어떤 데이터셋으로 학습되었는지 추적합니다. 원천 데이터 변경 시 모델 재학습 필요성을 파악하는 데 활용합니다.

```bash
# 학습 데이터 등록
POST /api/v1/models/{name}/lineage
{
  "dataset_id": 42,
  "model_version": 3,
  "relation_type": "TRAINING_DATA",
  "description": "2025년 고객 주문 데이터"
}

# 연결된 데이터셋 조회
GET /api/v1/models/{name}/lineage
→ [
    { "dataset_name": "ecommerce.orders", "platform_type": "mysql",
      "relation_type": "TRAINING_DATA", "model_version": 3 },
    { "dataset_name": "ecommerce.users", "platform_type": "mysql",
      "relation_type": "FEATURE_SOURCE", "model_version": 3 }
  ]
```

| relation_type | 의미 |
|--------------|------|
| TRAINING_DATA | 학습에 사용된 데이터 |
| EVALUATION_DATA | 평가/검증에 사용된 데이터 |
| FEATURE_SOURCE | 피처 추출 원천 |

### 모델 메트릭 비교

버전별 성능 지표를 기록하고 비교합니다.

```bash
# 메트릭 기록
POST /api/v1/models/{name}/versions/3/metrics
{ "metrics": { "accuracy": 0.91, "f1": 0.88, "latency_ms": 18, "model_size_mb": 5.2 } }

# 전체 버전 메트릭 비교
GET /api/v1/models/{name}/metrics
→ [
    { "version": 1, "metrics": { "accuracy": 0.82, "f1": 0.78, "latency_ms": 12 } },
    { "version": 2, "metrics": { "accuracy": 0.87, "f1": 0.83, "latency_ms": 15 } },
    { "version": 3, "metrics": { "accuracy": 0.91, "f1": 0.88, "latency_ms": 18 } }
  ]
```

### 모델 카드 (Model Card)

모델의 용도, 성능, 제한사항, 학습 데이터, 프레임워크, 라이선스 등 거버넌스 정보를 구조화하여 관리합니다.

```bash
# 모델 카드 작성/수정
PUT /api/v1/models/{name}/card
{
  "purpose": "고객 이탈 예측. CRM 시스템에서 실시간 이탈 위험 점수 제공.",
  "performance": "AUC 0.91, F1 0.88 (2025년 테스트셋 기준)",
  "limitations": "30일 미만 신규 고객 정확도 저하. 해외 고객 미학습.",
  "training_data": "ecommerce.orders + ecommerce.users (2025.01~2025.12, 1.5M rows)",
  "framework": "scikit-learn 1.3.0 / Python 3.11",
  "license": "Internal Use Only",
  "contact": "ml-team@company.com"
}

# 모델 카드 조회
GET /api/v1/models/{name}/card
```

| 필드 | 설명 |
|------|------|
| purpose | 모델의 용도와 비즈니스 목적 |
| performance | 정량적 성능 지표 (정확도, F1 등) |
| limitations | 알려진 제한사항과 편향 |
| training_data | 학습에 사용된 데이터 출처와 기간 |
| framework | 사용된 ML 프레임워크와 버전 |
| license | 사용 허가 범위 |
| contact | 모델 관리 담당자 연락처 |

## 확장 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| PUT | `/models/{name}/versions/{ver}/stage` | 버전 Stage 변경 |
| POST | `/models/{name}/lineage` | 모델-데이터셋 리니지 등록 |
| GET | `/models/{name}/lineage` | 모델-데이터셋 리니지 조회 |
| DELETE | `/models/{name}/lineage/{id}` | 리니지 삭제 |
| POST | `/models/{name}/versions/{ver}/metrics` | 메트릭 기록 |
| GET | `/models/{name}/metrics` | 전체 버전 메트릭 비교 |
| GET | `/models/{name}/card` | 모델 카드 조회 |
| PUT | `/models/{name}/card` | 모델 카드 작성/수정 |
