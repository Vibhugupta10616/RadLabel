# Evaluation notes

Decisions that shape how numbers are computed. Results come only from `eval/` scripts.

## Output vs evaluation policy (same text as SPEC §6.2)
- System output is four-valued: `present | uncertain | absent | not_mentioned`, representing what the report text says.
- Headline evaluation binarises it: `present` = positive, everything else = negative, against the expert codes.
  The "`uncertain` = positive" row is a sensitivity check, not the headline metric (on the `hedged` subset both
  policies are reported).
- The verifier's hedge downgrade (`present` → `uncertain`) is product policy (hedged statements go to review). Its
  cost (−0.006 headline macro-F1, LLM + verifier − LLM only; mostly "borderline cardiomegaly", which the expert
  codes treat as present) is reported as a known disagreement with the expert coding policy.
- The Atelectasis gap to the rule baseline comes from the LLM's own `uncertain` outputs (e.g. "scarring or
  atelectasis"), not from the verifier.
- The absent-evidence rules (`absent` with no or generic evidence → flag) affect routing only, never scores.
- Checked against every eval script (M5): `eval/labelling.py` (all systems, subsets, negation_only, paired
  bootstrap), `eval/pilot.py`, `eval/m4_analysis.py`, `eval/repair.py` (label changes, escalation precision) all
  score `present` as the only positive; the only exceptions are the labelled sensitivity row and the hedged-subset
  "uncertain = present" policy. No script deviates.

## Counting unit and CIs
- One report per exact normalised text (3,086); clusters (3,073) decide fold assignment only.
- 95% CIs: 1,000 bootstrap resamples over duplicate clusters (`eval/bootstrap.py`).

## Exclusions
- `hedged` reports (279, `data_prep/subset_stats.py`) are excluded from headline, rare-label and the abnormal /
  redaction_adjacent subset scores (owner decision D6).
- Reports coded only with ignored codes (Technical Quality 6, Contrast Media 1) are excluded from No Finding scoring.
- **Tier 1 pilot leakage (M4):** the 102 pilot reports used to choose the Tier 1 model come from fold 0's
  training folds but are test reports in folds 1–4 (30/20/26/26). They are **excluded from all headline
  out-of-fold metrics** (`data/splits/pilot_ids.txt`), and the all-reports headline macro-F1 is reported once as
  a sensitivity check in every labelling results file.

## Frozen artefacts
- Eval lexicon + negspacy termset `eval_v1.2` (end of M1).
- Pipeline alias list (end of M3; changes only from training-fold error analysis, with owner OK).
- Tier 1 prompt `tier1-v1` (after the M4 pilot). Any future prompt iteration uses a separate dev slice that is
  never a test fold.
- Tier 1 model: gpt-4.1-mini, chosen on the pilot (CIs overlap; not "significantly better").

## Not computed
- Noise-adjusted scores (SPEC §4.6, Stretch), owner decision D7.

## Verifier rule C (section_rule): decided by ground truth (M4)
Pre-committed owner rule: if the LLM is right in at least half of the pilot's section_rule disagreements, section_rule becomes a FLAG (review) instead of a FAIL (repair). Cache-only, $0. Generated from `artifacts/results/section_rule_check.json` (`python -m eval.pilot section-rule`).

**Result: LLM right in 26 of 39 disagreements (67%) → apply C (section_rule -> flag).** In every disagreement the pipeline said present and the LLM said absent / uncertain / not_mentioned. `uncertain` counts as not present.

| Model | Disagreements | LLM right |
|---|---|---|
| gpt-4.1-mini | 18 | 12 |
| gpt-5.4-mini | 10 | 6 |
| gpt-5.4-nano | 11 | 8 |

