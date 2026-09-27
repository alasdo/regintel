# Definition of done: `make check` passes.
# Claude's Stop hook runs `make check` automatically when the tree has changed.
# Set UV= to run with a plain virtualenv instead: `make check UV=`
UV ?= uv
RUN := $(if $(UV),$(UV) run,)

.PHONY: help setup fmt lint typecheck test cov check clean

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

setup:  ## Install dependencies (incl. dev)
	$(UV) sync

fmt:  ## Format and auto-fix
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

lint:  ## Check formatting and lint (no changes)
	$(RUN) ruff format --check .
	$(RUN) ruff check .

typecheck:  ## Static types
	$(RUN) mypy

test:  ## Run tests
	$(RUN) pytest

cov:  ## Tests with coverage report
	$(RUN) pytest --cov=src --cov-report=term-missing

check: lint typecheck test  ## Everything that must pass before a change is done

clean:  ## Remove caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
