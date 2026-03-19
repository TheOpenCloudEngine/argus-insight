# PowerDNS Service

PowerDNS Authoritative Server, PowerDNS Admin, MariaDB를 Docker 및 Kubernetes 환경에 배포하는 프로젝트입니다. Argus Insight 플랫폼의 DNS 관리 서비스로, API를 통해 DNS 레코드를 프로그래밍 방식으로 관리합니다. Airgap 환경을 지원하기 위해 공식 이미지를 Dockerfile wrapper로 빌드하여 프라이빗 레지스트리(Zot)에 배포합니다.

## 프로젝트 구조

```
PowerDNS-service/
├── CLAUDE.md                            # 이 파일
├── Makefile                             # Docker 이미지 빌드/푸시/저장 오케스트레이션
├── versions.env                         # 컴포넌트 버전 핀
├── .gitignore
├── .dockerignore
├── mariadb/
│   ├── Dockerfile                       # FROM mariadb, 스키마 내장
│   ├── my.cnf                           # MariaDB 클라이언트 설정
│   └── mysql-init/
│       └── 01-schema.sql                # PowerDNS DB 스키마
├── powerdns-server/
│   └── Dockerfile                       # FROM pschiffe/pdns-mysql
├── powerdns-admin/
│   └── Dockerfile                       # FROM powerdnsadmin/pda-legacy
├── docker/
│   ├── docker-compose.yml               # Docker Compose 오케스트레이션
│   ├── my.cnf                           # bind mount용 my.cnf
│   └── mysql-init/
│       └── 01-schema.sql                # bind mount용 스키마
├── kubernetes/
│   ├── kustomization.yaml               # Kustomize 엔트리포인트
│   ├── namespace.yaml                   # argus-insight 네임스페이스
│   ├── secret.yaml                      # DB 비밀번호, API 키
│   ├── configmap.yaml                   # my.cnf + 스키마 SQL
│   ├── pvc.yaml                         # MySQL 데이터 볼륨
│   ├── powerdns-db.yaml                 # MariaDB Deployment + Service
│   ├── powerdns-server.yaml             # PowerDNS Server Deployment + Service (LoadBalancer)
│   ├── powerdns-admin.yaml              # PowerDNS Admin Deployment + Service (ClusterIP)
│   └── ingress.yaml                     # Traefik Ingress (Admin + API 호스트 기반 라우팅)
└── dist/                                # 빌드 산출물 (gitignored)
    └── powerdns-*.tar.gz                # docker save 이미지
```

## 빌드 방법

```bash
# Docker 이미지 빌드
make docker                      # 전체 빌드 (mariadb + server + admin)
make docker-mariadb              # MariaDB만 빌드
make docker-powerdns-server      # PowerDNS Server만 빌드
make docker-powerdns-admin       # PowerDNS Admin만 빌드

# 프라이빗 레지스트리 푸시
make docker-push                                                    # 기본 (argus-insight/ prefix)
make docker-push DOCKER_REGISTRY=zot.argus.local:5000/argus-insight # Zot Registry 지정

# Airgap 환경용 이미지 저장/로드
make docker-save                 # dist/ 에 tar.gz 저장
make docker-load                 # tar.gz 에서 이미지 로드

# 정리
make clean                       # dist/ 삭제

# Docker Compose
cd docker
docker compose --env-file versions.env up --build -d

# Kubernetes
kubectl apply -k kubernetes/
kubectl get all -n argus-insight -l app.kubernetes.io/name=powerdns-server
```

## 초기 관리자 계정

### PowerDNS Admin

| 항목 | 값 |
|---|---|
| URL (Docker) | `http://localhost:15000` |
| URL (Kubernetes) | `http://powerdns-admin.argus-insight.dev.net` |
| 계정 | 최초 접속 시 관리자 계정 생성 (Sign Up) |

PowerDNS Admin은 최초 접속 시 회원가입 폼을 통해 관리자 계정을 생성합니다.

### MariaDB

| 항목 | 값 |
|---|---|
| root 비밀번호 | `Argus!nsight2026` |
| pdns 사용자 | `pdns` / `pdns` |

