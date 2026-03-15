# Portable Docker Registry (Zot)

## Installation

```shell
# 최신 버전 확인 후 다운로드 (x86_64 기준)
curl -Lo zot https://github.com/project-zot/zot/releases/latest/download/zot-linux-amd64

# 실행 권한 부여 및 경로 이동
chmod +x zot
sudo mv zot /usr/local/bin/zot
```

## Generate Certificates

`/etc/zot/certs/generate_certs.sh` 파일을 다음과 같이 생성합니다. `DOMAIN`에는 FQDN 형식을 권장하기 때문에 도메인명을 추가합니다. 해당 FQDN명은 DNS에 등록되어 있거나 `/etc/hosts`에 추가되어 있어야 합니다.

```shell
#!/bin/bash
###############################################################################
# generate_certs.sh
#
# 내부 CA를 생성하고, hosts.txt에 나열된 각 호스트에 대해
# CA 서명된 인증서를 생성하는 스크립트
#
# 생성되는 인증서 특성:
#   - X509v3 Extended Key Usage: TLS Web Server Auth, TLS Web Client Auth
#   - X509v3 Subject Alternative Name: DNS:<hostname>
#   - 브라우저에서 에러 없이 사용 가능 (CA를 신뢰 저장소에 등록 시)
#
# 사용법:
#   1. hosts.txt 파일에 호스트명을 한 줄에 하나씩 기입
#   2. 아래 변수 섹션에서 조직 정보 및 도메인 설정
#   3. ./generate_certs.sh 실행  (sh generate_certs.sh 사용금지)
###############################################################################

#==============================================================================
# 사용자 설정 변수 (환경에 맞게 수정)
#==============================================================================

# 인증서 Subject 정보
COUNTRY="KR"                                # C  - 국가 코드
STATE="Gyeonggi-do"                         # ST - 시/도
LOCALITY="Yongin-si"                        # L  - 도시
ORGANIZATION="Open Cloud Engine Community"  # O  - 조직명
ORG_UNIT="Platform Engineering"             # OU - 부서명

# 도메인 정보
DOMAIN="dev.net"
WILDCARD="*.${DOMAIN}"              # 와일드카드 도메인

# CA 설정
CA_CN="Open Cloud Engine Community CA"      # CA의 Common Name
CA_DAYS=3650                        # CA 인증서 유효기간 (일)
CA_KEY_BITS=4096                    # CA RSA 키 크기

# 서버 인증서 설정
CERT_DAYS=825                       # 서버 인증서 유효기간 (일, Apple 요구사항 충족)
CERT_KEY_BITS=2048                  # 서버 RSA 키 크기

# 파일 경로
HOSTS_FILE="hosts.txt"              # 호스트 목록 파일
OUTPUT_DIR="./"                # 인증서 출력 디렉토리
CA_DIR="${OUTPUT_DIR}/ca"           # CA 인증서 디렉토리

#==============================================================================
# 사전 검증
#==============================================================================

if [ ! -f "${HOSTS_FILE}" ]; then
    echo "[ERROR] 호스트 파일을 찾을 수 없습니다: ${HOSTS_FILE}"
    echo "        호스트명을 한 줄에 하나씩 기입한 hosts.txt 파일을 생성하세요."
    echo "        예시:"
    echo "          node01"
    echo "          node02"
    echo "          cm-server"
    exit 1
fi

# 호스트 목록 읽기
HOSTS=`cat ${HOSTS_FILE}`
HOSTS_STRING=$(cat ${HOSTS_FILE} | tr '\n' ',' | sed 's/,$//')

echo "============================================================"
echo " 인증서 생성 스크립트"
echo "============================================================"
echo " 조직 정보: C=${COUNTRY}, ST=${STATE}, L=${LOCALITY}, O=${ORGANIZATION}, OU=${ORG_UNIT}"
echo " 도메인: ${DOMAIN}"
echo "============================================================"

#==============================================================================
# 디렉토리 생성
#==============================================================================

mkdir -p "${CA_DIR}"

#==============================================================================
# 1단계: CA (Certificate Authority) 생성
#==============================================================================

echo ""
echo "[1/3] CA (Certificate Authority) 생성 중..."

CA_KEY="${CA_DIR}/ca.key"
CA_CERT="${CA_DIR}/ca.crt"
CA_SERIAL="${CA_DIR}/ca.srl"

if [ -f "${CA_CERT}" ] && [ -f "${CA_KEY}" ]; then
    echo "  -> 기존 CA가 존재합니다. 기존 CA를 사용합니다."
    echo "     CA 인증서: ${CA_CERT}"
    echo "     (새로 생성하려면 ${CA_DIR} 디렉토리를 삭제 후 재실행)"
else
    # CA 개인키 생성
    openssl genrsa -out "${CA_KEY}" ${CA_KEY_BITS} 2>/dev/null
    chmod 400 "${CA_KEY}"

    # CA 자체 서명 인증서 생성
    openssl req -x509 -new -nodes \
        -key "${CA_KEY}" \
        -sha256 \
        -days ${CA_DAYS} \
        -out "${CA_CERT}" \
        -subj "/C=${COUNTRY}/ST=${STATE}/L=${LOCALITY}/O=${ORGANIZATION}/OU=${ORG_UNIT}/CN=${CA_CN}" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,keyCertSign,cRLSign"

    echo "  -> CA 생성 완료"
    echo "     CA 키:     ${CA_KEY}"
    echo "     CA 인증서: ${CA_CERT}"
fi

# serial 파일 초기화 (없을 경우)
if [ ! -f "${CA_SERIAL}" ]; then
    echo "01" > "${CA_SERIAL}"
fi

#==============================================================================
# 2단계: 각 호스트별 인증서 생성
#==============================================================================

echo ""
echo "[2/3] 호스트별 인증서 생성 중..."

for HOST in ${HOSTS}
do

    # FQDN 구성: 이미 도메인이 포함된 경우 그대로 사용
    if [[ "$HOST" =~ \."$DOMAIN"$ ]]; then
        FQDN="${HOST}"
    else
        FQDN="${HOST}.${DOMAIN}"
    fi

    HOST_DIR="${OUTPUT_DIR}/${HOST}"
    mkdir -p "${HOST_DIR}"

    HOST_KEY="${HOST_DIR}/${HOST}.key"
    HOST_CSR="${HOST_DIR}/${HOST}.csr"
    HOST_CERT="${HOST_DIR}/${HOST}.crt"
    HOST_EXT="${HOST_DIR}/${HOST}.ext"
    HOST_PEM="${HOST_DIR}/${HOST}.pem"       # 인증서 체인 (서버 + CA)
    HOST_FULLKEY="${HOST_DIR}/${HOST}-full.pem"  # 키 + 체인 통합

    echo ""
    echo "  ---- ${HOST} (${FQDN}) ----"

    # 2-1. 서버 개인키 생성
    openssl genrsa -out "${HOST_KEY}" ${CERT_KEY_BITS} 2>/dev/null
    chmod 400 "${HOST_KEY}"
    echo "    [+] 개인키 생성: ${HOST_KEY}"

    # 2-2. CSR (Certificate Signing Request) 생성
    openssl req -new \
        -key "${HOST_KEY}" \
        -out "${HOST_CSR}" \
        -subj "/C=${COUNTRY}/ST=${STATE}/L=${LOCALITY}/O=${ORGANIZATION}/OU=${ORG_UNIT}/CN=${FQDN}"
    echo "    [+] CSR 생성:   ${HOST_CSR}"

    # 2-3. X509v3 확장 설정 파일 생성
    cat > "${HOST_EXT}" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth,clientAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=${FQDN}
DNS.2=${HOST}
DNS.3=*.${DOMAIN}
EOF

    echo "    [+] 확장설정:   ${HOST_EXT}"

    # 2-4. CA로 서명하여 인증서 생성
    openssl x509 -req \
        -in "${HOST_CSR}" \
        -CA "${CA_CERT}" \
        -CAkey "${CA_KEY}" \
        -CAserial "${CA_SERIAL}" \
        -out "${HOST_CERT}" \
        -days ${CERT_DAYS} \
        -sha256 \
        -extfile "${HOST_EXT}" \
        2>/dev/null
    echo "    [+] 인증서:     ${HOST_CERT}"

    # 2-5. 인증서 체인 파일 생성 (서버 인증서 + CA 인증서)
    cat "${HOST_CERT}" "${CA_CERT}" > "${HOST_PEM}"
    echo "    [+] 체인 PEM:   ${HOST_PEM}"

    # 2-6. 통합 PEM 파일 (키 + 체인, Nginx/HAProxy 등에서 사용)
    cat "${HOST_KEY}" "${HOST_CERT}" "${CA_CERT}" > "${HOST_FULLKEY}"
    chmod 400 "${HOST_FULLKEY}"
    echo "    [+] 통합 PEM:   ${HOST_FULLKEY}"

done

#==============================================================================
# 3단계: 검증
#==============================================================================

echo ""
echo "[3/3] 인증서 검증 중..."
echo ""

VERIFY_PASS=0
VERIFY_FAIL=0

for HOST in ${HOSTS}
do

    if [[ "${HOST}" == *.* ]]; then
        FQDN="${HOST}"
    else
        FQDN="${HOST}.${DOMAIN}"
    fi

    HOST_CERT="${OUTPUT_DIR}/${HOST}/${HOST}.crt"

    echo "  ---- ${HOST} ----"

    # CA 체인 검증
    if openssl verify -CAfile "${CA_CERT}" "${HOST_CERT}" 2>/dev/null | grep -q "OK"; then
        echo "    [OK] CA 서명 검증 통과"
    else
        echo "    [FAIL] CA 서명 검증 실패"
        ((VERIFY_FAIL++))
    fi

    # Extended Key Usage 확인
        echo "    [인증서] 인증서정보 출력"
    openssl x509 -in "${HOST_CERT}" -noout -text
    
    EKU=$(openssl x509 -in "${HOST_CERT}" -noout -text 2>/dev/null | grep -A1 "Extended Key Usage")
    if echo "${EKU}" | grep -q "TLS Web Server Authentication" && echo "${EKU}" | grep -q "TLS Web Client Authentication"; then
        echo "    [OK] Extended Key Usage: Server + Client Auth"
    else
        echo "    [FAIL] Extended Key Usage 누락"
        ((VERIFY_FAIL++))
    fi

    # SAN 확인
    SAN=$(openssl x509 -in "${HOST_CERT}" -noout -text 2>/dev/null | grep -A1 "Subject Alternative Name")
    if echo "${SAN}" | grep -q "DNS:${FQDN}"; then
        echo "    [OK] SAN: DNS:${FQDN}"
    else
        echo "    [FAIL] SAN에 ${FQDN} 누락"
        ((VERIFY_FAIL++))
    fi

    ((VERIFY_PASS++))
    echo ""

done

#==============================================================================
# 요약
#==============================================================================

echo "============================================================"
echo " 완료 요약"
echo "============================================================"
echo ""
echo " 출력 디렉토리 구조:"
echo "   ${OUTPUT_DIR}/"
echo "   ├── ca/"
echo "   │   ├── ca.key          (CA 개인키 - 안전하게 보관)"
echo "   │   └── ca.crt          (CA 인증서 - 클라이언트에 배포)"
for HOST in $HOSTS
do
echo "   ├── ${HOST}/"
echo "   │   ├── ${HOST}.key     (서버 개인키)"
echo "   │   ├── ${HOST}.crt     (서버 인증서)"
echo "   │   ├── ${HOST}.pem     (인증서 체인: 서버+CA)"
echo "   │   └── ${HOST}-full.pem(키+체인 통합)"
done
echo ""
echo " 검증 결과: ${VERIFY_PASS}개 호스트 처리, ${VERIFY_FAIL}개 오류"
echo ""
echo "============================================================"
echo " 브라우저에서 에러 없이 사용하기 위한 안내"
echo "============================================================"
echo ""
echo " 1. CA 인증서를 클라이언트(브라우저)에 신뢰 CA로 등록:"
echo "    - Windows: ca.crt 더블클릭 → '신뢰할 수 있는 루트 인증 기관'에 설치"
echo "    - macOS:   '키체인 접근' → ca.crt 가져오기 → '항상 신뢰'로 변경"
echo "    - Linux:   sudo cp ca.crt /usr/local/share/ca-certificates/"
echo "               sudo update-ca-certificates"
echo ""
echo " 2. 웹 서버 설정 예시 (Nginx):"
echo "    ssl_certificate     /path/to/<host>.pem;    # 체인 인증서"
echo "    ssl_certificate_key /path/to/<host>.key;    # 개인키"
echo ""
echo " 3. Java 환경:"
echo "    - JKS 변환: openssl pkcs12 → keytool importkeystore"
echo "    - CA를 JDK truststore(jssecacerts)에 등록 : keytool -importcert -alias ${DOMAIN} -file ${CA_CERT} -keystore <JAVA_HOME>/lib/security/cacerts -storepass changeit"
echo "============================================================"
```

