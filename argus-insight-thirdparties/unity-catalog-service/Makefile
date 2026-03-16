include versions.env

DIST_DIR      := dist
BUILD_DIR     := $(DIST_DIR)/build
PACKAGE_DIR   := $(DIST_DIR)/packages
NFPM_BIN      := $(DIST_DIR)/nfpm

GITHUB_URL    := https://github.com/unitycatalog/unitycatalog

# sed substitution for nfpm.yaml placeholders
NFPM_SED := sed \
	-e 's|__UNITY_CATALOG_VERSION__|$(UNITY_CATALOG_VERSION)|g' \
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

SOURCE_TARBALL := unitycatalog-$(UNITY_CATALOG_VERSION).tar.gz

# Package filenames
UC_RPM := $(PACKAGE_DIR)/unitycatalog-server-$(UNITY_CATALOG_VERSION)-1.x86_64.rpm
UC_DEB := $(PACKAGE_DIR)/unitycatalog-server_$(UNITY_CATALOG_VERSION)-1_$(ARCH).deb

# Docker
DOCKER_REGISTRY ?= argus-insight

# Print package info after build
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

.PHONY: all clean download build nfpm rpm deb packages docker docker-push helm-package

all: packages

# ─── nfpm ────────────────────────────────────────────────────────────────────

$(NFPM_BIN):
	@mkdir -p $(DIST_DIR)
	@echo "Downloading nfpm $(NFPM_VERSION)..."
	curl -sSL "https://github.com/goreleaser/nfpm/releases/download/v$(NFPM_VERSION)/nfpm_$(NFPM_VERSION)_$(UNAME_OS)_$(HOST_ARCH).tar.gz" \
		| tar -xz -C $(DIST_DIR) nfpm
	@chmod +x $(NFPM_BIN)

nfpm: $(NFPM_BIN)

# ─── Download source ─────────────────────────────────────────────────────────

$(DIST_DIR)/$(SOURCE_TARBALL):
	@mkdir -p $(DIST_DIR)
	@echo "Downloading Unity Catalog $(UNITY_CATALOG_VERSION) source..."
	curl -sSL -o $@ "$(GITHUB_URL)/archive/refs/tags/v$(UNITY_CATALOG_VERSION).tar.gz"

download: $(DIST_DIR)/$(SOURCE_TARBALL)

# ─── Build from source using Docker ──────────────────────────────────────────

$(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION): $(DIST_DIR)/$(SOURCE_TARBALL)
	@mkdir -p $(BUILD_DIR)
	@echo "Building Unity Catalog $(UNITY_CATALOG_VERSION) from source (using Docker)..."
	docker run --rm \
		-v $(CURDIR)/$(DIST_DIR):/dist \
		amazoncorretto:17 \
		bash -c " \
			yum install -y tar gzip git && \
			mkdir -p /build && \
			tar -xzf /dist/$(SOURCE_TARBALL) -C /build --strip-components=1 && \
			cd /build && \
			build/sbt -batch createTarball && \
			mkdir -p /dist/build && \
			tar -xzf /build/target/unitycatalog-*.tar.gz -C /dist/build \
		"
	@echo "Build complete: $(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION)"

build: $(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION)

# ─── Packages (RPM + DEB) ───────────────────────────────────────────────────

packages: $(NFPM_BIN) $(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION)
	@mkdir -p $(PACKAGE_DIR)
	@echo "Building Unity Catalog packages..."
	$(NFPM_SED) server/nfpm.yaml > $(DIST_DIR)/unitycatalog-nfpm.yaml
	cd server && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/unitycatalog-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(UC_RPM))
	cd server && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/unitycatalog-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(UC_DEB))

rpm: $(NFPM_BIN) $(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION)
	@mkdir -p $(PACKAGE_DIR)
	$(NFPM_SED) server/nfpm.yaml > $(DIST_DIR)/unitycatalog-nfpm.yaml
	cd server && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/unitycatalog-nfpm.yaml --packager rpm --target ../$(PACKAGE_DIR)/
	$(call print-rpm,$(UC_RPM))

deb: $(NFPM_BIN) $(BUILD_DIR)/unitycatalog-$(UNITY_CATALOG_VERSION)
	@mkdir -p $(PACKAGE_DIR)
	$(NFPM_SED) server/nfpm.yaml > $(DIST_DIR)/unitycatalog-nfpm.yaml
	cd server && ../$(NFPM_BIN) pkg --config ../$(DIST_DIR)/unitycatalog-nfpm.yaml --packager deb --target ../$(PACKAGE_DIR)/
	$(call print-deb,$(UC_DEB))

# ─── Docker ──────────────────────────────────────────────────────────────────

docker:
	docker build -t $(DOCKER_REGISTRY)/unity-catalog:$(UNITY_CATALOG_VERSION) \
		--build-arg UNITY_CATALOG_VERSION=$(UNITY_CATALOG_VERSION) \
		server/

docker-push:
	docker push $(DOCKER_REGISTRY)/unity-catalog:$(UNITY_CATALOG_VERSION)

# ─── Helm ────────────────────────────────────────────────────────────────────

helm-package:
	@mkdir -p $(PACKAGE_DIR)
	helm package helm/unity-catalog --destination $(PACKAGE_DIR)/

# ─── Clean ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(DIST_DIR)
