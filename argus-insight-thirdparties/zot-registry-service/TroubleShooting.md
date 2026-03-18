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

## 5. Docker HTTPS 에러 - insecure-registries 없이 TLS 설정

### 증상

ClusterIP로 직접 Docker login 시 HTTPS 에러:

```bash
$ docker login 10.43.234.67:5000 -u admin -p 'Argus!insight2026'

Error response from daemon: Get "https://10.43.234.67:5000/v2/":
  http: server gave HTTP response to HTTPS client
```

### 원인

Docker 클라이언트는 기본적으로 HTTPS로 레지스트리에 접속한다. Kubernetes ConfigMap의 `config.json`에는 TLS 설정이 제거되어 있어 Zot이 HTTP로만 동작하는데, Docker는 이를 거부한다.

### 해결 (Production 권장 방식: Ingress TLS 종단)

`insecure-registries`는 개발/테스트 환경에서만 사용하고, Production에서는 Nginx Ingress에서 TLS를 종단하는 방식을 사용한다.

**Step 1.** Nginx Ingress Controller 설치:

```bash
$ kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml

$ kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller
NAME                                        READY   STATUS    RESTARTS   AGE
ingress-nginx-controller-5768fd7c75-b9575   1/1     Running   0          60s
```

**Step 2.** TLS 인증서 생성 및 Secret 등록:

```bash
# 자체 서명 인증서 생성
$ openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /tmp/zot-tls.key -out /tmp/zot-tls.crt \
    -subj "/CN=zot.argus-insight.dev.net" \
    -addext "subjectAltName=DNS:zot.argus-insight.dev.net"

# Kubernetes TLS Secret 생성
$ kubectl create secret tls zot-registry-tls \
    --cert=/tmp/zot-tls.crt --key=/tmp/zot-tls.key \
    -n argus-insight
```

**Step 3.** `kubernetes/ingress.yaml` 생성:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: zot-registry
  namespace: argus-insight
  labels:
    app.kubernetes.io/name: zot-registry
    app.kubernetes.io/part-of: argus-insight
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - zot.argus-insight.dev.net
      secretName: zot-registry-tls
  rules:
    - host: zot.argus-insight.dev.net
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: zot-registry
                port:
                  number: 5000
```

주요 annotation 설명:
- `proxy-body-size: "0"`: 이미지 push 시 업로드 크기 제한 해제 (기본 1MB)
- `proxy-read-timeout: "600"`: 대용량 이미지 pull 시 타임아웃 방지
- `proxy-send-timeout: "600"`: 대용량 이미지 push 시 타임아웃 방지

**Step 4.** `kubernetes/kustomization.yaml`에 ingress 추가:

```yaml
resources:
  - namespace.yaml
  - secret.yaml
  - configmap.yaml
  - pvc.yaml
  - zot-registry.yaml
  - ingress.yaml          # 추가
```

**Step 5.** 배포 및 확인:

```bash
$ kubectl apply -k kubernetes/

$ kubectl get ingress -n argus-insight
NAME           CLASS   HOSTS                       PORTS     AGE
zot-registry   nginx   zot.argus-insight.dev.net   80, 443   4s
```

**Step 6.** DNS/호스트 등록:

```bash
# /etc/hosts에 호스트명 등록
$ echo "10.0.1.50 zot.argus-insight.dev.net" >> /etc/hosts
```

**Step 7.** Nginx Ingress의 HTTPS NodePort 확인:

```bash
$ kubectl get svc -n ingress-nginx ingress-nginx-controller

NAME                       TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)
ingress-nginx-controller   LoadBalancer   10.43.191.29   <pending>     80:32655/TCP,443:31274/TCP
```

ExternalIP가 `<pending>`인 경우 NodePort(`31274`)를 사용한다.

**Step 8.** Docker 클라이언트에 자체 서명 CA 등록:

```bash
$ mkdir -p /etc/docker/certs.d/zot.argus-insight.dev.net:31274
$ cp /tmp/zot-tls.crt /etc/docker/certs.d/zot.argus-insight.dev.net:31274/ca.crt
```

**Step 9.** 접속 테스트:

```bash
# Docker login
$ echo 'Argus!insight2026' | docker login zot.argus-insight.dev.net:31274 -u admin --password-stdin
Login Succeeded

# 이미지 push
$ docker tag hello-world:latest zot.argus-insight.dev.net:31274/library/hello-world:latest
$ docker push zot.argus-insight.dev.net:31274/library/hello-world:latest
latest: digest: sha256:2771e37a12b7bcb... size: 1035

# 레지스트리 카탈로그 확인
$ curl -sk -u admin:'Argus!insight2026' https://zot.argus-insight.dev.net:31274/v2/_catalog
{"repositories":["library/hello-world"]}
```

---

## 최종 변경 파일 요약

| 파일 | 변경 내용 |
|---|---|
| `kubernetes/zot-registry.yaml` | `imagePullPolicy: IfNotPresent` 추가, probe를 `tcpSocket`으로 변경, `strategy: Recreate` 추가 |
| `kubernetes/secret.yaml` | htpasswd placeholder를 실제 bcrypt 해시로 교체 |
| `kubernetes/ingress.yaml` | **신규** - Nginx Ingress 리소스 (TLS 종단, body-size 제한 해제) |
| `kubernetes/kustomization.yaml` | `ingress.yaml` 리소스 추가 |

## 최종 리소스 상태

```bash
$ kubectl get all,ingress,pvc -n argus-insight -l app.kubernetes.io/name=zot-registry

NAME                                READY   STATUS    RESTARTS   AGE
pod/zot-registry-54d747498b-6jknq   1/1     Running   0          5m

NAME                   TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
service/zot-registry   ClusterIP   10.43.234.67   <none>        5000/TCP   5m

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/zot-registry   1/1     1            1           5m

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/zot-registry-54d747498b   1         1         1       5m

NAME                                        CLASS   HOSTS                       PORTS     AGE
ingress.networking.k8s.io/zot-registry      nginx   zot.argus-insight.dev.net   80, 443   3m

NAME                             STATUS   VOLUME   CAPACITY   ACCESS MODES   AGE
persistentvolumeclaim/argus-zot-data   Bound    ...      50Gi       RWO            5m
```
