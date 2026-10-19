# RadLabel status

_Updated per milestone. Numbers come only from scripts (see `artifacts/results/`)._

## Environment (checked 2026-10-19)
| Item | State |
|---|---|
| Python | 3.11.15 (uv-managed) in a **stdlib** venv `.venv`. uv's own venv launcher is blocked by Windows Application Control, so `make setup` uses `python -m venv` + `uv pip install --python`. Run tools as `python -m <tool>`. |
| `make` | **Not installed** on the dev machine. Makefile is written for CI/Linux; locally the same commands are run directly. Optional: `winget install ezwinports.make`. |
| Docker | **Not installed** (neither Windows nor WSL). `docker compose up` untested. Local runs use embedded fallbacks (Qdrant local mode, SQLite, in-process cache). |
| GPU | NVIDIA RTX 5050 Laptop present; training defaults to `--device auto` (CPU torch wheel). |
| Git remote | `origin = https://github.com/Vibhugupta10616/RadLabel` (empty). Nothing pushed yet. |

## Azure deployments
| Role | Deployment (.env) | Version (.env) | Version returned by API |
|---|---|---|---|
| Tier 1 | `AZURE_OPENAI_DEPLOYMENT` | set | **not tested: no API key** |
| Fallback | `AZURE_OPENAI_FALLBACK_DEPLOYMENT` | set | not tested |
| Repair / agents | `AZURE_OPENAI_REPAIR_DEPLOYMENT` | set | not tested |
| Cheap | `AZURE_OPENAI_CHEAP_DEPLOYMENT` | set | not tested |

## Blocked (owner action needed)
1. **`.env`: `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_API_VERSION` are empty.** All LLM work is built and tested against `FakeLLM`; no real Tier 1 / agent numbers until filled.
2. **Docker Desktop not installed.** Needed for `make up` / M0 compose check / M10 end-to-end on Postgres+Qdrant+Redis.

## Done
- M0: skeleton, `pyproject.toml`, Makefile, `.gitignore`, `config.py` (tested to match `.env.example`), docker-compose (postgres, qdrant, redis with healthchecks), CI workflow, pre-commit. `make test` commands green. Compose health **not verified** (no Docker).

## Next
- M1: `make data`.
