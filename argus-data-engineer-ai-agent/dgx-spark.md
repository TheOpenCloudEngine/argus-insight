# DGX Spark 운영 가이드 — Data Engineer AI Agent

DGX Spark 2대 클러스터에서 LLM 추론 서버(Ollama, vLLM)를 운영하는 방법을 정리합니다.

---

## 1. 하드웨어 사양

### 단일 DGX Spark

| 항목 | 사양 |
|------|------|
| GPU | NVIDIA GB10 (Blackwell, sm_121) |
| CPU | ARM Cortex-X925 10코어 (aarch64) |
| 통합 메모리 | 128GB (GPU+CPU 공유, 가용 ~119GB) |
| 스토리지 | NVMe 2TB |
| NIC | ConnectX-7 x 4포트 (200GbE, RoCE v2) |
| OS | Ubuntu 24.04 LTS (커널 6.14.0-nvidia) |
| CUDA | 13.0, Driver 580.95.05 |
| NCCL | 2.29.3 |

### 2대 클러스터 구성

```
┌─────────────────────┐         ConnectX-7 200GbE        ┌─────────────────────┐
│   DGX Spark #1      │◄───── (RoCE v2, MTU 9000) ──────►│   DGX Spark #2      │
│   10.0.1.47         │         192.168.200.1/24          │   10.0.1.48         │
│   192.168.200.1     │◄────────────────────────────────►│   192.168.200.2     │
│                     │         Latency: ~0.37ms          │                     │
│   GB10 (128GB)      │         Bandwidth: 200Gbps        │   GB10 (128GB)      │
└─────────────────────┘                                   └─────────────────────┘
```

| 항목 | Spark #1 (10.0.1.47) | Spark #2 (10.0.1.48) |
|------|---------------------|---------------------|
| 역할 | Head (Ray) | Worker (Ray) |
| 관리 IP | 10.0.1.47 | 10.0.1.48 |
| 클러스터 IP | 192.168.200.1 | 192.168.200.2 |
| ConnectX-7 인터페이스 | enP2p1s0f1np1 | enP2p1s0f1np1 |
| MTU | 9000 (Jumbo Frame) | 9000 (Jumbo Frame) |
| RDMA | ACTIVE (RoCE v2) | ACTIVE (RoCE v2) |

---

## 2. Ollama vs vLLM 비교

### 기능 비교

| 항목 | Ollama | vLLM |
|------|--------|------|
| 설치 난이도 | 매우 쉬움 (`curl \| sh`) | 보통 (NGC 컨테이너 권장) |
| 모델 관리 | `ollama pull` 한 줄 | HuggingFace 직접 다운로드 |
| API 호환성 | 자체 API + OpenAI 호환 | OpenAI 호환 (`/v1/chat/completions`) |
| 멀티노드 (2대 합침) | **미지원** | **지원** (Ray + Tensor Parallelism) |
| 동시 요청 처리 | 제한적 | **우수** (continuous batching) |
| 양자화 지원 | GGUF (Q4, Q8 등) | AWQ, GPTQ, FP8 |
| GPU 메모리 관리 | 자동 | PagedAttention (효율적) |
| Tool-use 지원 | 모델 의존 | 모델 의존 |
| 프로덕션 안정성 | 개발/소규모 | **프로덕션 권장** |

### 성능 비교 (DGX Spark 단일 노드, Qwen2.5:72b)

| 지표 | Ollama (Q4_K_M) | vLLM (FP16) |
|------|----------------|-------------|
| 프롬프트 처리 (prompt eval) | ~210 tok/s | ~300-400 tok/s |
| 토큰 생성 (eval) | ~4.5-5.3 tok/s | ~8-12 tok/s |
| 첫 토큰 지연 (TTFT) | ~300ms | ~200ms |
| 메모리 사용량 | ~47GB (Q4) | ~144GB (FP16), ~47GB (AWQ) |
| 동시 요청 | 1-2개 | **10+ (continuous batching)** |
| Cold start | ~18초 | ~30-60초 |

> **참고**: Ollama는 GGUF 양자화(Q4_K_M) 모델을 사용하고, vLLM은 기본적으로 FP16을 사용합니다.
> DGX Spark의 128GB 통합 메모리에서는 FP16도 로드 가능하지만, 양자화 모델 대비 메모리를 3배 더 사용합니다.

### 실측 벤치마크 (Ollama, DGX Spark #2)

```
모델: qwen2.5:72b (GGUF Q4_K_M, 47GB)

[Cold Start - 모델 최초 로드]
  total duration:       19.6초
  load duration:        18.0초
  prompt eval:          129.6 tok/s (37 tokens)
  token generation:     5.3 tok/s (7 tokens)

[Warm - 모델 로드된 상태, 짧은 응답]
  total duration:       4.8초
  load duration:        0.08초
  prompt eval:          218.5 tok/s (62 tokens)
  token generation:     4.8 tok/s (21 tokens)

[Warm - 긴 코드 생성 (PySpark ETL)]
  total duration:       68.1초
  prompt eval:          207.8 tok/s (59 tokens)
  token generation:     4.5 tok/s (307 tokens)
```