### PowerDNS API

| 항목 | 값 |
|---|---|
| API URL (Docker) | `http://localhost:15001` |
| API URL (Kubernetes) | `http://ns.argus-insight.dev.net/api/v1/servers/localhost` |
| API Key | `Argus!nsight2026` |

## 버전 관리

`versions.env` 파일에서 모든 컴포넌트 버전을 관리합니다. 버전 변경 후 `make docker`로 재빌드합니다.

```
MARIADB_VERSION=11.7
PDNS_VERSION=4.9
PDNS_ADMIN_VERSION=v0.4.2
```

## Docker 이미지

| 공식 이미지 | Argus 이미지 | 설명 |
|---|---|---|
| `mariadb:11.7` | `argus-insight/powerdns-mariadb:11.7` | MariaDB + PowerDNS 스키마 내장 |
| `pschiffe/pdns-mysql:4.9-alpine` | `argus-insight/powerdns-server:4.9` | PowerDNS Authoritative Server |
| `powerdnsadmin/pda-legacy:v0.4.2` | `argus-insight/powerdns-admin:v0.4.2` | PowerDNS Admin Web UI |

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

## Docker Compose 배포

### 배포

```bash
cd docker
docker compose --env-file ../versions.env up --build -d
```

### 삭제

```bash
cd docker
docker compose --env-file ../versions.env down       # 컨테이너만 삭제
docker compose --env-file ../versions.env down -v     # 컨테이너 + 볼륨 삭제 (데이터 초기화)
```

### 컨테이너 구성

| 서비스 | 이미지 | 포트 매핑 | 설명 |
|---|---|---|---|
| `mariadb` | `argus-insight/powerdns-mariadb:11.7` | `3306:3306` | MariaDB 데이터베이스 |
| `powerdns-server` | `argus-insight/powerdns-server:4.9` | `10053:53`, `15001:8081` | DNS 서버 + API |
| `powerdns-admin` | `argus-insight/powerdns-admin:v0.4.2` | `15000:80` | 관리 웹 UI |

### Docker 볼륨

| 볼륨 이름 | 컨테이너 경로 | 용도 |
|---|---|---|
| `argus-powerdns-mysql-data` | `/var/lib/mysql` | MariaDB 데이터 |

## Kubernetes 배포

### 배포

```bash
# 전체 배포 (Kustomize)
kubectl apply -k kubernetes/

# 배포 상태 확인
kubectl get all,ingress -n argus-insight -l app.kubernetes.io/part-of=argus-insight

# Pod 상태 확인
kubectl get pods -n argus-insight -l 'app.kubernetes.io/name in (powerdns-db,powerdns-server,powerdns-admin)'

# 로그 확인
kubectl logs -n argus-insight deployment/powerdns-db
kubectl logs -n argus-insight deployment/powerdns-server
kubectl logs -n argus-insight deployment/powerdns-admin
```

### 삭제

```bash
# 전체 삭제 (PVC 제외 — 데이터 보존)
kubectl delete -k kubernetes/

# PVC까지 삭제 (데이터 초기화)
kubectl delete pvc argus-powerdns-mysql-data -n argus-insight

# 개별 컴포넌트 삭제
kubectl delete deployment powerdns-admin -n argus-insight
kubectl delete deployment powerdns-server -n argus-insight
kubectl delete deployment powerdns-db -n argus-insight
kubectl delete ingress powerdns -n argus-insight
```

### 배포 순서 및 주의사항

PowerDNS 컴포넌트는 다음 의존 관계를 가집니다:

```
MariaDB (powerdns-db)
  └─▶ PowerDNS Server (powerdns-server)  ← DB 연결 필요
        └─▶ PowerDNS Admin (powerdns-admin)  ← DB + API 연결 필요
```

Kubernetes는 모든 리소스를 동시에 생성하므로, MariaDB가 준비되기 전에 PowerDNS Server와 Admin이 시작되어 연결 실패로 재시작될 수 있습니다. 이는 정상적인 동작이며, MariaDB가 Ready 상태가 되면 자동으로 안정화됩니다 (보통 1~2회 재시작 후 정상화).

