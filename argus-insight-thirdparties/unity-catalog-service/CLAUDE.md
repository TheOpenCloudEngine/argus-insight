# Unity Catalog Packaging

[Unity Catalog](https://www.unitycatalog.io/) v0.4.0의 공식 Docker 이미지를 래핑하여 Docker 이미지, Helm 차트, Kubernetes 매니페스트로 배포하는 프로젝트입니다. 공식 이미지(`unitycatalog/unitycatalog`)를 기반으로 설정 파일만 오버레이하는 래퍼 Dockerfile 방식을 사용합니다. Airgap 환경을 지원하기 위해 Docker 이미지를 빌드하여 프라이빗 레지스트리(Zot)에 배포합니다.

메타데이터 저장소로 PostgreSQL 17을 함께 배포합니다. Hibernate ORM을 통해 Unity Catalog가 PostgreSQL에 접속하며, 스키마는 `hbm2ddl.auto=update` 설정으로 자동 생성됩니다.

## 프로젝트 구조

```
unity-catalog-service/
├── CLAUDE.md                         # 이 파일
├── Makefile                          # 빌드 오케스트레이션
├── versions.env                      # 컴포넌트 버전 핀
├── .gitignore
├── .dockerignore
├── common/scripts/                   # 패키지 설치/제거 scriptlet
│   ├── preinstall.sh                 # unitycatalog 시스템 사용자 생성
│   ├── postinstall.sh                # systemctl daemon-reload, enable, 디렉토리 생성
│   ├── preremove.sh                  # 서비스 stop/disable
│   └── postremove.sh                 # systemctl daemon-reload
├── postgresql/
│   ├── Dockerfile                    # PostgreSQL 이미지 (스키마 내장)
│   └── initdb/
│       └── 01-schema.sql             # DB 초기화 스크립트
├── server/
│   ├── Dockerfile                    # 공식 이미지 래퍼 (설정 오버레이)
│   ├── hibernate.properties          # Hibernate 설정 (PostgreSQL 연결)
│   ├── server.properties             # 기본 설정 파일
│   ├── nfpm.yaml                     # 패키지 정의 (RPM/DEB)
│   ├── unitycatalog-server.service   # systemd unit
│   └── unitycatalog-server.default   # /etc/default (CLI 옵션)
├── docker/
│   ├── docker-compose.yml            # Docker Compose 오케스트레이션
│   └── initdb/
│       └── 01-schema.sql             # DB 초기화 (bind mount용)
├── kubernetes/                       # Kubernetes 매니페스트 (Kustomize)
│   ├── kustomization.yaml            # Kustomize 엔트리 포인트
│   ├── namespace.yaml
│   ├── secret.yaml
│   ├── configmap.yaml
│   ├── pvc.yaml
│   ├── unity-catalog-db.yaml         # PostgreSQL Deployment + Service
│   └── unity-catalog-server.yaml     # UC Server Deployment + Service (NodePort)
├── helm/
│   └── unity-catalog/                # Helm 차트
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── pvc.yaml
│           ├── secret.yaml
│           ├── postgresql-deployment.yaml
│           ├── postgresql-service.yaml
│           ├── postgresql-pvc.yaml
│           └── NOTES.txt
└── dist/                             # 빌드 산출물 (gitignored)
```

## 빌드 방법

```bash
# Docker 이미지 빌드
make docker                         # 전체 빌드 (PostgreSQL + Unity Catalog)
make docker-postgresql              # PostgreSQL 이미지만 빌드
make docker-unity-catalog           # Unity Catalog 이미지만 빌드
make clean                          # dist/ 삭제

# 프라이빗 레지스트리 푸시
make docker-push                                                    # 기본 (argus-insight/ prefix)
make docker-push DOCKER_REGISTRY=zot.argus.local:5000/argus-insight # Zot Registry 지정
make docker-push-postgresql                                         # PostgreSQL만 푸시
make docker-push-unity-catalog                                      # Unity Catalog만 푸시

# Airgap 환경용 이미지 저장/로드
make docker-save                    # dist/ 에 tar.gz 저장
make docker-load                    # tar.gz 에서 이미지 로드

# Docker Compose
cd docker
docker compose --env-file ../versions.env up --build -d

# Kubernetes (Kustomize)
kubectl apply -k kubernetes/

# Helm
make helm-package                     # Helm 차트 패키징
helm install unity-catalog helm/unity-catalog  # Helm 배포
```

빌드 호스트에 `make`, `docker`가 필요합니다. 공식 이미지를 래핑하므로 JDK나 sbt 빌드가 불필요합니다.

## 버전 관리

`versions.env` 파일에서 모든 컴포넌트 버전을 관리합니다. 버전을 변경한 후 `make clean && make all`로 재빌드합니다.

```
UNITY_CATALOG_VERSION=0.4.0
NFPM_VERSION=2.41.1
POSTGRESQL_VERSION=17
```

## Docker 이미지

| 공식 이미지 | Argus 이미지 | 설명 |
|---|---|---|
| `postgres:17-alpine` | `argus-insight/unity-catalog-postgresql:17` | PostgreSQL 메타데이터 DB |
| `unitycatalog/unitycatalog:v0.4.0` | `argus-insight/unity-catalog:0.4.0` | Unity Catalog Server |

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

## 패키지 설치 후 파일 레이아웃

### 바이너리

| 경로 | 설명 |
|---|---|
| `/opt/argus-insight/unity-catalog/bin/` | 실행 스크립트 (start-uc-server 등) |
| `/opt/argus-insight/unity-catalog/jars/` | Java 라이브러리 |
| `/opt/argus-insight/unity-catalog/jre/` | 번들 JRE 17 |

### 설정 및 데이터

| 컴포넌트 | 바인딩 주소 | 설정 파일 | 데이터 디렉토리 |
|---|---|---|---|
| UC Server | `0.0.0.0:8080` | `/etc/unity-catalog/server.properties` | `/var/lib/unity-catalog/data` |

### 공통 사항

- 서비스는 `unitycatalog` 시스템 사용자로 실행
- CLI 옵션은 `/etc/default/unitycatalog-server` EnvironmentFile에서 관리
- 설정 파일은 `config|noreplace`로 마킹되어 패키지 업그레이드 시 보존
- systemd 서비스: `systemctl start|stop|restart|status unitycatalog-server`
- 로그 디렉토리: `/var/log/unity-catalog/`

## Docker Compose 배포

### 컨테이너 구성

| 서비스 | 이미지 | 포트 매핑 | 설명 |
|---|---|---|---|
| `postgresql` | `argus-insight/unity-catalog-postgresql:17` | `5432:5432` | PostgreSQL 메타데이터 DB |
| `unity-catalog-server` | `argus-insight/unity-catalog:0.4.0` | `31000:8080` | Unity Catalog Server |

### Docker 볼륨

| 볼륨 이름 | 컨테이너 경로 | 용도 |
|---|---|---|
| `argus-unity-catalog-pgdata` | `/var/lib/postgresql/data` | PostgreSQL 데이터 |
| `argus-unity-catalog-data` | `/var/lib/unity-catalog` | UC 데이터 |

### 의존성 체인

```
PostgreSQL (postgresql)
  └──▶ Unity Catalog Server (unity-catalog-server)  [JDBC 연결]
```

### 기본 자격 증명

| 서비스 | 사용자 | 비밀번호 | 데이터베이스 |
|---|---|---|---|
| PostgreSQL | `unity_catalog` | `Argus!insight2026` | `unity_catalog` |

## Helm 차트

`helm/unity-catalog/` 디렉토리에 표준 Helm 차트를 제공합니다.

### 주요 설정 (values.yaml)

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `image.repository` | `argus-insight/unity-catalog` | Docker 이미지 |
| `image.tag` | `0.4.0` | 이미지 태그 |
| `service.type` | `NodePort` | Service 타입 |
| `service.port` | `8080` | 컨테이너 포트 |
| `service.nodePort` | `31000` | 외부 노출 포트 |
| `persistence.enabled` | `true` | UC 데이터 PVC 사용 여부 |
| `persistence.size` | `10Gi` | UC 스토리지 크기 |
| `postgresql.enabled` | `true` | PostgreSQL 배포 여부 |
| `postgresql.image.repository` | `argus-insight/unity-catalog-postgresql` | PostgreSQL 이미지 |
| `postgresql.image.tag` | `17` | PostgreSQL 버전 |
| `postgresql.persistence.enabled` | `true` | PostgreSQL PVC 사용 여부 |
| `postgresql.persistence.size` | `10Gi` | PostgreSQL 스토리지 크기 |
| `postgresql.auth.database` | `unity_catalog` | 데이터베이스 이름 |
| `postgresql.auth.username` | `unity_catalog` | 사용자 이름 |
| `postgresql.auth.password` | `Argus!insight2026` | 비밀번호 |
| `resources.requests.memory` | `512Mi` | UC 메모리 요청 |
| `resources.limits.memory` | `2Gi` | UC 메모리 제한 |

### 주요 특징

- non-root(UID 65534)로 실행, initContainer로 데이터 디렉토리 권한 설정
- ConfigMap으로 server.properties 관리 (이미지 재빌드 없이 설정 변경 가능)
- PostgreSQL과 UC Server 모두 PVC로 데이터 영속성 보장
- PostgreSQL Deployment는 Recreate 전략 사용 (단일 인스턴스, 동시 접근 방지)
- Secret으로 PostgreSQL 비밀번호 관리
- initContainer `wait-for-db`로 PostgreSQL 기동 대기 후 UC Server 시작
- liveness/readiness probe로 헬스체크 구성

## Kubernetes (Kustomize) 배포

`kubernetes/` 디렉토리에 Kustomize 기반 매니페스트를 제공합니다. powerdns-service와 동일한 네이밍 규칙을 따릅니다.

```bash
kubectl apply -k kubernetes/
```

### 리소스 구성

| 파일 | 리소스 | 설명 |
|---|---|---|
| `namespace.yaml` | Namespace | `argus-insight` |
| `secret.yaml` | Secret | PostgreSQL 자격 증명 |
| `configmap.yaml` | ConfigMap | hibernate.properties, server.properties, 01-schema.sql |
| `pvc.yaml` | PVC x 2 | PostgreSQL 데이터 + UC 데이터 |
| `unity-catalog-db.yaml` | Deployment + Service | PostgreSQL (ClusterIP) |
| `unity-catalog-server.yaml` | Deployment + Service | UC Server (NodePort 31000) |

### 의존성 체인

```
PostgreSQL (unity-catalog-db)
  └──▶ Unity Catalog Server (unity-catalog-server)  [JDBC 연결, wait-for-db initContainer]
```

## Unity Catalog API

- API Base Path: `/api/2.1/unity-catalog`
- Swagger Docs: https://docs.unitycatalog.io/swagger-docs/
- 주요 리소스: Catalogs, Schemas, Tables, Volumes, Functions, Registered Models

### 인증 및 토큰

`server.authorization=enable` 설정 시 모든 API 호출에 Bearer 토큰이 필요합니다.

#### 1. Admin 토큰 확인 (개발/테스트 환경)

서버 기동 시 자동 생성되는 관리자 토큰을 사용합니다.

```bash
# Docker Compose
docker exec unity-catalog-server cat /home/unitycatalog/etc/conf/token.txt

# Kubernetes
kubectl exec -n argus-insight deploy/unity-catalog-server -- cat /home/unitycatalog/etc/conf/token.txt
```

#### 2. API 호출 시 토큰 사용

```bash
# 토큰을 변수에 저장
TOKEN=$(kubectl exec -n argus-insight deploy/unity-catalog-server -- cat /home/unitycatalog/etc/conf/token.txt)

# Catalog 목록 조회
curl -H "Authorization: Bearer $TOKEN" \
  http://<NODE_IP>:31000/api/2.1/unity-catalog/catalogs

# Schema 목록 조회
curl -H "Authorization: Bearer $TOKEN" \
  http://<NODE_IP>:31000/api/2.1/unity-catalog/schemas?catalog_name=unity
```

#### 3. CLI에서 토큰 사용

```bash
# 컨테이너 내부에서 CLI 실행
kubectl exec -n argus-insight deploy/unity-catalog-server -- \
  ./bin/uc --auth_token $(cat /home/unitycatalog/etc/conf/token.txt) catalog list
```

#### 4. 외부 IdP 연동 (프로덕션)

`server.properties`에서 OAuth2/OIDC 프로바이더를 설정하면 외부 토큰을 교환할 수 있습니다. Unity Catalog는 표준 OIDC를 지원하므로 Keycloak, Google, Okta 등의 프로바이더를 사용할 수 있습니다.

토큰 교환 엔드포인트: `POST /api/1.0/unity-control/auth/tokens`

#### 5. Keycloak 연동

##### Keycloak 설정

1. Realm 생성 (예: `unity-catalog`)
2. Client 생성:
   - Client type: `OpenID Connect`
   - Client authentication: `On` (Confidential)
   - Valid redirect URIs: `http://<UC_SERVER>:31000/*`
   - Web origins: `http://<UC_SERVER>:31000`
3. Client ID와 Client Secret을 기록

##### server.properties 설정

```properties
server.authorization=enable
server.authorization-url=https://<KEYCLOAK_HOST>/realms/<REALM>/protocol/openid-connect/auth
server.token-url=https://<KEYCLOAK_HOST>/realms/<REALM>/protocol/openid-connect/token
server.client-id=<client-id>
server.client-secret=<client-secret>
```

##### Kubernetes ConfigMap 예시

```yaml
# kubernetes/configmap.yaml 의 server.properties 섹션
server.properties: |
  server.env=dev
  server.authorization=enable
  server.authorization-url=https://keycloak.example.com/realms/unity-catalog/protocol/openid-connect/auth
  server.token-url=https://keycloak.example.com/realms/unity-catalog/protocol/openid-connect/token
  server.client-id=unity-catalog
  server.client-secret=<client-secret>
  server.cookie-timeout=P5D
```

설정 변경 후 재배포:

```bash
kubectl apply -k kubernetes/
kubectl rollout restart deploy/unity-catalog-server -n argus-insight
```

##### 주의사항

- v0.4.0에는 JWT issuer 검증 우회 취약점(GHSA-qqcj-rghw-829x, CVSS 9.1)이 존재합니다. 외부 노출 환경에서는 패치 버전 대기를 권장합니다.
- `server.authorization=enable` 설정 시 IdP URL이 비어 있으면 서버 기동에 실패합니다. IdP 없이 운영할 경우 `disable`로 설정하세요.

## 네이밍 규칙

### Docker 이미지

| 규칙 | 패턴 | 예시 |
|---|---|---|
| 이미지 이름 | `argus-insight/<component>:<version>` | `argus-insight/unity-catalog:0.4.0` |
| DB 이미지 | `argus-insight/<service>-<db>:<version>` | `argus-insight/unity-catalog-postgresql:17` |
| 레지스트리 포함 | `<registry>/argus-insight/<component>:<version>` | `zot.argus.local:5000/argus-insight/unity-catalog:0.4.0` |
| 저장 파일명 | `<component>-<version>.tar.gz` | `unity-catalog-0.4.0.tar.gz` |

### Docker 볼륨

| 규칙 | 패턴 | 예시 |
|---|---|---|
| Docker Compose | `argus-unity-catalog-<용도>` | `argus-unity-catalog-data`, `argus-unity-catalog-pgdata` |

### Kubernetes 리소스

| 리소스 | UC Server | PostgreSQL |
|---|---|---|
| Deployment | `unity-catalog-server` | `unity-catalog-db` |
| Service | `unity-catalog-server` (NodePort) | `unity-catalog-db` (ClusterIP) |
| ConfigMap | `unity-catalog-config` | — |
| Secret | `unity-catalog-secrets` | — |
| PVC | `argus-unity-catalog-data` | `argus-unity-catalog-pgdata` |

### 포트 할당

| 프로토콜 | Docker 호스트 포트 | 컨테이너 포트 | K8s NodePort | 설명 |
|---|---|---|---|---|
| HTTP | `31000` | `8080` | `31000` | Unity Catalog REST API |
| PostgreSQL | `5432` | `5432` | — (ClusterIP) | PostgreSQL (내부 전용) |

## 코드 컨벤션

- `nfpm.yaml`의 `maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- Dockerfile의 `LABEL maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `nfpm.yaml`에서 `__PLACEHOLDER__` 패턴 사용, Makefile의 `sed`로 `versions.env` 값을 치환하여 빌드
- `versions.env`에서 모든 컴포넌트 버전을 중앙 관리
- Makefile의 `DOCKER_REGISTRY` 변수로 레지스트리 주소를 주입 (기본값: `argus-insight`)
