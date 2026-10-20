# RadLabel status

_Updated per milestone. Numbers come only from scripts (see `artifacts/results/`)._
_Owner rule (2026-10-19): stop after every milestone and report hard stops / gaps before continuing._

## Milestones
| ID | State | Notes |
|---|---|---|
| M0 | **Done except Docker** (`4af0dea`) | Owner accepted the direct commands in place of `make test`. `docker compose up` deferred; **must pass before M5**. |
| M1 | **Done** (tag `m1-data`) | Owner-approved 2026-10-20. Numbers below. eval_v1.2 lexicon/termset **permanently frozen**. |
| M2 | **Done** (owner-approved 2026-10-20) | 5 folds over 3,073 clusters, every label within ±1 of equal share (check: ±2); no cluster or exact-text group spans two folds; inner val 245–261 clusters per fold. `artifacts/results/folds.json`. |
| M3 | **Done** (tag `m3-rule-baseline`, owner-approved 2026-10-20) | Rule baseline §8.1 table: `artifacts/tables/labelling_rule_baseline.md`; macro-F1 (9 headline) v1 0.833 (0.818–0.846), strict 0.824; pooled rare micro-F1 v1 0.746. |
| M4 | **Done** (acceptance: rerun from cache $0, 3,086/3,086 cached, raw outputs identical) | gpt-4.1-mini over 3,086 texts: invalid 0, content-filtered 7 (scored with rule-baseline labels), reports with a verifier fail 6.9% (→ Tier 2: 212), review escalations 790. Macro-F1 (9 headline, v1, pilot excluded): rule 0.834, LLM 0.863, LLM+verifier 0.856; paired LLM − rule +0.028 (0.013–0.044). Tier 0: 0 OOF hits by construction. Total LLM spend $2.08. |
| M5–M11 | not started | |

## Decisions (owner)
- **D1 (2026-10-20): nothing is tuned per label.** Every tuned parameter (Tier 0 patterns, refusal threshold, embedding checkpoint, any rule-baseline setting) is ONE global value, selected on a pooled metric (macro-F1 or nDCG over the 9 headline labels) on inner validation. Rare labels are never used for selection.
- **D2 (2026-10-20): gpt-5.4-mini is missing access.** If it still returns 404 at M4, run the Tier 1 pilot with gpt-4.1-mini and gpt-5.4-nano, and use gpt-5-mini as the Tier 1 fallback.
- D3: strict-label fold balance accepted; iterstrat accepted.
- D4: CLAUDE.md stays in the pushed history (`origin/main` was at `dacd923` when checked); no history rewrite.
- **D5 (M3): pipeline/eval vocabulary overlap accepted** (README §11 limitation). The pipeline alias list is **frozen** at the M3 commit (alias-set hash pinned in `tests/test_alias_freeze.py`); any later change needs owner OK and may only be based on training-fold error analysis, never on out-of-fold or test results.
- D6 (M3): `hedged` is excluded from rare-label scores and from the abnormal / redaction_adjacent subset scores, as for headline scores.
- D7 (M3): noise-adjusted scores (README §4.6, Stretch) skipped for now.

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
| Fallback | gpt-5.4-mini | `gpt-5.4-mini-2026-03-17` (works since 2026-10-20) |
| Repair / agents | gpt-5-mini | `gpt-5-mini-2025-08-07` |
| Cheap | gpt-5.4-nano | `gpt-5.4-nano-2026-03-17` |

`AZURE_OPENAI_API_VERSION` is empty, so the client uses Azure's GA v1 API. LLM spend so far: **$0.0710** (ledger `artifacts/llm_cache/ledger.jsonl`).

## M2 notes
- `iterstrat` (CLAUDE.md fallback) used: scikit-multilearn 0.2.0 can't take a seed with scikit-learn 1.9.
- Stratified on the 13 **v1** labels. Strict labels are not stratified: strict Lung Opacity per fold 78–87 (equal share 81.2).
- Inner validation (10% of training clusters) has only **2** Consolidation and **2** Pneumothorax positives per fold (Edema 4, Pleural Other 4): per-label thresholds tuned there will be noisy for rare labels.
- Bootstrap CI utility: `eval/bootstrap.py` (1,000 resamples over clusters).

