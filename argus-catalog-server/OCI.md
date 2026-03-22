# OCI-based Model Store

Argus Catalog Server의 S3/MinIO 기반 모델 아티팩트 저장소입니다.
OCI (Open Container Initiative) Manifest 형식으로 모델 메타데이터를 관리하여,
프레임워크에 무관하게 모델을 저장하고 배포할 수 있습니다.

## 아키텍처

```
┌──────────────────┐     ┌───────────────────────┐     ┌─────────────┐
│ Client            │     │  Catalog Server        │     │   MinIO     │
│                   │     │  (FastAPI :4600)        │     │  (S3 :9000) │
│ • argus-model CLI │────▶│                         │────▶│             │
│ • Python SDK      │     │  /api/v1/model-store/*  │     │  Bucket:    │
│ • Web UI          │     │                         │     │  model-     │
│ • MLflow client   │     │  ┌───────────────────┐  │     │  artifacts  │
│                   │     │  │ model_store.py     │  │     │             │
└──────────────────┘     │  │ (S3 ops + OCI)     │──┼────▶│  {name}/    │
                          │  └───────────────────┘  │     │   v{N}/     │
                          │  ┌───────────────────┐  │     │    files    │
                          │  │ DB (3 tables)      │  │     │             │
                          │  └───────────────────┘  │     └─────────────┘
                          └───────────────────────┘
```

## S3 저장 구조

```
model-artifacts/                    ← MinIO Bucket (config.yml: object_storage.bucket)
  {model_name}/
    v{version}/
      model.pkl                     ← 모델 가중치
      config.json                   ← 모델 설정 (HuggingFace 등)
      tokenizer.json                ← 토크나이저 (HuggingFace 등)
      MLmodel                       ← MLflow 메타데이터 (MLflow 모델인 경우)
      conda.yaml                    ← Conda 환경
      requirements.txt              ← pip 의존성
      python_env.yaml               ← Python 환경
      manifest.json                 ← OCI Manifest (finalize 시 자동 생성)
```

## 설정

`config.yml`:

```yaml
object_storage:
  endpoint: http://localhost:9000   # MinIO 또는 S3 엔드포인트
  access_key: minioadmin
  secret_key: minioadmin
  region: us-east-1
  use_ssl: false
  bucket: model-artifacts           # 모델 아티팩트 버킷
  presigned_url_expiry: 3600        # Presigned URL 만료 시간 (초)
```

`config.properties`:

```properties
os.endpoint=http://localhost:9000
os.access_key=minioadmin
os.secret_key=minioadmin
os.bucket=model-artifacts
```

## API 엔드포인트

Base path: `/api/v1/model-store`

### 업로드

| Method | Path | 설명 |
|--------|------|------|
| POST | `/{name}/versions/{ver}/upload` | 파일 직접 업로드 (multipart/form-data) |
| POST | `/{name}/versions/{ver}/upload-url` | Presigned PUT URL 발급 (대형 파일용) |

**직접 업로드 예시:**

```bash
curl -X POST "http://localhost:4600/api/v1/model-store/argus.ml.bert/versions/1/upload" \
  -F "file=@model.pkl"
```

**Presigned URL 업로드 (대형 파일):**

```bash
# 1. URL 발급
curl -X POST "http://localhost:4600/api/v1/model-store/argus.ml.bert/versions/1/upload-url" \
  -H "Content-Type: application/json" \
  -d '{"filename": "model.safetensors"}'
# → {"url": "http://minio:9000/model-artifacts/...?X-Amz-Signature=...", "key": "...", "expires_in": 3600}

# 2. MinIO에 직접 PUT (서버 우회)
curl -X PUT "<presigned_url>" --upload-file model.safetensors
```

### 다운로드

| Method | Path | 설명 |
|--------|------|------|
| GET | `/{name}/versions/{ver}/download-url?filename=X` | 단일 파일 Presigned GET URL |
| GET | `/{name}/versions/{ver}/download-urls` | 전체 파일 Presigned URL 일괄 발급 |

