Docker Image는 https://hub.docker.com/r/prom/prometheus와 같은 형식으로 접근할 수 있습니다.

```
#!/bin/sh
ZOT="${ZOT}"

# Minio
docker pull ${ZOT}/minio/minio:RELEASE.2025-09-07T16-13-09Z
docker pull ${ZOT}/minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1

# Prometheus
docker pull ${ZOT}/prom/prometheus:main-distroless
docker pull ${ZOT}/prom/pushgateway:v1.11.2
docker pull ${ZOT}/prom/alertmanager:v0.31.1

# Grafana
docker pull ${ZOT}/grafana/grafana:12.3

docker pull ${ZOT}/gitpod/openvscode-server:1.105.1

docker pull ${ZOT}/jupyter/datascience-notebook:x86_64-ubuntu-22.04

docker pull ${ZOT}/keycloak/keycloak:26.5

docker pull ${ZOT}/postgres:16.13-alpine3.23

docker pull ${ZOT}/mariadb:10.11.16

docker pull ${ZOT}/larribas/mlflow:1.9.1

# PowerDNS
docker pull ${ZOT}/postgres:15-alpine
docker pull ${ZOT}/psitrax/powerdns:v4.4.1
docker pull ${ZOT}/powerdnsadmin/pda-legacy:v0.4.2
```
