NAME = argus-insight-usersync
VERSION = 0.1.0

.PHONY: help install dev run test lint clean rpm deb

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -e .

dev: ## Install with dev dependencies
	pip install -e ".[dev]"

run: ## Run the usersync batch job
	python -m app.main

dry-run: ## Run in dry-run mode (no changes to Ranger)
	python -m app.main --dry-run

test: ## Run tests
	pytest tests/ -v

lint: ## Run linter
	ruff check app/ tests/
	ruff format --check app/ tests/

format: ## Format code
	ruff format app/ tests/
	ruff check --fix app/ tests/

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

rpm: clean ## Build RPM package
	mkdir -p build/rpm
	tar czf build/rpm/$(NAME)-$(VERSION).tar.gz \
		--transform 's,^,$(NAME)-$(VERSION)/,' \
		app/ scripts/ packaging/ pyproject.toml README.md LICENSE
	rpmbuild -ba packaging/rpm/$(NAME).spec \
		--define "_sourcedir $(CURDIR)/build/rpm" \
		--define "_srcrpmdir $(CURDIR)/dist" \
		--define "_rpmdir $(CURDIR)/dist"

deb: clean ## Build Debian package
	dpkg-buildpackage -us -uc -b
