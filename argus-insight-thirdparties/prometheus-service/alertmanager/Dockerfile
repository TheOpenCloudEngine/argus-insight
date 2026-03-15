FROM alpine:3.21 AS builder
ARG ALERTMANAGER_VERSION
ARG OS=linux
ARG ARCH=amd64
RUN apk add --no-cache curl tar
RUN curl -sSL -o /tmp/alertmanager.tar.gz \
    "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.${OS}-${ARCH}.tar.gz" \
    && tar -xzf /tmp/alertmanager.tar.gz -C /tmp \
    && mv /tmp/alertmanager-${ALERTMANAGER_VERSION}.${OS}-${ARCH} /tmp/alertmanager

FROM alpine:3.21
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

RUN addgroup -S prometheus && adduser -S -G prometheus -s /sbin/nologin prometheus
RUN mkdir -p /etc/prometheus /var/lib/prometheus/alertmanager \
    && chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus

COPY --from=builder /tmp/alertmanager/alertmanager /opt/argus-insight/prometheus/alertmanager
COPY --from=builder /tmp/alertmanager/amtool       /opt/argus-insight/prometheus/amtool
COPY alertmanager.yml /etc/prometheus/alertmanager.yml

RUN chown -R prometheus:prometheus /etc/prometheus

USER prometheus
EXPOSE 9093
VOLUME ["/var/lib/prometheus"]
ENTRYPOINT ["/opt/argus-insight/prometheus/alertmanager"]
CMD ["--config.file=/etc/prometheus/alertmanager.yml", \
     "--storage.path=/var/lib/prometheus/alertmanager", \
     "--web.listen-address=0.0.0.0:9093"]
