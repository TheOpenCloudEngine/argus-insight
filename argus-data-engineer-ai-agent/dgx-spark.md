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

## 4. vLLM 설정

### 설치 (NGC 컨테이너 — DGX Spark 권장)

DGX Spark(aarch64 + CUDA 13 + Blackwell sm_121)에서는 NGC 컨테이너가 유일하게 검증된 방법입니다.
PyPI의 `pip install vllm`은 CUDA 13/aarch64에서 동작하지 않습니다.

```bash
# 양쪽 노드 모두 실행
sudo docker pull nvcr.io/nvidia/vllm:26.02-py3
```

### 단일 노드 실행 (작은 모델)

```bash
sudo docker run -d --name vllm-single \
    --gpus all \
    --network host \
    --ipc host \
    -v /root/.cache/huggingface:/root/.cache/huggingface \
    nvcr.io/nvidia/vllm:26.02-py3 \
    vllm serve Qwen/Qwen2.5-72B-Instruct \
        --host 0.0.0.0 \
        --port 8000 \
        --gpu-memory-utilization 0.85 \
        --trust-remote-code
```

### 멀티노드 실행 (Ray 클러스터 — 대형 모델)

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
    nvcr.io/nvidia/vllm:26.02-py3 \
    bash -c "ray start --address=192.168.200.1:6379 \
             --node-ip-address=192.168.200.2 && sleep infinity"
```

#### Step 3: 클러스터 확인

```bash
sudo docker exec vllm-head ray status
# 2 node(s), 2 GPU(s) 확인
```

#### Step 4: 대형 모델 서빙 (2대 합쳐서)

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

### vLLM API 호출 (OpenAI 호환)

```bash
# 모델 목록
curl http://10.0.1.47:8000/v1/models

# 채팅
curl http://10.0.1.47:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 256
    }'
```

### DE Agent config.yml 설정 (vLLM — OpenAI 호환)

```yaml
llm:
  provider: "openai"
  model: "Qwen/Qwen2.5-72B-Instruct"
  api_key: "not-needed"
  api_url: "http://10.0.1.47:8000/v1"
  temperature: 0.3
  max_tokens: 4096
```

### NCCL 환경 변수 레퍼런스

| 변수 | 값 | 설명 |
|------|-----|------|
| `NCCL_SOCKET_IFNAME` | `enP2p1s0f1np1` | ConnectX-7 인터페이스 |
| `NCCL_IB_HCA` | `mlx5` | Mellanox RDMA 디바이스 |
| `NCCL_IB_DISABLE` | `0` | IB/RoCE 활성화 |
| `NCCL_IB_ROCE_VERSION_NUM` | `2` | RoCE v2 사용 |
| `VLLM_HOST_IP` | 노드별 IP | 노드마다 다르게 설정 |
| `RAY_memory_monitor_refresh_ms` | `0` | 통합 메모리 OOM 방지 |

---

## 5. 운영 스크립트

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

## 6. 이슈 및 해결

### 이슈 1: DGX Spark 2대 연결 시 GPU가 1개만 인식됨

**증상**: `nvidia-smi`에 GPU 1개만 표시, NVLink 정보 없음

**원인**: DGX Spark는 NVLink가 아닌 ConnectX-7(RoCE)로 2대를 연결합니다. 각 노드의 GPU는 독립적으로 인식되며, 하나의 통합 GPU로 보이지 않습니다.

**해결**: 이것은 정상 동작입니다. 2대를 하나처럼 사용하려면 Ray 클러스터 + vLLM Tensor Parallelism을 사용해야 합니다.

### 이슈 2: ConnectX-7 직접 연결 포트에 IP 미설정

**증상**: `enP2p1s0f1np1` 인터페이스가 UP이지만 IPv4 주소 없음, 노드 간 통신 불가

**해결**:

```bash
# 10.0.1.47
sudo nmcli con add type ethernet ifname enP2p1s0f1np1 \
    con-name enP2p1s0f1np1 ipv4.addresses 192.168.200.1/24 \
    ipv4.method manual 802-3-ethernet.mtu 9000
sudo nmcli con up enP2p1s0f1np1

# 10.0.1.48
sudo nmcli con add type ethernet ifname enP2p1s0f1np1 \
    con-name enP2p1s0f1np1 ipv4.addresses 192.168.200.2/24 \
    ipv4.method manual 802-3-ethernet.mtu 9000
sudo nmcli con up enP2p1s0f1np1

# 검증
ping -M do -s 8972 -c 3 192.168.200.1    # Jumbo frame 테스트
```

### 이슈 3: Ollama 외부 접근 불가 (Connection Refused)

**증상**: `curl http://10.0.1.48:11434` 실패

**원인**: Ollama 기본 설정은 localhost만 수신

**해결**:

```bash
# /etc/systemd/system/ollama.service [Service] 섹션에 추가
Environment="OLLAMA_HOST=0.0.0.0"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 이슈 4: Ollama 재시작 후 모델 소실 (10.0.1.47)

**증상**: `ollama list`가 비어있음, pull했던 모델이 사라짐

**원인**: Ollama 서비스가 다른 유저로 실행되면서 모델 저장 경로가 달라질 수 있음

**해결**:

```bash
# 모델 저장 위치 확인
sudo ls -la /usr/share/ollama/.ollama/models/
sudo ls -la /root/.ollama/models/

# 필요 시 재다운로드
sudo ollama pull qwen2.5:72b
```

### 이슈 5: vLLM `pip install` 실패 (aarch64/CUDA 13)

**증상**: `pip install vllm` 시 `ImportError: libcudart.so.12` 또는 빌드 실패

**원인**: PyPI의 vLLM wheel은 x86_64 + CUDA 12 전용

**해결**: NGC 컨테이너 사용 (유일한 공식 지원 방법)

```bash
sudo docker pull nvcr.io/nvidia/vllm:26.02-py3
```

만약 bare-metal이 반드시 필요하다면 nightly wheel 사용:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu130
pip install -U vllm --extra-index-url https://wheels.vllm.ai/nightly/cu130
```

### 이슈 6: Ray 클러스터에서 NCCL 통신 실패

**증상**: vLLM Tensor Parallelism 시작 시 NCCL timeout 또는 hang

**원인**: NCCL이 잘못된 네트워크 인터페이스를 사용하거나 RoCE 설정 불일치

**해결**:

```bash
# 반드시 ConnectX-7 인터페이스를 지정
export NCCL_SOCKET_IFNAME=enP2p1s0f1np1
export NCCL_IB_HCA=mlx5
export NCCL_IB_DISABLE=0
export NCCL_IB_ROCE_VERSION_NUM=2

# NCCL 디버그 로그 활성화 (문제 진단 시)
export NCCL_DEBUG=INFO
export NCCL_DEBUG_SUBSYS=ALL
```

### 이슈 7: 통합 메모리에서 Ray OOM Kill

**증상**: Ray가 메모리 모니터링으로 프로세스를 강제 종료

**원인**: DGX Spark의 통합 메모리(GPU+CPU 공유) 구조를 Ray가 정확히 인식하지 못함

**해결**:

```bash
export RAY_memory_monitor_refresh_ms=0    # Ray 메모리 모니터 비활성화
```

---

## 7. 성능 최적화

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

## 8. DE Agent 권장 구성

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
