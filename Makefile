.DEFAULT_GOAL := help
PYTHON ?= python3
VENV   ?= .venv

.PHONY: help venv install test lint format typecheck check build clean demo release

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv:  ## Create the virtualenv
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"

install: venv  ## Install the package in editable mode

test:  ## Run the test suite
	$(VENV)/bin/python -m pytest -q

test-standalone:  ## Run the test suite with the standard library only
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:  ## Check formatting and style
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests

format:  ## Apply formatting
	$(VENV)/bin/ruff format src tests
	$(VENV)/bin/ruff check --fix src tests

typecheck:  ## Run mypy
	$(VENV)/bin/mypy src/cronport

check: lint typecheck test  ## Run every check

build:  ## Build the sdist and the wheel
	$(VENV)/bin/python -m build

clean:  ## Remove build artefacts
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

demo:  ## Regenerate the demo animation
	$(PYTHON) scripts/make_demo.py

release: build  ## Build and upload to PyPI
	$(VENV)/bin/python -m twine upload dist/*
