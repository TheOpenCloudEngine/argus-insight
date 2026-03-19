# Zot Registry - Kubernetes Deployment Troubleshooting

Zot Registry를 Kubernetes에 배포하면서 발생한 이슈와 해결 과정을 기록합니다.

---

## 1. ImagePullBackOff - 로컬 빌드 이미지를 찾지 못함

### 증상

```bash
$ kubectl apply -k kubernetes/
$ kubectl get pods -n argus-insight -l app.kubernetes.io/name=zot-registry

NAME                            READY   STATUS             RESTARTS   AGE
zot-registry-7d5b6688cd-k9h7l   0/1     ImagePullBackOff   0          3m52s
```

Pod describe에서 다음 에러 확인:

```bash
$ kubectl describe pod -n argus-insight -l app.kubernetes.io/name=zot-registry

Events:
  Warning  Failed  68s  kubelet  Failed to pull image "argus-insight/zot-registry:2.1.2":
    Error response from daemon: pull access denied for argus-insight/zot-registry,
    repository does not exist or may require 'docker login'
```

### 원인

`imagePullPolicy`가 지정되지 않으면 Kubernetes 기본값인 `Always`가 적용되어, 로컬에 이미지가 있더라도 원격 레지스트리(Docker Hub)에서 pull을 시도한다. `argus-insight/zot-registry`는 Docker Hub에 존재하지 않으므로 실패한다.

### 해결

**Step 1.** 로컬에 이미지 빌드:

```bash
$ make docker
```

빌드 결과 확인:

```bash
$ docker images | grep zot-registry
argus-insight/zot-registry   2.1.2   7d10c64a2597   ...
```

**Step 2.** `kubernetes/zot-registry.yaml`에 `imagePullPolicy: IfNotPresent` 추가:

```yaml
containers:
  - name: zot-registry
    image: argus-insight/zot-registry:2.1.2
    imagePullPolicy: IfNotPresent    # 추가
    ports:
      - containerPort: 5000
```

---

## 2. Readiness/Liveness Probe 실패 - 인증으로 인한 401 응답

### 증상

Pod이 `Running` 상태이지만 `READY`가 `0/1`로 유지된다:

```bash
$ kubectl get pods -n argus-insight -l app.kubernetes.io/name=zot-registry

NAME                            READY   STATUS    RESTARTS   AGE
zot-registry-7d5b6688cd-ngbqx   0/1     Running   0          51s
```

Pod 로그에서 kube-probe 요청이 401로 응답:

```json
{
  "module": "http",
  "clientIP": "10.42.0.1:47440",
  "method": "GET",
  "path": "/v2/",
  "statusCode": 401,
  "headers": {
    "User-Agent": ["kube-probe/1.34"]
  }
}
```

### 원인

`/v2/` 엔드포인트는 Zot의 htpasswd 인증이 적용되어 인증 없이 접근하면 `401 Unauthorized`를 반환한다. Kubernetes의 `httpGet` probe는 `2xx`~`3xx` 응답만 성공으로 처리하므로, `401`은 probe 실패로 간주된다.

### 해결

`kubernetes/zot-registry.yaml`에서 `httpGet` probe를 `tcpSocket` probe로 변경:

```yaml
# 변경 전
livenessProbe:
  httpGet:
    path: /v2/
    port: 5000
readinessProbe:
  httpGet:
    path: /v2/
    port: 5000

# 변경 후
livenessProbe:
  tcpSocket:
    port: 5000
  initialDelaySeconds: 10
  periodSeconds: 30
readinessProbe:
  tcpSocket:
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### 참고

Zot이 인증 없는 헬스체크 엔드포인트를 제공하지 않으므로 `tcpSocket`이 가장 단순한 방법이다. 인증 헤더를 포함한 `exec` probe도 가능하지만 과도한 설정이 된다.

---

## 3. CrashLoopBackOff - BoltDB 파일 잠금 충돌

### 증상

Deployment를 `rollout restart`하면 새 Pod이 `CrashLoopBackOff`에 빠진다:

```bash
$ kubectl rollout restart deployment/zot-registry -n argus-insight
$ kubectl get pods -n argus-insight -l app.kubernetes.io/name=zot-registry

NAME                            READY   STATUS             RESTARTS     AGE
zot-registry-54d747498b-6jknq   0/1     CrashLoopBackOff   1 (10s ago)  33s
zot-registry-57cccd5d54-m4t2j   1/1     Running            1 (3m38s)    3m49s
```

Pod 로그:

```bash
$ kubectl logs -n argus-insight zot-registry-54d747498b-6jknq

Error: operation timeout: boltdb file is already in use, path '/var/lib/zot/cache.db'
```

### 원인

기본 Deployment 전략인 `RollingUpdate`는 새 Pod을 먼저 생성한 후 기존 Pod을 종료한다. 그런데 Zot은 BoltDB(`cache.db`)에 파일 잠금을 사용하며, PVC가 `ReadWriteOnce`이므로 두 Pod이 동시에 같은 DB 파일에 접근하면 잠금 충돌이 발생한다.

### 해결

`kubernetes/zot-registry.yaml`에서 Deployment 전략을 `Recreate`로 변경:

```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate        # 추가: 기존 Pod 종료 후 새 Pod 생성
  selector:
    matchLabels:
      app.kubernetes.io/name: zot-registry
