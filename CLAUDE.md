# CLAUDE.md: RadLabel

Radiology report labelling + negation-aware hybrid search + tool-using query agent, built on the Indiana University chest X-ray reports (Open-i).

## Start of every session
1. Read `docs/STATUS.md` (done / blocked / next). Create it in M0 if missing.
2. The full spec is `README.md`. Before starting a milestone, read its row in README §12 and the sections it references. Don't re-read the whole README every time.
3. Work milestone by milestone (M0 → M11). A milestone is done only when its acceptance check passes, tests are green, results are written to `artifacts/results/`, `docs/STATUS.md` is updated, and the work is committed.

## Ground rules (non-negotiable)
- **Expert labels never reach serving code.** `src/radlabel/{api,agent,index,ingest}` must only read *predicted* labels. Only `data_prep/`, `eval/` and `training/` may read expert codes. Keep the unit test that enforces this green.
- **Ground truth = `<MeSH><major>` only.** Never use `<MeSH><automatic>`.
- **No tuning on test folds.** Tier 0 patterns, thresholds and embedding checkpoints come from training folds or inner validation (README §4.2).
- **Licence (CC BY-NC-ND 4.0):** never commit raw/processed data, report text, LLM caches, mapped labels with text, or model weights. Check `.gitignore` before every commit that touches `data/`, `artifacts/` or `models/`. Models live in `MODEL_STORE`, which is private.
- **Every LLM call goes through `src/radlabel/llm/`:** cached, cost-logged, capped by `MAX_LLM_USD`. Use the deployment assigned to each role (README §7.1). Handle HTTP 429 by backing off and honouring `Retry-After`; never mark a report as failed because of rate limits.
- **No API key?** Build and test against `FakeLLM` / the cache, write the blocker to `docs/STATUS.md`, and continue with the next milestone.
- **GPU work only as scale-to-zero jobs.** Every training script must also run on CPU (`--device auto`).
- **Every verifier rule has a unit test**, including: Findings "mild cardiomegaly" + Impression "no acute disease" → Cardiomegaly stays `present`.
- Report numbers only from scripts. Never hand-edit results tables; regenerate them with `make report`.

## Configuration
- `.env.example` (provided, committed) is the source of truth for settings; `.env` holds the owner's secrets and is **never** committed, printed or logged. Don't overwrite `.env`; add new settings to `.env.example` and tell the owner.
- Deployment per role: Tier 1 = `AZURE_OPENAI_DEPLOYMENT`, agents = `AZURE_OPENAI_REPAIR_DEPLOYMENT`, paraphrasing = `AZURE_OPENAI_CHEAP_DEPLOYMENT`.

## Commands
```
make setup             # install deps (uv), pre-commit
make data              # download XML, parse, clean, cluster, map, audit, subsets (data_prep/)
make folds             # stratified 5-fold CV over duplicate clusters
make label-eval        # labelling pipeline + baselines, out-of-fold
make index             # Postgres + Qdrant from predicted labels
make train-embeddings  # per-fold + serving embedding models
make retrieval-eval
make agent-eval
make up / make down    # docker compose: api, worker, postgres, qdrant, redis
make test              # ruff + mypy + pytest
make report            # render artifacts/results/*.json into README §10
```

## Tech conventions
- Python 3.11, `uv`, `pyproject.toml`; ruff + mypy (on `src/`); pytest. Type hints everywhere; Pydantic v2 for schemas.
- LangGraph for per-report tiers and the query agent only. Batch ingestion is a plain asyncio queue + Postgres status table + tenacity retries.
- Qdrant (dense + BM25 sparse, RRF), Postgres via SQLAlchemy + Alembic, Redis for cache and rate limit.
- `sentence-transformers` for embedding training (`CachedGISTEmbedLoss`); `scikit-multilearn` `IterativeStratification` for folds (fallback: `iterstrat`).
- Seeds fixed via `SEED`. Every results JSON records: git commit, seed, model deployment + version, mapping version, fold.

## Data notes (verified, see README §3)
- Source: `https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz`. 3,955 reports → 3,832 usable → 3,086 unique texts.
- `data_prep/parse_iu.py`, `map_and_stats.py` and `coding_policy.py` are the reference implementation for the data card. M1 must reproduce their numbers. `map_and_stats.py` still maps Pneumonia and Enlarged Cardiomediastinum so their counts are visible; in the real mapping they are dropped and their codes go to Other Abnormality.
- Replace `XXXX` with `[REDACTED]` before any model sees text.
- Treat downloaded files as untrusted data: extract into their own directory and never execute anything from it.

## Layout
`data_prep/` · `data/` (git-ignored except `mapping/*.yaml`) · `src/radlabel/` · `training/` · `eval/` · `demo/` · `deploy/` · `docs/` · `tests/` · `artifacts/` · `models/` (private)