`/etc/zot/certs/hosts.txt` 파일에 호스트명을 추가합니다. 다음의 서버는 Zot을 구동할 서버의 호스트명입니다.

```
dev-server
```

이제 다음과 같이 인증서를 생성합니다.

```
cd /etc/zot/certs
sh generate_certs.sh
```

## Configuration

Helm Charts를 가져오기 위해서 다음과 같이 `/etc/zot/credentials.json` 파일에 Docker Hub의 인증키를 추가합니다. Key는 Docker Hub 사이트에 로그인 하여 

```
{
  "registry-1.docker.io": {
    "username": "USERNAME",
    "password": "KEY"
  }
}
```

OCI 형식이 아닌 Helm Charts를 push하기 위해서 다음과 같이 인증 정보를 생성합니다.

```
apt install apache2-utils  # 또는 yum install httpd-tools
htpasswd -bBc /etc/zot/htpasswd admin your-password
```

다음과 같이 `/etc/zot/config.json` 파일을 작성합니다. 5000 포트는 Coder가 사용하므로 포트 충돌이 나지 않도록 확인하도록 합니다.

```json
{
  "distSpecVersion": "1.1.0",
  "storage": {
    "rootDirectory": "/var/lib/zot",
    "gc": true
  },
  "http": {
    "address": "0.0.0.0",
    "port": "5000",
    "tls": {
      "cert": "/etc/zot/certs/dev-server/dev-server.crt",
      "key": "/etc/zot/certs/dev-server/dev-server.key"
    },
    "auth": {
      "htpasswd": {
        "path": "/etc/zot/htpasswd"
      }
    }
  },
  "log": {
    "level": "info"
  },
  "extensions": {
    "sync": {
      "enable": true,
      "credentialsFile": "/etc/zot/credentials.json",
      "registries": [
        {
          "urls": ["https://registry-1.docker.io"],
          "onDemand": true,
          "content": [
            { "prefix": "**" }
          ]
        },
        {
          "urls": ["https://quay.io"],
          "onDemand": true,
          "content": [
            { "prefix": "**" }
          ]
        },
        {
          "urls": ["https://gcr.io"],
          "onDemand": true,
          "content": [
            { "prefix": "**" }
          ]
        },
        {
          "urls": ["https://ghcr.io"],
          "onDemand": true,
          "content": [
            { "prefix": "**" }
          ]
        },
        {
          "urls": ["https://mcr.microsoft.com"],
          "onDemand": true,
          "content": [
            { "prefix": "**" }
          ]
        }
      ]
    }
  }
}
```