### 파일 조회

| Method | Path | 설명 |
|--------|------|------|
| GET | `/{name}/versions/{ver}/files` | 파일 목록 (filename, size, last_modified) |
| GET | `/{name}/versions/{ver}/manifest` | OCI manifest.json 조회 |

### Finalize

| Method | Path | 설명 |
|--------|------|------|
| POST | `/{name}/versions/{ver}/finalize` | 파일 스캔 + OCI manifest 생성 |

Finalize 시 수행되는 작업:
1. S3의 모든 파일을 스캔하여 파일 수/총 크기 집계
2. 각 파일의 SHA256 digest 계산
3. OCI Image Manifest 형식의 `manifest.json` 생성 및 S3 저장
4. 응답에 manifest 포함

### Import

| Method | Path | 설명 |
|--------|------|------|
| POST | `/import/huggingface` | HuggingFace Hub에서 모델 다운로드 → S3 저장 |
| POST | `/import/local` | 서버 로컬 디렉토리에서 S3로 import (airgap) |

## OCI Manifest

Finalize 시 자동 생성되는 [OCI Image Manifest](https://github.com/opencontainers/image-spec/blob/main/manifest.md) 형식:

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.argus.model.config.v1+json",
    "digest": "sha256:abc123...",
    "size": 512
  },
  "layers": [
    {
      "mediaType": "application/vnd.argus.model.weights",
      "digest": "sha256:def456...",
      "size": 177230,
      "annotations": {
        "org.opencontainers.image.title": "model.pkl"
      }
    },
    {
      "mediaType": "application/vnd.argus.model.mlflow.requirements+text",
      "digest": "sha256:789abc...",
      "size": 124,
      "annotations": {
        "org.opencontainers.image.title": "requirements.txt"
      }
    }
  ],
  "annotations": {
    "org.opencontainers.image.created": "2026-03-22T10:00:00+00:00",
    "ai.argus.model.name": "argus.ml.iris_classifier",
    "ai.argus.model.version": "1",
    "ai.argus.model.source": "huggingface:bert-base-uncased"
  }
}
```

### Media Type 매핑

| 파일 | Media Type |
|------|-----------|
| `model.pkl` | `application/vnd.argus.model.weights` |
| `model.safetensors` | `application/vnd.argus.model.weights.safetensors` |
| `*.pt` | `application/vnd.argus.model.weights.pytorch` |
| `*.onnx` | `application/vnd.argus.model.weights.onnx` |
| `MLmodel` | `application/vnd.argus.model.mlflow.mlmodel+yaml` |
| `conda.yaml` | `application/vnd.argus.model.mlflow.conda+yaml` |
| `python_env.yaml` | `application/vnd.argus.model.mlflow.python-env+yaml` |
| `requirements.txt` | `application/vnd.argus.model.mlflow.requirements+text` |
| `config.json` | `application/vnd.argus.model.config+json` |
| `tokenizer.json` | `application/vnd.argus.model.tokenizer+json` |
| `tokenizer_config.json` | `application/vnd.argus.model.tokenizer-config+json` |
| 기타 | `application/octet-stream` |

### Content-addressable Storage

모든 파일은 SHA256 digest로 식별됩니다:
- 업로드 시 digest를 계산하여 S3 object metadata에 저장
- manifest.json의 `layers[].digest`에 기록
- 동일한 파일의 무결성 검증에 사용

## HuggingFace Import

### 온라인 환경

```bash
# CLI
argus-model import-hf bert-base-uncased argus.ml.bert --server http://catalog:4600

# Python SDK
from argus_catalog_sdk import ModelClient
client = ModelClient("http://catalog:4600")
client.import_huggingface("bert-base-uncased", "argus.ml.bert")

# REST API
curl -X POST "http://catalog:4600/api/v1/model-store/import/huggingface" \
  -H "Content-Type: application/json" \
  -d '{"hf_model_id": "bert-base-uncased", "model_name": "argus.ml.bert"}'