### 언제 무엇을 사용하는가

| 시나리오 | 권장 | 이유 |
|---------|------|------|
| 개발/테스트 단계 | **Ollama** | 설치 1분, 모델 관리 간편 |
| DE Agent 프로덕션 (단일 노드) | **Ollama** 또는 **vLLM** | 동시 요청 적으면 Ollama로 충분 |
| DE Agent 프로덕션 (동시 다수 사용자) | **vLLM** | continuous batching으로 높은 throughput |
| 120B+ 대형 모델 (2대 합침) | **vLLM** | 멀티노드 Tensor Parallelism 유일 지원 |
| 모델 빠른 교체/실험 | **Ollama** | `ollama pull/run` 한 줄로 전환 |

---

## 3. Ollama 설정

### 설치

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 외부 접근 허용

```bash
# /etc/systemd/system/ollama.service의 [Service] 섹션에 추가
Environment="OLLAMA_HOST=0.0.0.0"

# 적용
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 모델 설치 및 실행

```bash
ollama pull qwen2.5:72b    # 47GB 다운로드
ollama pull qwen2.5:7b     # 4.7GB (경량)

ollama run qwen2.5:72b "테스트 프롬프트"          # CLI 실행
ollama run qwen2.5:72b "프롬프트" --verbose       # 성능 지표 포함
```

### API 호출

```bash
# 모델 목록
curl http://10.0.1.48:11434/api/tags

# 채팅
curl http://10.0.1.48:11434/api/chat -d '{
  "model": "qwen2.5:72b",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false
}'
```

### DE Agent config.yml 설정 (Ollama)

```yaml
llm:
  provider: "ollama"
  model: "qwen2.5:72b"
  api_key: ""
  api_url: "http://10.0.1.48:11434"
  temperature: 0.3
  max_tokens: 4096
```

---

## 4. vLLM 설치

DGX Spark(aarch64 + CUDA 13 + Blackwell sm_121)는 일반적인 x86 서버와 다릅니다.
PyPI의 `pip install vllm`은 **동작하지 않습니다**. 아래 3가지 방법 중 하나를 사용해야 합니다.

### 방법 A: NGC 컨테이너 (권장)

NVIDIA가 DGX Spark용으로 검증한 공식 컨테이너입니다. 가장 안정적입니다.

```bash
# 전제 조건: Docker + NVIDIA Container Toolkit 설치 확인
docker --version                        # Docker 28.x+
nvidia-container-cli --version          # NVIDIA Container Toolkit 1.18+

# vLLM NGC 컨테이너 pull (양쪽 노드 모두)
sudo docker pull nvcr.io/nvidia/vllm:26.02-py3    # ~14.7GB

# 설치 확인
sudo docker run --rm --gpus all nvcr.io/nvidia/vllm:26.02-py3 \
    python -c "import vllm; print(f'vLLM {vllm.__version__}')"
```

> **NGC 태그 확인**: [catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm)
> 에서 최신 태그를 확인하세요. `26.02-py3`에는 vLLM 0.13.0, CUDA 13.1.1, NCCL 2.29, FlashInfer 0.6.0이 포함됩니다.

### 방법 B: Nightly Wheel (Bare-metal)

Docker 없이 직접 설치해야 하는 경우입니다. CUDA 13 + aarch64 전용 nightly wheel을 사용합니다.

```bash
# Python 3.12 가상환경 생성
python3.12 -m venv /opt/vllm-env
source /opt/vllm-env/bin/activate

# PyTorch (CUDA 13.0 전용)
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu130

# vLLM (CUDA 13.0 nightly)
pip install -U vllm \
    --extra-index-url https://wheels.vllm.ai/nightly/cu130

# 필수 환경 변수 (~/.bashrc에 추가)
export TORCH_CUDA_ARCH_LIST="12.1a"
export PATH="/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"
export TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas
```

> **주의**: `UserWarning: sm_120 used instead of sm_121` 경고는 무시해도 됩니다.
> sm_120과 sm_121은 바이너리 호환됩니다. `flash-attn`은 별도 설치하지 마세요 — vLLM이 FlashInfer를 내장합니다.

### 방법 C: 커뮤니티 Docker (spark-vllm-docker)

DGX Spark 전용으로 만들어진 커뮤니티 프로젝트입니다. 2대 구성을 자동 처리합니다.

```bash
git clone https://github.com/eugr/spark-vllm-docker.git
cd spark-vllm-docker
./build-and-copy.sh -c    # 이미지 빌드 + 두 번째 노드로 복사
```

### 설치 방법 비교

| 방법 | 지원 수준 | 사용 시 |
|------|----------|--------|
| **A. NGC 컨테이너** | 공식 (NVIDIA 검증) | 프로덕션, 멀티노드 |
| **B. Nightly wheel** | 커뮤니티 | Docker 못 쓰는 환경 |
| **C. spark-vllm-docker** | 커뮤니티 | 빠른 2대 구성 |
| ~~pip install vllm~~ | **미지원** | ~~사용 불가 (CUDA 13/aarch64)~~ |

---

## 5. vLLM 사용법

### 5.1 단일 노드 서빙

하나의 DGX Spark에서 모델을 서빙합니다. 128GB 통합 메모리에 들어가는 모델에 적합합니다.

#### Docker 실행

```bash
sudo docker run -d --name vllm-single \
    --gpus all \
    --network host \
    --ipc host \
    -v /root/.cache/huggingface:/root/.cache/huggingface \
    -e HF_HOME=/root/.cache/huggingface \
    nvcr.io/nvidia/vllm:26.02-py3 \
    vllm serve Qwen/Qwen2.5-72B-Instruct \
        --host 0.0.0.0 \
        --port 8000 \
        --gpu-memory-utilization 0.85 \
        --trust-remote-code
