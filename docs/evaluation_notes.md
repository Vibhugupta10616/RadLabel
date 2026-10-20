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
