# Zot Registry Service

Zot는 OCI Distribution Specification을 준수하는 컨테이너 이미지 레지스트리입니다. Argus Insight 플랫폼에서 airgap 환경의 프라이빗 레지스트리로 사용됩니다. 공식 바이너리를 Dockerfile wrapper로 빌드하여 프라이빗 레지스트리에 배포합니다.

## 프로젝트 구조

```
zot-registry-service/
├── CLAUDE.md                       # 이 파일
├── Makefile                        # Docker 이미지 빌드/푸시/저장 오케스트레이션
├── versions.env                    # 컴포넌트 버전 핀
├── .gitignore
├── zot-registry/
│   └── Dockerfile                  # Rocky Linux 9 기반 Docker 이미지
├── docker/
│   └── docker-compose.yml          # Docker Compose 오케스트레이션
├── kubernetes/
│   ├── kustomization.yaml          # Kustomize 엔트리포인트
│   ├── namespace.yaml              # argus-insight 네임스페이스
│   ├── secret.yaml                 # htpasswd, credentials
│   ├── configmap.yaml              # config.json
│   ├── pvc.yaml                    # 이미지 스토리지 볼륨
│   └── zot-registry.yaml           # Zot Deployment + Service
├── config.json                     # Zot 메인 설정 파일
├── credentials.json                # 업스트림 레지스트리 인증 정보
├── htpasswd                        # Zot 접근용 사용자 인증 파일
├── hosts.txt                       # TLS 인증서 생성 대상 호스트 목록
├── generate_certs.sh               # TLS 인증서 생성 스크립트
├── zot.service                     # systemd 서비스 유닛 파일
├── list-all-images.sh              # 레지스트리 이미지 목록 조회
├── registry-migrator/              # 레지스트리 마이그레이션 도구
│   ├── README.md
│   ├── config.env.example
│   └── migrate.sh
└── rpm/                            # RPM 패키지 빌드
    ├── build-rpm.sh
    └── zot.spec
```

## 빌드 방법

```bash
# Docker 이미지 빌드
make docker                         # zot 바이너리 다운로드 + Docker 이미지 빌드

# 프라이빗 레지스트리 푸시
make docker-push                                                    # 기본 (argus-insight/ prefix)
make docker-push DOCKER_REGISTRY=zot.argus.local:5000/argus-insight # Zot Registry 지정

# Airgap 환경용 이미지 저장/로드
make docker-save                    # dist/ 에 tar.gz 저장
make docker-load                    # tar.gz 에서 이미지 로드

# 정리
make clean                          # dist/ 및 다운로드된 바이너리 삭제

# Docker Compose
cd docker
docker compose --env-file ../versions.env up --build -d

# Kubernetes
kubectl apply -k kubernetes/
kubectl get all -n argus-insight -l app.kubernetes.io/name=zot-registry
```

## Getting Started (Docker Compose)

Docker Compose로 Zot Registry를 실행하고 이미지를 push/pull하는 빠른 시작 가이드입니다.

### 1. TLS 인증서 생성

```bash
# hosts.txt에 호스트명 설정 (기본값: dev-server)
cat hosts.txt

# 인증서 생성
bash generate_certs.sh

# 생성된 인증서를 certs/ 디렉토리에 배치
mkdir -p certs
cp -r dev-server certs/
```

### 2. Docker 이미지 빌드 및 실행

```bash
# Zot Registry 이미지 빌드
make docker

# Docker Compose로 실행
cd docker
docker compose --env-file ../versions.env up --build -d

# 로그 확인
docker compose logs -f zot-registry
```

### 3. 클라이언트에서 TLS 인증서 신뢰 설정

자체 서명 CA를 사용하므로, Docker 데몬이 레지스트리를 신뢰하도록 CA 인증서를 등록해야 합니다.

```bash
# Linux
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/dev-server/dev-server.crt /etc/docker/certs.d/localhost:5000/ca.crt

# macOS (Docker Desktop)
# ca/ca.crt를 키체인에 '항상 신뢰'로 등록 후 Docker Desktop 재시작
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ca/ca.crt
```

### 4. 레지스트리 로그인

```bash
# htpasswd에 등록된 계정으로 로그인 (기본 계정: admin)
docker login localhost:5000
```

