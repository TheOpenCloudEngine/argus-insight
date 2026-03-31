# Kubernetes Worker Node Configuration

Argus Insight 플랫폼의 K8s 워커 노드에 필요한 시스템 설정을 정리합니다.

## inotify 파일 감시 제한 설정

### 문제

컨테이너 로그에 다음 오류가 반복 출력됩니다:

```
failed to create fsnotify watcher: too many open files
```

Airflow git-sync, Next.js dev 서버, VS Code Server, JupyterLab 등 파일 변경을 감시하는 컨테이너가 다수 실행되면 Linux 커널의 inotify 기본 제한(`max_user_watches=8192`, `max_user_instances=128`)이 빠르게 소진됩니다.

### 해결

모든 K8s 워커 노드에서 다음을 실행합니다.

#### 즉시 적용

```bash
sudo sysctl fs.inotify.max_user_watches=524288
sudo sysctl fs.inotify.max_user_instances=1024
```

#### 영구 적용 (재부팅 후에도 유지)

```bash
cat <<'EOF' | sudo tee /etc/sysctl.d/99-inotify.conf
fs.inotify.max_user_watches=524288
fs.inotify.max_user_instances=1024
EOF

sudo sysctl --system
```

#### 적용 확인

```bash
sysctl fs.inotify.max_user_watches fs.inotify.max_user_instances
```

### 설정 값 설명

| 파라미터 | 기본값 | 권장값 | 설명 |
|----------|--------|--------|------|
| `fs.inotify.max_user_watches` | 8,192 | 524,288 | 사용자당 inotify watch 최대 수 |
| `fs.inotify.max_user_instances` | 128 | 1,024 | 사용자당 inotify 인스턴스 최대 수 |

### 적용 대상

- 모든 K8s 워커 노드 (컨트롤 플레인 포함 권장)
- 노드 추가 시에도 동일하게 적용 필요