| Model | Report | Label | LLM | Pipeline | Ground truth (v1) | Right | Hedged report |
|---|---|---|---|---|---|---|---|
| gpt-4.1-mini | 240 | Lung Opacity | absent | present | negative | llm |  |
| gpt-4.1-mini | 520 | Lung Opacity | absent | present | negative | llm |  |
| gpt-4.1-mini | 746 | Cardiomegaly | uncertain | present | negative | llm |  |
| gpt-4.1-mini | 746 | Lung Opacity | absent | present | negative | llm |  |
| gpt-4.1-mini | 1080 | Lung Opacity | uncertain | present | positive | pipeline | yes |
| gpt-4.1-mini | 1166 | Atelectasis | uncertain | present | positive | pipeline |  |
| gpt-4.1-mini | 1715 | Lung Lesion | absent | present | positive | pipeline |  |
| gpt-4.1-mini | 2088 | Support Devices | absent | present | negative | llm |  |
| gpt-4.1-mini | 2088 | Pleural Other | not_mentioned | present | negative | llm |  |
| gpt-4.1-mini | 2112 | Lung Opacity | not_mentioned | present | positive | pipeline |  |
| gpt-4.1-mini | 2330 | Other Abnormality | not_mentioned | present | positive | pipeline |  |
| gpt-4.1-mini | 2469 | Lung Opacity | uncertain | present | negative | llm |  |
| gpt-4.1-mini | 2778 | Lung Lesion | uncertain | present | negative | llm |  |
| gpt-4.1-mini | 2891 | Lung Opacity | absent | present | negative | llm |  |
| gpt-4.1-mini | 2954 | Pleural Effusion | uncertain | present | positive | pipeline |  |
| gpt-4.1-mini | 3418 | Lung Opacity | absent | present | negative | llm |  |
| gpt-4.1-mini | 3613 | Cardiomegaly | uncertain | present | negative | llm |  |
| gpt-4.1-mini | 3614 | Edema | uncertain | present | negative | llm |  |
| gpt-5.4-mini | 240 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-mini | 520 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-mini | 746 | Cardiomegaly | uncertain | present | negative | llm |  |
| gpt-5.4-mini | 1166 | Atelectasis | uncertain | present | positive | pipeline |  |
| gpt-5.4-mini | 2088 | Pleural Other | not_mentioned | present | negative | llm |  |
| gpt-5.4-mini | 2112 | Lung Opacity | not_mentioned | present | positive | pipeline |  |
| gpt-5.4-mini | 2891 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-mini | 2954 | Pleural Effusion | uncertain | present | positive | pipeline |  |
| gpt-5.4-mini | 3418 | Other Abnormality | not_mentioned | present | positive | pipeline |  |
| gpt-5.4-mini | 3614 | Edema | not_mentioned | present | negative | llm |  |
| gpt-5.4-nano | 240 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-nano | 746 | Cardiomegaly | uncertain | present | negative | llm |  |
| gpt-5.4-nano | 746 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-nano | 1166 | Atelectasis | uncertain | present | positive | pipeline |  |
| gpt-5.4-nano | 2088 | Pleural Other | not_mentioned | present | negative | llm |  |
| gpt-5.4-nano | 2112 | Fracture | not_mentioned | present | negative | llm |  |
| gpt-5.4-nano | 2330 | Other Abnormality | uncertain | present | positive | pipeline |  |
| gpt-5.4-nano | 2891 | Lung Opacity | absent | present | negative | llm |  |
| gpt-5.4-nano | 2954 | Pleural Effusion | uncertain | present | positive | pipeline |  |
| gpt-5.4-nano | 3613 | Cardiomegaly | absent | present | negative | llm |  |
| gpt-5.4-nano | 3614 | Edema | absent | present | negative | llm |  |

## Verifier on the pilot after rules A, B, C, D (cache-only)

| Model | Reports with a fail | Reports with a flag | Fails by check |
|---|---|---|---|
| gpt-4.1-mini | 6.9% | 85.3% | {'evidence_mentions_label': 6, 'negation_consistency': 1} |
| gpt-5.4-mini | 14.7% | 65.7% | {'evidence_mentions_label': 14, 'negation_consistency': 2} |
| gpt-5.4-nano | 19.6% | 66.7% | {'evidence_exists': 55, 'evidence_mentions_label': 9, 'negation_consistency': 2} |

