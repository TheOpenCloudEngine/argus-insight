include versions.env

DIST_DIR         := dist
DOCKER_REGISTRY  ?= argus-insight
PLATFORMS        ?= linux/amd64,linux/arm64

.PHONY: docker docker-push docker-save docker-load clean

# ─── Docker ──────────────────────────────────────────────────────────────────

docker:
	docker buildx build --platform $(PLATFORMS) \
		--build-arg ZOT_VERSION=$(ZOT_VERSION) \
		-t $(DOCKER_REGISTRY)/zot-registry:$(ZOT_VERSION) \
		--load zot-registry/

docker-push:
	docker buildx build --platform $(PLATFORMS) \
		--build-arg ZOT_VERSION=$(ZOT_VERSION) \
		-t $(DOCKER_REGISTRY)/zot-registry:$(ZOT_VERSION) \
		--push zot-registry/

# ─── Airgap Save / Load ─────────────────────────────────────────────────────

docker-save:
	@mkdir -p $(DIST_DIR)
	docker save $(DOCKER_REGISTRY)/zot-registry:$(ZOT_VERSION) | gzip > $(DIST_DIR)/zot-registry-$(ZOT_VERSION).tar.gz
	@echo "Saved: $(DIST_DIR)/zot-registry-$(ZOT_VERSION).tar.gz"

docker-load:
	docker load < $(DIST_DIR)/zot-registry-$(ZOT_VERSION).tar.gz

# ─── Clean ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(DIST_DIR)
