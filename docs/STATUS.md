# RadLabel status

_Updated per milestone. Numbers come only from scripts (see `artifacts/results/`)._
_Owner rule (2026-10-19): stop after every milestone and report hard stops / gaps before continuing._

## Milestones
| ID | State | Notes |
|---|---|---|
| M0 | **Done** (`4af0dea`; Docker check 2026-10-20) | Owner accepted the direct commands in place of `make test`. `docker compose up -d --wait`: postgres, qdrant, redis healthy (Docker 29.9.1, Compose v5.6.0). |
| M1 | **Done** (tag `m1-data`) | Owner-approved 2026-10-20. Numbers below. eval_v1.2 lexicon/termset **permanently frozen**. |
| M2 | **Done** (owner-approved 2026-10-20) | 5 folds over 3,073 clusters, every label within ±1 of equal share (check: ±2); no cluster or exact-text group spans two folds; inner val 245–261 clusters per fold. `artifacts/results/folds.json`. |
| M3 | **Done** (tag `m3-rule-baseline`, owner-approved 2026-10-20) | Rule baseline §8.1 table: `artifacts/tables/labelling_rule_baseline.md`; numbers at M3 (pre-splitter): macro-F1 (9 headline) v1 0.833 (0.818–0.846), strict 0.824; pooled rare micro-F1 v1 0.746. Current, after the M4 splitter fix: v1 0.838, strict 0.829, rare 0.742 (docs/RESULTS.md). |
| M4 | **Done** (acceptance: rerun from cache $0, 3,086/3,086 cached, outputs byte-identical) | gpt-4.1-mini over 3,086 texts, after the splitter fix: invalid 0, content-filtered 7 (policy: scored with rule-baseline labels), Tier 2: 211 (6.8%), review escalations 785. Macro-F1 (9 headline, v1, pilot excluded): rule 0.838, LLM 0.862, LLM+verifier 0.857; paired LLM − rule +0.025 (0.010–0.040). Tier 0: 0 OOF hits by construction. Total LLM spend $2.12. Pre-splitter results: tag `m4-pre-splitter`. |
| M5 | **Done** (rerun from cache $0, outputs byte-identical) | Tier 2 repair agent (gpt-5-mini-2025-08-07, `repair-v1`, LangGraph, 6 tool calls / 60K tokens per report) on the 211 FAIL reports: repair success 78/211 (37.0%), 0 refusals, 0 errors. Macro-F1 v1: LLM+verifier 0.857 → +Tier 2 0.862; paired +0.006 (0.003–0.009) → **kept** (pre-committed rule); vs rule +0.025 (0.010–0.040). Labels changed 75: wrong→right 29, right→wrong 5. Review 954 (hedged 58.1% vs clear 28.2%); escalation precision Tier 2 64.9% (base 25.5%). Spend $0.26; total $2.38. |
| M6 | **Done** (code `567b093`; results rerun from cache at that commit, $0) | Through `run_pipeline`: clean join headline macro-F1 (v1) 0.860 (0.845–0.873), identical to LLM + verifier (paired 0.000; 1 report differs: IU text with inner "Impression:" headers); 30% varied joins 0.848, paired varied − clean −0.012 (−0.017 to −0.007). Parser: clean 100.0% of sentences in the right section, 3,083/3,086 fully parsed; alternative headers 100%; no headers 62.6% (308/309 no sections found). Correctly parsed clean joins: 0 new tagger inputs (all from the M4 cache). Hedge fix: conversions 147 → 125, LLM + verifier 0.857 → 0.860, Cardiomegaly F1 0.914 → 0.944. Normal-claim count: 833 of 1,302 (64.0%) "no acute" impressions have non-normal codes; the tagger predicted No Finding for 3 of them. Spend $0.25 (461 new tagger inputs); total $2.63. |
| M7 | **Done** (owner-accepted 2026-10-22; tag `m7-verifier-agent`) (code `77e8abd`, `6729cb0`, `33e2667`) | Full run (prompt `verifier-v2`, owner-approved): headline macro-F1 (v1) **0.887** (0.874–0.899), strict 0.883; paired v2 − LLM + verifier + Tier 2 +0.022 (0.013–0.031), v2 − LLM only +0.025 (0.016–0.035), v2 − rule baseline +0.050 (0.037–0.063) → agent **kept** (pre-committed rule). Verified + verified_rules labels precision 0.938 vs unverified 0.393. Reports with any unverified label 2.9% (v1 review rate 30.5%). Escalated 1,290 (41.8%). Agent cost $2.07 new ($2.12 incl. the cached dev reports); rerun from cache $0, byte-identical. |
| M8 | **Done** (owner-accepted 2026-10-22) (spec `8628794`, code `d4c154b`..`0f25dfa`) | Serving index from the M7 v2 outputs: Postgres 3,086 reports / 40,118 labels (Alembic `0001`), Qdrant 3,086 report + 19,006 contextual sentence points; leakage checks on the stored points pass (payload whitelist; indication text 0 of 2,192). Retrieval (spec frozen before the run, 259 queries, per fold + pooled): best pooled nDCG@10 the negated-sentence filter 0.528 ≈ RRF 0.526; seen-label nDCG 0.637 → 0.871 and contamination 0.310 → 0.070 with the filter; report-to-report best BM25 0.463. No LLM calls ($0). |
| M9 | **results in, waiting for owner review** (code `a793a6f`, `fe859bc`, `853ffd0`) | Fine-tuned bge-small (plain sentences, CachedGISTEmbedLoss, GPU): pooled nDCG@10 0.564 → 0.592, paired +0.028 (0.019–0.038), negation contamination 0.140 → 0.097 → **use rule passes**, search default = fine-tuned serving model. Seen labels +0.134, held-out aliases +0.069, compositional +0.045; held-out labels −0.010 (CI includes 0), attribute −0.013 (CI includes 0). With the filter: 0.582 → 0.602. |
| M10a | **next** | Website backend: session API (`/api/session`, `/reports`, `/ask` scope report or all, `/timeline`), in memory, nothing stored; session RAG. |
| M10b | planned | Website evaluation: 20 frozen questions (`docs/m9b_handwritten_questions.md`) on the dev slice; session RAG vs all reports in the prompt on batches of 3/10/30/50; latency and cost. |
| M10c | in progress (branch `m9c-frontend`) | Website frontend (React); runs on a mock API until M10a. |
| M11 | planned | Deployment: Vercel (frontend) + Hugging Face Docker Space (backend); secrets as Space secrets; no private models in the image. |