## M3 notes
- Pipeline modules: `preprocess/negation.py` (NegEx-style, own cue lists), `preprocess/aliases.py` (hand + CheXpert phrases, 30% held out by a fixed SHA-1 rule, anatomy-only anchors), `labelling/schema.py`, `labelling/verifier.py` (6 checks, 7 unit tests), `eval/baselines/rule_baseline.py` (no tuned parameters), `eval/labelling.py` (§8.1).
- Rule baseline verifier messages: 13 `evidence_exists` fails (No Finding predicted present in reports with no No-Finding phrase to cite).
- Pipeline/eval vocabulary overlap: 46 identical entries; accepted (D5).

## M4 notes
- Pilot: 102 reports (96 non-hedged scored) from fold-0 inner-validation clusters; temperature 0; GPT-5.x with reasoning_effort "none".
- Process slip: 5 probe calls went directly through the SDK (not `radlabel.llm`); cost ~$0.00006, logged in the ledger after the fact.
- Owner decisions (2026-10-20): Tier 1 = gpt-4.1-mini (chosen on pilot, CIs overlap); No Finding derived in code; absent-evidence rule (normal_phrases.yaml, else flag); pilot reports excluded from headline OOF metrics (+ all-reports sensitivity); prompt `tier1-v1` frozen; `openai` importable only in `radlabel.llm` (test).
- Follow-up (cache only, $0 new spend): gpt-4.1-mini macro-F1 LLM-only 0.886, paired diff vs rule baseline +0.079 (-0.053 to 0.224); Lung Lesion support in the scored pilot: 2. Report fail rate 46% / flag rate 73% → stop (item 2c).
- (resolved) **Q-M4-1:** 87–96% of pilot outputs fail the verifier, almost all `evidence_mentions_label` on `absent` labels: the models cite generic sentences ("Clear lungs.", "No acute disease.") as evidence of absence, and No Finding `absent` cites abnormal sentences. Scoring is unaffected (only `present` counts), but Tier 2 would receive ~90% of reports.
- **Q-M4-2:** pilot reports come from fold 0's training folds but are test items in folds 1–4 (30/20/26/26).
- (fixed in `cd215fa`) Sentence split missed "[REDACTED].In ...". Still not split: "..", " ." (known issue, `docs/evaluation_notes.md`).

- Full run: 7 reports refused by Azure's content filter (violence, medium); handled as filtered, cached, routed to review. Two runs were interrupted (content-filter 400, then a network error); client/run hardened; completed responses were cached, so no call was paid twice.
- `negation_only` FP pairs now exclude the pilot reports (6,164 pairs): rule 41, LLM 6.
- Owner follow-ups (2026-10-20), all cache-only, $0: paired bootstrap; Atelectasis analysis (57 of 59 LLM FNs are `uncertain` on "scarring or atelectasis"-type alternatives); verifier-column drop explained (hedge conversions, mostly "borderline cardiomegaly"); content-filtered → rule-baseline fallback (default, not owner-decided); `negation_consistency` → flag (pipeline wrong in 20/23, owner's pre-committed rule). Details: `docs/evaluation_notes.md`, `artifacts/results/m4_analysis.json`.
- Tier 0 per fold: 67–81 patterns, 0 OOF hits (exact duplicates share a cluster → fold). Serving patterns: 96.
- Review: 790 escalations (25.6%); M5+ error analysis uses a random sample of ~50.

## Blocked (owner action)
- Docker not installed. Needed before M5.

## Notes
- CLAUDE.md is untracked (`607d1ed`) but remains in the M0 commit's history; no history rewrite (owner decides).
- No commit contains a Co-Authored-By trailer (checked 2026-10-20).
- `.venv`: stdlib venv on uv-managed CPython 3.11.15, packages via `uv pip --python`. `make` not installed; run the Makefile commands directly.
- Data source: Wayback raw capture (Open-i serving a maintenance page). SHA-256 verified.
