.PHONY: dev run test lint format clean

dev:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --host 0.0.0.0 --port 4700 --reload

test:
	pytest tests/ -v

lint:
	ruff check app/ tests/ && ruff format --check app/ tests/

format:
	ruff format app/ tests/ && ruff check --fix app/ tests/

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