## Decisions (owner)
- **D1 (2026-10-20): nothing is tuned per label.** Every tuned parameter (Tier 0 patterns, refusal threshold, embedding checkpoint, any rule-baseline setting) is ONE global value, selected on a pooled metric (macro-F1 or nDCG over the 9 headline labels) on inner validation. Rare labels are never used for selection.
- **D2 (2026-10-20): gpt-5.4-mini is missing access.** If it still returns 404 at M4, run the Tier 1 pilot with gpt-4.1-mini and gpt-5.4-nano, and use gpt-5-mini as the Tier 1 fallback.
- D3: strict-label fold balance accepted; iterstrat accepted.
- D4: no history rewrite and no force push; the pushed history stays as is.
- **D5 (M3): pipeline/eval vocabulary overlap accepted** (SPEC §11 limitation). The pipeline alias list is **frozen** at the M3 commit (alias-set hash pinned in `tests/test_alias_freeze.py`); any later change needs owner OK and may only be based on training-fold error analysis, never on out-of-fold or test results.
- D6 (M3): `hedged` is excluded from rare-label scores and from the abnormal / redaction_adjacent subset scores, as for headline scores.
- D7 (M3): noise-adjusted scores (SPEC §4.6, Stretch) skipped for now.

### Docs split and new order (owner, 2026-10-22)
- **D18:** README.md is the short overview (owner-written); the full spec is `docs/SPEC.md`; all results are
  generated into `docs/RESULTS.md`, and the README's summary block is generated from the same results files.
