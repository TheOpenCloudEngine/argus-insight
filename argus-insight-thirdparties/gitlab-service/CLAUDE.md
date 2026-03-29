# GitLab Service

GitLab CE(Community Edition) 17.9.1을 Docker 및 Kubernetes 환경에 배포하는 프로젝트입니다. Argus Insight 플랫폼의 Git 저장소 관리 서비스로, 화면에서 작성한 코드를 Git을 통해 버전 관리하고 CI/CD 파이프라인을 실행합니다. OpenID Connect 기반 SSO 연동을 지원하여 Argus Insight와 통합 인증을 구성할 수 있습니다. Airgap 환경을 지원하기 위해 공식 이미지를 Dockerfile wrapper로 빌드하여 프라이빗 레지스트리(Zot)에 배포합니다.

## 프로젝트 구조

```
gitlab-service/
├── CLAUDE.md                        # 이 파일
├── Makefile                         # Docker 이미지 빌드/푸시/저장 오케스트레이션
├── versions.env                     # 컴포넌트 버전 핀
├── .gitignore
├── .dockerignore
├── gitlab-ce/
│   ├── Dockerfile                   # FROM gitlab/gitlab-ce, gitlab.rb 내장
│   └── gitlab.rb                    # GitLab Omnibus 기본 설정 (이미지 내장용)
├── gitlab-runner/
│   └── Dockerfile                   # FROM gitlab/gitlab-runner
├── docker/
│   ├── docker-compose.yml           # Docker Compose 오케스트레이션
│   └── gitlab.rb                    # GitLab Omnibus 설정 파일 (bind mount 오버라이드용)
├── kubernetes/
│   ├── kustomization.yaml           # Kustomize 엔트리포인트
│   ├── namespace.yaml               # argus-insight 네임스페이스
│   ├── secret.yaml                  # root 비밀번호, Runner 토큰, OIDC secret
│   ├── configmap.yaml               # gitlab.rb를 ConfigMap으로 관리
│   ├── pvc.yaml                     # 영구 볼륨 (argus-gitlab-config/logs/data)
│   ├── gitlab.yaml                  # GitLab Deployment + Service
│   ├── gitlab-runner.yaml           # GitLab Runner Deployment
│   └── ingress.yaml                 # nginx Ingress
└── dist/                            # 빌드 산출물 (gitignored)
    └── gitlab-*.tar.gz              # docker save 이미지
```

## 빌드 방법

```bash
# Docker 이미지 빌드
make docker                  # gitlab-ce + gitlab-runner 전체 빌드
make docker-gitlab-ce        # GitLab CE만 빌드
make docker-gitlab-runner    # GitLab Runner만 빌드

# 프라이빗 레지스트리 푸시
make docker-push                                                    # 기본 (argus-insight/ prefix)
make docker-push DOCKER_REGISTRY=zot.argus.local:5000/argus-insight # Zot Registry 지정

# Airgap 환경용 이미지 저장/로드
make docker-save             # dist/ 에 tar.gz 저장
make docker-load             # tar.gz 에서 이미지 로드

# 정리
make clean                   # dist/ 삭제

# Docker Compose
cd docker
docker compose --env-file ../versions.env up --build -d

# Kubernetes
kubectl apply -k kubernetes/
kubectl get all -n argus-insight -l app.kubernetes.io/name=gitlab
```

## 초기 관리자 계정

| 항목 | 값 |
|---|---|
| 사용자명 | `root` (GitLab CE 고정, 변경 불가) |
| 비밀번호 | `Argus!nsight2026` |

- 최초 로그인 후 반드시 비밀번호를 변경하세요
- 비밀번호는 `gitlab.rb`의 `initial_root_password`, Kubernetes에서는 `secret.yaml`의 `initial_root_password`에서 설정
- GitLab 비밀번호 정책: 최소 8자 이상

## 버전 관리

`versions.env` 파일에서 모든 컴포넌트 버전을 관리합니다. 버전 변경 후 `make docker`로 재빌드합니다.

```
GITLAB_VERSION=17.9.1-ce.0
GITLAB_RUNNER_VERSION=v17.9.1
```

## Docker 이미지

Airgap 환경을 지원하기 위해 공식 이미지를 Dockerfile wrapper로 빌드하여 기본 설정(`gitlab.rb`)을 이미지에 내장합니다. 런타임에 bind mount 또는 ConfigMap으로 설정을 오버라이드할 수 있습니다.