```

#### Bare-metal 실행

```bash
source /opt/vllm-env/bin/activate

vllm serve Qwen/Qwen2.5-72B-Instruct \
    --host 0.0.0.0 \
    --port 8000 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code
```

#### 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|-------|------|
| `--host` | `localhost` | 수신 주소 (`0.0.0.0`으로 외부 허용) |
| `--port` | `8000` | API 포트 |
| `--gpu-memory-utilization` | `0.9` | GPU 메모리 사용 비율 (KV cache 포함) |
| `--max-model-len` | 모델 기본 | 최대 컨텍스트 길이 (메모리 절약 시 줄임) |
| `--trust-remote-code` | `false` | HuggingFace 커스텀 코드 허용 |
| `--quantization` | `none` | 양자화 방식 (`awq`, `gptq`, `fp8`) |
| `--dtype` | `auto` | 데이터 타입 (`float16`, `bfloat16`, `auto`) |
| `--enable-chunked-prefill` | `false` | 큰 프롬프트 청크 처리 |
| `--disable-log-requests` | `false` | 요청 로그 비활성화 (프로덕션) |
| `--api-key` | `none` | API 인증키 설정 |

### 5.2 멀티노드 서빙 (Ray 클러스터)

2대의 DGX Spark를 하나처럼 사용합니다. 128GB를 초과하는 대형 모델에 필요합니다.

#### Step 1: Head Node 시작 (10.0.1.47)

```bash
sudo docker run -d --name vllm-head \
    --gpus all \
    --network host \
    --ipc host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    -v /root/.cache/huggingface:/root/.cache/huggingface \
    -e VLLM_HOST_IP=192.168.200.1 \
    -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 \
    -e NCCL_IB_HCA=mlx5 \
    -e NCCL_IB_DISABLE=0 \
    -e NCCL_IB_ROCE_VERSION_NUM=2 \
    -e RAY_memory_monitor_refresh_ms=0 \
    -e HF_HOME=/root/.cache/huggingface \
    nvcr.io/nvidia/vllm:26.02-py3 \
    bash -c "ray start --head --node-ip-address=192.168.200.1 --port=6379 \
             --dashboard-host=0.0.0.0 --dashboard-port=8265 && sleep infinity"
```

#### Step 2: Worker Node 시작 (10.0.1.48)

```bash
sudo docker run -d --name vllm-worker \
    --gpus all \
    --network host \
    --ipc host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    -v /root/.cache/huggingface:/root/.cache/huggingface \
    -e VLLM_HOST_IP=192.168.200.2 \
    -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 \
    -e NCCL_IB_HCA=mlx5 \
    -e NCCL_IB_DISABLE=0 \
    -e NCCL_IB_ROCE_VERSION_NUM=2 \
    -e RAY_memory_monitor_refresh_ms=0 \
    -e HF_HOME=/root/.cache/huggingface \
    nvcr.io/nvidia/vllm:26.02-py3 \
    bash -c "ray start --address=192.168.200.1:6379 \
             --node-ip-address=192.168.200.2 && sleep infinity"
```

#### Step 3: 클러스터 확인

```bash
# Ray 클러스터 상태 확인
sudo docker exec vllm-head ray status
# 예상 출력: 2 node(s), 2 GPU(s)

# Ray 대시보드: http://10.0.1.47:8265
```

#### Step 4: 대형 모델 서빙 (Tensor Parallelism)

```bash
sudo docker exec vllm-head bash -c "
    export VLLM_HOST_IP=192.168.200.1
    export NCCL_SOCKET_IFNAME=enP2p1s0f1np1
    export NCCL_IB_HCA=mlx5
    export NCCL_IB_DISABLE=0
    export NCCL_IB_ROCE_VERSION_NUM=2
    vllm serve meta-llama/Llama-3.3-70B-Instruct \
        --tensor-parallel-size 2 \
        --distributed-executor-backend ray \
        --host 0.0.0.0 \
        --port 8000 \
        --gpu-memory-utilization 0.85 \
        --trust-remote-code