```

`Recreate` 전략은 기존 Pod을 먼저 종료한 후 새 Pod을 생성하므로 BoltDB 잠금 충돌을 방지한다. 단일 replica 레지스트리에서는 짧은 다운타임이 발생하지만, BoltDB 특성상 불가피하다.

---

## 4. Secret htpasswd Placeholder - 인증 실패

### 증상

Registry에 curl로 접근하면 올바른 계정으로도 `401 UNAUTHORIZED` 반환:

```bash
$ curl -s -u admin:'Argus!insight2026' http://<CLUSTER-IP>:5000/v2/ -w "\nHTTP_CODE:%{http_code}\n"
HTTP_CODE:401
```

### 원인

`kubernetes/secret.yaml`에 htpasswd 값이 placeholder로 되어 있었다:

```yaml
# secret.yaml 원본
stringData:
  htpasswd: |
    admin:$2y$05$placeholder_hash_replace_me
```

실제 bcrypt 해시가 아니므로 어떤 패스워드로도 인증이 불가능하다.

### 해결

`htpasswd` 파일의 실제 해시값으로 `kubernetes/secret.yaml`을 수정:

```bash
# 현재 htpasswd 파일의 해시 확인
$ cat htpasswd
admin:$2y$05$4CSdzVJFAscucxvjhe2U8etOq7nUxVB0JNcA18eld09eHpTGGrFdO
```

```yaml
# secret.yaml 수정
stringData:
  htpasswd: |
    admin:$2y$05$4CSdzVJFAscucxvjhe2U8etOq7nUxVB0JNcA18eld09eHpTGGrFdO
```

적용 후 Pod 재시작:

```bash
$ kubectl apply -k kubernetes/
$ kubectl rollout restart deployment/zot-registry -n argus-insight
```

### 참고

새로운 사용자를 추가하려면:

```bash
$ htpasswd -bB htpasswd <username> <password>
```

생성된 해시를 `secret.yaml`에 반영하고 재배포한다.

---

## 5. Docker HTTPS 에러 - NodePort TLS 설정

### 증상

Docker login 시 HTTPS 에러:

```bash
$ docker login 10.43.234.67:5000 -u admin -p 'Argus!insight2026'

Error response from daemon: Get "https://10.43.234.67:5000/v2/":
  http: server gave HTTP response to HTTPS client
```

### 원인

Docker 클라이언트는 기본적으로 HTTPS로 레지스트리에 접속한다. Zot에 TLS가 설정되지 않은 상태에서 직접 접근하면 HTTP 응답을 받아 거부한다.

### 해결 (Production 권장 방식: NodePort + Zot 자체 TLS 종단)

k3s 환경에서는 Ingress 없이 NodePort로 직접 노출하고, Zot 자체에서 TLS를 종단하는 방식을 사용한다.

**Step 1.** TLS 인증서 생성 (`generate_certs.sh` 사용):

```bash
$ echo "zot.argus-insight.dev.net" > hosts.txt
$ bash generate_certs.sh
```

**Step 2.** Kubernetes TLS Secret 생성:

```bash
$ HOST=zot.argus-insight.dev.net
$ kubectl create namespace argus-insight --dry-run=client -o yaml | kubectl apply -f -
$ kubectl create secret tls zot-registry-tls \
    --cert=$HOST/$HOST.crt --key=$HOST/$HOST.key \
    -n argus-insight
```

**Step 3.** ConfigMap에 TLS 설정 추가 (`kubernetes/configmap.yaml`):

```json
"http": {
  "address": "0.0.0.0",
  "port": "5000",
  "tls": {
    "cert": "/etc/zot/tls/tls.crt",
    "key": "/etc/zot/tls/tls.key"
  }
}
```

**Step 4.** Deployment에 TLS Secret 볼륨 마운트 추가 (`kubernetes/zot-registry.yaml`):

```yaml
volumeMounts:
  - name: tls
    mountPath: /etc/zot/tls
    readOnly: true
volumes:
  - name: tls
    secret:
      secretName: zot-registry-tls
```

**Step 5.** Service를 NodePort로 변경 (`kubernetes/zot-registry.yaml`):

```yaml
spec:
  type: NodePort
  ports:
    - port: 5000
      targetPort: 5000
      nodePort: 30000
      protocol: TCP
```

**Step 6.** 클라이언트에 CA 인증서 등록:

```bash
$ NODEPORT=30000

# Docker 클라이언트
$ mkdir -p /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT
$ cp ca/ca.crt /etc/docker/certs.d/zot.argus-insight.dev.net:$NODEPORT/ca.crt