| 공식 이미지 | Argus 이미지 | 설명 |
|---|---|---|
| `gitlab/gitlab-ce:17.9.1-ce.0` | `argus-insight/gitlab-ce:17.9.1-ce.0` | GitLab CE + 기본 gitlab.rb 내장 |
| `gitlab/gitlab-runner:v17.9.1` | `argus-insight/gitlab-runner:v17.9.1` | GitLab Runner |

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

1. 인터넷 환경에서 `make docker && make docker-save`
2. `dist/*.tar.gz` 파일을 Airgap 환경으로 전달 (USB, SCP 등)
3. Airgap 환경에서 `make docker-load`
4. 필요시 `docker tag` + `docker push`로 Zot Registry에 등록

## 설정 파일

### gitlab.rb

GitLab Omnibus의 전체 설정을 관리하는 Ruby 파일입니다. 두 곳에 존재합니다:

| 파일 | 용도 |
|---|---|
| `gitlab-ce/gitlab.rb` | Docker 이미지 빌드 시 내장되는 기본 설정 |
| `docker/gitlab.rb` | Docker Compose에서 bind mount로 오버라이드하는 설정 |

Kubernetes 환경에서는 `configmap.yaml`에 인라인으로 포함됩니다.

#### 주요 설정 섹션

| 섹션 | 설정 | 기본값 | 설명 |
|---|---|---|---|
| External URL | `external_url` | `http://gitlab.argus.local` | GitLab 접근 URL (실제 도메인으로 변경 필요) |
| Rails | `time_zone` | `Asia/Seoul` | 시간대 |
| Rails | `gitlab_shell_ssh_port` | `2224` (Docker) / `22` (K8s) | SSH 포트 |
| Rails | `initial_root_password` | `Argus!nsight2026` | 초기 root 비밀번호 (최초 로그인 후 변경) |
| Nginx | `listen_port` | `80` | 내부 HTTP 포트 |
| Nginx | `listen_https` | `false` | HTTPS 비활성화 (리버스 프록시에서 TLS 종료) |
| PostgreSQL | `shared_buffers` | `256MB` | 내장 PostgreSQL 버퍼 크기 |
| Puma | `worker_processes` | `2` | 웹 서버 워커 수 |
| Puma | `max_threads` | `4` | 워커당 최대 스레드 수 |
| Sidekiq | `max_concurrency` | `10` | 백그라운드 작업 동시 처리 수 |
| Monitoring | `prometheus['enable']` | `false` | 내장 Prometheus 비활성화 (Argus Prometheus 사용) |
| Registry | `registry['enable']` | `false` | 컨테이너 레지스트리 비활성화 (Argus Zot Registry 사용) |
| Pages | `gitlab_pages['enable']` | `false` | GitLab Pages 비활성화 |
| Backup | `backup_keep_time` | `604800` | 백업 보관 기간 (7일, 초 단위) |

### 비활성화된 번들 서비스

GitLab Omnibus에는 여러 서비스가 번들로 포함되어 있으나, Argus Insight 플랫폼의 기존 서비스와 중복을 피하기 위해 다음을 비활성화합니다:

| 번들 서비스 | 상태 | 대체 서비스 |
|---|---|---|
| Prometheus | 비활성화 | `argus-insight-thirdparties/prometheus-service` |
| Grafana | 비활성화 | Argus 대시보드 |
| Container Registry | 비활성화 | `argus-insight-thirdparties/zot-registry-service` |
| GitLab Pages | 비활성화 | 사용하지 않음 |

## SSO 연동 (OpenID Connect)

GitLab의 OmniAuth를 통해 OpenID Connect 기반 SSO를 지원합니다. `gitlab.rb`에 설정이 주석 처리되어 있으며, Keycloak 등의 Identity Provider와 연동할 때 주석을 해제하고 설정합니다.

### 설정 절차

1. Identity Provider(Keycloak 등)에 GitLab 클라이언트 등록
   - Client ID: `gitlab`
   - Redirect URI: `http://gitlab.argus.local/users/auth/openid_connect/callback`
   - Scope: `openid`, `profile`, `email`
2. `gitlab.rb`의 `omniauth_providers` 섹션 주석 해제
3. `issuer`, `identifier`, `secret` 값을 실제 IdP 정보로 교체
4. GitLab 재시작: `gitlab-ctl reconfigure`

### 주요 OmniAuth 설정

