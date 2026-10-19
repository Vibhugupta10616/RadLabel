# RadLabel status

_Updated per milestone. Numbers come only from scripts (see `artifacts/results/`)._
_Owner rule (2026-10-19): stop after every milestone and report hard stops / gaps before continuing._

## Milestones
| ID | State | Notes |
|---|---|---|
| M0 | **Done except Docker** (`4af0dea`) | Owner accepted the direct commands in place of `make test`. `docker compose up` deferred; **must pass before M5**. |
| M1 | **Done** (tag `m1-data`) | Owner-approved 2026-10-20. Numbers below. eval_v1.2 lexicon/termset **permanently frozen**. |
| M2 | **Done** (acceptance passes; waiting for owner OK before M3) | 5 folds over 3,073 clusters, every label within ±1 of equal share (check: ±2); no cluster or exact-text group spans two folds; inner val 245–261 clusters per fold. `artifacts/results/folds.json`. |
| M3–M11 | not started | |

## M1 results (`make data`, clean `data/processed`)
| Check | Result |
|---|---|
| §3.3 numbers | 3,955 / 95 / 3,832 / 3,086 / 897 / 50 / 1,363→650, all match |
| Clusters (exact pairwise Jaccard ≥ 0.9) | 3,073; 0 near-duplicate clusters with different expert label sets |
| Subsets (`subset_stats.py`, unchanged) | hedged 279, XXXX 1,579, redaction-adjacent 415 (407 unique) |
| §4.4 positives (v1, unique texts) | No Finding 650, Cardiomegaly 395, Lung Opacity 608, Lung Lesion 118, Atelectasis 332, Pleural Effusion 162, Fracture 84, Support Devices 376, Other Abnormality 2,077, Edema 46, Pleural Other 53, Consolidation 30, Pneumothorax 27 |
| Strict | v1-only positives left out of strict: 343 (Lung Opacity 202, Support Devices 106, Cardiomegaly 20, Pleural Other 6, Lung Lesion 4, Pneumothorax 4, Pleural Effusion 1) |
| No Finding exclusions | 7 reports coded only with ignored codes (Technical Quality 6, Contrast Media 1) |
| Audit | 51 rules; 3 below 60% (Pleura n=1, Opacity at pleural site n=3, Density at pleural site n=1), all accepted |
| Mapping cross-check | 64 → 38 disagreements; 3 fixes accepted (see `data_card.json` → `mapping_crosscheck`) |
| Tests | ruff, mypy, 55 pytest |

## Azure deployments (test call per deployment, 2026-10-20)
| Role | Deployment | Model returned |
|---|---|---|
| Tier 1 | gpt-4.1-mini | `gpt-4.1-mini-2025-04-14` |
| Fallback | gpt-5.4-mini | **404 DeploymentNotFound** |
| Repair / agents | gpt-5-mini | `gpt-5-mini-2025-08-07` |
| Cheap | gpt-5.4-nano | `gpt-5.4-nano-2026-03-17` |

`AZURE_OPENAI_API_VERSION` is empty, so the client uses Azure's GA v1 API. LLM spend so far: **$0.0710** (ledger `artifacts/llm_cache/ledger.jsonl`).

## M2 notes
- `iterstrat` (CLAUDE.md fallback) used: scikit-multilearn 0.2.0 can't take a seed with scikit-learn 1.9.
- Stratified on the 13 **v1** labels. Strict labels are not stratified: strict Lung Opacity per fold 78–87 (equal share 81.2).
- Inner validation (10% of training clusters) has only **2** Consolidation and **2** Pneumothorax positives per fold (Edema 4, Pleural Other 4): per-label thresholds tuned there will be noisy for rare labels.
- Bootstrap CI utility: `eval/bootstrap.py` (1,000 resamples over clusters).

## Blocked (owner action)
- **gpt-5.4-mini returns 404.** Check that the deployment name is exactly `gpt-5.4-mini`, on the same resource as `AZURE_OPENAI_ENDPOINT`. Needed for the Tier 1 fallback and the M4 pilot.
- Docker not installed. Needed before M5.

## Notes
- CLAUDE.md is untracked (`607d1ed`) but remains in the M0 commit's history; no history rewrite (owner decides).
- No commit contains a Co-Authored-By trailer (checked 2026-10-20).
- `.venv`: stdlib venv on uv-managed CPython 3.11.15, packages via `uv pip --python`. `make` not installed; run the Makefile commands directly.
- Data source: Wayback raw capture (Open-i serving a maintenance page). SHA-256 verified.