- **D19:** new order: M9 embedding fine-tuning · M10 website (M10a backend, M10b evaluation, M10c frontend, started on
  branch `m9c-frontend`) · M11 deployment (Vercel + Hugging Face). Product: labels + evidence + verification badges,
  questions about one report or RAG across the user's own uploads; the IU index is the evaluation test bed only.
  Dropped: the ingestion worker that stored uploads, the Redis answer cache, the IU-corpus query agent, the Gradio
  demo. Sentences are embedded without the predicted-label prefix; the verifier agent stays on the base model.
- **D20:** fine-tuned model used for search / RAG only if its pooled nDCG@10 paired difference vs base (no prefix) is
  not significantly negative and its negation contamination@10 is not higher (SPEC §8.2).

### After M8 (owner, 2026-10-22)
- **D15:** serving configuration = the evaluated v2 (`run_pipeline(normal_check_escalates=True)`, the default). The
  normal-check ablation stays a documented result: no label changes, ~$0.25 per 3,000 reports saved, but unverified
  reports 2.9% → 8.1%; showing "unverified" on ~99%-correct normals would mislead users.
- **D16:** embedding fine-tuning (M10) is judged two ways (SPEC §8.2): pure embedding effect = base vs fine-tuned,
  both WITHOUT the predicted-label prefix; full system = fine-tuned + prefix + negation filter vs the best filter
  row. The prefix / filter rows partly reflect the labelling pipeline's output. Base no-prefix row added to M8.
- **D17:** roadmap: M8 search index + retrieval eval (done) · M9 website (M9a backend, M9b evaluation, M9c frontend;
  the query agent is part of M9a) · M10 fine-tuning, swapped into the same search, retrieval eval re-run · M11 public
  deployment (Azure + safeguards). Product: upload one report or a patient series, 13 findings with evidence and
  verification badges, questions about one report or across all, with citations. IU reports are the test bed for
  search; user uploads are never stored.

### v2 plan (owner, 2026-10-21; SPEC §5, §6.2, §12)
- **D8:** the Tier 2 repair agent and the human-review queue (Tier 3) are replaced by one **ReAct verifier agent** that runs only on escalated reports (check FAIL, escalating flag, recall-scan disagreement) and marks each label `verified_rules | verified | verified_impression_only | corrected | suggested | unverified`. No review table, no review endpoints. v1 (M3–M5) results stay in docs/RESULTS.md as comparison columns.
- **D9:** QLoRA / local-model tagger **dropped**.
- **D10:** **no separate LLM-judge steps** anywhere (no LLM verifier judge, no retrieval reranking judge, no error audit, no RAGAS). Judgment happens only inside the verifier agent and the query agent.
- **D11:** the **indication** is never a tagger or verifier input; it is used only in RAG / Q&A (a separate index field and a query-agent tool), never embedded and never in retrieval-evaluation queries.
- **D12:** label set (13 labels, mapping v1 + strict) and **5-fold CV** over duplicate clusters are **unchanged**.
- **D13:** **every predicted No Finding goes through the normal check** (SPEC §6.2, free checks part 3): heart + lungs covered by normal statements and no `present`/`uncertain` rule-scan label; otherwise the report escalates to the agent, which confirms or withholds it. No extra "intermediate" training label unless the M6 normal-claim count shows the tagger confusing "nothing acute" with "fully normal", and only with the owner's OK.
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

`AZURE_OPENAI_API_VERSION` is empty, so the client uses Azure's GA v1 API. LLM spend so far, all milestones: **$5.43** (M6 $0.25; M6 follow-up $0.54; M7 dev slice $0.20; M7 full run $2.07) (ledger `artifacts/llm_cache/ledger.jsonl`; docs/RESULTS.md).