| 설정 | 값 | 설명 |
|---|---|---|
| `omniauth_enabled` | `true` | OmniAuth 활성화 |
| `omniauth_allow_single_sign_on` | `['openid_connect']` | OIDC로 자동 계정 생성 허용 |
| `omniauth_block_auto_created_users` | `false` | 자동 생성된 사용자 즉시 활성화 |
| `omniauth_auto_link_user` | `['openid_connect']` | 기존 사용자와 OIDC 계정 자동 연결 |

## Docker Compose 배포

### 컨테이너 구성

| 서비스 | 이미지 | 포트 매핑 | 설명 |
|---|---|---|---|
| `gitlab` | `argus-insight/gitlab-ce:17.9.1-ce.0` | `8929:80`, `8443:443`, `2224:22` | GitLab CE 서버 |
| `gitlab-runner` | `argus-insight/gitlab-runner:v17.9.1` | - | CI/CD Runner |

### Docker 볼륨

| 볼륨 이름 | 컨테이너 경로 | 용도 |
|---|---|---|
| `argus-gitlab-config` | `/etc/gitlab` | GitLab 설정 파일 |
| `argus-gitlab-logs` | `/var/log/gitlab` | 로그 파일 |
| `argus-gitlab-data` | `/var/opt/gitlab` | Git 저장소, DB, 업로드 등 전체 데이터 |
| `argus-gitlab-runner-config` | `/etc/gitlab-runner` | Runner 설정 |

### 헬스체크

GitLab 컨테이너는 `gitlab-healthcheck` 명령으로 헬스체크를 수행합니다:
- 주기: 60초
- 타임아웃: 30초
- 재시도: 5회
- 시작 대기: 300초 (GitLab 초기화에 시간이 소요됨)

### GitLab Runner 등록

GitLab이 기동된 후 Runner를 등록합니다:

```bash
docker compose exec gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab:80" \
  --registration-token "REGISTRATION_TOKEN" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --description "argus-runner"
```

Registration Token은 GitLab Admin > CI/CD > Runners 에서 확인합니다.

## Kubernetes 배포

### 리소스 구성

| 리소스 | 이름 | 설명 |
|---|---|---|
| Namespace | `argus-insight` | 전용 네임스페이스 (다른 서비스와 공유) |
| Secret | `gitlab-secrets` | root 비밀번호, Runner 토큰, OIDC secret |
| ConfigMap | `gitlab-config` | gitlab.rb 설정 파일 |
| PVC | `argus-gitlab-config` | 설정 파일 (1Gi, ReadWriteOnce) |
| PVC | `argus-gitlab-logs` | 로그 파일 (5Gi, ReadWriteOnce) |
| PVC | `argus-gitlab-data` | 데이터 (50Gi, ReadWriteOnce) |
| Deployment + Service | `gitlab` | 포트 80 (HTTP), 443 (HTTPS), 22 (SSH) |
| Deployment | `gitlab-runner` | CI/CD Runner |
| Ingress | `gitlab` | nginx Ingress (`gitlab.argus.local`) |

### 배포 전 필수 설정

1. **secret.yaml**: `initial_root_password`, `runner_registration_token`, `oidc_client_secret`을 실제 값으로 변경
2. **configmap.yaml**: `external_url`을 실제 도메인으로 변경
3. **ingress.yaml**: `host`를 실제 도메인으로 변경, TLS 필요 시 `tls` 섹션 주석 해제
4. **pvc.yaml**: 스토리지 크기 조정 (기본 data 50Gi)
5. **gitlab.yaml, gitlab-runner.yaml**: 이미지 경로를 프라이빗 레지스트리 주소로 변경

### 리소스 요구사항

| 컴포넌트 | CPU 요청 | CPU 제한 | 메모리 요청 | 메모리 제한 |
|---|---|---|---|---|
| GitLab | 1 | 4 | 4Gi | 8Gi |
| GitLab Runner | 250m | 1 | 256Mi | 1Gi |

### Probe 설정

GitLab은 Omnibus 패키지 특성상 기동에 시간이 오래 걸리므로 probe 설정에 주의가 필요합니다:

| Probe | 경로 | 초기 대기 | 주기 | 설명 |
|---|---|---|---|---|
| startupProbe | `/-/liveness` | 60s | 10s (최대 30회) | 최초 기동 완료 대기 (최대 5분) |
| livenessProbe | `/-/liveness` | 300s | 30s | 프로세스 정상 동작 확인 |
| readinessProbe | `/-/readiness` | 120s | 15s | 트래픽 수신 가능 여부 |

