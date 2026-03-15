FROM alpine:3.21 AS builder
ARG PROMETHEUS_VERSION
ARG OS=linux
ARG ARCH=amd64
RUN apk add --no-cache curl tar
RUN curl -sSL -o /tmp/prometheus.tar.gz \
    "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.${OS}-${ARCH}.tar.gz" \
    && tar -xzf /tmp/prometheus.tar.gz -C /tmp \
    && mv /tmp/prometheus-${PROMETHEUS_VERSION}.${OS}-${ARCH} /tmp/prometheus

FROM alpine:3.21
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

RUN addgroup -S prometheus && adduser -S -G prometheus -s /sbin/nologin prometheus
RUN mkdir -p /etc/prometheus/rules /etc/prometheus/consoles /etc/prometheus/console_libraries \
             /var/lib/prometheus/data \
    && chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus

COPY --from=builder /tmp/prometheus/prometheus          /opt/argus-insight/prometheus/prometheus
COPY --from=builder /tmp/prometheus/promtool            /opt/argus-insight/prometheus/promtool
COPY --from=builder /tmp/prometheus/consoles/           /etc/prometheus/consoles/
COPY --from=builder /tmp/prometheus/console_libraries/  /etc/prometheus/console_libraries/
COPY prometheus.yml  /etc/prometheus/prometheus.yml
COPY rules/          /etc/prometheus/rules/

RUN chown -R prometheus:prometheus /etc/prometheus

USER prometheus
EXPOSE 9090
VOLUME ["/etc/prometheus", "/var/lib/prometheus/data"]
ENTRYPOINT ["/opt/argus-insight/prometheus/prometheus"]
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/var/lib/prometheus/data", \
     "--web.listen-address=0.0.0.0:9090", \
     "--web.enable-lifecycle"]
