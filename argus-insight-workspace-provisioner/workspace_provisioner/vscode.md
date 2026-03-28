# VS Code Server — 운영 가이드

## 개요

Argus Insight의 VS Code Server는 사용자별로 독립된 브라우저 기반 VS Code 개발 환경을 Kubernetes 클러스터에 배포합니다. 각 인스턴스는 S3(MinIO) 기반 영구 워크스페이스 스토리지와 Nginx Ingress 기반 인증을 포함합니다.

### 아키텍처

```
[브라우저] ── https://argus-vscode-{user}.{domain} ──▶ [Nginx Ingress]
                                                            │
                                             auth-url 서브리퀘스트
                                                            │
                                                            ▼
                                          [Argus Server :4500/auth-verify]
                                             Cookie: argus_app_token 검증
                                                            │
                                               200 OK ──▶ 프록시 통과
                                                            │
                                                            ▼
                                          ┌──────────────────────────────┐
                                          │  Pod: argus-vscode-{user}    │
                                          │  ┌────────────┐ ┌─────────┐ │
                                          │  │ code-server │ │  s3fs   │ │
                                          │  │  :8080      │ │  mount  │ │
                                          │  │ /workspace ◄┼─┤ MinIO   │ │
                                          │  └────────────┘ └─────────┘ │
                                          │     emptyDir (bidirectional) │
                                          └──────────────────────────────┘
```

---

## 사전 요구사항

### Kubernetes 클러스터
- K3s 또는 표준 K8s (kubectl 접근 가능)
- Nginx Ingress Controller 설치 및 80/443 포트 바인딩
- Ingress Controller의 LoadBalancer 또는 externalIPs 설정

### 인프라 서비스
| 서비스 | 설정 위치 (UI) | 필수 항목 |
|--------|---------------|-----------|
| **Object Storage (MinIO/S3)** | Settings > Argus > Object Storage | endpoint, access_key, secret_key |
| **PowerDNS** | Settings > Domain | pdns_ip, pdns_port, pdns_api_key, domain_name |
| **DNS Resolver** | 서버 `/etc/resolv.conf` 또는 netplan | PowerDNS IP를 nameserver로 등록 |

### 서버 설정
- `argus-insight-server`가 포트 4500에서 실행 중
- 서버에서 `kubectl` 명령이 클러스터에 접근 가능
- PowerDNS에서 서버 IP로 와일드카드 DNS 또는 개별 A 레코드 resolve 가능

---

## 데이터베이스 테이블

### argus_apps (앱 카탈로그)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | 자동 증가 ID |
| app_type | VARCHAR(50) UNIQUE | 앱 식별자 (예: `vscode`) |
| display_name | VARCHAR(100) | 표시명 (예: `VS Code Server`) |
| description | VARCHAR(500) | 설명 |
| icon | VARCHAR(50) | Lucide 아이콘명 (예: `Code`) |
| template_dir | VARCHAR(100) | K8s 템플릿 디렉토리명 |
| default_namespace | VARCHAR(255) | 기본 K8s 네임스페이스 (기본: `argus-apps`) |
| hostname_pattern | VARCHAR(255) | 호스트네임 패턴 (예: `argus-vscode-{username}.{domain}`) |
| enabled | BOOLEAN | 활성화 여부 |

### argus_app_instances (인스턴스)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | 자동 증가 ID |
| app_id | INT FK → argus_apps | 앱 참조 |
| user_id | INT FK → argus_users | 사용자 참조 |
| username | VARCHAR(100) | 사용자명 |
| app_type | VARCHAR(50) | 앱 타입 (denormalized) |
| domain | VARCHAR(255) | 도메인 (예: `dev.net`) |
| k8s_namespace | VARCHAR(255) | K8s 네임스페이스 |
| hostname | VARCHAR(500) | 전체 호스트네임 |
| status | VARCHAR(20) | `deploying` / `running` / `failed` / `deleting` / `deleted` |
| deploy_steps | TEXT | 배포/삭제 단계 진행 JSON |
| UNIQUE | (app_id, user_id) | 사용자당 앱별 1개 인스턴스 |

---

## API 엔드포인트

