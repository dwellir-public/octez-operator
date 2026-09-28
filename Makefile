.PHONY: charm-venv lock fmt-test lint-test unit-test integration-test build-charm
charm-venv:
	uv sync --frozen --all-groups
lock:
	uv lock
fmt-test:
	uv run --frozen --group lint ruff format src tests
lint-test:
	uv run --frozen --group lint ruff check src tests
	uv run --frozen --group lint ruff format --check src tests
unit-test:
	uv run --frozen --group unit pytest tests/unit --cov=src --cov-report=term-missing
integration-test:
	uv run --frozen --group integration pytest tests/integration --destructive-mode -v $(ARGS)
build-charm:
	charmcraft pack --platform=ubuntu@24.04:amd64
