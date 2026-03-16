include versions.env

DIST_DIR      := dist
DOWNLOAD_DIR  := $(DIST_DIR)/download
PACKAGE_DIR   := $(DIST_DIR)/packages
NFPM_BIN      := $(DIST_DIR)/nfpm

GITHUB_URL    := https://github.com/prometheus

# sed substitution for nfpm.yaml placeholders
NFPM_SED := sed \
	-e 's|__PROMETHEUS_VERSION__|$(PROMETHEUS_VERSION)|g' \
	-e 's|__PUSHGATEWAY_VERSION__|$(PUSHGATEWAY_VERSION)|g' \
	-e 's|__ALERTMANAGER_VERSION__|$(ALERTMANAGER_VERSION)|g' \
	-e 's|__ARCH__|$(ARCH)|g' \
	-e 's|__OS__|$(OS)|g'

# Detect host OS/arch for nfpm binary download
UNAME_OS      := $(shell uname -s | tr '[:upper:]' '[:lower:]')
UNAME_ARCH    := $(shell uname -m)
ifeq ($(UNAME_ARCH),x86_64)
  HOST_ARCH := x86_64
else ifeq ($(UNAME_ARCH),aarch64)
  HOST_ARCH := arm64
else ifeq ($(UNAME_ARCH),arm64)
  HOST_ARCH := arm64
else
  HOST_ARCH := $(UNAME_ARCH)
endif

PROMETHEUS_TARBALL   := prometheus-$(PROMETHEUS_VERSION).$(OS)-$(ARCH).tar.gz
PUSHGATEWAY_TARBALL  := pushgateway-$(PUSHGATEWAY_VERSION).$(OS)-$(ARCH).tar.gz
ALERTMANAGER_TARBALL := alertmanager-$(ALERTMANAGER_VERSION).$(OS)-$(ARCH).tar.gz

# Package filenames
PROMETHEUS_RPM   := $(PACKAGE_DIR)/prometheus-$(PROMETHEUS_VERSION)-1.x86_64.rpm
PROMETHEUS_DEB   := $(PACKAGE_DIR)/prometheus_$(PROMETHEUS_VERSION)-1_$(ARCH).deb
PUSHGATEWAY_RPM  := $(PACKAGE_DIR)/pushgateway-$(PUSHGATEWAY_VERSION)-1.x86_64.rpm
PUSHGATEWAY_DEB  := $(PACKAGE_DIR)/pushgateway_$(PUSHGATEWAY_VERSION)-1_$(ARCH).deb
ALERTMANAGER_RPM := $(PACKAGE_DIR)/alertmanager-$(ALERTMANAGER_VERSION)-1.x86_64.rpm
ALERTMANAGER_DEB := $(PACKAGE_DIR)/alertmanager_$(ALERTMANAGER_VERSION)-1_$(ARCH).deb

# Print package info after build (silently skip if rpm/dpkg-deb not installed)
define print-rpm
	@echo ""
	@echo "=== RPM: $(notdir $(1)) ==="
	-@rpm -qpi $(1) 2>/dev/null
	@echo "--- Files ---"
	-@rpm -qlp $(1) 2>/dev/null
	@echo ""
endef

define print-deb
	@echo ""
	@echo "=== DEB: $(notdir $(1)) ==="
	-@dpkg-deb -I $(1) 2>/dev/null
	@echo "--- Files ---"
	-@dpkg-deb -c $(1) 2>/dev/null
	@echo ""
endef

PROMETHEUS_URL   := $(GITHUB_URL)/prometheus/releases/download/v$(PROMETHEUS_VERSION)/$(PROMETHEUS_TARBALL)
PUSHGATEWAY_URL  := $(GITHUB_URL)/pushgateway/releases/download/v$(PUSHGATEWAY_VERSION)/$(PUSHGATEWAY_TARBALL)
ALERTMANAGER_URL := $(GITHUB_URL)/alertmanager/releases/download/v$(ALERTMANAGER_VERSION)/$(ALERTMANAGER_TARBALL)

DOCKER_REGISTRY ?= argus-insight

.PHONY: all clean download nfpm prometheus pushgateway alertmanager rpm deb \
        docker docker-prometheus docker-pushgateway docker-alertmanager docker-push

all: prometheus pushgateway alertmanager

# ─── nfpm ────────────────────────────────────────────────────────────────────

$(NFPM_BIN):
	@mkdir -p $(DIST_DIR)
	@echo "Downloading nfpm $(NFPM_VERSION)..."
	curl -sSL "https://github.com/goreleaser/nfpm/releases/download/v$(NFPM_VERSION)/nfpm_$(NFPM_VERSION)_$(UNAME_OS)_$(HOST_ARCH).tar.gz" \
		| tar -xz -C $(DIST_DIR) nfpm
	@chmod +x $(NFPM_BIN)

nfpm: $(NFPM_BIN)

# ─── Download ────────────────────────────────────────────────────────────────

$(DOWNLOAD_DIR)/$(PROMETHEUS_TARBALL):
	@mkdir -p $(DOWNLOAD_DIR)
	@echo "Downloading Prometheus $(PROMETHEUS_VERSION)..."
	curl -sSL -o $@ "$(PROMETHEUS_URL)"
	tar -xzf $@ -C $(DOWNLOAD_DIR)

$(DOWNLOAD_DIR)/$(PUSHGATEWAY_TARBALL):
	@mkdir -p $(DOWNLOAD_DIR)
	@echo "Downloading Pushgateway $(PUSHGATEWAY_VERSION)..."
	curl -sSL -o $@ "$(PUSHGATEWAY_URL)"
	tar -xzf $@ -C $(DOWNLOAD_DIR)