### 인스턴스 관리 (`/api/v1/apps/instances/{app_type}`)

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/status` | JWT | 내 인스턴스 상태 + 배포 단계 |
| POST | `/launch` | JWT | 인스턴스 배포 |
| DELETE | `/destroy` | JWT | 인스턴스 삭제 |
| GET | `/auth-launch` | JWT | 앱 접속용 토큰 발급 |
| GET | `/auth-redirect?token=xxx` | 없음 | 쿠키 설정 + 리다이렉트 (브라우저 직접 접속) |
| GET | `/auth-verify` | Cookie | Nginx auth-url 서브리퀘스트 검증 |

### 앱 카탈로그 (`/api/v1/apps/registry`)

| Method | Path | 인증 | 설명 |
|--------|------|------|------|
| GET | `/` | JWT | 등록된 앱 목록 |
| POST | `/` | Admin | 앱 등록 |
| PUT | `/{app_type}` | Admin | 앱 수정 |
| DELETE | `/{app_type}` | Admin | 앱 삭제 |

---

## 배포 절차 (Launch)

사용자가 UI에서 "Launch VS Code"를 클릭하면 다음 단계가 순서대로 실행됩니다:

### 1. Prepare S3 storage
- S3/MinIO 설정 로드 (Settings > Argus > Object Storage)
- `user-{username}` 버킷 생성 (이미 존재하면 skip)

### 2. Create namespace
- K8s 네임스페이스 생성 (`argus-apps`, 이미 존재하면 skip)
- `kubectl create namespace argus-apps --dry-run=client -o yaml | kubectl apply -f -`

### 3. Apply K8s manifests
K8s 리소스 3개를 순서대로 생성:

**Secret** (`argus-vscode-{username}`)
- S3 access key / secret key 저장

**Deployment** (`argus-vscode-{username}`)
- `codercom/code-server:4.96.4` 컨테이너 (포트 8080, auth 비활성)
- `efrecon/s3fs:1.94` 사이드카 (FUSE 마운트, privileged)
- 리소스: 500m/512Mi 요청, 1CPU/2Gi 제한
- Readiness probe: GET /healthz

**Service + Ingress** (`argus-vscode-{username}`)
- ClusterIP 서비스 (포트 8080)
- Nginx Ingress (auth-url → Argus Server auth-verify 엔드포인트)

### 4. Register DNS
- PowerDNS API로 A 레코드 등록
- `argus-vscode-{username}.{domain}` → 서버 IP
- TTL: 300초

### 5. Wait for deployment ready
- `kubectl rollout status deployment/argus-vscode-{username}` 실행
- 최대 180초 대기
- 타임아웃 시 status → `failed`

### 템플릿 변수

배포 시 K8s 매니페스트에 치환되는 변수:

| 변수 | 예시 값 | 출처 |
|------|---------|------|
| `${USERNAME}` | `admin` | 로그인 사용자명 |
| `${K8S_NAMESPACE}` | `argus-apps` | argus_apps.default_namespace |
| `${HOSTNAME}` | `argus-vscode-admin.dev.net` | hostname_pattern + domain |
| `${DOMAIN}` | `dev.net` | Settings > Domain > domain_name |
| `${S3_ENDPOINT}` | `http://10.0.1.50:51000` | Settings > Argus > Object Storage |
| `${S3_ACCESS_KEY}` | `minioadmin` | Settings > Argus > Object Storage |
| `${S3_SECRET_KEY}` | `minioadmin` | Settings > Argus > Object Storage |
| `${S3_USE_SSL}` | `false` | Settings > Argus > Object Storage |
| `${ARGUS_SERVER_HOST}` | `10.0.1.50` | PowerDNS 설정의 pdns_ip |
| `${APP_TYPE}` | `vscode` | argus_apps.app_type |

---

## 삭제 절차 (Destroy)

사용자가 UI에서 "Destroy"를 클릭하면 다음 단계가 순서대로 실행됩니다:

### 1. Delete K8s resources
- `kubectl delete -f - --ignore-not-found`로 매니페스트의 모든 리소스 삭제
- Ingress, Service, Deployment, Secret 순서로 삭제

### 2. Verify pods terminated
- 3초 간격으로 Pod 존재 여부 폴링
- 최대 60초 대기
- 라벨 필터: `app.kubernetes.io/name=code-server,app.kubernetes.io/instance={username}`

### 3. Delete DNS record
- PowerDNS API로 A 레코드 삭제
- `changetype: DELETE`

> **참고**: 삭제는 best-effort 방식으로 동작합니다. 한 단계가 실패해도 다음 단계를 계속 실행합니다. S3 버킷의 파일은 삭제되지 않으며 보존됩니다.

---

## 인증 플로우

### 접속 흐름 (Open VS Code 클릭 시)

```
1. [UI] GET /api/v1/apps/instances/vscode/auth-launch  (JWT 인증)
   ← { token: "eyJ..." }

2. [UI] window.open → http://{server}:4500/api/v1/apps/instances/vscode/auth-redirect?token=eyJ...
   (브라우저가 백엔드 서버에 직접 접속, Next.js 프록시 우회)

3. [Server] 토큰 검증 → Set-Cookie: argus_app_token=eyJ...; domain=.{domain}
   ← 302 Redirect → https://argus-vscode-{username}.{domain}

4. [Nginx Ingress] auth-url 서브리퀘스트
   → GET /api/v1/apps/instances/vscode/auth-verify
   쿠키 전달 + X-Original-URL 헤더에서 호스트 추출
   ← 200 OK → code-server로 프록시
```

