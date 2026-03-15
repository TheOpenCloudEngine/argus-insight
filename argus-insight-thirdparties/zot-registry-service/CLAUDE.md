# Zot Registry Service

Zot는 OCI Distribution Specification을 준수하는 컨테이너 이미지 레지스트리입니다.
Argus Insight 플랫폼에서 airgap 환경의 프라이빗 레지스트리로 사용됩니다.

## 프로젝트 구조

```
zot-registry-service/
├── CLAUDE.md              # 이 파일
├── config.json            # Zot 메인 설정 파일
├── credentials.json       # 업스트림 레지스트리 인증 정보
├── htpasswd               # Zot 접근용 사용자 인증 파일
├── hosts.txt              # TLS 인증서 생성 대상 호스트 목록
├── generate_certs.sh      # TLS 인증서 생성 스크립트
├── zot.service            # systemd 서비스 유닛 파일
├── Dockerfile             # Rocky Linux 9 기반 Docker 이미지
├── docker-compose.yml     # Docker Compose 구성
├── Makefile               # Docker 이미지 빌드 자동화
└── rpm/
    ├── build-rpm.sh       # RPM 패키지 빌드 스크립트
    └── zot.spec           # RPM spec 파일
```

## 배포 방식

### 1. RPM 패키지 (베어메탈/VM)

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

설치 후 절차:
1. `/etc/zot/certs/hosts.txt`에 호스트명 추가
2. `/etc/zot/certs/generate_certs.sh` 실행하여 인증서 생성
3. `/etc/zot/config.json`에서 인증서 경로 수정
4. `/etc/zot/credentials.json`에 업스트림 레지스트리 인증 정보 설정
5. `systemctl start zot`

### 2. Docker Image

Makefile을 통해 zot 바이너리를 다운로드하고 Docker 이미지를 빌드합니다.

```bash
make build    # zot 바이너리 다운로드 + Docker 이미지 빌드
make clean    # 다운로드된 zot 바이너리 삭제
```

- 베이스 이미지: `rockylinux:9-minimal`
- 이미지 이름: `argus-zot`
- zot 바이너리는 빌드 시 다운로드되며, 저장소에는 포함되지 않음 (`.gitignore`)

### 3. Docker Compose

Docker Compose로 실행합니다. 사전에 `make build`로 이미지를 빌드해야 합니다.

```bash
make build
docker compose up -d
```

볼륨 및 마운트 구성:

| 컨테이너 경로 | 호스트 매핑 | 설명 |
|---|---|---|
| `/var/lib/zot` | `argus-zot` (named volume) | 이미지 스토리지 |
| `/etc/zot/config.json` | `./config.json` | 메인 설정 파일 |
| `/etc/zot/htpasswd` | `./htpasswd` | 사용자 인증 파일 |
| `/etc/zot/credentials.json` | `./credentials.json` | 업스트림 인증 정보 |
| `/etc/zot/certs` | `./certs/` | TLS 인증서 디렉토리 |

포트: `5000:5000`

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

```json
{
  "registry-1.docker.io": {
    "username": "USERNAME",
    "password": "ACCESS_TOKEN"
  }
}
```

- `username`: Docker Hub 계정의 사용자명
- `password`: Docker Hub Access Token (계정 비밀번호가 아닌 Access Token 사용)
- Access Token 생성: Docker Hub > Account Settings > Security > New Access Token

### htpasswd

Zot 레지스트리에 push/pull할 때 사용하는 사용자 인증 파일입니다. bcrypt 해시 형식입니다.

사용자 추가:
```bash
htpasswd -bB htpasswd <username> <password>
```

### hosts.txt

TLS 인증서를 생성할 호스트명 목록입니다. 한 줄에 하나씩 기입합니다.

### generate_certs.sh

내부 CA를 생성하고 `hosts.txt`에 나열된 각 호스트에 대해 CA 서명된 TLS 인증서를 생성합니다.

```bash
cd certs   # 또는 인증서를 생성할 디렉토리
# hosts.txt 파일 준비 후
./generate_certs.sh
```

생성되는 파일:
- `ca/ca.key`, `ca/ca.crt` — CA 키 및 인증서
- `<host>/<host>.key` — 서버 개인키
- `<host>/<host>.crt` — 서버 인증서
- `<host>/<host>.pem` — 인증서 체인 (서버 + CA)