"
```

> **Tensor Parallelism vs Pipeline Parallelism**:
> - `--tensor-parallel-size 2`: 각 레이어를 2개 GPU에 분할. 고대역폭 연결(ConnectX-7 200GbE)에 적합.
> - `--pipeline-parallel-size 2`: 레이어를 순차적으로 나눔. 저대역폭 연결에 적합.
> - DGX Spark 2대에서는 **tensor parallelism** 권장 (200GbE RoCE 활용).

#### Step 5: 종료

```bash
# 서빙 중인 모델 중지 (head 컨테이너 내부에서 Ctrl+C)
# 컨테이너 정리
sudo docker rm -f vllm-worker    # Worker 먼저
sudo docker rm -f vllm-head      # Head 나중
```

### 5.3 API 사용법 (OpenAI 호환)

vLLM은 OpenAI API 형식과 완전 호환됩니다. 기존 OpenAI 클라이언트를 그대로 사용할 수 있습니다.

#### API 엔드포인트

| 엔드포인트 | Method | 설명 |
|-----------|--------|------|
| `/v1/models` | GET | 로드된 모델 목록 |
| `/v1/chat/completions` | POST | 채팅 (OpenAI chat 형식) |
| `/v1/completions` | POST | 텍스트 완성 (legacy) |
| `/v1/embeddings` | POST | 임베딩 |
| `/health` | GET | 헬스체크 |

#### curl 예시

```bash
# 헬스체크
curl http://10.0.1.47:8000/health

# 모델 목록
curl http://10.0.1.47:8000/v1/models

# 채팅 (단일 응답)
curl http://10.0.1.47:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful data engineer assistant."},
            {"role": "user", "content": "sakila.film 테이블의 평균 rental_rate를 구하는 SQL을 작성해줘"}
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }'

# 스트리밍 응답
curl http://10.0.1.47:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": true
    }'

# Tool-use (function calling)
curl http://10.0.1.47:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "messages": [{"role": "user", "content": "sakila.film 데이터를 미리보기 해줘"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "preview_data",
                    "description": "Preview sample data from a dataset",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dataset_id": {"type": "integer", "description": "Dataset ID"},
                            "limit": {"type": "integer", "description": "Number of rows"}
                        },
                        "required": ["dataset_id"]
                    }
                }
            }
        ]
    }'
```

#### Python 클라이언트 (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://10.0.1.47:8000/v1",
    api_key="not-needed"    # vLLM은 기본적으로 인증 없음
)

# 채팅
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-72B-Instruct",
    messages=[
        {"role": "system", "content": "You are a data engineer assistant."},
        {"role": "user", "content": "MySQL에서 PostgreSQL로 ETL 코드를 작성해줘"}
    ],
    temperature=0.3,
    max_tokens=2048
)

print(response.choices[0].message.content)
```

#### Python 클라이언트 (httpx — DE Agent 방식)

```python
import httpx

async def chat_with_vllm(prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            "http://10.0.1.47:8000/v1/chat/completions",
            json={
                "model": "Qwen/Qwen2.5-72B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )
        return resp.json()
```

### 5.4 모델 다운로드

vLLM은 HuggingFace에서 모델을 자동 다운로드합니다. 첫 실행 시 시간이 오래 걸릴 수 있습니다.

```bash
# 사전 다운로드 (컨테이너 내부)
sudo docker exec -it vllm-head bash -c "
    pip install huggingface_hub
    huggingface-cli download Qwen/Qwen2.5-72B-Instruct
"

# 또는 호스트에서 직접
pip install huggingface_hub
huggingface-cli download Qwen/Qwen2.5-72B-Instruct \
    --local-dir /root/.cache/huggingface/hub/models--Qwen--Qwen2.5-72B-Instruct

# Gated 모델 (Llama 등)은 토큰 필요
huggingface-cli login    # HF 토큰 입력
huggingface-cli download meta-llama/Llama-3.3-70B-Instruct
```

### 5.5 DE Agent config.yml 설정

```yaml
# vLLM 사용 시 (OpenAI 호환 provider)
llm:
  provider: "openai"
  model: "Qwen/Qwen2.5-72B-Instruct"
  api_key: "not-needed"
  api_url: "http://10.0.1.47:8000/v1"
  temperature: 0.3
  max_tokens: 4096
```

### 5.6 NCCL 환경 변수 레퍼런스

| 변수 | 값 | 설명 |
|------|-----|------|
| `NCCL_SOCKET_IFNAME` | `enP2p1s0f1np1` | ConnectX-7 인터페이스 |
| `NCCL_IB_HCA` | `mlx5` | Mellanox RDMA 디바이스 |
| `NCCL_IB_DISABLE` | `0` | IB/RoCE 활성화 |
| `NCCL_IB_ROCE_VERSION_NUM` | `2` | RoCE v2 사용 |
| `VLLM_HOST_IP` | 노드별 IP | 노드마다 다르게 설정 |
| `RAY_memory_monitor_refresh_ms` | `0` | 통합 메모리 OOM 방지 |
| `NCCL_DEBUG` | `INFO` | 디버그 로그 (문제 진단 시만 사용) |
| `NCCL_DEBUG_SUBSYS` | `ALL` | 디버그 서브시스템 (문제 진단 시만 사용) |

---

## 6. 운영 스크립트

클러스터 관리 스크립트는 양쪽 노드의 `/opt/vllm-cluster/`에 배치되어 있습니다.

