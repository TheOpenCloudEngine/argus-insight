# Zot Registry Service

Zot는 OCI Distribution Specification을 준수하는 컨테이너 이미지 레지스트리입니다. Argus Insight 플랫폼에서 airgap 환경의 프라이빗 레지스트리로 사용됩니다. 공식 바이너리를 Dockerfile wrapper로 빌드하여 프라이빗 레지스트리에 배포합니다.

## 프로젝트 구조

```
zot-registry-service/
├── CLAUDE.md                       # 이 파일
├── TroubleShooting.md              # Kubernetes 배포 트러블슈팅
├── Makefile                        # Docker 이미지 빌드/푸시/저장 오케스트레이션
├── versions.env                    # 컴포넌트 버전 핀 (ZOT_VERSION=2.1.2)
├── .gitignore
├── zot-registry/
│   └── Dockerfile                  # Rocky Linux 9 기반 Docker 이미지
├── docker/
│   └── docker-compose.yml          # Docker Compose 오케스트레이션
├── kubernetes/
│   ├── kustomization.yaml          # Kustomize 엔트리포인트
│   ├── namespace.yaml              # argus-insight 네임스페이스
│   ├── secret.yaml                 # htpasswd, credentials
│   ├── configmap.yaml              # config.json (TLS 포함, Zot 자체 TLS 종단)
│   ├── pvc.yaml                    # 이미지 스토리지 볼륨 (50Gi)
│   ├── zot-registry.yaml           # Deployment (Recreate) + Service (NodePort:30000)
│   └── ingress.yaml                # Nginx Ingress (미사용, NodePort 방식 사용 시 불필요)
├── config.json                     # Zot 메인 설정 파일 (Docker Compose/RPM용, TLS 포함)
├── credentials.json                # 업스트림 레지스트리 인증 정보
├── htpasswd                        # Zot 접근용 사용자 인증 파일 (bcrypt)
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

## 초기 관리자 계정

| 항목 | 값 |
|---|---|
| 인증 방식 | htpasswd 파일 기반 (bcrypt) |
| 기본 사용자명 | `admin` |
| 기본 패스워드 | `Argus!insight2026` |

```bash
# 사용자 추가
htpasswd -bB htpasswd <username> <password>
```

## 빌드

```bash
# Docker 이미지 빌드
make docker

# Airgap 환경용 이미지 저장/로드
make docker-save                    # dist/ 에 tar.gz 저장
make docker-load                    # tar.gz 에서 이미지 로드

# 프라이빗 레지스트리 푸시
make docker-push DOCKER_REGISTRY=zot.argus-insight.dev.net/argus-insight

# 정리
make clean
```

## 배포 방식별 가이드

### Docker Compose 배포

```bash
# 1. TLS 인증서 생성
bash generate_certs.sh
mkdir -p certs && cp -r dev-server certs/

# 2. Docker 이미지 빌드 및 실행
make docker
cd docker
docker compose --env-file ../versions.env up --build -d

# 3. 클라이언트 TLS 인증서 신뢰 등록
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/dev-server/dev-server.crt /etc/docker/certs.d/localhost:5000/ca.crt

# 4. 접속 확인
docker login localhost:5000
```

### RPM 패키지 배포 (베어메탈/VM)

```bash
cd rpm && ./build-rpm.sh
sudo rpm -ivh dist/zot-*.rpm
sudo systemctl enable --now zot
```

### Kubernetes 배포 (k3s / NodePort + TLS)

Ingress 없이 NodePort로 직접 노출하고, Zot 자체에서 TLS를 종단하는 구조입니다. k3s 환경에 적합합니다.

#### 사전 요구사항

- k3s 또는 Kubernetes 클러스터
- 도메인 DNS 또는 `/etc/hosts` 등록
- NodePort 범위에 사용할 포트가 포함되어 있을 것 (기본 30000-32767)

#### Step 1. Docker 이미지 빌드

```bash
make docker

# 빌드 확인
docker images | grep zot-registry
```

> Airgap 환경에서는 `make docker-save`로 저장 후 대상 노드에서 `make docker-load`로 로드합니다.

#### Step 2. TLS 인증서 생성

`generate_certs.sh`는 Self-signed CA → 서버 인증서 2단계 구조로 인증서를 생성합니다.

```bash
# hosts.txt에 호스트명 설정
echo "zot.argus-insight.dev.net" > hosts.txt