```

처리 흐름:
1. `huggingface_hub.snapshot_download()`로 임시 디렉토리에 다운로드
2. 모든 파일을 S3에 업로드 (`model_name/v{N}/` 하위)
3. `config.json`에서 모델 메타데이터 추출 (model_type, architectures 등)
4. OCI manifest.json 생성 + S3 저장
5. DB 기록 (catalog_registered_models, catalog_model_versions, catalog_models)

### Airgap 환경

인터넷이 없는 폐쇄망에서는 2단계로 진행합니다:

```bash
# 1단계: 인터넷 환경에서 모델 다운로드
argus-model import-hf bert-base-uncased argus.ml.bert --server http://online-catalog:4600
argus-model pull argus.ml.bert 1 /usb/bert-export/

# 2단계: Airgap 환경에서 import (USB 등으로 파일 전송 후)
argus-model import-local /usb/bert-export/ argus.ml.bert --server http://airgap-catalog:4600
```

또는 서버 API 직접 호출:

```bash
# 서버가 접근 가능한 경로에 파일을 복사한 후
curl -X POST "http://airgap-catalog:4600/api/v1/model-store/import/local" \
  -H "Content-Type: application/json" \
  -d '{"local_dir": "/data/transferred/bert", "model_name": "argus.ml.bert"}'
```

## DB 스키마

### catalog_registered_models (OCI 관련 컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `storage_type` | VARCHAR(20) | `local` (file://) 또는 `s3` (s3://) |
| `bucket_name` | VARCHAR(255) | S3 bucket 이름 (storage_type=s3일 때) |

### catalog_models (OCI 관련 컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `manifest` | TEXT | OCI manifest.json 원본 |
| `config` | TEXT | OCI config.json 원본 |
| `content_digest` | VARCHAR(100) | manifest의 content digest |
| `source_type` | VARCHAR(50) | 모델 출처: `mlflow`, `huggingface`, `local`, `oras` |

## Python SDK

설치:

```bash
pip install argus-catalog-sdk
```

사용:

```python
from argus_catalog_sdk import ModelClient

client = ModelClient("http://catalog-server:4600")

# 모델 목록
models = client.list_models(search="bert")

# HuggingFace 임포트
result = client.import_huggingface("bert-base-uncased", "argus.ml.bert")
print(f"Imported v{result['version']}: {result['file_count']} files")

# 모델 Pull (Presigned URL로 다운로드)
files = client.pull("argus.ml.bert", version=1, dest="/tmp/model")

# 로컬 → S3 Push
client.push("/path/to/my-model", "argus.ml.custom", description="Custom model")

# 파일 목록
client.list_files("argus.ml.bert", version=1)

# OCI Manifest 조회
manifest = client.get_manifest("argus.ml.bert", version=1)

# Presigned URL로 직접 다운로드
urls = client.get_download_urls("argus.ml.bert", version=1)
# → {"files": {"model.safetensors": "https://minio/...?sig=...", ...}}
```

## CLI

```bash
# 모델 목록
argus-model list --server http://catalog:4600

# HuggingFace 임포트
argus-model import-hf bert-base-uncased argus.ml.bert

# 모델 Pull
argus-model pull argus.ml.bert 1 /tmp/model

# 로컬 Push
argus-model push /path/to/model argus.ml.custom --description "My model"

# Airgap Import (서버 로컬 디렉토리)
argus-model import-local /data/bert argus.ml.bert

# 파일 목록
argus-model files argus.ml.bert 1

# OCI Manifest 조회
argus-model manifest argus.ml.bert 1

# 모델 삭제
argus-model delete argus.ml.bert argus.ml.old-model
```

## 소스 코드 구조

```
app/
├── core/
│   └── s3.py                  ← S3 클라이언트 (aioboto3, MinIO 호환)
└── models/
    ├── model_store.py         ← S3 업로드/다운로드, OCI manifest, HF import
    └── store_router.py        ← REST API 엔드포인트
```