### Ingress 설정

nginx Ingress Controller를 사용하며, Git push 등 대용량 요청을 위해 다음 annotation이 적용됩니다:

| Annotation | 값 | 설명 |
|---|---|---|
| `proxy-body-size` | `512m` | 최대 요청 본문 크기 (대용량 push 허용) |
| `proxy-read-timeout` | `600` | 읽기 타임아웃 (초) |
| `proxy-connect-timeout` | `60` | 연결 타임아웃 (초) |
| `proxy-send-timeout` | `600` | 전송 타임아웃 (초) |

## Argus Insight 연동

### argus-insight-server에서 GitLab API 호출

`python-gitlab` 라이브러리(LGPL-3.0)를 사용하여 argus-insight-server에서 GitLab API를 호출합니다:

- 프로젝트 생성/삭제/목록 조회
- 저장소 파일 읽기/쓰기/커밋
- Merge Request 관리
- CI/CD 파이프라인 조회

### argus-insight-server에서 Git 저장소 조작

`GitPython` 라이브러리를 사용하여 로컬 Git 저장소를 조작합니다:

- clone, add, commit, push, pull
- branch 생성/삭제/전환
- diff, log 조회

## 백업 및 복원

### 백업

```bash
# Docker
docker compose exec gitlab gitlab-backup create

# Kubernetes
kubectl exec -n argus-insight deploy/gitlab -- gitlab-backup create
```

백업 파일은 `/var/opt/gitlab/backups/`에 저장되며, 7일간 보관됩니다 (`backup_keep_time: 604800`).

### 복원

```bash
# Docker
docker compose exec gitlab gitlab-backup restore BACKUP=<timestamp>

# Kubernetes
kubectl exec -n argus-insight deploy/gitlab -- gitlab-backup restore BACKUP=<timestamp>
```

## 네이밍 규칙

### Docker 이미지

| 규칙 | 패턴 | 예시 |
|---|---|---|
| 이미지 이름 | `argus-insight/<component>:<version>` | `argus-insight/gitlab-ce:17.9.1-ce.0` |
| 레지스트리 포함 | `<registry>/argus-insight/<component>:<version>` | `zot.argus.local:5000/argus-insight/gitlab-ce:17.9.1-ce.0` |
| 저장 파일명 | `<component>-<version>.tar.gz` | `gitlab-ce-17.9.1-ce.0.tar.gz` |

### Docker 볼륨

| 규칙 | 패턴 | 예시 |
|---|---|---|
| Docker Compose | `argus-gitlab-<용도>` | `argus-gitlab-config`, `argus-gitlab-logs`, `argus-gitlab-data` |
| Runner | `argus-gitlab-runner-<용도>` | `argus-gitlab-runner-config` |

### Kubernetes 리소스

| 리소스 | 패턴 | 예시 |
|---|---|---|
| PVC | `argus-gitlab-<용도>` | `argus-gitlab-config`, `argus-gitlab-logs`, `argus-gitlab-data` |
| Secret | `gitlab-secrets` | — |
| ConfigMap | `gitlab-config` | — |
| Deployment | `gitlab`, `gitlab-runner` | — |
| Service | `gitlab` | — |
| Ingress | `gitlab` | — |

### Kubernetes 라벨

| 라벨 | 값 | 설명 |
|---|---|---|
| `app.kubernetes.io/name` | `gitlab` 또는 `gitlab-runner` | 컴포넌트 식별 |
| `app.kubernetes.io/component` | `config`, `logs`, `data` | PVC 용도 구분 |
| `app.kubernetes.io/part-of` | `argus-insight` | 플랫폼 소속 |

### 호스트명 및 URL

| 항목 | 패턴 | 예시 |
|---|---|---|
| External URL | `http://gitlab.<도메인>` | `http://gitlab.argus.local` |
| Ingress Host | `gitlab.<도메인>` | `gitlab.argus.local` |
| K8s 내부 DNS | `gitlab.argus-insight.svc.cluster.local` | — |
| SSH Clone URL | `ssh://git@gitlab.<도메인>:<port>/<group>/<project>.git` | `ssh://git@gitlab.argus.local:2224/argus/my-repo.git` |
| HTTP Clone URL | `http://gitlab.<도메인>/<group>/<project>.git` | `http://gitlab.argus.local/argus/my-repo.git` |

### 포트 할당

