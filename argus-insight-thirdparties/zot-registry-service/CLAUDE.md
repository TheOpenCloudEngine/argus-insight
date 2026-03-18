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
│   ├── configmap.yaml              # config.json (TLS 없음, Ingress에서 종단)
│   ├── pvc.yaml                    # 이미지 스토리지 볼륨 (50Gi)
│   ├── zot-registry.yaml           # Deployment (Recreate) + Service (ClusterIP)
│   └── ingress.yaml                # Nginx Ingress (TLS 종단)
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

### Kubernetes Production 배포

Nginx Ingress Controller를 통해 TLS를 종단하고, Zot은 HTTP로 동작하는 구조입니다.

#### 사전 요구사항

- Kubernetes 클러스터
- Nginx Ingress Controller
- 도메인 DNS 또는 `/etc/hosts` 등록

#### Step 1. Nginx Ingress Controller 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml

# 설치 확인
kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller
kubectl get ingressclass
```

#### Step 2. Docker 이미지 빌드

```bash
make docker

# 빌드 확인
docker images | grep zot-registry
```

> Airgap 환경에서는 `make docker-save`로 저장 후 대상 노드에서 `make docker-load`로 로드합니다.

#### Step 3. Secret 설정

`kubernetes/secret.yaml`의 placeholder를 실제 값으로 변경합니다:

```bash
# htpasswd 해시 확인
cat htpasswd
```

```yaml
# kubernetes/secret.yaml
stringData:
  htpasswd: |
    admin:$2y$05$4CSdzVJFAscucxvjhe2U8etOq7nUxVB0JNcA18eld09eHpTGGrFdO
  credentials.json: |
    {
      "registry-1.docker.io": {
        "username": "<DOCKER_HUB_USERNAME>",
        "password": "<DOCKER_HUB_ACCESS_TOKEN>"
      }
    }
```

> `credentials.json`은 업스트림 미러링(onDemand)에서 Docker Hub rate limit을 회피하기 위해 필요합니다. 업스트림 미러링을 사용하지 않거나 airgap 환경이면 빈 `{}`로 설정합니다.

#### Step 4. TLS 인증서 생성

```bash
# 자체 서명 인증서 생성 (Production에서는 CA 발급 인증서 사용 권장)
DOMAIN=zot.argus-insight.dev.net
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/zot-tls.key -out /tmp/zot-tls.crt \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN"

# Kubernetes TLS Secret 생성
kubectl create namespace argus-insight --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret tls zot-registry-tls \
  --cert=/tmp/zot-tls.crt --key=/tmp/zot-tls.key \
  -n argus-insight
```

#### Step 5. Ingress 호스트명 설정

`kubernetes/ingress.yaml`에서 호스트명을 환경에 맞게 변경합니다:

```yaml
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - zot.argus-insight.dev.net    # 환경에 맞게 변경
      secretName: zot-registry-tls
  rules:
    - host: zot.argus-insight.dev.net  # 환경에 맞게 변경
```

#### Step 6. Kustomize 배포

```bash
kubectl apply -k kubernetes/

# 리소스 상태 확인
kubectl get all,ingress,pvc -n argus-insight -l app.kubernetes.io/name=zot-registry
```

정상 상태 예시:

```
NAME                                READY   STATUS    RESTARTS   AGE
pod/zot-registry-54d747498b-6jknq   1/1     Running   0          5m

NAME                   TYPE        CLUSTER-IP     PORT(S)    AGE
service/zot-registry   ClusterIP   10.43.234.67   5000/TCP   5m

NAME                                   CLASS   HOSTS                       PORTS     AGE
ingress.networking.k8s.io/zot-registry nginx   zot.argus-insight.dev.net   80, 443   5m
```

#### Step 7. DNS 등록

```bash
# Ingress Controller의 HTTPS NodePort 확인
kubectl get svc -n ingress-nginx ingress-nginx-controller
# 출력 예: 443:31274/TCP

# /etc/hosts 등록 (또는 DNS 서버에 등록)
echo "<NODE_IP> zot.argus-insight.dev.net" >> /etc/hosts
```

#### Step 8. Docker 클라이언트 설정

```bash
# 자체 서명 인증서인 경우 CA 등록 (CA 발급 인증서면 불필요)
NODEPORT=31274  # Step 7에서 확인한 포트
mkdir -p /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT
cp /tmp/zot-tls.crt /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT/ca.crt
```

#### Step 9. 접속 확인

```bash
NODEPORT=31274

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

## Kubernetes 배포 시 주의사항

- **Deployment 전략**: BoltDB 파일 잠금 때문에 `Recreate` 전략을 사용합니다. RollingUpdate 시 두 Pod이 동시에 PVC에 접근하면 `cache.db` 잠금 충돌이 발생합니다.
- **imagePullPolicy**: 로컬 빌드 이미지를 사용할 때 반드시 `IfNotPresent`로 설정합니다. 미설정 시 Docker Hub에서 pull을 시도하여 실패합니다.
- **Health Probe**: `tcpSocket` probe를 사용합니다. Zot의 `/v2/` 엔드포인트는 인증이 필요하여 `httpGet` probe가 401로 실패합니다.
- **TLS 구조**: Kubernetes에서는 Nginx Ingress에서 TLS를 종단하고, ConfigMap의 config.json에는 TLS 설정이 없습니다 (Docker Compose/RPM용 config.json과 다름).
- **Secret 값**: `secret.yaml`의 htpasswd와 credentials.json은 placeholder이므로, 배포 전 반드시 실제 값으로 교체해야 합니다.
- **NodePort**: Nginx Ingress Service의 HTTPS NodePort는 자동 할당됩니다. 고정하려면 Service에 `nodePort`를 지정하거나 MetalLB로 ExternalIP를 할당합니다.

세부 트러블슈팅은 `TroubleShooting.md`를 참고하세요.

## 설정 파일

### config.json

Zot 메인 설정 파일입니다. 두 가지 버전이 존재합니다:

| 파일 | TLS | 용도 |
|---|---|---|
| `config.json` (루트) | 포함 | Docker Compose, RPM 배포 |
| `kubernetes/configmap.yaml` | 미포함 | Kubernetes 배포 (Ingress에서 TLS 종단) |

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