| 노드 | 스크립트 | 설명 |
|------|---------|------|
| 10.0.1.47 | `/opt/vllm-cluster/start-head.sh` | Ray head + vLLM 컨테이너 시작 |
| 10.0.1.48 | `/opt/vllm-cluster/start-worker.sh` | Ray worker + vLLM 컨테이너 시작 |
| 10.0.1.47 | `/opt/vllm-cluster/serve-model.sh` | 모델 서빙 (단일/멀티노드) |

### 사용법

```bash
# 1) 클러스터 시작 (Head 먼저, Worker 나중)
ssh root@10.0.1.47 '/opt/vllm-cluster/start-head.sh'
ssh root@10.0.1.48 '/opt/vllm-cluster/start-worker.sh'

# 2) 모델 서빙
# 큰 모델 (2대 합침, TP=2)
ssh root@10.0.1.47 '/opt/vllm-cluster/serve-model.sh meta-llama/Llama-3.3-70B-Instruct 2 8000'

# 작은 모델 (1대만, TP=1)
ssh root@10.0.1.47 '/opt/vllm-cluster/serve-model.sh Qwen/Qwen2.5-7B-Instruct 1 8000'

# 3) 종료
ssh root@10.0.1.48 'docker rm -f vllm-worker'
ssh root@10.0.1.47 'docker rm -f vllm-head'
```

---

## 7. 트러블슈팅

### 진단 명령어 모음

문제 발생 시 아래 명령어로 먼저 상태를 확인합니다.

```bash
# GPU 상태
nvidia-smi                                          # GPU 인식, 메모리, 프로세스
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv   # 간단 요약

# 네트워크 상태
ip addr show enP2p1s0f1np1                          # ConnectX-7 IP 확인
rdma link show                                      # RDMA/RoCE 상태
ethtool enP2p1s0f1np1 | grep Speed                  # 링크 속도 (200Gbps 기대)
ping -M do -s 8972 -c 3 192.168.200.X               # Jumbo frame 연결 테스트

# Ollama 상태
systemctl status ollama                             # 서비스 상태
journalctl -u ollama -f                             # 실시간 로그
ollama list                                         # 설치된 모델
ollama ps                                           # 현재 로드된 모델
curl http://localhost:11434/api/version              # API 응답 확인

# vLLM / Docker 상태
docker ps                                           # 실행 중인 컨테이너
docker logs vllm-head --tail 50                     # vLLM 로그
docker exec vllm-head ray status                    # Ray 클러스터 상태
curl http://localhost:8000/health                    # vLLM 헬스체크

# 시스템 리소스
free -h                                             # 메모리 사용량
df -h /                                             # 디스크 공간
htop                                                # CPU/메모리 모니터링
```

---

### 이슈 1: DGX Spark 2대 연결 시 GPU가 1개만 인식됨

**증상**: `nvidia-smi`에 GPU 1개만 표시, NVLink 정보 없음, `nvidia-smi nvlink -s` 출력 없음

**원인**: DGX Spark는 NVLink가 아닌 ConnectX-7(RoCE)로 2대를 연결합니다. 각 노드의 GPU는 독립적으로 인식되며, 하나의 통합 GPU로 보이지 않습니다. 이는 DGX A100/H100과 다른 DGX Spark만의 특성입니다.

**해결**: 이것은 **정상 동작**입니다. 각 노드에서 `nvidia-smi`는 항상 1개의 GPU만 표시됩니다.

2대를 하나처럼 사용하려면 소프트웨어 레벨에서 분산 처리를 설정해야 합니다:
- vLLM + Ray 클러스터 + `--tensor-parallel-size 2` (5장 참조)
- 또는 각 노드에서 독립적으로 Ollama를 실행하고 로드밸런싱

**확인 방법**:

```bash
# 양쪽 노드에서 각각 실행
nvidia-smi -L
# 예상: GPU 0: NVIDIA GB10 (UUID: GPU-xxxx)  ← 1개만 표시되는 것이 정상

# ConnectX-7 링크 확인 (2대가 물리적으로 연결되었는지)
rdma link show | grep ACTIVE
# 예상: roceP2p1s0f1/1 state ACTIVE  ← 이 포트가 2대 연결용
```

---

### 이슈 2: ConnectX-7 직접 연결 포트에 IP 미설정

**증상**: `enP2p1s0f1np1` 인터페이스가 UP이지만 IPv4 주소 없음, 노드 간 `ping` 불가

**원인**: DGX Spark 출하 시 ConnectX-7 포트에 IP가 자동 설정되지 않음

**해결**:

```bash
# 10.0.1.47 (Head)
sudo nmcli con add type ethernet ifname enP2p1s0f1np1 \
    con-name enP2p1s0f1np1 ipv4.addresses 192.168.200.1/24 \
    ipv4.method manual 802-3-ethernet.mtu 9000
sudo nmcli con up enP2p1s0f1np1

# 10.0.1.48 (Worker)
sudo nmcli con add type ethernet ifname enP2p1s0f1np1 \
    con-name enP2p1s0f1np1 ipv4.addresses 192.168.200.2/24 \
    ipv4.method manual 802-3-ethernet.mtu 9000
sudo nmcli con up enP2p1s0f1np1
```