# CA + 서버 인증서 생성
bash generate_certs.sh
```

생성되는 파일 구조:

```
ca/
├── ca.key                              # CA 개인키 (안전하게 보관)
└── ca.crt                              # CA 인증서 (클라이언트에 배포)
zot.argus-insight.dev.net/
├── zot.argus-insight.dev.net.key       # 서버 개인키
├── zot.argus-insight.dev.net.crt       # 서버 인증서
└── zot.argus-insight.dev.net.pem       # 인증서 체인 (서버 + CA)
```

> **인증서 유효기간**: CA 10년 (3650일), 서버 인증서 825일. 서버 인증서 갱신 시 CA를 재생성할 필요 없이 `generate_certs.sh`를 다시 실행하면 기존 CA로 새 서버 인증서를 발급합니다.

#### Step 3. Kubernetes TLS Secret 생성

생성된 인증서를 Kubernetes TLS Secret으로 등록합니다. ConfigMap의 config.json에서 이 Secret을 `/etc/zot/tls/` 경로로 마운트하여 Zot이 직접 TLS를 처리합니다.

```bash
HOST=zot.argus-insight.dev.net
kubectl create namespace argus-insight --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret tls zot-registry-tls \
  --cert=$HOST/$HOST.crt --key=$HOST/$HOST.key \
  -n argus-insight
```

> Deployment에서 `zot-registry-tls` Secret을 `/etc/zot/tls/`에 마운트하고, ConfigMap의 config.json에서 `tls.cert`와 `tls.key` 경로로 참조합니다.

#### Step 4. Secret 설정

`kubernetes/secret.yaml`의 placeholder를 실제 값으로 변경합니다:

```bash
# htpasswd 해시 생성
htpasswd -nbB admin 'Argus!insight2026'
```

```yaml
# kubernetes/secret.yaml
stringData:
  htpasswd: |
    admin:<위에서 생성한 bcrypt 해시>
  credentials.json: |
    {
      "registry-1.docker.io": {
        "username": "<DOCKER_HUB_USERNAME>",
        "password": "<DOCKER_HUB_ACCESS_TOKEN>"
      }
    }
```

> `credentials.json`은 업스트림 미러링(onDemand)에서 Docker Hub rate limit을 회피하기 위해 필요합니다. 업스트림 미러링을 사용하지 않거나 airgap 환경이면 빈 `{}`로 설정합니다.

#### Step 5. Kustomize 배포

```bash
kubectl apply -k kubernetes/

# 리소스 상태 확인
kubectl get all,pvc -n argus-insight -l app.kubernetes.io/name=zot-registry
```

정상 상태 예시:

```
NAME                                READY   STATUS    RESTARTS   AGE
pod/zot-registry-dcd856d5f-hb5nj    1/1     Running   0          5m

NAME                   TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/zot-registry   NodePort   10.43.240.199   <none>        5000:30000/TCP   5m
```

#### Step 6. DNS 등록

```bash
# /etc/hosts 등록 (또는 DNS 서버에 등록)
echo "<NODE_IP> zot.argus-insight.dev.net" >> /etc/hosts
```

#### Step 7. 클라이언트 CA 인증서 등록

Self-signed CA를 사용하므로, 레지스트리에 접근하는 모든 클라이언트 노드에 CA 인증서를 등록해야 합니다.

```bash
NODEPORT=30000

# Docker 클라이언트
mkdir -p /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT
cp ca/ca.crt /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT/ca.crt

# OS 신뢰 저장소 (curl, 브라우저 등에서 사용)
# RHEL/Rocky Linux
sudo cp ca/ca.crt /etc/pki/ca-trust/source/anchors/argus-insight-ca.crt
sudo update-ca-trust

# Ubuntu/Debian
sudo cp ca/ca.crt /usr/local/share/ca-certificates/argus-insight-ca.crt
sudo update-ca-certificates
```

> CA 인증서는 한 번만 등록하면 됩니다. 이후 해당 CA로 발급한 서버 인증서를 교체하더라도 클라이언트 재설정은 불필요합니다.

#### Step 8. 접속 확인

```bash
NODEPORT=30000

# 레지스트리 API 확인
curl -sk -u admin:'Argus!insight2026' https://zot.argus-insight.dev.net:$NODEPORT/v2/

