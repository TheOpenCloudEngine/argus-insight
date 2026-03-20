.PHONY: dev run test lint format

dev:
	pip install -e ".[dev,kerberos]"

run:
	metadata-sync

server:
	uvicorn sync.api:app --host 0.0.0.0 --port 4610 --reload

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