**검증**:

```bash
# 기본 연결
ping -c 3 192.168.200.1

# Jumbo frame (MTU 9000)
ping -M do -s 8972 -c 3 192.168.200.1
# 8980 bytes ... time=0.37ms 이면 정상

# RDMA 상태
rdma link show | grep roceP2p1s0f1
# state ACTIVE physical_state LINK_UP 이면 정상
```

> **인터페이스 이름 찾기**: `ip link show | grep enP` 로 ConnectX-7 인터페이스를 확인하세요.
> DGX Spark에서는 보통 `enP2p1s0f1np1`이 노드 간 직접 연결 포트입니다.

---

### 이슈 3: Ollama 외부 접근 불가 (Connection Refused)

**증상**: 다른 머신에서 `curl http://10.0.1.48:11434` 시 `Connection refused`

**원인**: Ollama 기본 설정은 `127.0.0.1:11434`만 수신 (localhost only)

**해결**:

```bash
# systemd 서비스 파일 수정
sudo systemctl edit ollama
# 또는 직접 편집:
sudo vi /etc/systemd/system/ollama.service

# [Service] 섹션에 추가:
Environment="OLLAMA_HOST=0.0.0.0"

# 적용
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**검증**:

```bash
# 로컬 확인
curl http://localhost:11434/api/version

# 외부 확인 (다른 머신에서)
curl http://10.0.1.48:11434/api/version
# {"version":"0.13.0"} 이면 정상

# 수신 포트 확인
ss -tlnp | grep 11434
# 0.0.0.0:11434 이면 정상, 127.0.0.1:11434 이면 외부 접근 불가
```

---

### 이슈 4: Ollama 재시작 후 모델 소실

**증상**: `ollama list`가 비어있음, 이전에 pull한 모델이 사라짐

**원인**: Ollama가 다른 유저(root vs ollama)로 실행되면서 모델 저장 경로가 달라짐. systemd 서비스는 `ollama` 유저로, `sudo ollama pull`은 root로 실행됨.

**해결**:

```bash
# 1) 모델 저장 위치 확인
sudo find / -name "manifests" -path "*/ollama/*" 2>/dev/null
# /usr/share/ollama/.ollama/models/manifests  ← systemd 서비스 경로
# /root/.ollama/models/manifests              ← root로 실행 시 경로

# 2) 서비스로 모델 pull (올바른 방법)
sudo -u ollama ollama pull qwen2.5:72b
# 또는 서비스가 실행 중일 때:
sudo ollama pull qwen2.5:72b    # 서비스에 API로 요청됨

# 3) 모델 경로 통일 (Environment로 지정)
# /etc/systemd/system/ollama.service [Service] 섹션:
Environment="OLLAMA_MODELS=/opt/ollama/models"
# 이후 sudo ollama pull 시에도 동일 경로 사용:
OLLAMA_MODELS=/opt/ollama/models sudo ollama pull qwen2.5:72b
```

---

### 이슈 5: vLLM `pip install` 실패 (aarch64/CUDA 13)

**증상**: `pip install vllm` 시 `ImportError: libcudart.so.12`, 빌드 실패, 또는 GPU 인식 안됨

**원인**: PyPI의 vLLM wheel은 x86_64 + CUDA 12 전용. DGX Spark는 aarch64 + CUDA 13.

**해결 (방법 선택)**:

```bash
# 방법 1: NGC 컨테이너 (가장 안정적)
sudo docker pull nvcr.io/nvidia/vllm:26.02-py3

# 방법 2: Nightly wheel (bare-metal 필요 시)
pip install torch --index-url https://download.pytorch.org/whl/cu130
pip install -U vllm --extra-index-url https://wheels.vllm.ai/nightly/cu130

# 방법 3: 특정 wheel 직접 지정
pip install https://wheels.vllm.ai/nightly/cu130/vllm-0.14.0rc1.dev530+cu130-cp312-cp312-manylinux_2_35_aarch64.whl
```

**확인**:

```bash
python -c "import vllm; print(vllm.__version__)"
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# True NVIDIA GB10 이면 정상
```

> **참고**: `UserWarning: ... sm_120 used instead of sm_121` 경고는 무시해도 됩니다.
> sm_120과 sm_121은 바이너리 호환됩니다.

---

### 이슈 6: Ray 클러스터에서 NCCL 통신 실패

**증상**: vLLM TP 시작 시 NCCL timeout, hang, 또는 `NCCL error: remote process exited`

**원인**: NCCL이 관리 네트워크(10.0.1.x)를 사용하거나, RoCE 설정이 잘못됨

**해결**:

```bash
# 1) 반드시 ConnectX-7 인터페이스를 지정
export NCCL_SOCKET_IFNAME=enP2p1s0f1np1    # ConnectX-7 직접 연결
export NCCL_IB_HCA=mlx5                     # Mellanox RDMA 디바이스
export NCCL_IB_DISABLE=0                    # RoCE 활성화
export NCCL_IB_ROCE_VERSION_NUM=2           # RoCE v2

