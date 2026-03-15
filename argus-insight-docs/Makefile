NAME = argus-insight-docs
VERSION = 0.1.0

.PHONY: help install build pdf preview clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (npm for Antora, gem for PDF)
	npm install
	gem install asciidoctor-pdf rouge

build: ## Build HTML site
	npx antora antora-playbook.yml

pdf: ## Build PDF document
	@mkdir -p build/pdf
	asciidoctor-pdf pdf/argus-insight-book.adoc \
		-a pdf-themesdir=pdf \
		-a pdf-theme=argus-insight \
		-o build/pdf/argus-insight.pdf

preview: ## Build and preview in browser
	npm run preview

clean: ## Clean build artifacts
	rm -rf build .antora-cache