## Known pipeline issues (frozen rules, not fixed)
- `negation.py`: "heart size near the upper limits of normal" is read as an affirmed Cardiomegaly mention ("upper limits" is an enlargement cue; "of normal" isn't a following negation). The LLM's `uncertain` matched the ground truth.
- `negation.py`: "no cardiomegaly with bilateral small pleural effusions" negates the effusions too (the strong cue "no" scopes to the end of the clause; "with" is not a boundary). The LLM was right.
- Pipeline aliases are frozen (D5), so e.g. "sternotomy" alone (device word redacted) is not an alias; handled by rule D (cited [REDACTED] → flag), not by adding aliases.

## Scoring of the M4 columns
All numbers: v1, 9 headline labels, hedged + pilot excluded, from `artifacts/results/labelling_*.json`,
`labelling_paired_diffs.json` and `artifacts/tables/labelling_summary.md` (`python -m eval.labelling tier1
--cache-only`), **after the splitter fix** (see "Splitter fix" below; earlier values are in tag `m4-pre-splitter`).

- **"LLM + verifier" before Tier 2 exists** = the Tier 1 output after the deterministic verifier, with nothing
  repaired. Fails do not change any label: a report with a fail keeps its Tier 1 labels in this column (it is only
  marked for Tier 2). The only status changes the verifier makes are `hedge_consistency` conversions
  (`present` → `uncertain`, which then scores as negative outside the hedged subset).
- **Why it is lower than LLM only (−0.006, paired 95% CI −0.008 to −0.003):** on the 2,711 scored reports the
  verifier converts 70 `present` labels to `uncertain`; 57 of them are ground-truth positive. 18 of the 19
  Cardiomegaly cases are "borderline cardiomegaly", which MeSH codes as Cardiomegaly but the pipeline reads as
  hedged (Cardiomegaly F1 0.946 → 0.914); Other Abnormality has 28 (of 35). Known issue, not fixed (frozen rules); the
  hedged-evidence check is right in direction only for genuinely uncertain phrasing.
- **Content-filter refusals (7 reports: 206, 800, 1095, 1874, 2729, 2827, 3154). Policy (owner-confirmed, M4):**
  they are scored with the **rule baseline's labels** in both LLM columns (recorded as
  `content_filtered_scoring: rule_baseline_fallback` in the run stats) and routed to review. Before this they were
  scored as all `not_mentioned`; the change moved LLM-only macro-F1 from 0.860 to 0.863 (pre-splitter).
- **Paired bootstrap** (same reports, same 1,000 cluster resamples): LLM only − rule baseline **+0.025
  (0.010 to 0.040)**; LLM + verifier − LLM only **−0.006 (−0.008 to −0.003)**. Both CIs exclude 0, so "LLM beats
  the rule baseline on headline macro-F1" holds on the paired test even though the marginal CIs touch.
- `negation_only` FP rate now excludes the pilot reports too (6,164 pairs): rule baseline 41 (0.67%), LLM 6 (0.10%).

## Tier 0 (M4)
Per fold, patterns = exact normalised texts coded `normal` ≥ 3 times in that fold's training folds (67–81 per
fold). **Out-of-fold hits: 0, by construction:** identical normalised texts share a cluster, and a cluster stays
in one fold, so a test report never repeats a training text exactly. Tier 0 therefore leaves every OOF metric
unchanged and only saves calls in serving (patterns learned on all reports: 96, matching 773 of 3,832 usable
reports, measured in-sample: patterns learned and matched on the same reports, not a held-out result). No parameter tuned (`MIN_COUNT = 3` is the README value).

## Review volume
785 reports (25.4%) escalate to review (section_rule, hedge_consistency or negation_consistency flags on reports
that pass, plus the 7 content-filtered). Too many to review by hand: **for M5+ error analysis, review a random
sample of ~50 (seeded with `SEED`)**, not all of them.