# OS 신뢰 저장소 (RHEL/Rocky Linux)
$ sudo cp ca/ca.crt /etc/pki/ca-trust/source/anchors/argus-insight-ca.crt
$ sudo update-ca-trust
```

**Step 7.** 접속 테스트:

```bash
$ curl -sk -u 'admin:Argus!insight2026' https://zot.argus-insight.dev.net:30000/v2/_catalog
{"repositories":[]}
```

---

## 6. htpasswd 해시 생성 시 `!` 문자가 변환되어 인증 실패

### 증상

올바른 비밀번호(`Argus!insight2026`)로 레지스트리에 접근하면 curl에서는 성공하지만, Python httpx 등 프로그래밍 언어의 HTTP 클라이언트에서는 `401 UNAUTHORIZED`가 반환된다:

```bash
# curl은 성공 (bash가 ! 를 동일하게 변환)
$ curl -sk -u 'admin:Argus!insight2026' https://zot.argus-insight.dev.net:30000/v2/_catalog
{"repositories":[]}

# Python httpx는 실패 (정확한 비밀번호를 전송)
import httpx
resp = httpx.get(url, auth=('admin', 'Argus!insight2026'), verify=False)
# Status: 401 UNAUTHORIZED
```

### 원인

bash의 **history expansion** 기능이 `!` 문자를 특수하게 처리한다. `htpasswd -nbB admin 'Argus!insight2026'` 실행 시, bash가 `!`를 `\!`로 변환하여 실제로는 `Argus\!insight2026`(백슬래시 포함) 비밀번호의 해시가 생성된다.

```bash
# history expansion이 활성화된 상태에서 생성
$ htpasswd -nbB admin 'Argus!insight2026'
admin:$2y$05$...  # 실제로는 "Argus\!insight2026" 비밀번호의 해시

# curl도 동일한 bash 환경에서 ! 를 \! 로 변환하므로 우연히 성공
# 하지만 Python, Java 등 프로그래밍 언어는 정확한 "Argus!insight2026"을 전송하여 실패
```

검증:

```bash
# curl이 보낸 Base64 디코딩
$ echo 'YWRtaW46QXJndXNcIWluc2lnaHQyMDI2' | base64 -d
admin:Argus\!insight2026    # 백슬래시 포함!

# httpx가 보낸 Base64 디코딩
$ echo 'YWRtaW46QXJndXMhaW5zaWdodDIwMjY=' | base64 -d
admin:Argus!insight2026     # 올바른 비밀번호
```

### 해결

**`set +H`로 bash의 history expansion을 비활성화**한 후 htpasswd 해시를 재생성한다:

```bash
# 1. history expansion 비활성화
$ set +H

# 2. 올바른 해시 생성
$ htpasswd -nbB admin 'Argus!insight2026'
admin:$2y$05$zOX0mfN...

# 3. 해시 검증 (반드시 확인)
$ echo 'admin:$2y$05$zOX0mfN...' > /tmp/verify_htpasswd
$ htpasswd -vb /tmp/verify_htpasswd admin 'Argus!insight2026'
Password for user admin correct.

# 4. htpasswd 파일 및 kubernetes/secret.yaml 업데이트

# 5. Secret 재적용 및 Pod 재시작
$ kubectl apply -f kubernetes/secret.yaml
$ kubectl rollout restart deployment/zot-registry -n argus-insight
```

### 참고

- `set +H`는 현재 셸 세션에만 적용된다. 영구 적용하려면 `~/.bashrc`에 추가한다.
- 비밀번호에 `!`, `^`, `{`, `}` 등 bash 특수문자가 포함된 경우 항상 `set +H`를 먼저 실행하는 것이 안전하다.
- `zsh`에서는 이 문제가 발생하지 않는다 (history expansion 기본 비활성화).
- htpasswd 해시 생성 후에는 **반드시 `htpasswd -vb`로 검증**하는 것을 권장한다.

---

## 최종 변경 파일 요약

| 파일 | 변경 내용 |
|---|---|
| `kubernetes/zot-registry.yaml` | `imagePullPolicy: IfNotPresent` 추가, probe를 `tcpSocket`으로 변경, `strategy: Recreate` 추가, TLS 볼륨 마운트, `NodePort:30000` |
| `kubernetes/secret.yaml` | htpasswd placeholder를 실제 bcrypt 해시로 교체 |
| `kubernetes/configmap.yaml` | TLS 설정 추가 (Zot 자체 TLS 종단) |
| `kubernetes/kustomization.yaml` | `ingress.yaml` 제거 (NodePort 방식 사용) |

## 최종 리소스 상태

```bash
$ kubectl get all,pvc -n argus-insight -l app.kubernetes.io/name=zot-registry

NAME                                READY   STATUS    RESTARTS   AGE
pod/zot-registry-dcd856d5f-hb5nj    1/1     Running   0          5m

NAME                   TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/zot-registry   NodePort   10.43.240.199   <none>        5000:30000/TCP   5m

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/zot-registry   1/1     1            1           5m

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/zot-registry-5dfdb487f5   1         1         1       5m

NAME                             STATUS   VOLUME   CAPACITY   ACCESS MODES   AGE
persistentvolumeclaim/argus-zot-data   Bound    ...      50Gi       RWO            5m
```
