include versions.env

DIST_DIR      := dist
PACKAGE_DIR   := $(DIST_DIR)/packages

# Docker
DOCKER_REGISTRY ?= argus-insight

.PHONY: all clean \
	docker docker-postgresql docker-unity-catalog \
	docker-push docker-push-postgresql docker-push-unity-catalog \
	docker-save docker-load helm-package

all: docker

# ─── Docker ──────────────────────────────────────────────────────────────────

docker: docker-postgresql docker-unity-catalog

docker-postgresql:
	docker build -t $(DOCKER_REGISTRY)/unity-catalog-postgresql:$(POSTGRESQL_VERSION) \
		postgresql/

docker-unity-catalog:
	docker build -t $(DOCKER_REGISTRY)/unity-catalog:$(UNITY_CATALOG_VERSION) \
		server/

# ─── Docker Push ─────────────────────────────────────────────────────────────

docker-push: docker-push-postgresql docker-push-unity-catalog

docker-push-postgresql:
	docker push $(DOCKER_REGISTRY)/unity-catalog-postgresql:$(POSTGRESQL_VERSION)

docker-push-unity-catalog:
	docker push $(DOCKER_REGISTRY)/unity-catalog:$(UNITY_CATALOG_VERSION)

# ─── Airgap Save / Load ─────────────────────────────────────────────────────

docker-save:
	@mkdir -p $(DIST_DIR)
	docker save $(DOCKER_REGISTRY)/unity-catalog-postgresql:$(POSTGRESQL_VERSION) | gzip > $(DIST_DIR)/unity-catalog-postgresql-$(POSTGRESQL_VERSION).tar.gz
	@echo "Saved: $(DIST_DIR)/unity-catalog-postgresql-$(POSTGRESQL_VERSION).tar.gz"
	docker save $(DOCKER_REGISTRY)/unity-catalog:$(UNITY_CATALOG_VERSION) | gzip > $(DIST_DIR)/unity-catalog-$(UNITY_CATALOG_VERSION).tar.gz
	@echo "Saved: $(DIST_DIR)/unity-catalog-$(UNITY_CATALOG_VERSION).tar.gz"

docker-load:
	gunzip -c $(DIST_DIR)/unity-catalog-postgresql-$(POSTGRESQL_VERSION).tar.gz | docker load
	gunzip -c $(DIST_DIR)/unity-catalog-$(UNITY_CATALOG_VERSION).tar.gz | docker load

# ─── Helm ────────────────────────────────────────────────────────────────────

helm-package:
	@mkdir -p $(PACKAGE_DIR)
	helm package helm/unity-catalog --destination $(PACKAGE_DIR)/

# ─── Clean ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(DIST_DIR)
