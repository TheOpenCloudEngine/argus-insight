# Registry Migrator

Zot 레지스트리에 등록된 모든 Docker 이미지와 Helm Chart를 다른 OCI 호환 레지스트리(Harbor, Zot, Docker Hub 등)로 일괄 마이그레이션하는 도구입니다.

## 주요 기능

- Zot v2 API를 통해 모든 리포지토리와 태그를 자동 탐색
- Docker 이미지와 Helm Chart(OCI artifact) 모두 지원
- `skopeo copy --all`을 사용하여 multi-arch 이미지 완벽 지원
- 병렬 복사로 빠른 마이그레이션 (기본 4개 동시 작업)
- 실패 시 자동 재시도 (기본 3회)
- Dry-run 모드로 사전 확인 가능
- 상세 로그 파일 자동 생성

## 사전 요구 사항

```bash
# skopeo 설치 (RHEL/CentOS/Fedora)
sudo dnf install -y skopeo

# skopeo 설치 (Ubuntu/Debian)
sudo apt-get install -y skopeo

# jq, curl (대부분 기본 설치)
sudo dnf install -y jq curl
```

## 사용법

### 1. 설정 파일 생성

```bash
cp config.env.example config.env
vi config.env
```

### 2. 설정 파일 편집

```bash
# Source (Zot 레지스트리)
SRC_REGISTRY="zot.example.com:5000"
SRC_USERNAME="admin"
SRC_PASSWORD="changeme"

# Destination (Harbor 등)
DST_REGISTRY="harbor.example.com"
DST_USERNAME="admin"
DST_PASSWORD="changeme"
```

### 3. 마이그레이션 실행

```bash
# Dry-run (실제 복사 없이 대상 확인)
./migrate.sh --dry-run

# 실제 마이그레이션 실행
./migrate.sh

# 옵션 지정
./migrate.sh --jobs 8 --retry 5 --log /tmp/migration.log
```

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-c, --config` | 설정 파일 경로 | `config.env` |
| `-n, --dry-run` | 실제 복사 없이 대상만 출력 | `false` |
| `-j, --jobs` | 병렬 복사 작업 수 | `4` |
| `-r, --retry` | 실패 시 재시도 횟수 | `3` |
| `-l, --log` | 로그 파일 경로 | `migrate-YYYYMMDD-HHMMSS.log` |
| `-h, --help` | 도움말 출력 | - |

## 설정 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `SRC_REGISTRY` | O | 소스 레지스트리 주소 (호스트:포트) |
| `SRC_SCHEME` | O | 프로토콜 (`https` 또는 `http`) |
| `SRC_USERNAME` | - | 소스 레지스트리 사용자명 |
| `SRC_PASSWORD` | - | 소스 레지스트리 비밀번호 |
| `SRC_TLS_VERIFY` | - | TLS 인증서 검증 여부 (기본: `true`) |
| `DST_REGISTRY` | O | 대상 레지스트리 주소 |
| `DST_SCHEME` | O | 프로토콜 (`https` 또는 `http`) |
| `DST_USERNAME` | - | 대상 레지스트리 사용자명 |
| `DST_PASSWORD` | - | 대상 레지스트리 비밀번호 |
| `DST_TLS_VERIFY` | - | TLS 인증서 검증 여부 (기본: `true`) |
| `DST_PROJECT_PREFIX` | - | 대상 리포지토리 앞에 붙일 프로젝트명 |

## 실행 예시

```
$ ./migrate.sh --dry-run

[2025-01-15 10:30:00] ==========================================
[2025-01-15 10:30:00] Registry Migrator
[2025-01-15 10:30:00] ==========================================
[2025-01-15 10:30:00] Source:      zot.example.com:5000
[2025-01-15 10:30:00] Destination: harbor.example.com
[2025-01-15 10:30:00] Dry-run:     true
[2025-01-15 10:30:00] ==========================================
[2025-01-15 10:30:01] >>> Found 5 repositories, 12 total image/tag combinations
[2025-01-15 10:30:01] [1/12] (image) nginx:latest
[2025-01-15 10:30:01] [DRY-RUN] nginx:latest -> nginx:latest
[2025-01-15 10:30:01] [2/12] (helm-chart) charts/my-app:1.0.0
[2025-01-15 10:30:01] [DRY-RUN] charts/my-app:1.0.0 -> charts/my-app:1.0.0
...
```
