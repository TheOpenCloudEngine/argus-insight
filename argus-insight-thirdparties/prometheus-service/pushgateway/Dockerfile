FROM alpine:3.21 AS builder
ARG PUSHGATEWAY_VERSION
ARG OS=linux
ARG ARCH=amd64
RUN apk add --no-cache curl tar
RUN curl -sSL -o /tmp/pushgateway.tar.gz \
    "https://github.com/prometheus/pushgateway/releases/download/v${PUSHGATEWAY_VERSION}/pushgateway-${PUSHGATEWAY_VERSION}.${OS}-${ARCH}.tar.gz" \
    && tar -xzf /tmp/pushgateway.tar.gz -C /tmp \
    && mv /tmp/pushgateway-${PUSHGATEWAY_VERSION}.${OS}-${ARCH} /tmp/pushgateway

FROM alpine:3.21
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

RUN addgroup -S prometheus && adduser -S -G prometheus -s /sbin/nologin prometheus

COPY --from=builder /tmp/pushgateway/pushgateway /opt/argus-insight/prometheus/pushgateway

USER prometheus
EXPOSE 9091
ENTRYPOINT ["/opt/argus-insight/prometheus/pushgateway"]
CMD ["--web.listen-address=0.0.0.0:9091"]