### 토큰 구조

**앱 토큰** (HMAC-SHA256 서명, base64 인코딩):
```json
{
  "payload": {
    "sub": "admin",
    "app_type": "vscode",
    "role": "admin",
    "exp": 1774793592
  },
  "sig": "a83c55b348fae0fe3701c9e3cdebd1af..."
}
```

- 유효기간: 24시간
- 쿠키명: `argus_app_token`
- 쿠키 도메인: `.{domain}` (예: `.dev.net`)

---

## K8s 리소스 구조

### 네임스페이스

```
argus-apps                    # 모든 앱 인스턴스가 배포되는 네임스페이스
```

### 사용자별 리소스 (username=admin 예시)

```
argus-apps/
├── Secret/argus-vscode-admin          # S3 인증 정보
├── Deployment/argus-vscode-admin      # code-server + s3fs Pod
│   └── Pod/argus-vscode-admin-xxx
│       ├── container: code-server     # VS Code (포트 8080)
│       └── container: s3fs-mount      # S3 FUSE 마운트 (privileged)
├── Service/argus-vscode-admin         # ClusterIP :8080
└── Ingress/argus-vscode-admin         # Nginx, host: argus-vscode-admin.dev.net
```

### 라벨 체계

| 라벨 | 값 | 용도 |
|------|-----|------|
| `app.kubernetes.io/name` | `code-server` | 앱 종류 |
| `app.kubernetes.io/instance` | `{username}` | 사용자 구분 |
| `app.kubernetes.io/part-of` | `argus-insight` | 플랫폼 소속 |
| `argus-insight/component` | `vscode` | 컴포넌트 구분 |

---

## 비상 시 수동 리소스 관리

### 특정 사용자의 VS Code 리소스 수동 삭제

```bash
# 변수 설정
USERNAME=admin
NAMESPACE=argus-apps

# 1. K8s 리소스 삭제 (역순: Ingress → Service → Deployment → Secret)
kubectl delete ingress   argus-vscode-${USERNAME} -n ${NAMESPACE} --ignore-not-found
kubectl delete service   argus-vscode-${USERNAME} -n ${NAMESPACE} --ignore-not-found
kubectl delete deployment argus-vscode-${USERNAME} -n ${NAMESPACE} --ignore-not-found
kubectl delete secret    argus-vscode-${USERNAME} -n ${NAMESPACE} --ignore-not-found

# 2. Pod 강제 삭제 (Deployment 삭제 후에도 남아있는 경우)
kubectl delete pods -n ${NAMESPACE} \
  -l app.kubernetes.io/name=code-server,app.kubernetes.io/instance=${USERNAME} \
  --force --grace-period=0

# 3. Pod 완전 종료 확인
kubectl get pods -n ${NAMESPACE} \
  -l app.kubernetes.io/name=code-server,app.kubernetes.io/instance=${USERNAME}

# 4. PowerDNS A 레코드 삭제
PDNS_IP=10.0.1.50
PDNS_PORT=8083
PDNS_API_KEY="Argus!insight2026"
DOMAIN=dev.net

curl -X PATCH \
  -H "X-API-Key: ${PDNS_API_KEY}" \
  -H "Content-Type: application/json" \
  "http://${PDNS_IP}:${PDNS_PORT}/api/v1/servers/localhost/zones/${DOMAIN}." \
  -d "{\"rrsets\":[{\"name\":\"argus-vscode-${USERNAME}.${DOMAIN}.\",\"type\":\"A\",\"changetype\":\"DELETE\"}]}"

# 5. DB 레코드 정리
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "DELETE FROM argus_app_instances WHERE username='${USERNAME}' AND app_type='vscode';"
```

### 전체 VS Code 리소스 일괄 삭제

```bash
NAMESPACE=argus-apps

# 라벨로 모든 VS Code 리소스 삭제
kubectl delete ingress,service,deployment,secret -n ${NAMESPACE} \
  -l argus-insight/component=vscode

# 남은 Pod 강제 삭제
kubectl delete pods -n ${NAMESPACE} \
  -l app.kubernetes.io/name=code-server \
  --force --grace-period=0

# DB 전체 인스턴스 삭제
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "DELETE FROM argus_app_instances WHERE app_type='vscode';"

# PowerDNS에서 argus-vscode-* 레코드 확인 후 개별 삭제
curl -s -H "X-API-Key: ${PDNS_API_KEY}" \
  "http://${PDNS_IP}:${PDNS_PORT}/api/v1/servers/localhost/zones/${DOMAIN}." \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for rr in data.get('rrsets', []):
    if 'argus-vscode' in rr['name']:
        print(rr['name'])
"
```

### 네임스페이스 전체 초기화

