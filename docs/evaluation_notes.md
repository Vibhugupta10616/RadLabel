# Evaluation notes

Decisions that shape how numbers are computed. Results come only from `eval/` scripts.

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
- Noise-adjusted scores (README §4.6, Stretch), owner decision D7.

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
All numbers: v1, 9 headline labels, hedged + pilot excluded, from `artifacts/results/labelling_*.json` and
`labelling_paired_diffs.json` (`python -m eval.labelling tier1 --cache-only`).

- **"LLM + verifier" before Tier 2 exists** = the Tier 1 output after the deterministic verifier, with nothing
  repaired. Fails do not change any label: a report with a fail keeps its Tier 1 labels in this column (it is only
  marked for Tier 2). The only status changes the verifier makes are `hedge_consistency` conversions
  (`present` → `uncertain`, which then scores as negative outside the hedged subset).
- **Why it is lower than LLM only (−0.007, paired 95% CI −0.010 to −0.004):** on the 2,711 scored reports the
  verifier converts 73 `present` labels to `uncertain`; 59 of them are ground-truth positive. 18 of the 19
  Cardiomegaly cases are "borderline cardiomegaly", which MeSH codes as Cardiomegaly but the pipeline reads as
  hedged (Cardiomegaly F1 0.946 → 0.914); Other Abnormality has 28. Known issue, not fixed (frozen rules); the
  hedged-evidence check is right in direction only for genuinely uncertain phrasing.
- **Content-filter refusals (7 reports: 206, 800, 1095, 1874, 2729, 2827, 3154). Policy (owner-confirmed, M4):**
  they are scored with the **rule baseline's labels** in both LLM columns (recorded as
  `content_filtered_scoring: rule_baseline_fallback` in the run stats) and routed to review. Before this they were
  scored as all `not_mentioned`; the change moved LLM-only macro-F1 from 0.860 to 0.863.
- **Paired bootstrap** (same reports, same 1,000 cluster resamples): LLM only − rule baseline **+0.028
  (0.013 to 0.044)**; LLM + verifier − LLM only **−0.007 (−0.010 to −0.004)**. Both CIs exclude 0, so "LLM beats
  the rule baseline on headline macro-F1" holds on the paired test even though the marginal CIs touch.
- `negation_only` FP rate now excludes the pilot reports too (6,164 pairs): rule baseline 41 (0.67%), LLM 6 (0.10%).

## Tier 0 (M4)
Per fold, patterns = exact normalised texts coded `normal` ≥ 3 times in that fold's training folds (67–81 per
fold). **Out-of-fold hits: 0, by construction:** identical normalised texts share a cluster, and a cluster stays
in one fold, so a test report never repeats a training text exactly. Tier 0 therefore leaves every OOF metric
unchanged and only saves calls in serving (patterns learned on all reports: 96, matching 773 of 3,832 usable
reports, measured in-sample: patterns learned and matched on the same reports, not a held-out result). No parameter tuned (`MIN_COUNT = 3` is the README value).

## Review volume
790 reports (25.6%) escalate to review (section_rule, hedge_consistency or negation_consistency flags on reports
that pass, plus the 7 content-filtered). Too many to review by hand: **for M5+ error analysis, review a random
sample of ~50 (seeded with `SEED`)**, not all of them.

## Known issue: Atelectasis (LLM 0.857 vs rule baseline 0.969), cache-only analysis, not fixed
`artifacts/results/m4_analysis.json` (`python -m eval.m4_analysis`, 0 LLM calls). Example sentences are in
`artifacts/analysis/m4_examples.md` (git-ignored: report text).

| Scored reports (n = 2,707, 257 positive) | TP | FP | FN |
|---|---|---|---|
| LLM (gpt-4.1-mini) | 198 | 7 | 59 |
| Rule baseline | 249 | 8 | 8 |

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
- Rule-baseline errors (8 FN / 8 FP): negation scope across a double full stop or "without significant interval
  change" (FN), and "cleared in the interval" / "favoring scar or atelectasis" (FP).
- Options for later (owner decision, not applied): prompt guidance that "A or B" alternatives are `present` for
  each alternative (the prompt is frozen, so only via a dev slice that is never a test fold), or a scoring policy
  change (a README decision).

## Verifier fails in the full run (cache-only)
After the change below: **212 reports with a fail (6.9%) → Tier 2**, all from `evidence_mentions_label`
(227 label-level fails).

- `evidence_mentions_label` by label: Consolidation 64, Support Devices 57, Lung Lesion 26, Lung Opacity 25,
  Pleural Other 16, Fracture 16, Cardiomegaly 14, Atelectasis 6, Edema 2, Pneumothorax 1. By LLM status:
  present 119, uncertain 108.
  - Consolidation: 60 of 64 are `uncertain` and GT-negative ("may reflect atelectasis or pneumonia": the LLM
    maps pneumonia to Consolidation; the pipeline aliases do not).
  - Support Devices: 31 GT-positive (device words outside the frozen alias list, e.g. a neurostimulator) and
    26 GT-negative (sternotomy sutures, a nipple ring).
  - Of the 119 `present` fails, 52 are GT-positive (alias gaps, e.g. "heart is large") and 67 GT-negative, so
    the fail is a useful but noisy Tier 2 signal.
  - 10 sampled examples (report IDs): 995, 1100, 3086, 3668, 3873, 664, 3014, 816, 3056, 590.
- **`negation_consistency` (23): LLM right in 20, pipeline right in 3** (1393, 3746: a line/stent "removed";
  2783: "no suggestion of enlargement of the known nodule"). 2 of the 23 are in hedged reports, 1 in the pilot.
  Pipeline errors: a double full stop or " ." is not split, so "Specifically, no evidence of …" scopes over the next
  sentence (54, 884, 1250, 2492, 3414, 3497, 3887); "no X with Y" / run-on sentences (546, 1203, 2682); "without
  significant interval change", "not seen on the previous exam", "normal thoracic kyphosis", "does not look
  like …" (3103, 1365, 3820, 3942, 3997).
  **Owner's pre-committed rule applied: negation_consistency is a FLAG (→ review), not a FAIL**, so Tier 2 does
  not "fix" correct answers. Tests and README §6.2 updated.
- Known pipeline issue (not fixed): the splitter does not split after "..", " ." or a full stop preceded by a
  non-letter. Fixing it changes sentence IDs, hence Tier 1 inputs and the cache (a paid re-run); owner decision.