## Systemd Service

`/etc/systemd/system/zot.service` 파일을 다음과 같이 작성합니다.

```
[Unit]
Description=Zot OCI Registry
After=network.target

[Service]
User=zot
Group=zot
WorkingDirectory=/var/lib/zot
ExecStart=/usr/local/bin/zot serve /etc/zot/config.json
Restart=always

[Install]
WantedBy=multi-user.target
```

에러 발생시 다음의 커맨드로 체크합니다.

```shell
journalctl -u zot.service -n 20 --no-pager
```

## Use

### Helm Chart의 `values.yaml`

```yaml
repository: dev-server.dev.net:5000/bitnami/postgresql
```

### OCI 방식의 Helm Chart 호출

```shell
helm pull oci://dev-server.dev.net:5000/bitnamicharts/postgresql
```

### Warming Up

```shell
# Docker Hub 공식 이미지
docker pull dev-server.dev.net:5000/library/nginx:latest

# Bitnami 이미지
docker pull dev-server.dev.net:5000/bitnami/postgresql:17

# ArgoCD (GHCR)
docker pull dev-server.dev.net:5000/argoproj/argocd:v2.10.0

# Helm Chart (OCI)
helm pull oci://dev-server.dev.net:5000/bitnamicharts/redis --version 21.0.2 # 버전 명시
```

