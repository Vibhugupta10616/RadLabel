ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python.exe
else
PY ?= .venv/bin/python
endif
EXTRAS ?= dev,eval

.PHONY: setup data folds label-eval index train-embeddings retrieval-eval agent-eval up down test report

# stdlib venv + uv pip: works on every platform (uv's own venv launcher was blocked by Windows Smart App Control)
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

# Reference scripts run isolated (-I) on the untrusted download; our modules run from the repo root.
data:
	$(PY) -I data_prep/download.py data/raw
	$(PY) -c "import pathlib; pathlib.Path('data/processed').mkdir(parents=True, exist_ok=True)"
	$(PY) -I data_prep/parse_iu.py data/raw/xml/ecgen-radiology data/processed/iu.jsonl
	$(PY) -I data_prep/map_and_stats.py data/processed/iu.jsonl data/processed/iu_mapped_ref.jsonl
	$(PY) -I data_prep/subset_stats.py data/processed/iu_mapped_ref.jsonl
	$(PY) -m data_prep.build_dataset
	$(PY) -m data_prep.audit_mapping

folds:
	$(PY) -m eval.cv
