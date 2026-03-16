# Unity Catalog Packaging

[Unity Catalog](https://www.unitycatalog.io/) v0.4.0의 소스 코드를 빌드하여 RPM/Debian 패키지, Docker 이미지, Helm 차트로 빌드 및 배포하는 프로젝트입니다. [nfpm](https://github.com/goreleaser/nfpm)을 사용하여 단일 YAML 설정에서 두 포맷의 패키지를 동시에 생성하고, Multi-stage Dockerfile로 Docker 이미지를 빌드하며, Helm 차트를 제공합니다.

## 프로젝트 구조

```
unity-catalog-service/
├── CLAUDE.md
├── Makefile                      # 빌드 오케스트레이션
├── versions.env                  # 컴포넌트 버전 핀
├── .gitignore
├── .dockerignore
├── common/scripts/               # 패키지 설치/제거 scriptlet
│   ├── preinstall.sh             # unitycatalog 시스템 사용자 생성
│   ├── postinstall.sh            # systemctl daemon-reload, enable, 디렉토리 생성
│   ├── preremove.sh              # 서비스 stop/disable
│   └── postremove.sh             # systemctl daemon-reload
├── server/
│   ├── Dockerfile                # Multi-stage Docker 빌드 (소스에서 빌드)
│   ├── nfpm.yaml                 # 패키지 정의 (RPM/DEB)
│   ├── unitycatalog-server.service   # systemd unit
│   ├── unitycatalog-server.default   # /etc/default (CLI 옵션)
│   └── server.properties         # 기본 설정 파일
├── docker-compose.yml            # Docker Compose 오케스트레이션
├── helm/
│   └── unity-catalog/            # Helm 차트
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── pvc.yaml
│           └── NOTES.txt
└── dist/                         # 빌드 산출물 (gitignored)
    ├── build/                    # 빌드된 바이너리
    └── packages/                 # 생성된 .rpm, .deb 파일
```

## 빌드 방법

```bash
make all          # 전체 빌드 (소스 다운로드 + 빌드 + RPM + DEB)
make build        # 소스 빌드만 (Docker 컨테이너에서 sbt 빌드)
make rpm          # RPM만 빌드
make deb          # DEB만 빌드
make packages     # RPM + DEB 모두 빌드
make clean        # dist/ 삭제

# Docker
make docker       # Docker 이미지 빌드
make docker-push  # 이미지 레지스트리 push

# Docker Compose
docker compose --env-file versions.env up --build -d

# Helm
make helm-package                     # Helm 차트 패키징
helm install unity-catalog helm/unity-catalog  # Helm 배포
```

빌드 시 nfpm 바이너리가 자동으로 다운로드됩니다. RPM/DEB 빌드는 Docker 컨테이너 안에서 소스를 컴파일하므로 빌드 호스트에 JDK가 필요하지 않습니다. 빌드 호스트에 `curl`, `tar`, `make`, `docker`가 필요합니다.

## 버전 관리

`versions.env` 파일에서 Unity Catalog 버전을 관리합니다. 버전을 변경한 후 `make clean && make all`로 재빌드합니다.

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

## Docker 이미지

Multi-stage build로 소스 코드에서 빌드합니다. `versions.env`의 버전을 `--build-arg`로 주입합니다.

- Base image: `amazoncorretto:17-alpine` (빌드), `alpine:3.21` (런타임)
- 이미지 네이밍: `argus-insight/unity-catalog:<version>`
- 바이너리 경로, 설정 파일 경로, 실행 사용자 등은 RPM/DEB 패키지와 동일
- 데이터 볼륨: `/var/lib/unity-catalog`

## Helm 차트

`helm/unity-catalog/` 디렉토리에 표준 Helm 차트를 제공합니다.

### 주요 설정 (values.yaml)

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `image.repository` | `argus-insight/unity-catalog` | Docker 이미지 |
| `image.tag` | `0.4.0` | 이미지 태그 |
| `service.type` | `ClusterIP` | Service 타입 |
| `service.port` | `8080` | 포트 |
| `persistence.enabled` | `true` | PVC 사용 여부 |
| `persistence.size` | `10Gi` | 스토리지 크기 |
| `resources.requests.memory` | `512Mi` | 메모리 요청 |
| `resources.limits.memory` | `2Gi` | 메모리 제한 |

### 주요 특징

- non-root(UID 65534)로 실행, initContainer로 데이터 디렉토리 권한 설정
- ConfigMap으로 server.properties 관리 (이미지 재빌드 없이 설정 변경 가능)
- PVC로 데이터 영속성 보장
- liveness/readiness probe로 헬스체크 구성

## Unity Catalog API

- API Base Path: `/api/2.1/unity-catalog`
- Swagger Docs: https://docs.unitycatalog.io/swagger-docs/
- 주요 리소스: Catalogs, Schemas, Tables, Volumes, Functions, Registered Models

## 코드 컨벤션

- `nfpm.yaml`의 `maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `nfpm.yaml`에서 `__PLACEHOLDER__` 패턴 사용, Makefile의 `sed`로 `versions.env` 값을 치환하여 빌드