## Known issue: Atelectasis (LLM 0.857 vs rule baseline 0.973), cache-only analysis, not fixed
**Owner decision (M4): no prompt change and no label-specific scoring change; documented finding only.** A
sensitivity row with `uncertain` = positive for **all** labels is in `artifacts/tables/labelling_summary.md`
(not the headline metric): rule baseline 0.839, LLM only 0.853, LLM + verifier 0.853. It lowers the LLM's macro-F1
(0.862 → 0.853) and barely moves the rule baseline (0.838 → 0.839).
`artifacts/results/m4_analysis.json` (`python -m eval.m4_analysis`, 0 LLM calls). Example sentences are in
`artifacts/analysis/m4_examples.md` (git-ignored: report text).

| Scored reports (n = 2,707, 257 positive) | TP | FP | FN |
|---|---|---|---|
| LLM (gpt-4.1-mini) | 198 | 7 | 59 |
| Rule baseline | 251 | 8 | 6 |

- LLM status on ground-truth positives: present 198, **uncertain 57**, not_mentioned 2. In 56 of the 57
  `uncertain` cases the rule baseline said `present` (2050: both uncertain). The gap is almost entirely the LLM marking alternatives as uncertain
  while MeSH codes Atelectasis as a major finding, not missed mentions.
- Driver: **"scarring or atelectasis" / "atelectasis or pneumonia" / "infiltrate or atelectasis"** alternatives.
  GT-positive reports with a scarring–atelectasis pair: 20 uncertain, 4 present; "… or/versus scarring": 8 / 8.
  `subset_stats.py`'s HEDGE regex contains "versus" but not "or", so these reports stay in the scored set where
  `uncertain` counts as negative.
- "subsegmental" is **not** the cause: 47 present, 8 uncertain. "likely/probable atelectasis" is rare in the
  scored set (4 present, 1 uncertain), because such reports are mostly in the excluded `hedged` subset; there
  (62 positives) the LLM says uncertain for 36 (rule baseline: 29).
- LLM false positives (7): "volume loss" read as atelectasis (1559, 3014), interstitial markings (41),
  "combination of consolidation and atelectasis" coded negative by MeSH (1015), and 3 that the rule baseline
  also gets wrong (104, 524, 2372).
- Rule-baseline errors (6 FN / 8 FP): "without significant interval change", "probably mostly atelectasis"
  (FN), and "cleared in the interval" / "favoring scar or atelectasis" (FP). The splitter fix removed 2 FN (54, 3414).
- Options considered (owner: neither applied): prompt guidance that "A or B" alternatives are `present` for
  each alternative (the prompt is frozen, so only via a dev slice that is never a test fold), or a scoring policy
  change (a README decision).

## Verifier fails in the full run (cache-only)
After the changes below: **211 reports with a fail (6.8%) → Tier 2**, all from `evidence_mentions_label`
(226 label-level fails).

- `evidence_mentions_label` by label: Consolidation 64, Support Devices 57, Lung Lesion 26, Lung Opacity 25,
  Pleural Other 16, Fracture 16, Cardiomegaly 13, Atelectasis 6, Edema 2, Pneumothorax 1. By LLM status:
  present 119, uncertain 107.
  - Consolidation: 60 of 64 are `uncertain` and GT-negative ("may reflect atelectasis or pneumonia": the LLM
    maps pneumonia to Consolidation; the pipeline aliases do not).
  - Support Devices: 31 GT-positive (device words outside the frozen alias list, e.g. a neurostimulator) and
    26 GT-negative (sternotomy sutures, a nipple ring).
  - Of the 119 `present` fails, 52 are GT-positive (alias gaps, e.g. "heart is large") and 67 GT-negative, so
    the fail is a useful but noisy Tier 2 signal.
  - 10 sampled examples (report IDs): 995, 1100, 3086, 3668, 3873, 664, 3014, 816, 3056, 590.
