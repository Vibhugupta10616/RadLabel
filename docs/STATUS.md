# RadLabel status

_Updated per milestone. Numbers come only from scripts (see `artifacts/results/`)._
_Owner rule (2026-10-19): stop after every milestone and report hard stops / gaps before continuing._

## Milestones
| ID | State | Notes |
|---|---|---|
| M0 | **Done** (`4af0dea`; Docker check 2026-10-20) | Owner accepted the direct commands in place of `make test`. `docker compose up -d --wait`: postgres, qdrant, redis healthy (Docker 29.9.1, Compose v5.6.0). |
| M1 | **Done** (tag `m1-data`) | Owner-approved 2026-10-20. Numbers below. eval_v1.2 lexicon/termset **permanently frozen**. |
| M2 | **Done** (owner-approved 2026-10-20) | 5 folds over 3,073 clusters, every label within ±1 of equal share (check: ±2); no cluster or exact-text group spans two folds; inner val 245–261 clusters per fold. `artifacts/results/folds.json`. |
| M3 | **Done** (tag `m3-rule-baseline`, owner-approved 2026-10-20) | Rule baseline §8.1 table: `artifacts/tables/labelling_rule_baseline.md`; numbers at M3 (pre-splitter): macro-F1 (9 headline) v1 0.833 (0.818–0.846), strict 0.824; pooled rare micro-F1 v1 0.746. Current, after the M4 splitter fix: v1 0.838, strict 0.829, rare 0.742 (README §10). |
| M4 | **Done** (acceptance: rerun from cache $0, 3,086/3,086 cached, outputs byte-identical) | gpt-4.1-mini over 3,086 texts, after the splitter fix: invalid 0, content-filtered 7 (policy: scored with rule-baseline labels), Tier 2: 211 (6.8%), review escalations 785. Macro-F1 (9 headline, v1, pilot excluded): rule 0.838, LLM 0.862, LLM+verifier 0.857; paired LLM − rule +0.025 (0.010–0.040). Tier 0: 0 OOF hits by construction. Total LLM spend $2.12. Pre-splitter results: tag `m4-pre-splitter`. |
| M5 | **Done** (rerun from cache $0, outputs byte-identical) | Tier 2 repair agent (gpt-5-mini-2025-08-07, `repair-v1`, LangGraph, 6 tool calls / 60K tokens per report) on the 211 FAIL reports: repair success 78/211 (37.0%), 0 refusals, 0 errors. Macro-F1 v1: LLM+verifier 0.857 → +Tier 2 0.862; paired +0.006 (0.003–0.009) → **kept** (pre-committed rule); vs rule +0.025 (0.010–0.040). Labels changed 75: wrong→right 29, right→wrong 5. Review 954 (hedged 58.1% vs clear 28.2%); escalation precision Tier 2 64.9% (base 25.5%). Spend $0.26; total $2.38. |
| M6 | **Done** (code `567b093`; results rerun from cache at that commit, $0) | Through `run_pipeline`: clean join headline macro-F1 (v1) 0.860 (0.845–0.873), identical to LLM + verifier (paired 0.000; 1 report differs: IU text with inner "Impression:" headers); 30% varied joins 0.848, paired varied − clean −0.012 (−0.017 to −0.007). Parser: clean 100.0% of sentences in the right section, 3,083/3,086 fully parsed; alternative headers 100%; no headers 62.6% (308/309 no sections found). Correctly parsed clean joins: 0 new tagger inputs (all from the M4 cache). Hedge fix: conversions 147 → 125, LLM + verifier 0.857 → 0.860, Cardiomegaly F1 0.914 → 0.944. Normal-claim count: 833 of 1,302 (64.0%) "no acute" impressions have non-normal codes; the tagger predicted No Finding for 3 of them. Spend $0.25 (461 new tagger inputs); total $2.63. |
| M7 | **next** (waits for owner OK) | Free checks with v2 escalation + recall scan (rule labeller as second reader) + normal check; ReAct verifier agent (blind first, caps); dev-slice prompt development and freeze; cost estimate before the full run. |
| M8 | planned | Postgres `labels` (verification state + evidence), Qdrant index (report + contextual sentence points, indication field, BM25), RRF, retrieval eval incl. report-to-report. |
| M9 | planned | Negation-aware embedding fine-tuning per fold (`CachedGISTEmbedLoss`), held-out eval vs the filter baseline; serving model; agent's `find_by_meaning` switches to it. |
| M10 | planned | Query agent + tools + guardrails, question set, agent eval on expert and predicted label tables. |
| M11 | planned | Ingestion worker, FastAPI, Redis, tracing, Gradio demo with verification badges, deploy files, model card, CI regression eval. |