# Docker 로그인
echo 'Argus!insight2026' | docker login zot.argus-insight.dev.net:$NODEPORT -u admin --password-stdin

# 이미지 Push 테스트
docker pull hello-world:latest
docker tag hello-world:latest zot.argus-insight.dev.net:$NODEPORT/library/hello-world:latest
docker push zot.argus-insight.dev.net:$NODEPORT/library/hello-world:latest

# 카탈로그 확인
curl -sk -u admin:'Argus!insight2026' https://zot.argus-insight.dev.net:$NODEPORT/v2/_catalog
```

#### TLS 인증서 갱신 (Kubernetes)

서버 인증서 만료 시 CA를 재생성할 필요 없이 다음 절차로 갱신합니다:

```bash
# 1. 서버 인증서 재발급 (기존 CA 재사용)
bash generate_certs.sh

# 2. Kubernetes TLS Secret 교체
HOST=zot.argus-insight.dev.net
kubectl delete secret zot-registry-tls -n argus-insight
kubectl create secret tls zot-registry-tls \
  --cert=$HOST/$HOST.crt --key=$HOST/$HOST.key \
  -n argus-insight

# 3. Pod 재시작 (새 인증서 로드)
kubectl rollout restart deployment/zot-registry -n argus-insight
```

> CA를 교체하지 않았으므로 클라이언트 노드의 신뢰 저장소는 재설정 불필요합니다.

### Kubernetes 리소스 삭제

배포된 Zot Registry와 관련 리소스를 모두 제거하는 절차입니다.

#### Step 1. Kubernetes 리소스 삭제

```bash
# Kustomize로 배포한 리소스 일괄 삭제 (namespace 포함)
kubectl delete -k kubernetes/

# TLS Secret은 namespace와 함께 삭제됨. 별도 확인:
kubectl get all,ingress,pvc,secret -n argus-insight 2>&1
# "No resources found" 또는 namespace 없음이 정상
```

#### Step 2. Docker 이미지 삭제

```bash
# Zot Registry 이미지
docker rmi argus-insight/zot-registry:2.1.2

# 테스트용 이미지 (push 테스트에 사용한 경우)
docker rmi zot.argus-insight.dev.net:$NODEPORT/library/hello-world:latest
```

#### Step 3. Docker 클라이언트 정리

```bash
# 레지스트리 로그인 정보 제거
docker logout zot.argus-insight.dev.net:$NODEPORT

# Docker 클라이언트 인증서 제거
rm -rf /etc/docker/certs.d/zot.argus-insight.dev.net:*
```

#### Step 4. DNS/호스트 등록 제거

```bash
# /etc/hosts에서 zot 항목 제거
sed -i '/zot.argus-insight.dev.net/d' /etc/hosts
```

#### Step 5. OS 신뢰 저장소에서 CA 제거 (선택)

CA 인증서를 다른 서비스에서도 사용 중이면 유지합니다. Zot 전용이었다면 제거합니다.

```bash
# RHEL/Rocky Linux
sudo rm -f /etc/pki/ca-trust/source/anchors/argus-insight-ca.crt
sudo update-ca-trust

# Ubuntu/Debian
sudo rm -f /usr/local/share/ca-certificates/argus-insight-ca.crt
sudo update-ca-certificates
```

> Nginx Ingress Controller는 다른 서비스에서도 사용할 수 있으므로 별도로 삭제하지 않습니다. 제거가 필요하면: `kubectl delete -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml`

---

## TLS 인증서 관리

### 인증서 구조

`generate_certs.sh`는 Self-signed CA → 서버 인증서 2단계 구조를 사용합니다. 폐쇄망/airgap 환경에서는 공인 CA 발급이 불가능하므로, 이 Self-signed CA 방식이 Production에서도 적합합니다.

```
┌──────────────────────────────────┐
│  Self-signed CA (ca/ca.crt)      │  유효기간: 10년
│  - 모든 클라이언트 노드에 1회 등록  │
└──────────┬───────────────────────┘
           │ 서명