```bash
# 주의: argus-apps 네임스페이스의 모든 리소스가 삭제됩니다
kubectl delete namespace argus-apps

# DB 전체 정리
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "DELETE FROM argus_app_instances;"
```

### DB에만 레코드가 남아있는 경우 (K8s 리소스는 이미 없음)

```bash
# 상태 확인
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "SELECT id, username, app_type, hostname, status FROM argus_app_instances;"

# 특정 인스턴스 삭제
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "DELETE FROM argus_app_instances WHERE id = {ID};"

# deploying/deleting 상태로 멈춘 인스턴스 일괄 정리
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "UPDATE argus_app_instances SET status='failed' WHERE status IN ('deploying', 'deleting');"
```

---

## 트러블슈팅

### 배포 실패 (status = failed)

```bash
# 1. deploy_steps 확인
PGPASSWORD=argus psql -h localhost -U argus -d argus -c \
  "SELECT deploy_steps FROM argus_app_instances WHERE username='admin' AND app_type='vscode';" \
  | python3 -m json.tool

# 2. Pod 상태 확인
kubectl get pods -n argus-apps -l app.kubernetes.io/instance=admin

# 3. Pod 로그 확인
kubectl logs -n argus-apps -l app.kubernetes.io/instance=admin -c code-server
kubectl logs -n argus-apps -l app.kubernetes.io/instance=admin -c s3fs-mount

# 4. Pod 이벤트 확인
kubectl describe pod -n argus-apps -l app.kubernetes.io/instance=admin
```

### 401 Authorization Required

```bash
# 1. 쿠키 확인 — 브라우저 개발자 도구 > Application > Cookies에서
#    argus_app_token이 .{domain} 도메인에 설정되어 있는지 확인

# 2. auth-verify 로그 확인
grep "Auth verify" /root/projects/argus-insight/argus-insight-server/logs/server.log | tail -5
# "no cookie" → 쿠키가 전달되지 않음
# "token mismatch" → 호스트네임 또는 앱 타입 불일치

# 3. 수동 토큰 검증
curl -v https://argus-vscode-admin.{domain}/ \
  --cookie "argus_app_token={token_value}" 2>&1 | head -20
```

### DNS 해석 실패

```bash
# 1. PowerDNS에 레코드가 있는지 확인
curl -s -H "X-API-Key: ${PDNS_API_KEY}" \
  "http://${PDNS_IP}:${PDNS_PORT}/api/v1/servers/localhost/zones/${DOMAIN}." \
  | python3 -c "import json,sys; [print(r['name'],r['records']) for r in json.load(sys.stdin).get('rrsets',[]) if 'argus-vscode' in r['name']]"

# 2. DNS resolve 테스트
dig @${PDNS_IP} argus-vscode-admin.${DOMAIN} A +short

# 3. 시스템 DNS 설정 확인
resolvectl status | grep -A5 "DNS Server"
```

### Ingress 접근 불가 (404 Not Found)

```bash
# 1. Ingress 리소스 확인
kubectl get ingress -n argus-apps

# 2. Nginx Ingress Controller 상태 확인
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx

# 3. LoadBalancer/externalIPs 확인
kubectl get svc ingress-nginx-controller -n ingress-nginx -o wide

# 4. Traefik과 포트 충돌 확인 (K3s)
kubectl get svc -n kube-system | grep traefik
# Traefik이 80/443을 점유하고 있으면:
kubectl patch svc traefik -n kube-system -p '{"spec":{"type":"ClusterIP"}}'
```

---

## 파일 구조

```
argus-insight-server/
├── app/apps/
│   ├── models.py               # ArgusApp, ArgusAppInstance ORM
│   ├── schemas.py              # Pydantic 요청/응답 모델
│   ├── service.py              # 배포/삭제/인증 비즈니스 로직
│   ├── instance_router.py      # /api/v1/apps/instances/{app_type}/*
│   ├── registry_router.py      # /api/v1/apps/registry/*
│   └── kubernetes/
│       └── templates/
│           └── vscode/         # VS Code K8s 매니페스트 템플릿
│               ├── secret.yaml
│               ├── deployment.yaml
│               └── service.yaml
```

## 새 앱 추가 방법

1. `kubernetes/templates/{app_type}/` 디렉토리에 K8s 매니페스트 템플릿 추가
2. DB에 앱 등록 (또는 `service.py`의 `seed_apps()`에 추가):
   ```sql
   INSERT INTO argus_apps (app_type, display_name, description, icon, template_dir)
   VALUES ('jupyter', 'JupyterLab', 'Interactive notebook environment', 'BookOpen', 'jupyter');
   ```
3. UI에 해당 앱의 Launcher 컴포넌트 추가
4. **서버 코드 수정 불필요** — 라우터는 `{app_type}` path parameter로 동적 처리
