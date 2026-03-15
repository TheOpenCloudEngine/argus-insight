# Prometheus Packaging

Prometheus, Pushgateway, Alertmanager의 공식 바이너리를 다운로드하여 RPM/Debian 패키지 및 Docker 이미지로 빌드하는 프로젝트입니다. [nfpm](https://github.com/goreleaser/nfpm)을 사용하여 단일 YAML 설정에서 두 포맷의 패키지를 동시에 생성하고, Multi-stage Dockerfile로 Docker 이미지를 빌드합니다.

## 프로젝트 구조

```
prometheus-service/
├── CLAUDE.md
├── Makefile                  # 빌드 오케스트레이션 (sed로 nfpm.yaml 플레이스홀더 치환)
├── versions.env              # 컴포넌트 버전 핀
├── .gitignore
├── common/scripts/           # 패키지 설치/제거 scriptlet
│   ├── preinstall.sh         # prometheus 시스템 사용자 생성
│   ├── postinstall-*.sh      # systemctl daemon-reload, enable, 디렉토리 생성
│   ├── preremove-*.sh        # 서비스 stop/disable
│   └── postremove.sh         # systemctl daemon-reload
├── docker-compose.yml        # Docker Compose 오케스트레이션
├── .dockerignore
├── prometheus/
│   ├── Dockerfile            # Multi-stage Docker 빌드
│   ├── nfpm.yaml             # 패키지 정의 (prometheus + promtool + consoles + rules)
│   ├── prometheus.service    # systemd unit
│   ├── prometheus.default    # /etc/default/prometheus (CLI 옵션)
│   ├── prometheus.yml        # /etc/prometheus/prometheus.yml (기본 설정)
│   └── rules/                # 예제 alert rule 파일
│       ├── node_alerts.yml       # 노드 알림 (InstanceDown, CPU, Memory, Disk)
│       └── prometheus_alerts.yml # Prometheus 자체 알림 (ConfigReload, TSDB 등)
├── pushgateway/
│   ├── Dockerfile            # Multi-stage Docker 빌드
│   ├── nfpm.yaml
│   ├── pushgateway.service
│   └── pushgateway.default
├── alertmanager/
│   ├── Dockerfile            # Multi-stage Docker 빌드
│   ├── nfpm.yaml             # alertmanager + amtool
│   ├── alertmanager.service
│   ├── alertmanager.default
│   └── alertmanager.yml      # /etc/prometheus/alertmanager.yml (기본 설정)
└── dist/                     # 빌드 산출물 (gitignored)
    ├── download/             # 다운로드된 바이너리
    └── packages/             # 생성된 .rpm, .deb 파일
```

## 빌드 방법

```bash
make all          # 전체 빌드 (다운로드 + RPM + DEB)
make prometheus   # Prometheus만 빌드
make pushgateway  # Pushgateway만 빌드
make alertmanager # Alertmanager만 빌드
make rpm          # RPM만 빌드
make deb          # DEB만 빌드
make clean        # dist/ 삭제

# Docker
make docker              # 전체 Docker 이미지 빌드
make docker-prometheus   # Prometheus 이미지만 빌드
make docker-pushgateway  # Pushgateway 이미지만 빌드
make docker-alertmanager # Alertmanager 이미지만 빌드
make docker-push         # 이미지 레지스트리 push

# Docker Compose
docker compose --env-file versions.env up --build -d
```

빌드 시 nfpm 바이너리가 자동으로 다운로드됩니다. 빌드 호스트에 `curl`, `tar`, `make`가 필요합니다. 패키지 생성 후 `rpm -qpi`/`dpkg-deb -I`로 패키지 정보와 파일 목록을 자동 출력합니다.

## 버전 관리

`versions.env` 파일에서 모든 컴포넌트 버전을 관리합니다. 버전을 변경한 후 `make clean && make all`로 재빌드합니다.

## 패키지 설치 후 파일 레이아웃

### 바이너리

모든 바이너리는 `/opt/argus-insight/prometheus/`에 설치됩니다.

| 패키지 | 바이너리 |
|---|---|
| prometheus | `prometheus`, `promtool` |
| pushgateway | `pushgateway` |
| alertmanager | `alertmanager`, `amtool` |

### 설정 및 데이터

| 컴포넌트 | 바인딩 주소 | 설정 파일 | 데이터 디렉토리 |
|---|---|---|---|
| Prometheus | `0.0.0.0:9090` | `/etc/prometheus/prometheus.yml` | `/var/lib/prometheus/data` |
| Pushgateway | `0.0.0.0:9091` | `/etc/default/pushgateway` | - |
| Alertmanager | `0.0.0.0:9093` | `/etc/prometheus/alertmanager.yml` | `/var/lib/prometheus/alertmanager` |

### Alert Rules

- `/etc/prometheus/rules/node_alerts.yml` - 노드 모니터링 (InstanceDown, HighCpuUsage, HighMemoryUsage, DiskSpaceLow, DiskSpaceCritical)
- `/etc/prometheus/rules/prometheus_alerts.yml` - Prometheus 자체 모니터링 (ConfigReloadFailed, TooManyRestarts, TSDB 장애 등)
- `prometheus.yml`에서 `rule_files: ["/etc/prometheus/rules/*.yml"]`로 자동 로드

### 공통 사항

- 모든 서비스는 `prometheus` 시스템 사용자로 실행
- CLI 옵션은 `/etc/default/<서비스명>` EnvironmentFile에서 관리
- 설정 파일은 `config|noreplace`로 마킹되어 패키지 업그레이드 시 보존
- systemd 서비스: `systemctl start|stop|restart|status <서비스명>`

## Docker 이미지

Airgap 환경을 지원하기 위해 Multi-stage build로 빌드 시점에 공식 바이너리를 다운로드하여 이미지에 내장합니다. `versions.env`의 버전을 `--build-arg`로 주입합니다.

- Base image: `alpine:3.21`
- 이미지 네이밍: `argus-insight/<component>:<version>`
- 바이너리 경로, 설정 파일 경로, 실행 사용자 등은 RPM/DEB 패키지와 동일

### Docker 볼륨

| 컴포넌트 | 볼륨 경로 | 용도 |
|---|---|---|
| Prometheus | `/etc/prometheus` | 설정 파일 (prometheus.yml, rules/) |
| Prometheus | `/var/lib/prometheus/data` | TSDB 데이터 |
| Alertmanager | `/etc/prometheus` | 설정 파일 (alertmanager.yml) |
| Alertmanager | `/var/lib/prometheus/alertmanager` | 알림 데이터 |

## 코드 컨벤션

- `nfpm.yaml`의 `maintainer`: `Open Cloud Engine <fharenheit@gmail.com>`
- 패키지 라이선스: Apache-2.0
- `nfpm.yaml`에서 `__PLACEHOLDER__` 패턴 사용, Makefile의 `sed`로 `versions.env` 값을 치환하여 빌드