# 2) NCCL 디버그 로그로 문제 진단
export NCCL_DEBUG=INFO
export NCCL_DEBUG_SUBSYS=ALL
# → 로그에서 "Using network" 줄을 확인하여 올바른 인터페이스 사용 중인지 확인

# 3) NCCL 2.21+ 에서는 GID_INDEX를 수동 설정하지 마세요
# export NCCL_IB_GID_INDEX=3    ← 이 설정은 사용하지 않음
# NCCL 2.29.3이 자동으로 올바른 GID를 선택합니다
```

**검증**:

```bash
# ConnectX-7 RDMA 디바이스 확인
ibstat | grep -E "(CA |State|Rate)"
# CA 'roceP2p1s0f1' → State: Active, Rate: 200 이면 정상

# 인터페이스 이름 ↔ RDMA 디바이스 매핑
ibdev2netdev 2>/dev/null || rdma link show
```

---

### 이슈 7: 통합 메모리에서 Ray OOM Kill

**증상**: Ray가 `RayOutOfMemoryError`로 프로세스를 강제 종료

**원인**: DGX Spark는 GPU+CPU가 128GB 통합 메모리를 공유하는데, Ray의 메모리 모니터가 이 구조를 정확히 인식하지 못하고 GPU 메모리 사용분을 시스템 메모리 부족으로 오인

**해결**:

```bash
# Docker 환경변수로 설정
-e RAY_memory_monitor_refresh_ms=0

# 또는 bare-metal에서
export RAY_memory_monitor_refresh_ms=0
```

---

### 이슈 8: vLLM 모델 로딩 시 OOM (Out of Memory)

**증상**: `torch.cuda.OutOfMemoryError` 또는 모델 로딩 중 프로세스 killed

**원인**: FP16 모델이 통합 메모리 128GB를 초과하거나, KV cache 할당이 과도

**해결**:

```bash
# 1) 메모리 사용률 줄이기
vllm serve <model> --gpu-memory-utilization 0.70    # 기본 0.9 → 0.7로

# 2) 최대 컨텍스트 길이 제한
vllm serve <model> --max-model-len 4096             # 기본값 대신 작은 값

# 3) 양자화 사용
vllm serve <model> --quantization awq               # AWQ 양자화 모델 사용

# 4) 모델 로딩 전 메모리 정리
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
pkill -9 -f ollama    # Ollama가 메모리를 점유하고 있을 수 있음
```

---

### 이슈 9: vLLM 컨테이너에서 GPU 인식 안됨

**증상**: `docker run --gpus all` 시 `could not select device driver` 에러

**원인**: NVIDIA Container Toolkit 미설치 또는 Docker 런타임 미설정

**해결**:

```bash
# 1) NVIDIA Container Toolkit 설치 확인
nvidia-container-cli --version
# 1.18.0 이상이면 정상

# 2) Docker 런타임 확인
cat /etc/docker/daemon.json
# "default-runtime": "nvidia" 또는 "runtimes": {"nvidia": ...} 확인

# 3) 미설정 시 Docker 런타임 추가
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4) 테스트
sudo docker run --rm --gpus all nvcr.io/nvidia/vllm:26.02-py3 nvidia-smi
```

---

### 이슈 10: vLLM 서빙 중 CUDA Graph 크래시 (async scheduling)

**증상**: 요청 처리 중 `CUDA error: an illegal memory access`, CUDA graph 관련 에러

**원인**: NGC vLLM 26.02 컨테이너의 async-scheduling이 Blackwell GPU에서 불안정

**해결**:

```bash
# async scheduling 비활성화
vllm serve <model> \
    --disable-async-output-proc \
    --enforce-eager                # CUDA graph 자체를 비활성화 (최후의 수단)
```

---

### 이슈 11: HuggingFace 모델 다운로드 실패 (Gated Model)

**증상**: `401 Unauthorized` 또는 `Access to model is restricted`

**원인**: Llama, Gemma 등 일부 모델은 HuggingFace 라이선스 동의 + 토큰 필요

**해결**:

```bash
# 1) HuggingFace 웹사이트에서 모델 라이선스 동의
# https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct → "Accept License"

# 2) HF 토큰 설정
huggingface-cli login    # 토큰 입력

# 3) Docker 환경에서 토큰 전달
sudo docker run ... \
    -e HF_TOKEN=hf_xxxxx \
    nvcr.io/nvidia/vllm:26.02-py3 \
    vllm serve meta-llama/Llama-3.3-70B-Instruct ...
```

---

### 이슈 12: Ollama 토큰 생성 속도가 너무 느림 (~4.5 tok/s)

**증상**: qwen2.5:72b에서 토큰 생성 속도가 4~5 tok/s로 느림

**원인**: DGX Spark의 GB10은 데스크톱/서버 GPU(RTX 4090 등) 대비 연산 성능이 낮음. 이는 하드웨어 한계이며 정상 동작입니다.

**개선 방법**:

```bash
# 1) 작은 모델 사용 (속도 vs 품질 트레이드오프)
ollama run qwen2.5:32b    # ~8-10 tok/s (예상)
ollama run qwen2.5:7b     # ~20+ tok/s (예상, 단 tool-use 불안정)

