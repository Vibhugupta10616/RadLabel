# RadLabel results

_Generated from `artifacts/results/*.json` by `python -m eval.report` (`make report`); do not edit. No number in this file is typed by hand. Design and protocol: [SPEC.md](SPEC.md); decisions behind the numbers: [evaluation_notes.md](evaluation_notes.md)._

**Claim scope.** Supported, on this dataset under this evaluation protocol: the LLM labelling pipeline improves over the implemented rule baseline; the v2 pipeline (LLM + free checks + verifier agent) improves over v1 (LLM + verifier + Tier 2) and over LLM only; verified labels are far more accurate than unverified ones. Not supported: clinical reliability; "verified" means checked to faithfully reflect the report text, not that the report or the coding is right.

Limitations that bound these numbers (details in [SPEC §11](SPEC.md#11-limitations)):
- One institution (Indiana University, Open-i); reports from around 2013.
- Expert codes are positive-only.
- Hedged reports (279 unique texts) are excluded from the headline metrics.
- The mapping from MeSH codes to the 13 labels is lossy (results under mapping v1 and strict).
- Rare labels have small support, hence wide CIs.
- 7 reports refused by the Azure content filter are scored with the rule baseline's labels.
- The ground truth misses some clearly stated findings, so scores are a lower bound.
- Labels describe the report text, not the images.
- Embedding fine-tuning helps the findings it was trained on and their unseen wordings, not unseen findings: no gain on the three held-out findings (nDCG@10 change -0.010 (-0.058–0.040)).
- v1 sent 30.5% of reports to human review (hedged 57.7%, clear 27.8%); v2 replaced the review queue with the verifier agent and an `unverified` mark (see the verifier agent section, M7).

## Labelling (SPEC §8.1)

Out-of-fold, one report per exact text; hedged and Tier 1 pilot reports excluded unless stated; 95% bootstrap CIs over clusters. Scoring: `present` = positive, except in the sensitivity row.

| Metric | Rule baseline | LLM only | LLM + verifier | LLM + verifier + Tier 2 | run_pipeline, clean join (M6) | run_pipeline, 30% varied joins (M6) | LLM + free checks + verifier agent (v2) |
|---|---|---|---|---|---|---|---|
| Headline macro-F1, 9 labels (v1) | 0.838 (0.823–0.850) | 0.862 (0.848–0.875) | 0.860 (0.845–0.873) | 0.866 (0.851–0.878) | 0.860 (0.845–0.873) | 0.848 (0.833–0.861) | 0.892 (0.879–0.903) |
| Headline macro-F1, 9 labels (strict) | 0.829 (0.814–0.843) | 0.863 (0.848–0.877) | 0.861 (0.846–0.875) | 0.868 (0.853–0.881) | 0.861 (0.846–0.875) | 0.850 (0.835–0.865) | 0.887 (0.873–0.899) |
| Pooled rare micro-F1 (v1) | 0.742 (0.677–0.805) | 0.831 (0.771–0.882) | 0.838 (0.777–0.889) | 0.829 (0.769–0.882) | 0.838 (0.777–0.889) | 0.824 (0.764–0.875) | 0.783 (0.723–0.832) |
| Abnormal subset: headline macro-F1 (v1) | 0.761 (0.748–0.773) | 0.767 (0.754–0.781) | 0.765 (0.752–0.778) | 0.771 (0.758–0.783) | 0.765 (0.752–0.778) | 0.757 (0.744–0.770) | 0.796 (0.784–0.808) |
| negation_only FP rate (pooled) | 41 / 6164 (0.0067) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 14 / 6164 (0.0023) |
| *Sensitivity, not headline:* macro-F1 (v1) with `uncertain` = positive for all labels | 0.839 (0.825–0.852) | 0.853 (0.839–0.866) | 0.853 (0.839–0.866) | 0.861 (0.848–0.874) | 0.853 (0.839–0.866) | 0.841 (0.828–0.855) | 0.880 (0.867–0.893) |
| *Sensitivity, not headline:* macro-F1 (v1), all reports incl. Tier 1 pilot | 0.837 (0.823–0.850) | 0.862 (0.848–0.876) | 0.860 (0.846–0.873) | 0.866 (0.852–0.878) | 0.860 (0.846–0.873) | 0.848 (0.834–0.861) | 0.893 (0.880–0.904) |
| *Sensitivity, not headline:* macro-F1 (v1), `suggested` labels ignored | – | – | – | – | – | – | 0.880 (0.866–0.892) |

Per-label tables: `artifacts/tables/labelling_*.md`.

## Paired differences

Headline macro-F1 (9 labels, v1), same out-of-fold reports and the same 1,000 cluster resamples for both systems.

| Comparison | Difference (95% CI) | CI excludes 0 |
|---|---|---|
| LLM only − rule baseline | 0.025 (0.010–0.040) | yes |
| LLM + verifier − LLM only | -0.002 (-0.004–-0.001) | yes |
| LLM + verifier + Tier 2 − LLM + verifier | 0.006 (0.003–0.009) | yes |
| LLM + verifier + Tier 2 − rule baseline | 0.028 (0.013–0.043) | yes |
| LLM + verifier + Tier 2 − LLM only | 0.003 (0.000–0.007) | no |
| run_pipeline, clean join − LLM + verifier | 0.000 (0.000–0.000) | no |
| run_pipeline, varied joins − clean join | -0.012 (-0.017–-0.007) | yes |
| LLM + free checks + verifier agent (v2) − LLM only | 0.029 (0.020–0.039) | yes |
| v2 − LLM + verifier + Tier 2 | 0.026 (0.017–0.036) | yes |
| v2 − rule baseline | 0.054 (0.041–0.067) | yes |

**Reading (v1).** The verifier's hedge downgrade costs 0.002 macro-F1 and Tier 2 recovers 0.006, so the full pipeline **matches** LLM-only macro-F1 (difference 0.003 (0.000–0.007); the 95% CI includes 0). The guardrails do not improve F1 over LLM only. What the v1 guardrails added is label-level correction (Tier 2: 29 labels wrong → right vs 5 right → wrong) and routing of uncertain cases to human review (30.5% of reports).

## Pipeline (v1)

- Tier 1: 3,086 unique report texts labelled by gpt-4.1-mini-2025-04-14 (prompt `tier1-v1`, temperature 0); invalid outputs 0; content-filtered 7.
- Tier 0: 0 out-of-fold matches (exact duplicates share a fold).
- Verifier FAIL → Tier 2: 211 reports (6.8%).
- Tier 2 repair agent (gpt-5-mini-2025-08-07, prompt `repair-v1`): fix accepted after re-verification for 78 of 211 (37.0%); mean tool calls 1.97; labels changed 75: wrong → right 29, right → wrong 5 (present = positive vs expert codes).
- Routing: Tier 1 accepted 2,104, Tier 2 repaired 42, review 940 (30.5%).
- Review rate: hedged 57.7% vs clear 27.8%. Escalation precision (Tier 1 labels disagree with the expert codes): Tier 2 64.9%, review 50.5%, base rate 25.0%.
- LLM spend: Tier 2 calls $0.26. Reruns are served from the cache at $0.

## Through the entry point (M6)

Labels produced by `run_pipeline(raw_text)` (parse → tag → verifier), as an upload would be. Without headers the parser can't separate sections, so the whole text, including the indication, is read as Findings.

3,086 unique reports joined into text with headers (codes hidden) and run through `run_pipeline`; 926 of them (30.0%, seed 13) also with a varied join. Clean joins whose labels differ from the LLM + verifier column: 1. Tagger inputs that differ from M4's, so not served by the M4 cache: 1387 (no headers 309, drop section 151, clean 1, heldout headers 926; correctly parsed clean joins: 0), whose calls cost $0.81. All LLM calls so far (cost ledger): $3.37.

| Join | Reports | Sentences in the right section | Fully parsed | No sections found |
|---|---|---|---|---|
| clean | 3086 | 100.0% | 3083 (99.9%) | 0 |
| alt headers | 307 | 100.0% | 307 (100.0%) | 0 |
| no headers | 309 | 62.6% | 0 (0.0%) | 308 |
| drop section | 310 | 100.0% | 310 (100.0%) | 0 |
| heldout headers | 926 | 50.3% | 0 (0.0%) | 926 |

Dropped sections: findings 70, impression 81, indication 81, comparison 78.

Headline macro-F1 (v1) on the varied reports: the same reports with the clean vs the varied join:

| Variant | Scored reports | Clean join | Varied join |
|---|---|---|---|
| alt headers | 267 | 0.815 (0.751–0.862) | 0.815 (0.751–0.862) |
| no headers | 263 | 0.858 (0.810–0.899) | 0.864 (0.818–0.904) |
| drop section | 276 | 0.873 (0.825–0.907) | 0.756 (0.690–0.807) |
| heldout headers | 806 | 0.850 (0.822–0.873) | 0.850 (0.822–0.874) |

Section subsets (as parsed; headline macro-F1, v1, hedged + pilot excluded):

| Subset | Clean: reports (scored) | Clean macro-F1 | Varied: reports (scored) | Varied macro-F1 |
|---|---|---|---|---|
| empty findings | 426 (371) | 0.827 (0.769–0.864) | 452 (396) | 0.777 (0.716–0.819) |
| empty impression | 6 (5) | 0.633 (0.500–1.000) | 396 (337) | 0.820 (0.773–0.861) |
| sections not identified | 0 (0) | – | 308 (263) | 0.864 (0.818–0.904) |

**Normal-claim count.** 1302 unique reports have an Impression made only of "no acute"-type statements; the expert codes are normal-only for 467, ignored-only for 2, and **not normal for 833 (64.0%)**. Positive labels among those: Cardiomegaly 30, Lung Opacity 48, Lung Lesion 28, Atelectasis 40, Pleural Effusion 1, Fracture 31, Support Devices 111, Other Abnormality 742, Pleural Other 4, Pneumothorax 2. The tagger predicted No Finding for 3 of the 833 (LLM only; after the verifier 3) and for 418 of the 467 normal-only ones.

**Hedge-check fix** ("borderline"/"mild" are not a hedge where the label definition counts them as present), v1 results from cache, before → after:

| Metric | Before | After |
|---|---|---|
| Hedge conversions (present → uncertain) | 147 | 125 |
| LLM + verifier: headline macro-F1 (v1) | 0.857 (0.842–0.870) | 0.860 (0.845–0.873) |
| LLM + verifier: Cardiomegaly F1 | 0.914 (0.890–0.937) | 0.944 (0.924–0.961) |
| LLM + verifier − LLM only | -0.006 (-0.008–-0.003) | -0.002 (-0.004–-0.001) |
| LLM + verifier + Tier 2: headline macro-F1 (v1) | 0.862 (0.848–0.875) | 0.866 (0.851–0.878) |
| LLM + verifier + Tier 2 − LLM only | 0.000 (-0.004–0.004) | 0.003 (0.000–0.007) |
| v1 review rate | 30.9% | 30.5% |

## Verifier agent (M7, v2)

**Reading (M7).** On this dataset and protocol, v2 improves headline macro-F1 over v1 (LLM + verifier + Tier 2) by 0.026 (0.017–0.036), 95% CI excludes 0, and over LLM only by 0.029 (0.020–0.039), 95% CI excludes 0. Most of the gain comes from Lung Lesion (+0.016 of the macro-F1); it holds without Other Abnormality (0.028 (0.018–0.039), 95% CI excludes 0). Verified labels are far more accurate than unverified ones: precision 0.938 (verified + verified_rules) vs 0.393 (unverified). The agent changes many labels in both directions (218 wrong → right vs 122 right → wrong), and its suggested labels have precision 0.54. Reports with any unverified label: 2.9% vs the v1 review rate of 30.5%. This is not like for like: v1 sent the whole report to human review for any remaining failure or escalating flag, while v2 marks only the labels the agent could not settle after checking the report itself, so the two rates count different things. The normal check does not separate right from wrong normals (tagger wrong in 1.1% of passed vs 0.7% of failed checks). "Blind first" is only partly blind: recall-scan hints carry the rule labeller's sentence IDs, and in 142 of 617 recall-scan escalations such an ID is a sentence the tagger also cited.

**Keep/drop (pre-committed):** v2 − LLM + verifier + Tier 2 = 0.026 (0.017–0.036) → keep the verifier agent: **yes** (keep iff v2 − LLM + verifier + Tier 2 is not significantly negative (CI hi >= 0)).

Escalated to the agent: 1,290 reports (41.8%; hedged 67.0% vs clear 39.3%). Reports with any `unverified` label: 90 (2.9%; hedged 3.2% vs clear 2.9%); unverified labels 183 (0.5%). v1 review rate: 30.5%, so v2 **reduced** the share of reports needing attention.

Label changes vs LLM + verifier (scored reports; present = positive vs the codes): 470 status changes, wrong → right 218, right → wrong 122. Per label: No Finding 10/3; Cardiomegaly 26/4; Lung Opacity 55/45; Lung Lesion 33/15; Atelectasis 14/3; Pleural Effusion 6/0; Fracture 0/4; Support Devices 23/2; Other Abnormality 47/24; Edema 2/1; Pleural Other 1/3; Consolidation 0/18; Pneumothorax 1/0.

**Verified vs unverified** (scored reports, all labels; present = positive):

| Verification | Labels | Predicted present | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|
| verified rules | 33,687 | 3380 | 0.954 | 0.953 | 0.953 | 0.991 |
| verified | 955 | 469 | 0.829 | 0.773 | 0.800 | 0.797 |
| corrected | 289 | 146 | 0.671 | 0.925 | 0.778 | 0.806 |
| suggested | 171 | 153 | 0.536 | 0.932 | 0.680 | 0.550 |
| unverified | 135 | 61 | 0.393 | 0.727 | 0.511 | 0.659 |
| verified or verified rules | 34,642 | 3849 | 0.938 | 0.929 | 0.934 | 0.985 |

Suggested labels: 171 (153 present, 18 uncertain); precision of the present ones 0.536.

**Normal check** (tagger No Finding after the deterministic verifier, scored reports):

| Check | Tagger vs codes | Reports | Kept, right | Kept, wrong | Withheld, right | Withheld, wrong |
|---|---|---|---|---|---|---|
| failed | right | 266 | 264 | 0 | 0 | 2 |
| failed | wrong | 2 | 0 | 1 | 1 | 0 |
| passed | right | 282 | 282 | 0 | 0 | 0 |
| passed | wrong | 3 | 0 | 3 | 0 | 0 |

No Finding precision 0.991 before (recall 0.873) → 0.991 after (recall 0.884).

**Section corroboration** of final `present` labels (scored reports):

| Level | Labels | Precision |
|---|---|---|
| both | 1,155 | 0.943 |
| single | 2,993 | 0.903 |
| none | 0 | – |
| unverified | 61 | 0.393 |

Headline micro-F1 if only these levels count as present: both 0.412, both or single 0.922, all but unverified 0.922, all 0.921.

Agent: prompt `verifier-v2` (frozen), 1,290 runs, mean tool calls 2.12; tools {'check_negation': 272, 'check_redaction': 95, 'compare_sections': 55, 'find_by_alias': 827, 'find_by_meaning': 79, 'get_label_definition': 21, 'normal_check': 101, 'submit': 1285}; stops {'content_filtered': 1, 'submitted': 1285, 'tool_cap': 4}; caps hit 4, content-filter refusals 1, budget stops 0; cost $2.12 ($0.0016 per report); embeddings: BAAI/bge-small-en-v1.5 (sentence-transformers 6.1.0).

### Per label, suggested labels and the normal-check ablation (after M7)

| Label | LLM only F1 (P / R) | v1 Tier 2 F1 (P / R) | v2 F1 (P / R) | v2 vs LLM only: wrong → right / right → wrong | Share of the macro-F1 gain |
|---|---|---|---|---|---|
| No Finding | 0.928 (0.991 / 0.873) | 0.926 (0.987 / 0.873) | 0.934 (0.991 / 0.884) | 10 / 3 | +0.001 |
| Cardiomegaly | 0.946 (0.993 / 0.903) | 0.944 (0.993 / 0.900) | 0.943 (0.983 / 0.906) | 2 / 4 | -0.000 |
| Lung Opacity | 0.835 (0.938 / 0.752) | 0.836 (0.949 / 0.748) | 0.863 (0.844 / 0.882) | 53 / 46 | +0.003 |
| Lung Lesion | 0.590 (0.621 / 0.562) | 0.614 (0.675 / 0.562) | 0.731 (0.679 / 0.792) | 34 / 15 | +0.016 |
| Atelectasis | 0.857 (0.966 / 0.770) | 0.855 (0.980 / 0.759) | 0.880 (0.959 / 0.813) | 15 / 6 | +0.003 |
| Pleural Effusion | 0.932 (1.000 / 0.873) | 0.932 (1.000 / 0.873) | 0.962 (1.000 / 0.927) | 6 / 0 | +0.003 |
| Fracture | 0.872 (0.783 / 0.985) | 0.884 (0.802 / 0.985) | 0.850 (0.747 / 0.985) | 0 / 4 | -0.003 |
| Support Devices | 0.856 (0.765 / 0.972) | 0.861 (0.784 / 0.956) | 0.879 (0.796 / 0.981) | 21 / 3 | +0.003 |
| Other Abnormality | 0.944 (0.941 / 0.946) | 0.937 (0.944 / 0.931) | 0.945 (0.933 / 0.957) | 34 / 32 | +0.000 |
| Edema (rare) | 0.903 (0.966 / 0.848) | 0.903 (0.966 / 0.848) | 0.923 (0.938 / 0.909) | 2 / 1 | – |
| Pleural Other (rare) | 0.682 (0.569 / 0.853) | 0.675 (0.571 / 0.824) | 0.674 (0.558 / 0.853) | 2 / 3 | – |
| Consolidation (rare) | 0.923 (0.857 / 1.000) | 0.923 (0.857 / 1.000) | 0.696 (0.533 / 1.000) | 1 / 18 | – |
| Pneumothorax (rare) | 0.919 (1.000 / 0.850) | 0.919 (1.000 / 0.850) | 0.947 (1.000 / 0.900) | 1 / 0 | – |

Without Other Abnormality (macro-F1 over the other 8 headline labels): v2 − LLM only 0.028 (0.018–0.039) (CI excludes 0).

Suggested labels per label (scored reports): Cardiomegaly 2 (present 2, precision 0.000); Lung Opacity 69 (present 65, precision 0.415); Lung Lesion 33 (present 32, precision 0.656); Atelectasis 1 (present 1, precision 1.000); Pleural Effusion 1 (present 0, precision –); Support Devices 5 (present 5, precision 0.600); Other Abnormality 51 (present 45, precision 0.667); Edema 5 (present 0, precision –); Pleural Other 4 (present 3, precision 0.000).

Known issue: Consolidation, v2 vs LLM + verifier wrong → right 0, right → wrong 18; candidate for a future prompt version developed on a new dev slice.

**Normal-check ablation (chosen after seeing the results; v2 stays the headline):** the 160 reports escalated only by the normal check skip the agent (tagger labels, No Finding `unverified`). Macro-F1 (v1) 0.887 (0.874–0.899); ablation − v2 0.000 (0.000–0.000); saves 160 agent runs (250 calls, $0.25); reports with an unverified label rise to 250 (8.1%), because those normals stay unconfirmed. Not significantly worse: **yes**. Serving configuration: **v2** (v2: the ablation changes no label but would show ~99%-correct normals as unverified (owner, 2026-10-22)).

### Final borderline rule (after M10a)

Final deterministic rule after the verifier agent (owner decision after M10a): an `uncertain` label whose only hedge-like wording is wording its definition counts as present (Cardiomegaly: "borderline", "mild") becomes `present`; any other hedge cue in the cited sentences keeps it `uncertain`. No LLM call changes; v2 re-scored from the cache. Found on the hand-written sample patient, not on test results. Before = results at `11f5f2e`.

| | Before | After |
|---|---|---|
| Macro-F1, 9 headline labels (v1) | 0.887 (0.874–0.899) | 0.892 (0.879–0.903) |
| Macro-F1, 9 headline labels (strict) | 0.883 (0.869–0.895) | 0.887 (0.873–0.899) |
| Pooled rare micro-F1 (v1) | 0.783 (0.723–0.832) | 0.783 (0.723–0.832) |
| Cardiomegaly F1 (v1) | 0.943 (0.924–0.960) | 0.981 (0.971–0.990) |
| Cardiomegaly precision / recall | 0.983 / 0.906 | 0.981 / 0.981 |
| Cardiomegaly present / uncertain (all reports) | 369 / 46 | 396 / 19 |

Paired headline macro-F1 (v1), after − before: 0.004 (0.003–0.006). Labels changed: 27 (uncertain -> present 27; by label {'Cardiomegaly': 27}; by verification state {'corrected': 27}); in hedged reports 2, in the Tier 1 pilot reports 0. Scored against the codes (present = positive, hedged and pilot reports excluded): v1 wrong → right 24, right → wrong 1; strict wrong → right 22, right → wrong 1.

### Escalation before any agent call, and the dev slice

Free checks on all 3,086 unique reports (clean join, tagger from cache, no agent call, $0): **1,290 reports escalate (41.8%)**; hedged 67.0% vs clear 39.3%; 1,777 labels. 7 content-filtered reports end `unverified` without an agent call.

| Reason | Reports | Labels | Reports with only this reason |
|---|---|---|---|
| section rule | 778 | 911 | 153 |
| recall scan | 576 | 617 | 0 |
| evidence mentions label | 424 | 463 | 265 |
| normal check | 278 | 278 | 160 |
| hedge consistency | 105 | 125 | 58 |
| negation consistency | 14 | 16 | 8 |

Escalation precision (tagger labels disagree with the codes): reports 44.3%, labels 32.6%; base rate 25.0%; not escalated 11.2% (201 reports). Predicted No Finding 577: normal check passed 299 (precision 99.0%), failed 278 (precision 99.3%).

Verifier agent on the **dev slice only** (38 escalated of 102 Tier 1 pilot reports; not a headline result), prompt `verifier-v2` (frozen): labels changed vs the codes wrong → right 11, right → wrong 3; suggested correct 3, wrong 3; verified 24, corrected 11, unverified 4; mean tool calls 1.87; $0.0017 per report. Estimated full run: 1,252 reports, $2.10.

## Retrieval (M8, SPEC §8.2): base models

Index from the M7 v2 outputs (predicted labels only): Postgres 3,086 reports and 40,118 labels; Qdrant 3,086 report and 19,006 sentence points (./models/serving/model). Checks on the stored points: payload keys whitelisted yes; indication text in a point 0 of 2,192 tested (4 reports repeat the indication's words in their own Findings/Impression).

**Reading (M8).** Best variant by nDCG@10: seen label base bge-small + negated-sentence payload filter (no training) (0.871); heldout label base bge-small + negated-sentence payload filter (no training) (0.643); heldout alias base bge-small, no prefix + negated-sentence filter (0.691); attribute base no-prefix sentences + BM25 (RRF) (0.822); compositional base bge-small + negated-sentence payload filter (no training) (0.523); report to report BM25 (0.470); all base bge-small, no prefix + negated-sentence filter (0.582). The negated-sentence filter lowers negation contamination on the label queries (seen labels 0.310 → 0.070). Part of its gain comes from the contextual prefix, which names the PREDICTED v2 labels: once the "No X" sentences are filtered out, sentences whose prefix mentions X come from reports predicted positive for X, so this row partly measures the labelling pipeline, not only the embeddings. Base models only; no held-out effect is expected before fine-tuning. **Best base combination** (owner rule, SPEC §8.2): **base bge-small, sentences without prefix (pure embedding)**: the top two, base bge-small, no prefix + negated-sentence filter (0.582) and base bge-small, sentences without prefix (pure embedding) (0.564), are within each other's 95% CI, so the simpler one is chosen. It is the reference for the M9 full-system comparison.

Per fold, each fold's reports indexed alone; pooled over (query, fold) pairs with 95% bootstrap CIs; spec frozen before the run (`eval/queries/retrieval_v1.yaml`).

**seen label** (40 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.463 (0.347–0.573) | 0.481 (0.367–0.592) | 0.407 (0.290–0.515) |
| base bge-small, report-level | 0.643 (0.549–0.741) | 0.672 (0.581–0.764) | 0.310 (0.205–0.415) |
| base bge-small, sentences without prefix (pure embedding) | 0.729 (0.650–0.805) | 0.731 (0.655–0.804) | 0.208 (0.120–0.300) |
| base bge-small, no prefix + negated-sentence filter | 0.824 (0.769–0.875) | 0.822 (0.766–0.875) | 0.083 (0.042–0.125) |
| base no-prefix sentences + BM25 (RRF) | 0.629 (0.526–0.725) | 0.646 (0.540–0.738) | 0.275 (0.175–0.380) |
| base bge-small, contextual sentences | 0.647 (0.562–0.734) | 0.637 (0.549–0.725) | 0.310 (0.205–0.410) |
| base bge-small + negated-sentence payload filter (no training) | 0.868 (0.831–0.908) | 0.871 (0.830–0.913) | 0.070 (0.032–0.118) |
| base contextual sentences + BM25 (RRF) | 0.659 (0.559–0.756) | 0.683 (0.581–0.779) | 0.310 (0.202–0.415) |

**heldout label** (15 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.253 (0.160–0.360) | 0.253 (0.154–0.363) | 0.140 (0.060–0.227) |
| base bge-small, report-level | 0.260 (0.187–0.327) | 0.265 (0.193–0.340) | 0.120 (0.047–0.220) |
| base bge-small, sentences without prefix (pure embedding) | 0.387 (0.287–0.500) | 0.406 (0.306–0.525) | 0.053 (0.007–0.113) |
| base bge-small, no prefix + negated-sentence filter | 0.413 (0.300–0.533) | 0.434 (0.318–0.558) | 0.027 (0.000–0.060) |
| base no-prefix sentences + BM25 (RRF) | 0.333 (0.220–0.453) | 0.367 (0.242–0.498) | 0.073 (0.020–0.127) |
| base bge-small, contextual sentences | 0.633 (0.540–0.733) | 0.638 (0.527–0.751) | 0.033 (0.013–0.060) |
| base bge-small + negated-sentence payload filter (no training) | 0.633 (0.533–0.733) | 0.643 (0.532–0.759) | 0.013 (0.000–0.033) |
| base contextual sentences + BM25 (RRF) | 0.433 (0.333–0.540) | 0.463 (0.349–0.573) | 0.053 (0.007–0.107) |

**heldout alias** (90 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.450 (0.380–0.514) | 0.494 (0.422–0.558) | 0.148 (0.096–0.204) |
| base bge-small, report-level | 0.619 (0.552–0.677) | 0.644 (0.581–0.700) | 0.089 (0.049–0.132) |
| base bge-small, sentences without prefix (pure embedding) | 0.643 (0.577–0.703) | 0.670 (0.607–0.728) | 0.104 (0.061–0.151) |
| base bge-small, no prefix + negated-sentence filter | 0.666 (0.599–0.725) | 0.691 (0.627–0.749) | 0.070 (0.039–0.108) |
| base no-prefix sentences + BM25 (RRF) | 0.596 (0.525–0.656) | 0.635 (0.565–0.694) | 0.107 (0.063–0.152) |
| base bge-small, contextual sentences | 0.625 (0.555–0.691) | 0.647 (0.581–0.710) | 0.108 (0.068–0.151) |
| base bge-small + negated-sentence payload filter (no training) | 0.651 (0.580–0.719) | 0.671 (0.602–0.737) | 0.073 (0.040–0.111) |
| base contextual sentences + BM25 (RRF) | 0.641 (0.569–0.700) | 0.669 (0.601–0.727) | 0.108 (0.067–0.151) |

**attribute** (100 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.739 (0.700–0.779) | 0.734 (0.695–0.772) | 0.135 (0.095–0.182) |
| base bge-small, report-level | 0.599 (0.552–0.648) | 0.613 (0.569–0.662) | 0.131 (0.089–0.177) |
| base bge-small, sentences without prefix (pure embedding) | 0.787 (0.746–0.826) | 0.803 (0.768–0.840) | 0.038 (0.022–0.058) |
| base bge-small, no prefix + negated-sentence filter | 0.796 (0.757–0.832) | 0.810 (0.777–0.845) | 0.011 (0.003–0.020) |
| base no-prefix sentences + BM25 (RRF) | 0.804 (0.764–0.841) | 0.822 (0.788–0.852) | 0.062 (0.034–0.094) |
| base bge-small, contextual sentences | 0.786 (0.746–0.823) | 0.777 (0.739–0.813) | 0.075 (0.051–0.103) |
| base bge-small + negated-sentence payload filter (no training) | 0.802 (0.763–0.836) | 0.792 (0.754–0.826) | 0.023 (0.011–0.037) |
| base contextual sentences + BM25 (RRF) | 0.825 (0.789–0.859) | 0.816 (0.783–0.847) | 0.062 (0.035–0.094) |

**compositional** (49 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.285 (0.215–0.354) | 0.288 (0.216–0.359) | 0.355 (0.249–0.463) |
| base bge-small, report-level | 0.304 (0.230–0.386) | 0.293 (0.219–0.376) | 0.316 (0.218–0.416) |
| base bge-small, sentences without prefix (pure embedding) | 0.343 (0.258–0.428) | 0.370 (0.283–0.458) | 0.310 (0.212–0.412) |
| base bge-small, no prefix + negated-sentence filter | 0.363 (0.278–0.444) | 0.380 (0.290–0.466) | 0.212 (0.143–0.286) |
| base no-prefix sentences + BM25 (RRF) | 0.296 (0.220–0.373) | 0.324 (0.239–0.405) | 0.337 (0.233–0.447) |
| base bge-small, contextual sentences | 0.379 (0.295–0.469) | 0.395 (0.310–0.485) | 0.308 (0.204–0.414) |
| base bge-small + negated-sentence payload filter (no training) | 0.534 (0.438–0.625) | 0.523 (0.426–0.616) | 0.163 (0.106–0.222) |
| base contextual sentences + BM25 (RRF) | 0.341 (0.265–0.421) | 0.352 (0.270–0.436) | 0.343 (0.235–0.447) |

**report to report** (200 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.720 (0.681–0.760) | 0.470 (0.439–0.502) | – |
| base bge-small, report-level | 0.590 (0.546–0.632) | 0.392 (0.358–0.427) | – |
| base bge-small, sentences without prefix (pure embedding) | 0.674 (0.636–0.712) | 0.421 (0.392–0.450) | – |
| base bge-small, no prefix + negated-sentence filter | 0.685 (0.647–0.723) | 0.431 (0.400–0.459) | – |
| base no-prefix sentences + BM25 (RRF) | 0.701 (0.664–0.741) | 0.451 (0.423–0.481) | – |
| base bge-small, contextual sentences | 0.442 (0.394–0.494) | 0.262 (0.230–0.297) | – |
| base bge-small + negated-sentence payload filter (no training) | 0.432 (0.383–0.482) | 0.257 (0.224–0.294) | – |
| base contextual sentences + BM25 (RRF) | 0.579 (0.531–0.627) | 0.360 (0.329–0.394) | – |

**all** (494 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.597 (0.565–0.627) | 0.504 (0.476–0.531) | 0.224 (0.185–0.263) |
| base bge-small, report-level | 0.563 (0.534–0.593) | 0.492 (0.465–0.518) | 0.178 (0.146–0.213) |
| base bge-small, sentences without prefix (pure embedding) | 0.654 (0.627–0.681) | 0.564 (0.537–0.589) | 0.140 (0.108–0.174) |
| base bge-small, no prefix + negated-sentence filter | 0.675 (0.649–0.701) | 0.582 (0.555–0.608) | 0.081 (0.061–0.103) |
| base no-prefix sentences + BM25 (RRF) | 0.645 (0.616–0.672) | 0.560 (0.533–0.585) | 0.163 (0.129–0.198) |
| base bge-small, contextual sentences | 0.561 (0.531–0.592) | 0.491 (0.462–0.519) | 0.164 (0.134–0.198) |
| base bge-small + negated-sentence payload filter (no training) | 0.598 (0.567–0.630) | 0.528 (0.497–0.559) | 0.074 (0.056–0.092) |
| base contextual sentences + BM25 (RRF) | 0.618 (0.589–0.649) | 0.537 (0.511–0.567) | 0.169 (0.135–0.203) |

## Embedding fine-tuning (M9, SPEC §8.2)

**Reading (M9).** Fine-tuning on plain sentences changes pooled nDCG@10 by +0.028 (+0.019 to +0.038) against the base model (paired, same query–fold pairs) and negation contamination@10 by -0.043 (-0.057 to -0.029). By query set: seen labels +0.134 (+0.082 to +0.191), better; held-out labels -0.010 (-0.058 to +0.040), no clear difference; held-out aliases +0.069 (+0.047 to +0.091), better; attribute -0.013 (-0.032 to +0.006), no clear difference; compositional +0.045 (+0.024 to +0.069), better; report-to-report +0.007 (-0.003 to +0.017), no clear difference. The pre-committed use rule (nDCG@10 difference not significantly negative and contamination not higher) **passes**, so search and session RAG use the **fine-tuned** model; the verifier agent keeps the base model. With the negated-sentence filter on both sides: +0.020 (+0.012 to +0.030) pooled (better). Held-out labels were never in training, so the held-out-label row is the test of generalisation to unseen findings.

| Query set | Base plain | Fine-tuned plain | Difference (95% CI) | Base + filter | Fine-tuned + filter | Difference (95% CI) |
|---|---|---|---|---|---|---|
| seen labels | 0.731 | 0.866 | +0.134 (+0.082 to +0.191) | 0.822 | 0.893 | +0.071 (+0.035 to +0.113) |
| held-out labels | 0.406 | 0.396 | -0.010 (-0.058 to +0.040) | 0.434 | 0.406 | -0.028 (-0.067 to +0.011) |
| held-out aliases | 0.670 | 0.739 | +0.069 (+0.047 to +0.091) | 0.691 | 0.743 | +0.052 (+0.032 to +0.076) |
| attribute | 0.803 | 0.791 | -0.013 (-0.032 to +0.006) | 0.810 | 0.795 | -0.016 (-0.035 to +0.003) |
| compositional | 0.370 | 0.416 | +0.045 (+0.024 to +0.069) | 0.380 | 0.444 | +0.065 (+0.030 to +0.105) |
| report-to-report | 0.421 | 0.428 | +0.007 (-0.003 to +0.017) | 0.431 | 0.436 | +0.006 (-0.004 to +0.015) |
| all (pooled) | 0.564 | 0.592 | +0.028 (+0.019 to +0.038) | 0.582 | 0.602 | +0.020 (+0.012 to +0.030) |
| *negation contamination@10, all* | 0.140 | 0.097 | -0.043 (-0.057 to -0.029) | 0.081 | 0.066 | -0.015 (-0.026 to -0.007) |

nDCG@10; paired 95% bootstrap CIs over (query, fold) pairs; model k evaluated on fold k only.

Training (training folds only; inner validation for epoch selection): best epochs 3, 3, 2, 3, 2; inner-validation nDCG@10 base → fine-tuned 0.519 → 0.753, 0.507 → 0.740, 0.541 → 0.744, 0.553 → 0.733, 0.482 → 0.713; about 4,232 triplets per fold; NVIDIA GeForce RTX 5050 Laptop GPU, torch 2.11.0+cu128, CUDA 12.8, driver 592.82.
Serving model: all reports, 3 epochs, 4,398 triplets; stored privately (MODEL_STORE), never in the repository.

### All rows, fine-tuning run

**seen label** (40 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.463 (0.347–0.573) | 0.481 (0.367–0.592) | 0.407 (0.290–0.515) |
| base bge-small, report-level | 0.643 (0.549–0.741) | 0.673 (0.581–0.764) | 0.310 (0.205–0.415) |
| base bge-small, sentences without prefix (pure embedding) | 0.729 (0.650–0.805) | 0.731 (0.655–0.804) | 0.208 (0.120–0.300) |
| base bge-small, no prefix + negated-sentence filter | 0.824 (0.769–0.875) | 0.822 (0.766–0.875) | 0.083 (0.042–0.125) |
| base no-prefix sentences + BM25 (RRF) | 0.629 (0.526–0.725) | 0.646 (0.540–0.738) | 0.275 (0.175–0.380) |
| base bge-small, contextual sentences | 0.647 (0.562–0.734) | 0.637 (0.549–0.725) | 0.310 (0.205–0.410) |
| base bge-small + negated-sentence payload filter (no training) | 0.868 (0.831–0.908) | 0.871 (0.830–0.913) | 0.070 (0.032–0.118) |
| base contextual sentences + BM25 (RRF) | 0.659 (0.559–0.756) | 0.683 (0.581–0.779) | 0.310 (0.202–0.415) |
| fine-tuned, sentences without prefix | 0.874 (0.831–0.916) | 0.866 (0.821–0.909) | 0.123 (0.062–0.188) |
| fine-tuned, no prefix + negated-sentence filter | 0.905 (0.869–0.936) | 0.893 (0.852–0.929) | 0.058 (0.028–0.092) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.692 (0.595–0.775) | 0.724 (0.634–0.806) | 0.250 (0.152–0.355) |

**heldout label** (15 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.253 (0.160–0.360) | 0.253 (0.154–0.363) | 0.140 (0.060–0.227) |
| base bge-small, report-level | 0.260 (0.187–0.327) | 0.265 (0.193–0.340) | 0.120 (0.047–0.220) |
| base bge-small, sentences without prefix (pure embedding) | 0.387 (0.287–0.500) | 0.406 (0.306–0.525) | 0.053 (0.007–0.113) |
| base bge-small, no prefix + negated-sentence filter | 0.413 (0.300–0.533) | 0.434 (0.318–0.558) | 0.027 (0.000–0.060) |
| base no-prefix sentences + BM25 (RRF) | 0.333 (0.220–0.453) | 0.367 (0.242–0.498) | 0.073 (0.020–0.127) |
| base bge-small, contextual sentences | 0.633 (0.540–0.733) | 0.638 (0.527–0.751) | 0.033 (0.013–0.060) |
| base bge-small + negated-sentence payload filter (no training) | 0.633 (0.533–0.733) | 0.643 (0.532–0.759) | 0.013 (0.000–0.033) |
| base contextual sentences + BM25 (RRF) | 0.433 (0.333–0.540) | 0.463 (0.349–0.573) | 0.053 (0.007–0.107) |
| fine-tuned, sentences without prefix | 0.407 (0.267–0.553) | 0.396 (0.268–0.549) | 0.027 (0.007–0.053) |
| fine-tuned, no prefix + negated-sentence filter | 0.407 (0.267–0.553) | 0.406 (0.270–0.559) | 0.020 (0.000–0.040) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.373 (0.240–0.507) | 0.390 (0.251–0.535) | 0.053 (0.013–0.100) |

**heldout alias** (90 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.450 (0.380–0.514) | 0.494 (0.422–0.558) | 0.148 (0.096–0.204) |
| base bge-small, report-level | 0.619 (0.552–0.677) | 0.644 (0.581–0.700) | 0.089 (0.049–0.132) |
| base bge-small, sentences without prefix (pure embedding) | 0.643 (0.577–0.703) | 0.670 (0.607–0.728) | 0.104 (0.061–0.151) |
| base bge-small, no prefix + negated-sentence filter | 0.666 (0.599–0.725) | 0.691 (0.627–0.749) | 0.070 (0.039–0.108) |
| base no-prefix sentences + BM25 (RRF) | 0.596 (0.525–0.656) | 0.635 (0.565–0.694) | 0.107 (0.063–0.152) |
| base bge-small, contextual sentences | 0.625 (0.555–0.691) | 0.647 (0.581–0.710) | 0.108 (0.068–0.151) |
| base bge-small + negated-sentence payload filter (no training) | 0.651 (0.580–0.719) | 0.671 (0.602–0.737) | 0.073 (0.040–0.111) |
| base contextual sentences + BM25 (RRF) | 0.641 (0.569–0.700) | 0.669 (0.601–0.727) | 0.108 (0.067–0.151) |
| fine-tuned, sentences without prefix | 0.738 (0.675–0.793) | 0.739 (0.678–0.796) | 0.079 (0.046–0.117) |
| fine-tuned, no prefix + negated-sentence filter | 0.741 (0.674–0.799) | 0.743 (0.680–0.803) | 0.074 (0.040–0.112) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.672 (0.604–0.733) | 0.696 (0.630–0.755) | 0.097 (0.054–0.144) |

**attribute** (100 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.739 (0.700–0.779) | 0.734 (0.695–0.772) | 0.135 (0.095–0.182) |
| base bge-small, report-level | 0.599 (0.552–0.648) | 0.613 (0.569–0.662) | 0.131 (0.089–0.177) |
| base bge-small, sentences without prefix (pure embedding) | 0.787 (0.746–0.826) | 0.803 (0.768–0.840) | 0.038 (0.022–0.058) |
| base bge-small, no prefix + negated-sentence filter | 0.796 (0.757–0.832) | 0.810 (0.777–0.845) | 0.011 (0.003–0.020) |
| base no-prefix sentences + BM25 (RRF) | 0.804 (0.764–0.841) | 0.822 (0.788–0.852) | 0.062 (0.034–0.094) |
| base bge-small, contextual sentences | 0.786 (0.746–0.823) | 0.777 (0.739–0.813) | 0.075 (0.051–0.103) |
| base bge-small + negated-sentence payload filter (no training) | 0.802 (0.763–0.836) | 0.792 (0.754–0.826) | 0.023 (0.011–0.037) |
| base contextual sentences + BM25 (RRF) | 0.825 (0.789–0.859) | 0.816 (0.783–0.847) | 0.062 (0.035–0.094) |
| fine-tuned, sentences without prefix | 0.770 (0.728–0.812) | 0.791 (0.753–0.829) | 0.022 (0.011–0.035) |
| fine-tuned, no prefix + negated-sentence filter | 0.774 (0.732–0.817) | 0.795 (0.756–0.832) | 0.009 (0.002–0.018) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.809 (0.771–0.847) | 0.819 (0.788–0.851) | 0.048 (0.025–0.075) |

**compositional** (49 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.285 (0.215–0.354) | 0.288 (0.216–0.359) | 0.355 (0.249–0.463) |
| base bge-small, report-level | 0.304 (0.230–0.386) | 0.293 (0.219–0.376) | 0.316 (0.218–0.416) |
| base bge-small, sentences without prefix (pure embedding) | 0.343 (0.258–0.428) | 0.370 (0.283–0.458) | 0.310 (0.212–0.412) |
| base bge-small, no prefix + negated-sentence filter | 0.363 (0.278–0.444) | 0.380 (0.290–0.466) | 0.212 (0.143–0.286) |
| base no-prefix sentences + BM25 (RRF) | 0.296 (0.220–0.373) | 0.324 (0.239–0.405) | 0.337 (0.233–0.447) |
| base bge-small, contextual sentences | 0.379 (0.295–0.469) | 0.395 (0.310–0.485) | 0.308 (0.204–0.414) |
| base bge-small + negated-sentence payload filter (no training) | 0.534 (0.438–0.625) | 0.523 (0.426–0.616) | 0.163 (0.106–0.222) |
| base contextual sentences + BM25 (RRF) | 0.341 (0.265–0.421) | 0.352 (0.270–0.436) | 0.343 (0.235–0.447) |
| fine-tuned, sentences without prefix | 0.398 (0.312–0.478) | 0.416 (0.321–0.505) | 0.229 (0.153–0.310) |
| fine-tuned, no prefix + negated-sentence filter | 0.435 (0.357–0.513) | 0.444 (0.357–0.532) | 0.147 (0.094–0.208) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.339 (0.259–0.419) | 0.355 (0.269–0.434) | 0.271 (0.182–0.363) |

**report to report** (200 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.720 (0.681–0.760) | 0.470 (0.439–0.502) | – |
| base bge-small, report-level | 0.590 (0.546–0.632) | 0.392 (0.358–0.427) | – |
| base bge-small, sentences without prefix (pure embedding) | 0.674 (0.636–0.712) | 0.421 (0.392–0.450) | – |
| base bge-small, no prefix + negated-sentence filter | 0.685 (0.647–0.723) | 0.431 (0.400–0.459) | – |
| base no-prefix sentences + BM25 (RRF) | 0.701 (0.664–0.741) | 0.451 (0.423–0.481) | – |
| base bge-small, contextual sentences | 0.442 (0.394–0.494) | 0.262 (0.230–0.297) | – |
| base bge-small + negated-sentence payload filter (no training) | 0.432 (0.383–0.482) | 0.257 (0.224–0.294) | – |
| base contextual sentences + BM25 (RRF) | 0.579 (0.531–0.627) | 0.360 (0.329–0.394) | – |
| fine-tuned, sentences without prefix | 0.679 (0.640–0.716) | 0.428 (0.399–0.457) | – |
| fine-tuned, no prefix + negated-sentence filter | 0.691 (0.653–0.727) | 0.436 (0.405–0.465) | – |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.712 (0.674–0.751) | 0.460 (0.431–0.491) | – |

**all** (494 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.597 (0.565–0.627) | 0.504 (0.476–0.531) | 0.224 (0.185–0.263) |
| base bge-small, report-level | 0.563 (0.534–0.593) | 0.492 (0.465–0.518) | 0.178 (0.146–0.213) |
| base bge-small, sentences without prefix (pure embedding) | 0.654 (0.627–0.681) | 0.564 (0.537–0.589) | 0.140 (0.108–0.174) |
| base bge-small, no prefix + negated-sentence filter | 0.675 (0.649–0.701) | 0.582 (0.555–0.608) | 0.081 (0.061–0.103) |
| base no-prefix sentences + BM25 (RRF) | 0.645 (0.616–0.672) | 0.560 (0.533–0.585) | 0.163 (0.129–0.198) |
| base bge-small, contextual sentences | 0.561 (0.531–0.592) | 0.491 (0.462–0.519) | 0.164 (0.134–0.198) |
| base bge-small + negated-sentence payload filter (no training) | 0.598 (0.567–0.630) | 0.528 (0.497–0.559) | 0.074 (0.056–0.092) |
| base contextual sentences + BM25 (RRF) | 0.618 (0.589–0.649) | 0.537 (0.511–0.567) | 0.169 (0.135–0.203) |
| fine-tuned, sentences without prefix | 0.688 (0.660–0.714) | 0.592 (0.565–0.618) | 0.097 (0.075–0.120) |
| fine-tuned, no prefix + negated-sentence filter | 0.700 (0.672–0.725) | 0.602 (0.575–0.628) | 0.066 (0.048–0.085) |
| fine-tuned no-prefix sentences + BM25 (RRF) | 0.675 (0.647–0.701) | 0.585 (0.557–0.610) | 0.139 (0.109–0.170) |

## Ask evaluation (M10b, SPEC §8.3)

Pre-registered in [evaluation_notes.md](evaluation_notes.md#ask-evaluation-m10b-owner-2026-10-22-pre-committed-before-any-run). Frozen website prompts through the real code, gpt-4.1-mini, one run per question; answers parsed by rules; expected answers from the expert codes (v1, `present` = positive; hedged reports left out of that column) and from the v2 labels; citations checked in code. Cells: share correct (95% bootstrap CI) n.

New spend 0.639 USD (1,594 answers).

**Part 1: one report, the 102 dev-slice reports** (the frozen questions of groups A, B, D on a seeded sample of 30 of them).

| Question group | Questions | Correct vs codes | Correct vs v2 | Unreadable answers |
|---|---|---|---|---|
| Is there <finding>? (6 labels) | 612 | 97.7% (96–99) n=576 | 98.2% (97–99) n=612 | 0 |
| What supports <label>? | 172 | 96.1% (93–99) n=154 | 98.3% (96–100) n=172 | 0 |
| Frozen A (answerable) | 180 | 96.4% (93–99) n=168 | 96.7% (94–99) n=180 | 0 |
| Frozen B (tricky wording) | 120 | 71.4% (65–78) n=112 | 71.7% (66–77) n=120 | 15 |
| Frozen D (must refuse) | 150 | 95.7% (92–99) n=140 | 95.3% (92–98) n=150 | 0 |

Frozen D is scored by the pre-registered rule (a refusal, `answer` null). Post-hoc, not pre-registered: the frozen scoring note also accepts an answer that says the reports don't state it, with no number or diagnosis (a redacted age is not a value); on that reading 99.3% (98–100) n=150.

Is there <finding>? by label (vs codes):

| Label | Coded present | Not coded |
|---|---|---|
| Cardiomegaly | 100.0% (100–100) n=11 | 98.8% (96–100) n=85 |
| Pleural Effusion | 100.0% (100–100) n=5 | 100.0% (100–100) n=91 |
| Support Devices | 81.8% (64–100) n=11 | 97.6% (94–100) n=85 |
| Lung Opacity | 86.7% (67–100) n=15 | 95.1% (90–99) n=81 |
| Atelectasis | 80.0% (50–100) n=10 | 100.0% (100–100) n=86 |
| Pneumothorax | 100.0% (100–100) n=1 | 100.0% (100–100) n=95 |

Citations (Part 1): 1,687 of 1,687 cited sentences existed among the given ones (100.0%; the rest were dropped by the code check; 0 answers became "not stated" because no valid citation was left). Of 165 answers that affirm a finding, at least one cited sentence names it (eval detector, not negated) in 77.0% (66–86) n=165; every cited sentence does in 66.1% (55–75) n=165.
Refusals (Part 1): precision 0.993, recall 0.953 (143 of 150 unanswerable questions refused; 1 of 143 answerable-and-positive questions wrongly refused).

**Part 2: across reports.** Synthetic patients: 3 batches of random out-of-fold IU reports per size (never the dev slice), upload order = batch order. RAG = the website configuration (fold-k fine-tuned model, top 12 sentences); all in prompt = every sentence of every report. 15 questions per batch (5 templated, frozen C and D).

| Reports | Method | Correct vs codes (all) | Templated | Frozen C | Frozen D (refuse) | D, post-hoc lenient | Correct vs v2 | Unreadable | Mean input tokens | Cost / request | Latency p50 / p95 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | RAG | 71.1% (58–84) n=45 | 60.0% (33–80) n=15 | 66.7% (40–87) n=15 | 86.7% (67–100) n=15 | 100.0% (100–100) n=15 | 71.1% (58–84) n=45 | 5 of 45 | 664 | $0.00034 | 1.21 / 1.84 |
| 3 | all in prompt | 68.9% (56–82) n=45 | 80.0% (60–100) n=15 | 53.3% (27–80) n=15 | 73.3% (53–93) n=15 | 80.0% (60–100) n=15 | 68.9% (56–82) n=45 | 5 of 45 | 934 | $0.00045 | 1.21 / 2.36 |
| 10 | RAG | 53.3% (40–67) n=45 | 33.3% (13–60) n=15 | 53.3% (27–80) n=15 | 73.3% (53–93) n=15 | 100.0% (100–100) n=15 | 48.9% (36–64) n=45 | 3 of 45 | 687 | $0.00037 | 1.28 / 2.55 |
| 10 | all in prompt | 53.3% (40–67) n=45 | 26.7% (7–47) n=15 | 53.3% (27–80) n=15 | 80.0% (60–100) n=15 | 93.3% (80–100) n=15 | 51.1% (38–67) n=45 | 4 of 45 | 2083 | $0.00042 | 1.40 / 3.03 |
| 30 | RAG | 51.1% (38–67) n=45 | 40.0% (20–67) n=15 | 53.3% (27–80) n=15 | 60.0% (33–87) n=15 | 93.3% (80–100) n=15 | 46.7% (33–62) n=45 | 3 of 45 | 674 | $0.00037 | 1.38 / 2.40 |
| 30 | all in prompt | 60.0% (47–73) n=45 | 20.0% (0–40) n=15 | 66.7% (47–87) n=15 | 93.3% (80–100) n=15 | 100.0% (100–100) n=15 | 60.0% (47–73) n=45 | 5 of 45 | 5345 | $0.00086 | 1.59 / 3.91 |
| 50 | RAG | 33.3% (20–47) n=45 | 20.0% (0–40) n=15 | 26.7% (7–47) n=15 | 53.3% (27–80) n=15 | 86.7% (67–100) n=15 | 35.6% (22–49) n=45 | 2 of 45 | 663 | $0.00040 | 1.54 / 2.53 |
| 50 | all in prompt | 48.9% (36–62) n=45 | 46.7% (20–73) n=15 | 20.0% (0–40) n=15 | 80.0% (60–100) n=15 | 100.0% (100–100) n=15 | 46.7% (33–60) n=45 | 2 of 45 | 8274 | $0.00142 | 2.00 / 7.30 |

| Reports | Paired RAG − all in prompt, vs codes | vs v2 | Reading (pre-registered rule) | Retrieved mention of a coded report's label |
|---|---|---|---|---|
| 3 | +2.2 pts (-8.9 to +13.3) | +2.2 pts (-8.9 to +13.3) | no detectable difference | 100.0% of 20 |
| 10 | +0.0 pts (-11.2 to +13.3) | -2.2 pts (-13.3 to +8.9) | no detectable difference | 97.0% of 33 |
| 30 | -8.9 pts (-24.5 to +8.9) | -13.3 pts (-28.9 to +2.2) | no detectable difference | 64.4% of 59 |
| 50 | -15.6 pts (-28.9 to -2.2) | -11.1 pts (-26.7 to +2.2) | all-in-prompt better | 51.1% of 88 |

Citations (Part 2), structural validity and support by the eval detector (at least one / every cited sentence):

| Reports | Method | Cited sentences that existed | Affirming answers | Support (≥1) | Support (all) | Refusal precision / recall |
|---|---|---|---|---|---|---|
| 3 | RAG | 100.0% | 14 | 78.6% (57–100) n=14 | 64.3% (43–86) n=14 | 1.00 / 0.87 |
| 3 | all in prompt | 100.0% | 14 | 92.9% (79–100) n=14 | 92.9% (79–100) n=14 | 1.00 / 0.73 |
| 10 | RAG | 100.0% | 19 | 84.2% (68–100) n=19 | 73.7% (53–89) n=19 | 1.00 / 0.73 |
| 10 | all in prompt | 100.0% | 20 | 75.0% (55–90) n=20 | 55.0% (35–75) n=20 | 1.00 / 0.80 |
| 30 | RAG | 100.0% | 20 | 70.0% (50–90) n=20 | 45.0% (25–70) n=20 | 1.00 / 0.60 |
| 30 | all in prompt | 100.0% | 18 | 83.3% (61–100) n=18 | 55.6% (33–78) n=18 | 1.00 / 0.93 |
| 50 | RAG | 100.0% | 21 | 76.2% (57–90) n=21 | 52.4% (33–71) n=21 | 1.00 / 0.53 |
| 50 | all in prompt | 100.0% | 20 | 65.0% (45–85) n=20 | 40.0% (20–60) n=20 | 1.00 / 0.80 |

**Hand-written questions** (the 20 frozen ones, scored with their scoring notes; correct vs codes, n answers scored): 

| # | Question | One report | RAG (3–50 reports) | All in prompt (3–50 reports) |
|---|---|---|---|---|
| 1 | Is the heart enlarged? | 96.4% (89–100) n=28 | – | – |
| 2 | Is there fluid around the lungs? | 100.0% (100–100) n=28 | – | – |
| 3 | Does the patient have any tubes, lines or devices in place? | 96.4% (89–100) n=28 | – | – |
| 4 | Is there any air outside the lung, a pneumothorax? | 100.0% (100–100) n=28 | – | – |
| 5 | Are any broken bones described? | 100.0% (100–100) n=28 | – | – |
| 6 | Is the report completely normal? | 85.7% (71–96) n=28 | – | – |
| 7 | Is there any sign of pulmonary edema? | 96.4% (89–100) n=28 | – | – |
| 8 | Is a lung nodule or mass definitely present? | 89.3% (79–100) n=28 | – | – |
| 9 | Does the report state that there is no pleural effusion? | 85.7% (71–96) n=28 | – | – |
| 10 | Is the lung opacity described with certainty, or only as possible? | 14.3% (4–29) n=28 | – | – |
| 11 | Which reports describe an enlarged heart? | – | 58.3% (33–83) n=12 | 50.0% (25–75) n=12 |
| 12 | In how many reports is a pleural effusion present? | – | 41.7% (17–67) n=12 | 33.3% (8–58) n=12 |
| 13 | In which report is a tube, line or device first mentioned? | – | 50.0% (25–75) n=12 | 58.3% (33–83) n=12 |
| 14 | Is there any report without abnormal findings? | – | 8.3% (0–25) n=12 | 0.0% (0–0) n=12 |
| 15 | Does any report describe a pneumothorax as present? | – | 91.7% (75–100) n=12 | 100.0% (100–100) n=12 |
| 16 | How old is the patient? | 78.6% (61–93) n=28; post-hoc lenient 96.7% (90–100) n=30 | 16.7% (0–42) n=12; post-hoc lenient 100.0% (100–100) n=12 | 25.0% (8–50) n=12; post-hoc lenient 83.3% (58–100) n=12 |
| 17 | Is this cancer? | 100.0% (100–100) n=28; post-hoc lenient 100.0% (100–100) n=30 | 83.3% (58–100) n=12; post-hoc lenient 83.3% (58–100) n=12 | 100.0% (100–100) n=12; post-hoc lenient 100.0% (100–100) n=12 |
| 18 | What treatment should the patient receive? | 100.0% (100–100) n=28; post-hoc lenient 100.0% (100–100) n=30 | 100.0% (100–100) n=12; post-hoc lenient 100.0% (100–100) n=12 | 100.0% (100–100) n=12; post-hoc lenient 100.0% (100–100) n=12 |
| 19 | What does the patient's CT scan show? | 100.0% (100–100) n=28; post-hoc lenient 100.0% (100–100) n=30 | 50.0% (25–75) n=12; post-hoc lenient 91.7% (75–100) n=12 | 83.3% (58–100) n=12; post-hoc lenient 83.3% (58–100) n=12 |
| 20 | What was the patient's oxygen saturation? | 100.0% (100–100) n=28; post-hoc lenient 100.0% (100–100) n=30 | 91.7% (75–100) n=12; post-hoc lenient 100.0% (100–100) n=12 | 100.0% (100–100) n=12; post-hoc lenient 100.0% (100–100) n=12 |
