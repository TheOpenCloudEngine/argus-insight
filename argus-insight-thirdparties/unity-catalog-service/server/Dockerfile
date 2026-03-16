FROM amazoncorretto:17-alpine AS builder
ARG UNITY_CATALOG_VERSION=0.4.0

RUN apk add --no-cache curl tar bash git

WORKDIR /build

# Download and extract Unity Catalog source
RUN curl -sSL -o /tmp/unitycatalog.tar.gz \
    "https://github.com/unitycatalog/unitycatalog/archive/refs/tags/v${UNITY_CATALOG_VERSION}.tar.gz" \
    && tar -xzf /tmp/unitycatalog.tar.gz -C /build --strip-components=1 \
    && rm /tmp/unitycatalog.tar.gz

# Build the tarball
RUN build/sbt -batch createTarball

# Extract the built tarball
RUN mkdir -p /opt/unitycatalog \
    && tar -xzf target/unitycatalog-*.tar.gz -C /opt/unitycatalog --strip-components=1

# --- Runtime stage ---
FROM alpine:3.21
LABEL maintainer="Open Cloud Engine <fharenheit@gmail.com>"

# Install JRE 17
RUN apk add --no-cache openjdk17-jre-headless bash

# Create system user
RUN addgroup -S unitycatalog && adduser -S -G unitycatalog -s /sbin/nologin unitycatalog

# Create directories
RUN mkdir -p /opt/argus-insight/unity-catalog \
             /etc/unity-catalog \
             /var/lib/unity-catalog/data \
             /var/log/unity-catalog \
    && chown -R unitycatalog:unitycatalog /var/lib/unity-catalog /var/log/unity-catalog

# Copy built artifacts from builder
COPY --from=builder /opt/unitycatalog/bin/    /opt/argus-insight/unity-catalog/bin/
COPY --from=builder /opt/unitycatalog/jars/   /opt/argus-insight/unity-catalog/jars/

# Create etc/data symlink for default storage
RUN mkdir -p /opt/argus-insight/unity-catalog/etc \
    && ln -s /var/lib/unity-catalog/data /opt/argus-insight/unity-catalog/etc/data

# Copy config
COPY server.properties /etc/unity-catalog/server.properties

RUN chown -R unitycatalog:unitycatalog /opt/argus-insight/unity-catalog \
    && chown -R root:unitycatalog /etc/unity-catalog \
    && chmod 750 /etc/unity-catalog

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk

USER unitycatalog
WORKDIR /opt/argus-insight/unity-catalog
EXPOSE 8080

VOLUME ["/var/lib/unity-catalog"]
ENTRYPOINT ["/opt/argus-insight/unity-catalog/bin/start-uc-server"]