$(DOWNLOAD_DIR)/$(ALERTMANAGER_TARBALL):
	@mkdir -p $(DOWNLOAD_DIR)
	@echo "Downloading Alertmanager $(ALERTMANAGER_VERSION)..."
	curl -sSL -o $@ "$(ALERTMANAGER_URL)"
	tar -xzf $@ -C $(DOWNLOAD_DIR)

download: $(DOWNLOAD_DIR)/$(PROMETHEUS_TARBALL) $(DOWNLOAD_DIR)/$(PUSHGATEWAY_TARBALL) $(DOWNLOAD_DIR)/$(ALERTMANAGER_TARBALL)

# ─── Prometheus ──────────────────────────────────────────────────────────────

prometheus: $(NFPM_BIN) $(DOWNLOAD_DIR)/$(PROMETHEUS_TARBALL)
	@mkdir -p $(PACKAGE_DIR)
	@echo "Building Prometheus packages..."
	$(NFPM_SED) prometheus/nfpm.yaml > $(DIST_DIR)/prometheus-nfpm.yaml
	cd prometheus && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/prometheus-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(PROMETHEUS_RPM))
	cd prometheus && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/prometheus-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(PROMETHEUS_DEB))

# ─── Pushgateway ─────────────────────────────────────────────────────────────

pushgateway: $(NFPM_BIN) $(DOWNLOAD_DIR)/$(PUSHGATEWAY_TARBALL)
	@mkdir -p $(PACKAGE_DIR)
	@echo "Building Pushgateway packages..."
	$(NFPM_SED) pushgateway/nfpm.yaml > $(DIST_DIR)/pushgateway-nfpm.yaml
	cd pushgateway && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/pushgateway-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(PUSHGATEWAY_RPM))
	cd pushgateway && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/pushgateway-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(PUSHGATEWAY_DEB))

# ─── Alertmanager ────────────────────────────────────────────────────────────

alertmanager: $(NFPM_BIN) $(DOWNLOAD_DIR)/$(ALERTMANAGER_TARBALL)
	@mkdir -p $(PACKAGE_DIR)
	@echo "Building Alertmanager packages..."
	$(NFPM_SED) alertmanager/nfpm.yaml > $(DIST_DIR)/alertmanager-nfpm.yaml
	cd alertmanager && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/alertmanager-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(ALERTMANAGER_RPM))
	cd alertmanager && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/alertmanager-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(ALERTMANAGER_DEB))

# ─── Format shortcuts ───────────────────────────────────────────────────────

rpm: $(NFPM_BIN) download
	@mkdir -p $(PACKAGE_DIR)
	$(NFPM_SED) prometheus/nfpm.yaml > $(DIST_DIR)/prometheus-nfpm.yaml
	$(NFPM_SED) pushgateway/nfpm.yaml > $(DIST_DIR)/pushgateway-nfpm.yaml
	$(NFPM_SED) alertmanager/nfpm.yaml > $(DIST_DIR)/alertmanager-nfpm.yaml
	cd prometheus && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/prometheus-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(PROMETHEUS_RPM))
	cd pushgateway && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/pushgateway-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(PUSHGATEWAY_RPM))
	cd alertmanager && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/alertmanager-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(ALERTMANAGER_RPM))

deb: $(NFPM_BIN) download
	@mkdir -p $(PACKAGE_DIR)
	$(NFPM_SED) prometheus/nfpm.yaml > $(DIST_DIR)/prometheus-nfpm.yaml
	$(NFPM_SED) pushgateway/nfpm.yaml > $(DIST_DIR)/pushgateway-nfpm.yaml
	$(NFPM_SED) alertmanager/nfpm.yaml > $(DIST_DIR)/alertmanager-nfpm.yaml
	cd prometheus && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/prometheus-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(PROMETHEUS_DEB))
	cd pushgateway && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/pushgateway-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(PUSHGATEWAY_DEB))
	cd alertmanager && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/alertmanager-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(ALERTMANAGER_DEB))

# ─── Docker ──────────────────────────────────────────────────────────────────

docker: docker-prometheus docker-pushgateway docker-alertmanager

docker-prometheus:
	docker build -t $(DOCKER_REGISTRY)/prometheus:$(PROMETHEUS_VERSION) \
		--build-arg PROMETHEUS_VERSION=$(PROMETHEUS_VERSION) \
		--build-arg OS=$(OS) --build-arg ARCH=$(ARCH) \
		prometheus/

docker-pushgateway:
	docker build -t $(DOCKER_REGISTRY)/pushgateway:$(PUSHGATEWAY_VERSION) \
		--build-arg PUSHGATEWAY_VERSION=$(PUSHGATEWAY_VERSION) \
		--build-arg OS=$(OS) --build-arg ARCH=$(ARCH) \
		pushgateway/

docker-alertmanager:
	docker build -t $(DOCKER_REGISTRY)/alertmanager:$(ALERTMANAGER_VERSION) \
		--build-arg ALERTMANAGER_VERSION=$(ALERTMANAGER_VERSION) \
		--build-arg OS=$(OS) --build-arg ARCH=$(ARCH) \
		alertmanager/

docker-push:
	docker push $(DOCKER_REGISTRY)/prometheus:$(PROMETHEUS_VERSION)
	docker push $(DOCKER_REGISTRY)/pushgateway:$(PUSHGATEWAY_VERSION)
	docker push $(DOCKER_REGISTRY)/alertmanager:$(ALERTMANAGER_VERSION)

# ─── Clean ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(DIST_DIR)