### 리소스 구성

| 리소스 | 이름 | 설명 |
|---|---|---|
| Namespace | `argus-insight` | 전용 네임스페이스 (다른 서비스와 공유) |
| Secret | `powerdns-secrets` | DB 비밀번호, API 키 |
| ConfigMap | `powerdns-config` | my.cnf + DB 스키마 SQL |
| PVC | `argus-powerdns-mysql-data` | MySQL 데이터 (5Gi, ReadWriteOnce) |
| Deployment + Service | `powerdns-db` | MariaDB (ClusterIP, 포트 3306) |
| Deployment + Service | `powerdns-server` | DNS (53 UDP/TCP) + API (8081), **LoadBalancer** |
| Deployment + Service | `powerdns-admin` | Web UI (ClusterIP, 포트 80) |
| Ingress | `powerdns` | Traefik 호스트 기반 라우팅 |

### 외부 접근 구성

PowerDNS는 두 가지 방식으로 외부에 노출됩니다:

| 서비스 | 호스트명 | 포트 | 노출 방식 | 설명 |
|---|---|---|---|---|
| DNS 쿼리 | `ns.argus-insight.dev.net` | **53** (UDP/TCP) | LoadBalancer | DNS 쿼리 수신 |
| PowerDNS API | `ns.argus-insight.dev.net` | **80** (HTTP) | Traefik Ingress | REST API (`/api/v1/...`) |
| PowerDNS Admin | `powerdns-admin.argus-insight.dev.net` | **80** (HTTP) | Traefik Ingress | 관리 웹 UI |

```
                                ┌─────────────────────────────────────┐
                                │           Kubernetes Cluster        │
                                │                                     │
 DNS :53 ──LoadBalancer──────▶  │  ┌──────────────┐                   │
                                │  │ powerdns-     │◀── powerdns-db   │
 API :80 ──Traefik Ingress──▶  │  │ server :8081  │    (MariaDB)     │
  (ns.argus-insight.dev.net)    │  └──────────────┘                   │
                                │                                     │
 Admin :80 ──Traefik Ingress─▶ │  ┌──────────────┐                   │
  (powerdns-admin.              │  │ powerdns-    │                   │
   argus-insight.dev.net)       │  │ admin :80    │                   │
                                │  └──────────────┘                   │
                                └─────────────────────────────────────┘
```

### DNS Zone 및 레코드 등록

Kubernetes 배포 후 Ingress 호스트명으로 접근하려면, PowerDNS에 DNS zone과 A 레코드를 등록해야 합니다. zone과 레코드가 없으면 `resolv.conf`에 PowerDNS를 추가하더라도 도메인 해석이 실패합니다.

아래는 `argus-insight.dev.net` zone을 생성하고 Ingress 호스트에 대한 A 레코드를 등록하는 예시입니다.

#### 1. External IP 확인

```bash
# LoadBalancer / Ingress External IP 확인
kubectl get svc -n argus-insight powerdns-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
kubectl get ingress -n argus-insight powerdns -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

#### 2. Zone 생성

```bash
# argus-insight.dev.net zone 생성 (Native 모드)
curl -X POST \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "argus-insight.dev.net.",
    "kind": "Native",
    "nameservers": ["ns.argus-insight.dev.net."]
  }' \
  http://<EXTERNAL_IP>:8081/api/v1/servers/localhost/zones
```

#### 3. NS 및 A 레코드 등록

```bash
# NS 레코드 + 서비스별 A 레코드를 한번에 등록
curl -X PATCH \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "rrsets": [
      {
        "name": "argus-insight.dev.net.",
        "type": "NS",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": "ns.argus-insight.dev.net.", "disabled": false}]
      },
      {
        "name": "ns.argus-insight.dev.net.",
        "type": "A",
        "ttl": 300,
        "changetype": "REPLACE",
        "records": [{"content": "<EXTERNAL_IP>", "disabled": false}]
      },
      {
        "name": "powerdns-admin.argus-insight.dev.net.",
        "type": "A",
        "ttl": 300,
        "changetype": "REPLACE",
        "records": [{"content": "<EXTERNAL_IP>", "disabled": false}]
      }
    ]
  }' \
  http://<EXTERNAL_IP>:8081/api/v1/servers/localhost/zones/argus-insight.dev.net.
