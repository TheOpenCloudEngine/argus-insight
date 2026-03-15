NAME = argus-insight-docs
VERSION = 0.1.0

.PHONY: help install build pdf preview clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	npm install

build: ## Build HTML site
	npx antora antora-playbook.yml

pdf: ## Build PDF document
	npx antora antora-playbook-pdf.yml

preview: ## Build and preview in browser
	npm run preview

clean: ## Clean build artifacts
	rm -rf build .antora-cache
