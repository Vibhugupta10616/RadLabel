ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python.exe
else
PY ?= .venv/bin/python
endif
EXTRAS ?= dev

.PHONY: setup data folds label-eval index train-embeddings retrieval-eval agent-eval up down test report

# stdlib venv: uv's venv launcher is blocked by Windows Application Control on the dev machine
setup:
	python3.11 -m venv .venv || python -m venv .venv
	uv pip install --python $(PY) -e ".[$(EXTRAS)]"
	$(PY) -m pre_commit install || true

test:
	$(PY) -m ruff check .
	$(PY) -m mypy
	$(PY) -m pytest -q

up:
	docker compose up -d --wait

down:
	docker compose down