## Decisions (owner)
- **D1 (2026-10-20): nothing is tuned per label.** Every tuned parameter (Tier 0 patterns, refusal threshold, embedding checkpoint, any rule-baseline setting) is ONE global value, selected on a pooled metric (macro-F1 or nDCG over the 9 headline labels) on inner validation. Rare labels are never used for selection.
- **D2 (2026-10-20): gpt-5.4-mini is missing access.** If it still returns 404 at M4, run the Tier 1 pilot with gpt-4.1-mini and gpt-5.4-nano, and use gpt-5-mini as the Tier 1 fallback.
- D3: strict-label fold balance accepted; iterstrat accepted.
- D4: no history rewrite and no force push; the pushed history stays as is.
- **D5 (M3): pipeline/eval vocabulary overlap accepted** (README §11 limitation). The pipeline alias list is **frozen** at the M3 commit (alias-set hash pinned in `tests/test_alias_freeze.py`); any later change needs owner OK and may only be based on training-fold error analysis, never on out-of-fold or test results.
- D6 (M3): `hedged` is excluded from rare-label scores and from the abnormal / redaction_adjacent subset scores, as for headline scores.
- D7 (M3): noise-adjusted scores (README §4.6, Stretch) skipped for now.

### v2 plan (owner, 2026-10-21; README §5, §6.2, §12)
- **D8:** the Tier 2 repair agent and the human-review queue (Tier 3) are replaced by one **ReAct verifier agent** that runs only on escalated reports (check FAIL, escalating flag, recall-scan disagreement) and marks each label `verified_rules | verified | verified_impression_only | corrected | suggested | unverified`. No review table, no review endpoints. v1 (M3–M5) results stay in README §10 as comparison columns.
- **D9:** QLoRA / local-model tagger **dropped**.
- **D10:** **no separate LLM-judge steps** anywhere (no LLM verifier judge, no retrieval reranking judge, no error audit, no RAGAS). Judgment happens only inside the verifier agent and the query agent.
- **D11:** the **indication** is never a tagger or verifier input; it is used only in RAG / Q&A (a separate index field and a query-agent tool), never embedded and never in retrieval-evaluation queries.
- **D12:** label set (13 labels, mapping v1 + strict) and **5-fold CV** over duplicate clusters are **unchanged**.
- **D13:** **every predicted No Finding goes through the normal check** (README §6.2, free checks part 3): heart + lungs covered by normal statements and no `present`/`uncertain` rule-scan label; otherwise the report escalates to the agent, which confirms or withholds it. No extra "intermediate" training label unless the M6 normal-claim count shows the tagger confusing "nothing acute" with "fully normal", and only with the owner's OK.
- **D14:** one entry point: labels are produced only through `run_pipeline(raw_text)`; evaluation joins each report's sections into text, hides the codes and calls it like an upload.

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

**Budget:** `MAX_LLM_USD=20` (`.env.example`; `.env` uses the same value). Stop rule (`src/radlabel/llm/client.py`, `BUDGET_FRACTION = 0.5`): fresh LLM calls are refused once the ledger total reaches 50% of `MAX_LLM_USD`, i.e. **$10**; cache hits are always free; the owner raises the limit explicitly. Per-run caps sit inside it (M5: $3 of new spend).

`AZURE_OPENAI_API_VERSION` is empty, so the client uses Azure's GA v1 API. LLM spend so far, all milestones: **$2.63** after M6 (M6: $0.25) (ledger `artifacts/llm_cache/ledger.jsonl`; README §10).

## M2 notes
- `iterstrat` (README §4.2 fallback) used: scikit-multilearn 0.2.0 can't take a seed with scikit-learn 1.9.
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
- (fixed) Sentence splitting: "[REDACTED].In ..." fixed in `cd215fa`; "..", " ." fixed in `b2d2045` (M4, owner-approved, Tier 1 re-run; before/after in `docs/evaluation_notes.md`).