```

#### 4. 등록 확인

```bash
# DNS 질의로 레코드 확인
dig @<EXTERNAL_IP> ns.argus-insight.dev.net A +short
dig @<EXTERNAL_IP> powerdns-admin.argus-insight.dev.net A +short

# 등록된 전체 레코드 조회 (API)
curl -s -H "X-API-Key: <API_KEY>" \
  http://<EXTERNAL_IP>:8081/api/v1/servers/localhost/zones/argus-insight.dev.net. | python3 -m json.tool
```

#### 5. resolv.conf 및 /etc/hosts 설정

```bash
# resolv.conf에 PowerDNS를 네임서버로 추가
echo "nameserver <EXTERNAL_IP>" >> /etc/resolv.conf

# /etc/hosts에도 추가 (DNS 못 타는 환경 대비 fallback)
echo "<EXTERNAL_IP> powerdns-admin.argus-insight.dev.net ns.argus-insight.dev.net" >> /etc/hosts
```

#### 새 서비스 추가 시

새로운 서비스의 Ingress 호스트를 추가할 때는 3단계의 PATCH 요청에 A 레코드 항목을 추가합니다:

```bash
# 예: grafana.argus-insight.dev.net 추가
curl -X PATCH \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "rrsets": [{
      "name": "grafana.argus-insight.dev.net.",
      "type": "A",
      "ttl": 300,
      "changetype": "REPLACE",
      "records": [{"content": "<EXTERNAL_IP>", "disabled": false}]
    }]
  }' \
  http://<EXTERNAL_IP>:8081/api/v1/servers/localhost/zones/argus-insight.dev.net.
```

### 배포 전 필수 설정

1. **secret.yaml**: `mysql_root_password`, `mysql_password`, `pdns_api_key`를 실제 값으로 변경
2. **pvc.yaml**: 스토리지 크기 조정 (기본 5Gi)
3. **powerdns-db.yaml, powerdns-server.yaml, powerdns-admin.yaml**: 이미지 경로를 프라이빗 레지스트리 주소로 변경
4. **ingress.yaml**: 호스트명을 실제 도메인으로 변경 (기본: `*.argus-insight.dev.net`)

### 배포 검증

```bash
# 1. 전체 Pod 상태 확인 (모두 Running/Ready 확인)
kubectl get pods -n argus-insight -l 'app.kubernetes.io/name in (powerdns-db,powerdns-server,powerdns-admin)'

# 2. DNS 쿼리 테스트
dig @<LoadBalancer-IP> version.bind chaos txt +short

# 3. PowerDNS API 테스트
curl -s -H "Host: ns.argus-insight.dev.net" \
     -H "X-API-Key: <API_KEY>" \
     http://<Ingress-IP>/api/v1/servers/localhost

# 4. PowerDNS Admin 접근 테스트
curl -s -o /dev/null -w "%{http_code}" \
     -H "Host: powerdns-admin.argus-insight.dev.net" \
     http://<Ingress-IP>/login