## M2 notes
- `iterstrat` (SPEC §4.2 fallback) used: scikit-multilearn 0.2.0 can't take a seed with scikit-learn 1.9.
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
  ":" / "-" or alone on its line; variants per SPEC §6.1. No headers → one block read as Findings,
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
  punctuation, line layout), not unknown header names (SPEC §11 already notes the joins only partly measure the
  parser).
- Normal-claim definition (pre-registered in `eval/entry_point.py`, `NORMAL_SENTENCE`): every Impression sentence is a
  general statement ("no acute/active …", "negative for acute …", "normal/negative/unremarkable chest/exam/study").
  Positives among the 833: Other Abnormality 742, Support Devices 111, Lung Opacity 48, Atelectasis 40, Fracture 31,
  Cardiomegaly 30, Lung Lesion 28. The tagger predicted No Finding for 3 of the 833 and for 418 of the 467
  normal-only ones, so it does not confuse "nothing acute" with "fully normal" (SPEC §6.2: no intermediate tag).
- `results.git_commit()` no longer counts README.md as dirty code (docs + generated §10), like `docs/`.

## M6 follow-ups (owner, 2026-10-22)
- README: six fixes (Cysts, stale "(rerun)" note, rare positives 27–53, table row, noise-adjusted deferred per D7,
  v1 review rate referred to §10); normal-claim finding added (§6.2, `docs/evaluation_notes.md`); no-header
  limitation (§11); §13 restored (the deletion was unintended).
- `run_pipeline` output carries `sections_identified` at the top level.
- Held-out header names (10, written before running, never added to the parser): parser recognises none; 926/926
  reports end with no sections found, 50.3% of sentences in the right section, 0 fully parsed; macro-F1 on the same
  reports 0.850 clean vs 0.850 held-out (everything is read as Findings). Cost $0.54.

## M7 notes (before the full run)
- Escalation (`artifacts/results/verifier_escalation.json`): reports by reason (several per report possible):
  section_rule 778, recall_scan 576, evidence_mentions_label 424 (FAIL or [REDACTED] on present/uncertain),
  normal_check 278, hedge_consistency 105, negation_consistency 14. The recall scan is never the only reason: every
  recall-scan escalation also has a section_rule flag. Escalation precision: reports 44.3% (base rate
  25.0%; not escalated 11.2%, 201 reports), labels 32.6%.