| 프로토콜 | Docker 호스트 포트 | 컨테이너 포트 | 설명 |
|---|---|---|---|
| HTTP | `8929` | `80` | GitLab Web UI |
| HTTPS | `8443` | `443` | GitLab Web UI (TLS) |
| SSH | `2224` | `22` | Git SSH |

## 코드 컨벤션

- Dockerfile의 `LABEL maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `versions.env`에서 모든 컴포넌트 버전을 중앙 관리
- Makefile의 `DOCKER_REGISTRY` 변수로 레지스트리 주소를 주입 (기본값: `argus-insight`)

## Argus Insight 운영 환경 배포 (Docker Compose)

### 배포 환경

| 항목 | 값 |
|------|-----|
| 서버 | dev-server (10.0.1.50) |
| 도메인 | dev.net |
| External URL | `http://gitlab-global.dev.net` |
| HTTP 포트 | 8929 (호스트) → 80 (컨테이너) |
| SSH 포트 | 2224 (호스트) → 22 (컨테이너) |
| 초기 관리자 | root / Argus!nsight2026 |

### 배포 절차

```bash
# 1. gitlab.rb에서 external_url 확인/수정
cd argus-insight-thirdparties/gitlab-service/docker
# external_url은 'http://gitlab-global.dev.net'으로 설정되어 있음

# 2. GitLab 기동 (초기화 3~5분 소요)
docker compose --env-file ../versions.env up -d gitlab

# 3. healthy 상태 확인
docker compose ps
# STATUS가 "Up (healthy)"로 변경될 때까지 대기

# 4. GitLab Runner 기동 (GitLab이 healthy 상태 후)
docker compose --env-file ../versions.env up -d gitlab-runner

# 5. PowerDNS에 DNS 레코드 등록 (Argus UI > Settings > Domain에서 설정된 PowerDNS 사용)
# gitlab-global.dev.net → 10.0.1.50 A 레코드 등록

# 6. 브라우저에서 GitLab 접속
# http://gitlab-global.dev.net:8929
# root / Argus!nsight2026 으로 로그인

# 7. Personal Access Token 생성
# User Settings > Access Tokens
# - Token name: argus-insight-service
# - Scopes: api, read_repository, write_repository
# - Create personal access token → glpat-xxx 복사

# 8. Argus Insight UI에서 GitLab 연동 설정
# Settings > Argus > GitLab
# - Server URL: http://gitlab-global.dev.net:8929
# - Private Token: glpat-xxx (위에서 생성한 토큰)
# - Group Path: workspaces
# - Test Connection으로 연결 확인 후 Save
```

### 컨테이너 관리

```bash
cd argus-insight-thirdparties/gitlab-service/docker

# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f gitlab
docker compose logs -f gitlab-runner

# 재시작
docker compose --env-file ../versions.env restart gitlab

# 중지
docker compose --env-file ../versions.env stop

# 완전 삭제 (데이터 포함)
docker compose --env-file ../versions.env down -v
```

### Argus Insight 연동 구조

```
Argus UI (Settings > Argus > GitLab)
  │  Save URL + Token
  ▼
Argus Server (app/settings → load_gitlab_settings)
  │  python-gitlab API 호출
  ▼
GitLab CE (docker-gitlab-1:8929)
  │  프로젝트 생성/삭제/커밋
  ▼
Workspace Provisioning
  ├── GitLabCreateProjectStep: workspaces/{ws-name} 프로젝트 생성
  ├── 초기 디렉토리 구조 커밋 (airflow/dags, notebooks, vscode, mlflow)
  └── Airflow git-sync: GitLab repo에서 DAG 자동 동기화
```

## 주의사항

- GitLab CE는 리소스를 많이 소비합니다 (최소 CPU 2코어, RAM 4GB 권장)
- 최초 기동 시 3~5분이 소요되며, 이 시간 동안 502 에러가 발생할 수 있습니다
- `external_url`은 반드시 실제 접근 가능한 URL로 설정해야 합니다 (SSH clone URL, 이메일 링크 등에 사용)
- 내장 PostgreSQL을 사용하므로 별도의 외부 DB가 필요하지 않습니다
- Kubernetes 환경에서는 Deployment strategy가 `Recreate`로 설정되어 있습니다 (데이터 볼륨 동시 접근 방지)
- Airgap 환경에서는 `make docker-save`로 이미지를 저장한 후 물리적으로 전달하여 `make docker-load`로 로드합니다