- **`negation_consistency`, pre-splitter (23): LLM right in 20, pipeline right in 3** (1393, 3746: a line/stent "removed";
  2783: "no suggestion of enlargement of the known nodule"). 2 of the 23 are in hedged reports, 1 in the pilot.
  Pipeline errors: a double full stop or " ." is not split, so "Specifically, no evidence of …" scopes over the next
  sentence (54, 884, 1250, 2492, 3414, 3497, 3887); "no X with Y" / run-on sentences (546, 1203, 2682); "without
  significant interval change", "not seen on the previous exam", "normal thoracic kyphosis", "does not look
  like …" (3103, 1365, 3820, 3942, 3997).
  **Owner's pre-committed rule applied: negation_consistency is a FLAG (→ review), not a FAIL**, so Tier 2 does
  not "fix" correct answers. Tests and SPEC §6.2 updated.
- After the splitter fix: 16 cases, LLM right in 13, pipeline right in 3 (the same three). The LLM's status did
  not change on any of the 23.

## Splitter fix (M4, owner-approved)
`sentences.py` now also splits after ".." and " ." when a capital follows (unit tests; "[REDACTED].In", "2.5 cm",
"1. …" and abbreviation rules kept). 109 usable reports / 66 unique texts got new sentences; expert labels, eval
mentions, subsets and the data card are byte-identical. Tier 1 re-run with the frozen prompt: 66 fresh calls,
$0.039 (total LLM spend $2.12); a second cache-only rerun cost $0 with byte-identical outputs. Before = tag
`m4-pre-splitter`.

| Metric | Before | After |
|---|---|---|
| Macro-F1 v1, rule baseline | 0.834 (0.820–0.847) | 0.838 (0.823–0.850) |
| Macro-F1 v1, LLM only | 0.863 (0.848–0.875) | 0.862 (0.848–0.875) |
| Macro-F1 v1, LLM + verifier | 0.856 (0.842–0.869) | 0.857 (0.842–0.870) |
| Paired LLM only − rule baseline | +0.028 (0.013 to 0.044) | +0.025 (0.010 to 0.040) |
| negation_only FP (rule / LLM), of 6,164 | 41 / 6 | 41 / 6 |
| Tier 2 reports | 212 | 211 |
| Review escalations | 790 | 785 |
| negation_consistency cases (LLM right / pipeline right) | 23 (20 / 3) | 16 (13 / 3) |