- Full run: 7 reports refused by Azure's content filter (violence, medium); handled as filtered, cached, routed to review. Two runs were interrupted (content-filter 400, then a network error); client/run hardened; completed responses were cached, so no call was paid twice.
- `negation_only` FP pairs now exclude the pilot reports (6,164 pairs): rule 41, LLM 6.
- Owner follow-ups (2026-10-20), all cache-only, $0: paired bootstrap; Atelectasis analysis (57 of 59 LLM FNs are `uncertain` on "scarring or atelectasis"-type alternatives); verifier-column drop explained (hedge conversions, mostly "borderline cardiomegaly"); content-filtered reports scored with rule-baseline labels (policy, owner-confirmed); `negation_consistency` → flag (pipeline wrong in 20/23, owner's pre-committed rule). Details: `docs/evaluation_notes.md`, `artifacts/results/m4_analysis.json`.
- Tier 0 per fold: 67–81 patterns, 0 OOF hits (exact duplicates share a cluster → fold). Serving patterns: 96.
- Review: 785 escalations (25.4%); M5+ error analysis uses a random sample of ~50.
- Owner decisions (2026-10-20, after the follow-ups): splitter fix approved incl. Tier 1 re-run (done: 66 fresh calls, $0.039); content-filter rule-baseline scoring is policy; Atelectasis stays a documented finding, plus an all-labels `uncertain` = positive sensitivity row (`artifacts/tables/labelling_summary.md`); Tier 0 serving match described as in-sample in the README.

## M5 notes
- Owner rules (2026-10-20): Tier 2 only on FAIL reports (211); agent never sees expert codes / eval mentions / folds / metrics (`tests/test_repair_leakage.py`); $3 new-spend cap for the run (the client's stop at 50% of MAX_LLM_USD = $10 total also applied; an earlier note said $5, which was wrong); pre-committed evaluation and keep/drop rule (`docs/evaluation_notes.md`); Tier 1 prompt and pipeline rules unchanged.
- LangGraph runs the loop only; model calls go through `radlabel.llm`, extended with native tool calling (cache key gains `tools` only when used, so Tier 1 cache entries are unchanged).
- Smoke test on 3 never-scored FAIL reports (pilot/hedged) before the full run: plumbing/cost only, no prompt change.
- Review table: rows (report id + reasons) in `artifacts/review/review.jsonl` (git-ignored). Kept as JSONL (owner). The Postgres `review` table and `POST /review/{id}` are dropped in v2 (D8).
- First cache rerun showed byte differences only in per-report bookkeeping (`cost_usd`, `cached_calls`) and file order; fixed (sorted file, call cost kept on cache hits); labels/routes were identical.

## M6 notes
- Parser (`src/radlabel/preprocess/parser.py`): header at the start of the text, a line or a sentence, followed by
  ":" / "-" or alone on its line; variants per README §6.1. No headers → one block read as Findings,
  `sections_identified = False`. Text before the first header → Findings if there is no Findings header, else
  `unassigned` (reported, not labelled).
- `run_pipeline` (`src/radlabel/pipeline.py`): parse → sentences → Tier 1 → deterministic verifier. Content-filtered
  **or invalid** tagger output → rule labeller labels (M4 eval policy scored invalid outputs as empty; there are 0
  invalid outputs, so no effect). Tier 0 is not in `run_pipeline` yet (0 out-of-fold hits by construction; serving
  only) → add with the serving patterns in M11.
- Rule labelling moved to `src/radlabel/labelling/rules.py`; `eval/baselines/rule_baseline.py` is a thin wrapper.
  Rule-baseline predictions and table byte-identical, results payload identical.
- Hedge fix (`verifier.DEFINITION_PRESENT`: Cardiomegaly ← "borderline", "mild"): 22 reports change, all
  Cardiomegaly uncertain → present; none is a FAIL report, so Tier 2 inputs and predictions are byte-identical (cache
  only, $0). v1 review 954 → 940 (30.9% → 30.5%); LLM + verifier − LLM only −0.006 → −0.002 (still significant: the
  remaining hedge conversions); Tier 2 − LLM only 0.000 → 0.003 (−0.000 to 0.007, CI includes 0).
- Varied joins (seed 13, 926 reports): alternative headers 307, no headers 309, one section dropped 310 (Findings 70,
  Impression 81, Indication 81, Comparison 78). The drop-section macro-F1 fall (0.873 → 0.756 on the same reports) is
  lost content, not parsing (sentence accuracy 100%). Without headers the tagger also reads the indication (no way to
  separate it); macro-F1 0.858 → 0.864 on those reports.
- Alternative header names come from the parser's own variant list, so that row checks the matching (case,
  punctuation, line layout), not unknown header names (README §11 already notes the joins only partly measure the
  parser).
- Normal-claim definition (pre-registered in `eval/entry_point.py`, `NORMAL_SENTENCE`): every Impression sentence is a
  general statement ("no acute/active …", "negative for acute …", "normal/negative/unremarkable chest/exam/study").
  Positives among the 833: Other Abnormality 742, Support Devices 111, Lung Opacity 48, Atelectasis 40, Fracture 31,
  Cardiomegaly 30, Lung Lesion 28. The tagger predicted No Finding for 3 of the 833 and for 418 of the 467
  normal-only ones, so it does not confuse "nothing acute" with "fully normal" (README §6.2: no intermediate tag).
- `results.git_commit()` no longer counts README.md as dirty code (docs + generated §10), like `docs/`.

## Blocked (owner action)
- (resolved 2026-10-20) Docker installed by the owner; compose healthy.

## Notes
- No commit contains a Co-Authored-By trailer (checked 2026-10-20).
- `.venv`: stdlib venv on uv-managed CPython 3.11.15, packages via `uv pip --python`. `make` not installed; run the Makefile commands directly.
- Data source: Wayback raw capture (Open-i serving a maintenance page). SHA-256 verified.