### 5. 이미지 Push / Pull

```bash
# 기존 이미지에 레지스트리 태그 추가
docker tag alpine:latest localhost:5000/library/alpine:latest

# 이미지 Push
docker push localhost:5000/library/alpine:latest

# 이미지 Pull (다른 머신 또는 확인용)
docker pull localhost:5000/library/alpine:latest

# 레지스트리에 저장된 이미지 목록 확인
curl -k -u admin:<password> https://localhost:5000/v2/_catalog
```

### 6. 업스트림 미러링 (onDemand)

Zot는 onDemand 미러링이 설정되어 있어, 업스트림 이미지를 직접 pull하면 자동으로 캐싱됩니다.

```bash
# Docker Hub 이미지를 Zot를 통해 pull (자동 캐싱)
docker pull localhost:5000/library/nginx:latest

# Quay.io 이미지
docker pull localhost:5000/quay.io/prometheus/prometheus:latest
```

## 초기 관리자 계정

### Zot Registry

| 항목 | 값 |
|---|---|
| URL | `https://localhost:5000` |
| 인증 | htpasswd 파일 기반 인증 |

htpasswd 파일에 사용자를 추가합니다:
```bash
htpasswd -bB htpasswd <username> <password>
```

## 버전 관리

`versions.env` 파일에서 Zot 버전을 관리합니다. 버전 변경 후 `make clean && make docker`로 재빌드합니다.

```
ZOT_VERSION=2.1.2
```

## Docker 이미지

| 공식 바이너리 | Argus 이미지 | 설명 |
|---|---|---|
| `zot-linux-amd64` (v2.1.2) | `argus-insight/zot-registry:2.1.2` | OCI 컨테이너 레지스트리 |

### Airgap 배포 흐름

```
인터넷 환경                          Airgap 환경
┌─────────────────┐                ┌──────────────────┐
│ make docker     │                │ make docker-load │
│ make docker-save│ ──USB/SCP──▶  │ docker tag ...   │
│ (dist/*.tar.gz) │                │ docker push ...  │
└─────────────────┘                │   → Zot Registry │
                                   └──────────────────┘
```

## 설정 파일

### config.json

Zot 메인 설정 파일입니다. 주요 섹션:

- **storage**: 이미지 저장 경로 (`/var/lib/zot`), GC 활성화
- **http**: 리스닝 주소/포트 (`0.0.0.0:5000`), TLS 인증서, htpasswd 인증
- **log**: 로그 레벨 (`info`)
- **extensions.sync**: 업스트림 레지스트리 미러링 설정 (onDemand 모드)

현재 설정된 업스트림 레지스트리:
- Docker Hub (`registry-1.docker.io`)
- Quay.io (`quay.io`)
- Google Container Registry (`gcr.io`)
- GitHub Container Registry (`ghcr.io`)
- Microsoft Container Registry (`mcr.microsoft.com`)

모든 업스트림은 `onDemand: true`로 설정되어, 클라이언트가 이미지를 pull할 때 자동으로 업스트림에서 가져와 캐싱합니다.

### credentials.json

업스트림 레지스트리에 접근하기 위한 인증 정보 파일입니다. Docker Hub의 rate limit을 회피하기 위해 인증을 설정합니다.

### htpasswd

Zot 레지스트리에 push/pull할 때 사용하는 사용자 인증 파일입니다. bcrypt 해시 형식입니다.

## 배포 방식

### RPM 패키지 (베어메탈/VM)

`rpm/build-rpm.sh`를 실행하면 zot 바이너리를 다운로드하고 RPM 패키지를 빌드합니다.

```bash
cd rpm
./build-rpm.sh
```

생성된 RPM을 설치하면 다음 경로에 파일이 배치됩니다:

| 경로 | 설명 |
|---|---|
| `/usr/local/bin/zot` | zot 바이너리 |
| `/usr/lib/systemd/system/zot.service` | systemd 서비스 파일 |
| `/etc/zot/config.json` | 메인 설정 파일 |
| `/etc/zot/credentials.json` | 업스트림 레지스트리 인증 정보 |
| `/etc/zot/htpasswd` | 사용자 인증 파일 |
| `/etc/zot/certs/` | TLS 인증서 디렉토리 |
| `/var/lib/zot/` | 이미지 스토리지 |

