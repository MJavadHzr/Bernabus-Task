# BARN-AIS-EVAL-001 — one documented command per task (Gate One).
.PHONY: install validate eval test reliability report hash-cases lint clean all
.DEFAULT_GOAL := help

VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
CONFIG := configs/run.default.yaml

help:
	@echo "make install     create venv and install pinned dependencies"
	@echo "make validate    schema + registry preconditions, no scoring"
	@echo "make eval        full evaluation run -> results/runs/<run_id>/"
	@echo "make test        unit tests"
	@echo "make reliability evaluator invariance suite (block condition 3.14.5)"
	@echo "make report      regenerate summary + evaluation card from latest run"
	@echo "make hash-cases  recompute content_hash for every evaluation case"
	@echo "make all         validate + eval + test"

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

validate:
	$(PY) -m barn_eval.cli validate --config $(CONFIG)

eval:
	$(PY) -m barn_eval.cli run --config $(CONFIG)

test:
	$(VENV)/bin/pytest

reliability:
	$(PY) -m barn_eval.cli reliability --config $(CONFIG)

report:
	$(PY) -m barn_eval.cli report --config $(CONFIG)

hash-cases:
	$(PY) -m barn_eval.cli validate --config $(CONFIG) --rehash

lint:
	$(VENV)/bin/ruff check src/barn_eval tests

clean:
	rm -rf $(VENV) .pytest_cache **/__pycache__

all: validate eval test
