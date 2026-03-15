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