┌──────────▼───────────────────────┐
│  서버 인증서 (<host>/<host>.crt) │  유효기간: 825일
│  - Ingress TLS Secret에 등록     │
└──────────────────────────────────┘
```

### CA와 서버 인증서 역할

| 구분 | 파일 | 배포 대상 | 유효기간 |
|---|---|---|---|
| CA 개인키 | `ca/ca.key` | 인증서 발급 서버에만 보관 (외부 유출 금지) | — |
| CA 인증서 | `ca/ca.crt` | 모든 클라이언트 노드의 신뢰 저장소 | 10년 |
| 서버 개인키 | `<host>/<host>.key` | Kubernetes TLS Secret | — |
| 서버 인증서 | `<host>/<host>.crt` | Kubernetes TLS Secret | 825일 |

### 서버 인증서 갱신

서버 인증서 만료 시 CA를 재생성할 필요 없이 `generate_certs.sh`를 다시 실행합니다. 기존 CA(`ca/` 디렉토리)가 존재하면 자동으로 재사용합니다.

```bash
# 서버 인증서 재발급 (기존 CA 재사용)
bash generate_certs.sh

# Kubernetes TLS Secret 교체
HOST=zot.argus-insight.dev.net
kubectl delete secret zot-registry-tls -n argus-insight
kubectl create secret tls zot-registry-tls \
  --cert=$HOST/$HOST.crt --key=$HOST/$HOST.key \
  -n argus-insight

# Ingress가 새 인증서를 인식하도록 재시작
kubectl rollout restart deployment/zot-registry -n argus-insight
```

> CA를 교체하지 않았으므로 클라이언트 노드의 신뢰 저장소는 재설정 불필요합니다.

### 호스트 추가

새로운 호스트의 인증서가 필요하면 `hosts.txt`에 호스트명을 추가하고 `generate_certs.sh`를 실행합니다. 기존 호스트의 인증서도 함께 재발급됩니다.

---

## Kubernetes 배포 시 주의사항

- **Deployment 전략**: BoltDB 파일 잠금 때문에 `Recreate` 전략을 사용합니다. RollingUpdate 시 두 Pod이 동시에 PVC에 접근하면 `cache.db` 잠금 충돌이 발생합니다.
- **imagePullPolicy**: 로컬 빌드 이미지를 사용할 때 반드시 `IfNotPresent`로 설정합니다. 미설정 시 Docker Hub에서 pull을 시도하여 실패합니다.
- **Health Probe**: `tcpSocket` probe를 사용합니다. Zot의 `/v2/` 엔드포인트는 인증이 필요하여 `httpGet` probe가 401로 실패합니다.
- **TLS 구조**: NodePort 방식에서는 Zot 자체에서 TLS를 종단합니다. ConfigMap의 config.json에 TLS 설정이 포함되어 있으며, `zot-registry-tls` Secret을 `/etc/zot/tls/`에 마운트합니다.
- **Secret 값**: `secret.yaml`의 htpasswd와 credentials.json은 placeholder이므로, 배포 전 반드시 실제 값으로 교체해야 합니다. htpasswd는 `htpasswd -nbB` 명령으로 생성한 해시를 사용합니다.
- **NodePort**: Service의 `nodePort: 30000`으로 고정되어 있습니다. k3s의 기본 NodePort 범위(8000-32767 또는 30000-32767)에 포함되는 포트를 사용해야 합니다.

세부 트러블슈팅은 `TroubleShooting.md`를 참고하세요.

## 설정 파일

### config.json

Zot 메인 설정 파일입니다. 두 가지 버전이 존재합니다:

| 파일 | TLS | 용도 |
|---|---|---|
| `config.json` (루트) | 포함 | Docker Compose, RPM 배포 |
| `kubernetes/configmap.yaml` | 포함 | Kubernetes 배포 (Zot 자체 TLS 종단, NodePort 방식) |

### 업스트림 미러링

onDemand 모드로 설정되어 클라이언트가 이미지를 pull할 때 자동으로 업스트림에서 가져와 캐싱합니다:

- Docker Hub (`registry-1.docker.io`)
- Quay.io (`quay.io`)
- Google Container Registry (`gcr.io`)
- GitHub Container Registry (`ghcr.io`)
- Microsoft Container Registry (`mcr.microsoft.com`)

## 코드 컨벤션

- Dockerfile의 `LABEL maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `versions.env`에서 Zot 버전을 중앙 관리
- Makefile의 `DOCKER_REGISTRY` 변수로 레지스트리 주소를 주입 (기본값: `argus-insight`)
