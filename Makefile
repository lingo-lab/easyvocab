.PHONY: install
install: ## Create the virtual environment and install the pre-commit hooks
	@uv sync --all-extras
	@uv run pre-commit install

.PHONY: check
check: ## Lock file, lint/format (pre-commit), types (ty), dependencies (deptry)
	@uv lock --locked
	@uv run pre-commit run -a
	@uv run ty check
	@uv run deptry src

.PHONY: test
test: ## Run unit tests with coverage
	@uv run pytest --cov --cov-report=term-missing --cov-report=xml

.PHONY: test-live
test-live: ## Run tests against real APIs (needs FIREWORKS_API_KEY, costs ~$0.01)
	@uv run pytest -m live

.PHONY: build
build: ## Build sdist + wheel into dist/
	@rm -rf dist
	@uv build

.PHONY: docs-test
docs-test: ## Check the docs build without warnings
	@uv run --group docs mkdocs build --strict

.PHONY: docs
docs: ## Serve the docs locally
	@uv run --group docs mkdocs serve

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