## Docker Compose 배포

### 컨테이너 구성

| 서비스 | 이미지 | 포트 매핑 | 설명 |
|---|---|---|---|
| `zot-registry` | `argus-insight/zot-registry:2.1.2` | `5000:5000` | OCI 컨테이너 레지스트리 |

### Docker 볼륨

| 볼륨 이름 | 컨테이너 경로 | 용도 |
|---|---|---|
| `argus-zot-data` | `/var/lib/zot` | 이미지 스토리지 |

## Kubernetes 배포

### 리소스 구성

| 리소스 | 이름 | 설명 |
|---|---|---|
| Namespace | `argus-insight` | 전용 네임스페이스 (다른 서비스와 공유) |
| Secret | `zot-registry-secrets` | htpasswd, 업스트림 인증 정보 |
| ConfigMap | `zot-registry-config` | config.json |
| PVC | `argus-zot-data` | 이미지 스토리지 (50Gi, ReadWriteOnce) |
| Deployment + Service | `zot-registry` | OCI 레지스트리 (포트 5000) |

### 배포 전 필수 설정

1. **secret.yaml**: `htpasswd` 내용을 실제 값으로 변경, `credentials.json`에 Docker Hub 토큰 설정
2. **pvc.yaml**: 스토리지 크기 조정 (기본 50Gi)
3. **zot-registry.yaml**: 이미지 경로를 프라이빗 레지스트리 주소로 변경

### 리소스 요구사항

| 컴포넌트 | CPU 요청 | CPU 제한 | 메모리 요청 | 메모리 제한 |
|---|---|---|---|---|
| Zot Registry | 100m | 1 | 256Mi | 1Gi |

## 네이밍 규칙

### Docker 이미지

| 규칙 | 패턴 | 예시 |
|---|---|---|
| 이미지 이름 | `argus-insight/<component>:<version>` | `argus-insight/zot-registry:2.1.2` |
| 레지스트리 포함 | `<registry>/argus-insight/<component>:<version>` | `zot.argus.local:5000/argus-insight/zot-registry:2.1.2` |
| 저장 파일명 | `<component>-<version>.tar.gz` | `zot-registry-2.1.2.tar.gz` |

### Docker 볼륨

| 규칙 | 패턴 | 예시 |
|---|---|---|
| Docker Compose | `argus-zot-<용도>` | `argus-zot-data` |

### Kubernetes 리소스

| 리소스 | 패턴 | 예시 |
|---|---|---|
| PVC | `argus-zot-<용도>` | `argus-zot-data` |
| Secret | `zot-registry-secrets` | — |
| ConfigMap | `zot-registry-config` | — |
| Deployment | `zot-registry` | — |
| Service | `zot-registry` | — |

### Kubernetes 라벨

| 라벨 | 값 | 설명 |
|---|---|---|
| `app.kubernetes.io/name` | `zot-registry` | 컴포넌트 식별 |
| `app.kubernetes.io/component` | `storage` | PVC 용도 구분 |
| `app.kubernetes.io/part-of` | `argus-insight` | 플랫폼 소속 |

### 포트 할당

| 프로토콜 | Docker 호스트 포트 | 컨테이너 포트 | 설명 |
|---|---|---|---|
| HTTPS | `5000` | `5000` | OCI Registry API |

## 코드 컨벤션

- Dockerfile의 `LABEL maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `versions.env`에서 Zot 버전을 중앙 관리
- Makefile의 `DOCKER_REGISTRY` 변수로 레지스트리 주소를 주입 (기본값: `argus-insight`)

## 주의사항

- zot 바이너리는 빌드 시 GitHub에서 다운로드되며, 저장소에는 포함되지 않음 (`.gitignore`)
- TLS 인증서는 `generate_certs.sh`로 생성 후 `config.json`에서 경로 지정 필요
- Kubernetes 배포 시 TLS는 ConfigMap의 config.json에서 TLS 섹션을 제거하고, Ingress/LoadBalancer에서 TLS 종단 권장
- 업스트림 레지스트리 미러링은 onDemand 모드로, 첫 pull 시 캐싱됨