## 기타

### OCI 형식이 아닌 Helm Charts

OCI 형식이 아닌 Helm Charts는 다음과 같이 처리합니다.

```
# Apache Airflow Helm repo 추가
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# chart 다운로드
helm pull apache-airflow/airflow --version 1.19.0

# zot 로그인 (인증이 있는 경우)
helm registry login dev-server.dev.net:5000 --username admin --password your-password

# OCI 형식으로 zot에 push (로그인)
helm push airflow-1.19.0.tgz oci://dev-server.dev.net:5000/apache-airflow

# 이후 사용
helm pull oci://dev-server.dev.net:5000/apache-airflow/airflow --version 1.19.0
helm install my-airflow oci://dev-server.dev.net:5000/apache-airflow/airflow --version 1.19.0
```

Helm Charts를 업로드한 후에 다음의 스크립트로 일괄 이미지를 Zot에 업로드할 수 있습니다.

```shell
#!/bin/bash
ZOT="dev-server.dev.net:5000"

# chart에서 이미지 목록 추출
IMAGES=$(helm template my-airflow oci://${ZOT}/apache-airflow/airflow --version 1.19.0 \
  | grep "image:" | sed 's/.*image: *"*\([^"]*\)"*/\1/' | sort -u)

echo "=== 발견된 이미지 ==="
echo "$IMAGES"

echo ""
echo "=== zot으로 pull 시작 ==="
for img in $IMAGES; do
  # 모든 원본 registry 주소 제거
  local_img=$(echo "$img" | sed \
    -e 's|^docker.io/||' \
    -e 's|^registry-1.docker.io/||' \
    -e 's|^quay.io/||' \
    -e 's|^gcr.io/||' \
    -e 's|^ghcr.io/||' \
    -e 's|^mcr.microsoft.com/||')

  echo "Pulling: ${ZOT}/${local_img}"
  docker pull "${ZOT}/${local_img}" || echo "FAILED: ${local_img}"
done
```

실제 사용시 다음의 커맨드를 사용합니다.

```
helm install my-airflow oci://dev-server.dev.net:5000/apache-airflow/airflow \
  --version 1.19.0 \
  --set defaultAirflowRepository=dev-server.dev.net:5000/apache/airflow \
  --set defaultAirflowTag=3.1.7
```