The 7 negation_consistency cases that disappeared (54, 884, 1250, 2492, 3414, 3497, 3887) are exactly the
".." / " ." cases. The remaining 13 pipeline errors are negation scope ("no X with Y", run-ons, "without
significant interval change", "not seen on the previous exam", "normal thoracic kyphosis"); not fixed (frozen rules).

## Tier 2 repair agent (M5): pre-committed before the run
Written and committed before any Tier 2 call (owner rules, M5).
- **Scope:** only the reports whose verified Tier 1 output has a verifier FAIL (211). Flag-only reports and the 7
  content-filter refusals never reach Tier 2.
- **Agent:** `src/radlabel/labelling/repair_agent.py`, prompt `repair-v1`, repair deployment gpt-5-mini
  (`reasoning_effort` low), LangGraph loop, tools `get_sentence`, `check_negation`, `get_label_rules`,
  `compare_sections`, `submit_fix`. Inputs: the report's sentences, its verified Tier 1 labels and the FAIL
  messages only; it never sees expert codes, eval mentions, folds or metrics (`tests/test_repair_leakage.py`).
  It may change only labels with a FAIL message. Tier 1 prompt and pipeline rules unchanged.
- **Limits:** 6 tool calls per report (submit_fix included), 60,000 tokens per report, 4,000 completion tokens
  per call; new spend for the whole run stops at **$3** (the client's 50%-of-`MAX_LLM_USD` stop, $10 total with `MAX_LLM_USD=20`, applies
  too). Reports not reached keep their Tier 1 labels and go to review. Every call is cached (reruns $0).
- **Column "LLM + verifier + Tier 2":** LLM + verifier labels; for a Tier 2 report, the agent's labels **only if
  they pass re-verification**, else the Tier 1 labels (report → review).
- **Tests:** paired bootstrap (v1 headline macro-F1, hedged + pilot excluded, 1,000 cluster resamples) of
  Tier 2 − LLM + verifier and Tier 2 − rule baseline. Per label on the 211: status changes, wrong→right and
  right→wrong (present = positive vs v1 codes).
- **Decision rule:** Tier 2 stays in the pipeline iff Tier 2 − LLM + verifier is **not significantly negative**
  (95% CI upper bound ≥ 0). If it is negative, it stays an evaluated component, reported as such; the agent
  prompt is not tuned on these results.
- **Smoke test:** a plumbing/cost check on up to 3 of the 211 that are never scored (pilot or hedged), before
  the full run; not used to change the prompt.

## Tier 2 results (M5)
`artifacts/results/labelling_llm_verifier_tier2.json`, `labelling_tier2_paired_diffs.json`,
`artifacts/tables/labelling_summary.md`, `artifacts/tables/tier2_changes.md` (`python -m eval.repair`).
gpt-5-mini-2025-08-07; new spend $0.26 (smoke $0.003 + run $0.257); total LLM spend $2.38. Rerun from cache: $0.

- **Run:** 211 / 211 attempted, all ended with `submit_fix` (no tool-cap, token-cap or budget stops; 0 content-filter
  refusals, 0 errors). Mean 1.97 tool calls (submit_fix 211, get_label_rules 160, get_sentence 42,
  check_negation 3). The agent never tried to change a label without a FAIL.
- **Repair success** (fix passes re-verification): **78 / 211 (37.0%)**. 36 of the 78 still go to review because of
  a review flag, so 42 end as `tier2_repaired`.
- The 133 not accepted keep their Tier 1 labels. In 114 failing labels the agent resubmitted the Tier 1 status
  (48 of them `present` and expert-positive: correct answers the frozen alias list cannot confirm, e.g.
  "heart is large"); in 32 it changed the status but the fix still failed.
- **Paired bootstrap:** Tier 2 − LLM + verifier **+0.006 (0.003 to 0.009)**; Tier 2 − rule baseline **+0.025
  (0.010 to 0.040)**. **Decision rule: Tier 2 is kept in the pipeline** (not significantly negative; here
  significantly positive). Headline macro-F1 0.862 (LLM + verifier 0.857); strict 0.865. Pooled rare micro-F1
  0.829 vs 0.838 (one Pleural Other and one Consolidation right→wrong; CIs overlap). Tier 2's 0.86226 equals LLM
  only's 0.86227 by coincidence: per-label F1s differ (Cardiomegaly 0.914 vs 0.946, Lung Lesion 0.614 vs 0.590).
- **Label changes on the 211:** 75 status changes; 29 wrong→right, 5 right→wrong, 41 without score effect
  (e.g. uncertain → not_mentioned). Scored reports only: 55 changes, 25 wrong→right, 5 right→wrong. Largest gains:
  Support Devices 11/1, Lung Lesion 6/0, Lung Opacity 5/0. Right→wrong: No Finding 2 (derived), Support Devices 1,
  Pleural Other 1, Consolidation 1.
- **Routing:** tier distribution: Tier 1 accepted 2,090, Tier 2 repaired 42, review 954 (30.9%; was 785 before
  Tier 2 existed, because the 133 not-accepted and 36 accepted-but-flagged reports now go to review). Review rate
  **hedged 58.1% vs clear 28.2%**. Escalation precision (Tier 1 labels disagree with v1 codes on ≥ 1 label):
  Tier 2 **64.9%**, review 51.7%, vs a base rate of 25.5% over all reports.
- Review rows: `artifacts/review/review.jsonl` (git-ignored; IDs and reasons only). Error analysis in M6+ uses a
  random sample of ~50 of them (owner).

## Guardrails vs LLM only (added after M5, owner)
Paired bootstrap, headline macro-F1 (v1), same out-of-fold reports and resamples
(`artifacts/results/labelling_tier2_paired_diffs.json`, key `tier2_minus_llm_only`):
**LLM + verifier + Tier 2 − LLM only = 0.000 (−0.004 to 0.004); the CI includes 0.**
Reading: the verifier's hedge downgrade costs about 0.006 and Tier 2 recovers about 0.006, so the full pipeline
**matches** LLM-only F1. The guardrails do **not** improve F1 over LLM only. What they add is label-level correction
(Tier 2: 29 labels wrong → right vs 5 right → wrong on the 211 FAIL reports) and routing of uncertain cases to human
review (30.9% of reports; hedged 58.1% vs clear 28.2%). That review volume is too high for production use; reducing
it is future work.

## Normal-claim count (M6; owner decision 2026-10-22)
Generated in `artifacts/results/pipeline_m6.json` (`normal_claim`, `python -m eval.entry_point`). Definition, fixed in
`eval/entry_point.py` (`NORMAL_SENTENCE`) before counting: every Impression sentence is a general "no acute"-type
statement. Over all 3,086 unique texts: **1,302** such reports; expert codes normal-only 467, ignored-only 2, **not
normal-only 833 (64.0%)** (mostly Other Abnormality 742 and Support Devices 111). The tagger predicted No Finding for
**3 of the 833** (and for 418 of the 467 normal-only ones). Decision: the tagger does not confuse "nothing acute" with
"fully normal", so **no intermediate label** is added. The normal check (SPEC §6.2, free checks part 3) still runs on
every predicted No Finding.

## Verifier agent full run (M7; owner, 2026-10-22, pre-committed before the run)
Generated by `python -m eval.verifier_agent full` (`artifacts/results/labelling_llm_agent_v2.json`,
`labelling_v2_paired_diffs.json`).
- Column "LLM + free checks + verifier agent (v2)": final statuses from `run_pipeline` (clean join), v1 + strict,
  abnormal-subset macro-F1 for every column. `suggested` labels count as present (output and headline scoring);
  sensitivity row with `suggested` labels ignored (the tagger's status kept); precision of suggested labels.
- Paired bootstrap vs LLM only, vs LLM + verifier + Tier 2 (v1) and vs the rule baseline. **Keep the agent iff
  v2 − LLM + verifier + Tier 2 is not significantly negative (CI hi >= 0).**
- Label changes vs LLM + verifier (this run's deterministic-verifier output), wrong → right vs right → wrong per label.
- Key result: precision / F1 of verified + verified_rules labels vs unverified labels.
- Escalation and unverified rates (labels, reports), hedged vs clear; reports with any unverified label vs the v1
  review rate in §10.
- Normal check table: tagger No Finding × check passed / failed × tagger right / wrong, with what the agent did.
  No Finding precision before / after.
- Section corroboration (code only, after the run): level of each final present label's evidence (both / single
  section / none / unverified); precision by level, and headline micro-F1 if only some levels count as present.
- Normal check unchanged (no tuning after the out-of-fold numbers). Prompt `verifier-v2` frozen.
- Embedding setup: the dev runs had the optional `embed` extra installed (sentence-transformers 6.1.0,
  BAAI/bge-small-en-v1.5; installed 12:26 UTC, first agent call 12:44 UTC); the full run requires the same
  (`EMBED_SETUP_REQUIRED`) and records it. Under v2 the agent called find_by_meaning 0 times on the dev slice.
- Blind first: escalation details never contain the tagger's evidence or its cited IDs. Recall-scan details carry the
  **rule labeller's** sentence IDs; in 142 of 617 recall-scan escalations (3 on the dev slice) such an ID is also one
  the tagger cited for that label (typically a sentence the tagger read as negated). Reported to the owner; the
  frozen setup is unchanged (the dev runs used the same messages).