- **Normal check:** 577 predicted No Finding; 278 fail the check (mostly no specific heart/lung statement), but the
  tagger's No Finding precision is 99.3% on those (99.0% on the 299 that pass). So the check escalates ~280 reports
  with little to catch. Not changed (it's an out-of-fold result): owner decision.
- Dev-slice development (102 pilot reports, 38 escalate): v1 net −5 (9 wrong → right, 14 right → wrong; the agent
  read "upper limits of normal" as Cardiomegaly, scarring as Lung Opacity, removed devices as present, congestion as
  Edema); v2 adds the frozen label definitions to the prompt, "an escalation is not evidence", removed/resolved and
  size-qualifier rules: net +8; v3 (+ a scarring line) net +4, so v2 is frozen (rule fixed before the v3 run).
  gpt-5-mini is not deterministic (temperature not settable), so part of the v2/v3 gap may be run-to-run noise.
- `suggested` labels count as `present` in the final labels (and in scoring); `verified`/`corrected`/`unverified`
  keep or change the status as the agent decided.
- `find_by_meaning` uses the base `BAAI/bge-small-en-v1.5` (optional extra `embed`; installed locally, not in CI).
- `normal_phrases.yaml` gained a `heart_normal` anchor used only by the normal check ("Heart size normal." has no
  verb the pipeline negation catches); the evidence check is unchanged.
- Spend: held-out headers $0.54, dev runs v1/v2/v3 $0.20; total **$3.37**.

## M7 full run (owner-approved 2026-10-22)
- Paused once at $2.06 (I projected an overrun; the run was in fact nearly done), restarted from the beginning on the
  owner's instruction with no extra cap: cached calls reused, $0.003 more. New spend $2.07 (estimate $2.10).
- Embedding setup identical to the dev runs (sentence-transformers 6.1.0, BAAI/bge-small-en-v1.5), recorded in the
  results; find_by_meaning used 79 times in 1,290 runs.
- Label changes vs LLM + verifier (scored reports): wrong → right 194, right → wrong 121. Worst per label:
  Consolidation 0 / 18, Lung Opacity 55 / 45, Fracture 0 / 4.
- Suggested labels: 171 (153 present, precision 0.536); headline macro-F1 with suggested ignored 0.875.
- Normal check does **not** separate right from wrong normals: failed 266 right / 2 wrong, passed 282 right / 3
  wrong. The agent kept 264 of the 266 right ones (withheld 2 wrongly) and withheld 1 of the 2 wrong ones. No Finding
  precision 0.991 → 0.991, recall 0.873 → 0.884.
- Section corroboration of final present labels: both sections precision 0.943 (1,151 labels), single section 0.903
  (2,972), unverified 0.393 (61).
- Agent runs 1,290: submitted 1,285, tool cap 4, content-filter refusal 1; mean tool calls 2.12.
- Unverified reasons are stored as fixed categories (the agent's free-text reasons quote report wording).
- Results tallies are key-sorted (set iteration order made reruns differ in key order only; fixed in `33e2667`).

## After M7 (owner decisions 2026-10-22; analyses from cache, $0; `verifier_agent_analysis.json`)
- v2 stays the headline; no prompt or rule change. Recall scan kept (its hints go into the agent's input).
- Gain over LLM only (+0.025) comes mostly from Lung Lesion (+0.016 of the macro-F1; recall 0.56 → 0.79); Fracture
  −0.003. Without Other Abnormality (8 headline labels): +0.028 (0.018–0.039).
- Suggested labels per label: Lung Opacity 65 present (precision 0.42), Other Abnormality 45 (0.67), Lung Lesion 32
  (0.66), others small.
- Known issue: Consolidation, v2 vs LLM + verifier 0 wrong → right, 18 right → wrong (F1 0.923 → 0.696); candidate
  for a future prompt version developed on a new dev slice.
- **Normal-check ablation (chosen after seeing the results):** the 160 reports escalated only by the normal check
  skip the agent. Every label identical (macro-F1 difference 0.000), saves 160 agent runs / 250 calls / $0.25; reports
  with an unverified label 2.9% → 8.1% (those normals stay unconfirmed). Not significantly worse → **serving
  configuration** (`run_pipeline` default; `normal_check_escalates=True` reproduces the evaluated v2).

## M8 notes
- Index content: predicted v2 labels only (status, verification, evidence; `not_mentioned` left out of payloads),
  pipeline negation tags per sentence; no codes from the dataset, folds, eval mentions or indication (payload
  whitelist in `radlabel.index.points`, checked in tests and on every stored point). The indication is only in
  Postgres `reports.indication`. One point per unique report text (3,086), as in evaluation.
- The leakage check first flagged 4 reports: their own Findings/Impression repeat the indication's words (e.g. "right
  pneumothorax"); the check now counts a leak only when the indication text is NOT in the report's own sections (0).
- Postgres store bug found on the first build (labels flushed before their report row, FK violation); fixed with a
  regression test (SQLite with FKs on).
- Retrieval spec `retrieval_v1` committed before any run; queries materialized with ids only (no report text).
  1 compositional query–fold pair skipped (no relevant report in that fold).
- **Caveat for M9:** the contextual prefix names the PREDICTED labels, so the filter row partly measures the labelling
  pipeline; it is the baseline the fine-tuned model must beat.
- Docker: compose stack (postgres, qdrant, redis) started for M8; stopped afterwards with `docker compose down`,
  volumes kept (`pgdata`, `qdrant`).
- New dependencies (core): qdrant-client ~1.12 (matches the server image), SQLAlchemy 2, Alembic, psycopg 3.
  From the host, run with `DATABASE_URL=postgresql://radlabel:radlabel@localhost:5432/radlabel` and
  `QDRANT_URL=http://localhost:6333` (`.env` keeps the in-network defaults).

## After M8 (owner decisions D15–D17; no LLM calls, $0)
- Serving default is the evaluated v2 (`normal_check_escalates=True`); the ablation stays documented.
- Pure-embedding row added (base bge-small, sentences WITHOUT the predicted-label prefix): pooled nDCG@10 **0.564**,
  the best variant overall (filter row 0.528, prefix row 0.491); seen labels 0.731 (prefix 0.637, filter 0.871).
- **Reproducibility fix:** re-running M8 changed the BM25 and RRF rows (dense rows stable). Causes: tied BM25 scores
  returned by Qdrant in no fixed order, and float32 sums in its sparse scoring that differ in the last digits between
  runs (my first guess, Qdrant's IDF statistics, was wrong; index-time IDF was kept anyway). Fix: deterministic
  tie-breaking for every search, and BM25 candidates rescored client-side from their stored sparse vectors in a fixed
  order (`radlabel.index.store._top`, unit tests). Two consecutive runs are now byte-identical (`564588e`).
- Effect on the accepted M8 numbers (pooled nDCG@10): BM25 0.498 → 0.504, RRF 0.526 → 0.537; dense rows unchanged
  (one ±0.001 from tie-breaking). Per set, BM25 / RRF move by up to 0.018 (RRF report-to-report 0.342 → 0.360).

## M9 notes
- Compute: local GPU (NVIDIA RTX 5050 Laptop, 8 GB, driver 592.82); PyTorch 2.11.0+cu128 installed in the venv only
  (no cu128 build of 2.14.1 exists); `pyproject.toml` pins unchanged, CI stays on CPU. bf16; batch 128, CachedGIST
  mini-batch 32. Timing test estimated 9 minutes for 5 folds; the real run took ~17 minutes (per-epoch evaluation
  and model loading were not in the estimate). Training still runs on CPU with `--device auto`.
- Optional extra `train` (`sentence-transformers[train]`: datasets, accelerate), local only.
- Pairs: ~4,200 triplets per fold from the training folds only (inner validation held out; test on synthetic folds
  that no fold-k text reaches fold k's pairs). The builder first used alias texts that are held out for another label
  (e.g. "airspace disease"); fixed before training: any alias text held out for any label is excluded.
- Best epochs per fold 3, 3, 2, 3, 2 → serving model 3 epochs on all reports (4,398 triplets), private
  (`models/serving/model`); the evaluation index was rebuilt with it and plain sentences (leakage checks pass).
- GPU vs CPU embeddings differ in the 4th–5th decimal (max 0.0001 on a pooled value); the fine-tuning run recomputes
  the base rows on the same device, so the paired comparisons are like for like. The GPU rerun was byte-identical.
- Held-out labels (never trained) show no gain; the gain is on seen labels, held-out aliases of seen labels and
  compositional queries. Attribute queries ("small left effusion") do not improve.
- Pending housekeeping: the owner's attached README.md and m9b_handwritten_questions.md did not arrive with the M9
  prompt; to be applied when resent.

## Blocked (owner action)
- (resolved 2026-10-20) Docker installed by the owner; compose healthy.

## Notes
- No commit contains a Co-Authored-By trailer (checked 2026-10-20).
- `.venv`: stdlib venv on uv-managed CPython 3.11.15, packages via `uv pip --python`. `make` not installed; run the Makefile commands directly.
- Data source: Wayback raw capture (Open-i serving a maintenance page). SHA-256 verified.