```

### 리소스 요구사항

| 컴포넌트 | CPU 요청 | CPU 제한 | 메모리 요청 | 메모리 제한 |
|---|---|---|---|---|
| MariaDB | 250m | 1 | 256Mi | 1Gi |
| PowerDNS Server | 100m | 500m | 128Mi | 512Mi |
| PowerDNS Admin | 100m | 500m | 128Mi | 512Mi |

## DB 스키마

PowerDNS MySQL 백엔드에 필요한 테이블:

| 테이블 | 용도 |
|---|---|
| `domains` | DNS 도메인(Zone) 목록 |
| `records` | DNS 레코드 (A, AAAA, CNAME, MX 등) |
| `supermasters` | 슈퍼마스터 서버 목록 |
| `comments` | 레코드 코멘트 |
| `domainmetadata` | 도메인 메타데이터 |
| `cryptokeys` | DNSSEC 키 |
| `tsigkeys` | TSIG 키 |

스키마는 `mariadb/mysql-init/01-schema.sql`에 정의되며, Docker 이미지 빌드 시 내장됩니다. Kubernetes에서는 ConfigMap으로도 마운트됩니다.

## 네이밍 규칙

### Docker 이미지

| 규칙 | 패턴 | 예시 |
|---|---|---|
| 이미지 이름 | `argus-insight/<component>:<version>` | `argus-insight/powerdns-server:4.9` |
| 레지스트리 포함 | `<registry>/argus-insight/<component>:<version>` | `zot.argus.local:5000/argus-insight/powerdns-server:4.9` |
| 저장 파일명 | `<component>-<version>.tar.gz` | `powerdns-server-4.9.tar.gz` |

### Docker 볼륨

| 규칙 | 패턴 | 예시 |
|---|---|---|
| Docker Compose | `argus-powerdns-<용도>` | `argus-powerdns-mysql-data` |

### Kubernetes 리소스

| 리소스 | 패턴 | 예시 |
|---|---|---|
| PVC | `argus-powerdns-<용도>` | `argus-powerdns-mysql-data` |
| Secret | `powerdns-secrets` | — |
| ConfigMap | `powerdns-config` | — |
| Deployment | `powerdns-db`, `powerdns-server`, `powerdns-admin` | — |
| Service | `powerdns-db`, `powerdns-server`, `powerdns-admin` | — |
| Ingress | `powerdns` | — |

### Kubernetes 라벨

| 라벨 | 값 | 설명 |
|---|---|---|
| `app.kubernetes.io/name` | `powerdns-db`, `powerdns-server`, `powerdns-admin` | 컴포넌트 식별 |
| `app.kubernetes.io/component` | `database` | PVC 용도 구분 |
| `app.kubernetes.io/part-of` | `argus-insight` | 플랫폼 소속 |

### 포트 할당

| 프로토콜 | Docker 호스트 포트 | 컨테이너 포트 | Kubernetes 노출 | 설명 |
|---|---|---|---|---|
| DNS UDP/TCP | `10053` | `53` | LoadBalancer :53 | DNS 쿼리 |
| HTTP (API) | `15001` | `8081` | Ingress :80 | PowerDNS REST API |
| HTTP (Admin) | `15000` | `80` | Ingress :80 | PowerDNS Admin Web UI |
| MySQL | `3306` | `3306` | ClusterIP (내부) | MariaDB |

## 코드 컨벤션

- Dockerfile의 `LABEL maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `versions.env`에서 모든 컴포넌트 버전을 중앙 관리
- Makefile의 `DOCKER_REGISTRY` 변수로 레지스트리 주소를 주입 (기본값: `argus-insight`)

## 주의사항

- MariaDB Deployment strategy는 `Recreate`로 설정 (데이터 볼륨 동시 접근 방지)
- PowerDNS API Key는 외부에 노출하지 않도록 주의 (Secret으로 관리)
- DNS 포트(53)는 Docker에서 `10053`으로 매핑 (호스트의 기본 DNS와 충돌 방지)
- PowerDNS Admin은 최초 접속 시 관리자 계정을 직접 생성해야 합니다
- PowerDNS Server의 liveness/readiness probe는 `exec` 방식을 사용해야 합니다 (Kubernetes `httpGet` probe는 환경변수 치환을 지원하지 않으므로, API Key 인증이 필요한 헬스체크에서 `httpGet`을 사용하면 인증 실패가 발생합니다)
- PowerDNS Server의 probe에서 `localhost` 대신 `127.0.0.1`을 사용해야 합니다 (Alpine 이미지에서 `localhost`가 IPv6로 해석되어 연결 실패 가능)
- `kubectl delete -k kubernetes/`는 PVC를 삭제하지 않으므로 데이터가 보존됩니다. 데이터 초기화가 필요하면 PVC를 명시적으로 삭제하세요
