FROM rockylinux:9-minimal
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

ARG ZOT_VERSION=2.1.2
ARG TARGETARCH

RUN microdnf install -y jq && microdnf clean all

ADD https://github.com/project-zot/zot/releases/download/v${ZOT_VERSION}/zot-linux-${TARGETARCH} /usr/local/bin/zot
RUN chmod +x /usr/local/bin/zot

RUN mkdir -p /etc/zot /var/lib/zot

EXPOSE 5000

VOLUME ["/var/lib/zot"]

CMD ["/usr/local/bin/zot", "serve", "/etc/zot/config.json"]