# 2) Ollama 환경 최적화
# /etc/systemd/system/ollama.service [Service] 섹션:
Environment="OLLAMA_NUM_PARALLEL=1"     # 동시 요청 1개로 제한 (단일 요청 속도 최대화)
Environment="OLLAMA_KEEP_ALIVE=30m"     # 모델 메모리 상주 시간 늘리기

# 3) vLLM으로 전환 (continuous batching으로 throughput 향상)
# 단일 요청 속도는 비슷하지만, 동시 다수 요청 시 전체 throughput이 높아짐
```

> **참고 성능 기준** (DGX Spark GB10, Qwen2.5:72b Q4):
> - 프롬프트 처리: ~210 tok/s
> - 토큰 생성: ~4.5 tok/s
> - 이 수치는 GB10 하드웨어의 정상 성능입니다.

---

## 8. 성능 최적화

### Ollama 최적화

```bash
# 모델 메모리 상주 시간 늘리기 (기본 5분)
Environment="OLLAMA_KEEP_ALIVE=30m"

# GPU 레이어 수 강제 지정 (전부 GPU에 올리기)
Environment="OLLAMA_NUM_GPU=999"

# 동시 요청 수 (기본 1)
Environment="OLLAMA_NUM_PARALLEL=2"
```

### vLLM 최적화

```bash
vllm serve <model> \
    --gpu-memory-utilization 0.90 \    # KV cache에 더 많은 메모리 할당
    --max-model-len 8192 \             # 최대 컨텍스트 길이 제한 (메모리 절약)
    --enable-chunked-prefill \         # 큰 프롬프트 청크 처리
    --disable-log-requests              # 프로덕션 시 로그 비활성화
```

### 모델 크기별 권장 구성

| 모델 | 크기 | 노드 수 | 도구 | TP | 비고 |
|------|------|---------|------|-----|------|
| Qwen2.5:7b | 4.7GB | 1 | Ollama | - | 테스트용, tool-use 불안정 |
| Qwen2.5:72b | 47GB (Q4) | 1 | Ollama | - | **DE Agent 현재 권장** |
| Qwen2.5-72B-Instruct | ~144GB (FP16) | 2 | vLLM | 2 | 품질 최상, 2대 필요 |
| Llama-3.3-70B-Instruct | ~140GB (FP16) | 2 | vLLM | 2 | 영문 우수, 한국어 약함 |
| Llama-3.1-405B | ~230GB (FP16) | 2 | vLLM | 2 | 통합 메모리 256GB에 로드 가능 |

### 단일 요청 vs 동시 처리 — GPU 추가의 효과

| 구성 | 단일 요청 속도 | 동시 처리량 |
|------|-------------|----------|
| 1 GPU, 모델이 메모리에 들어감 | 기준 | 기준 |
| 2 GPU 같은 PC (NVLink/PCIe) | TP 시 빨라짐 (통신 빠름) | 로드밸런싱 2배 |
| 2 GPU 네트워크 연결 (DGX Spark) | TP 시 비슷~느림 (통신 오버헤드) | 로드밸런싱 2배 |
| N GPU 독립 서빙 | 동일 | 로드밸런싱 N배 |

> **핵심**: 같은 PC 안의 GPU는 NVLink로 빠르게 통신하므로 단일 요청도 빨라지지만,
> 네트워크로 연결된 GPU는 매 레이어마다 네트워크 왕복이 필요해 단일 요청은 느려질 수 있습니다.
> 모델이 1대에 들어가면 **각각 독립 서빙 + 로드밸런싱**이 최적입니다.

---

## 9. DE Agent 권장 구성

### 현재 단계 (개발/초기 운영)

```
도구:      Ollama
모델:      qwen2.5:72b (Q4_K_M, 47GB)
노드:      10.0.1.48 (단일)
포트:      11434
성능:      ~4.5 tok/s, 프롬프트 ~210 tok/s
용도:      DE Agent 단일 사용자

config.yml:
  llm:
    provider: "ollama"
    model: "qwen2.5:72b"
    api_url: "http://10.0.1.48:11434"
```

### 다수 사용자 운영 시

```
도구:      Ollama x 2 (독립 서빙) + 앞단 로드밸런서
노드:      10.0.1.47 + 10.0.1.48
포트:      각각 11434
성능:      동시 2명 처리 가능
용도:      DE Agent 2명 동시 사용

nginx 로드밸런서 예시:
  upstream ollama {
      server 10.0.1.47:11434;
      server 10.0.1.48:11434;
  }
```

### 고성능/대형 모델 필요 시

```
도구:      vLLM (NGC 컨테이너)
모델:      Qwen2.5-72B-Instruct (FP16) 또는 Llama-3.1-405B
노드:      10.0.1.47 (head) + 10.0.1.48 (worker)
포트:      8000 (OpenAI 호환)
성능:      ~8-12 tok/s, continuous batching
용도:      다수 사용자, 대형 모델

config.yml:
  llm:
    provider: "openai"
    model: "Qwen/Qwen2.5-72B-Instruct"
    api_url: "http://10.0.1.47:8000/v1"
```
