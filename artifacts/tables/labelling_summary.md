# Labelling summary (README §8.1)

Out-of-fold, one report per exact text; hedged and Tier 1 pilot reports excluded unless stated; 95% bootstrap CIs over clusters. Scoring: `present` = positive, except in the sensitivity row.

| Metric | Rule baseline | LLM only | LLM + verifier | LLM + verifier + Tier 2 | run_pipeline, clean join (M6) | run_pipeline, 30% varied joins (M6) | LLM + free checks + verifier agent (v2) |
|---|---|---|---|---|---|---|---|
| Headline macro-F1, 9 labels (v1) | 0.838 (0.823–0.850) | 0.862 (0.848–0.875) | 0.860 (0.845–0.873) | 0.866 (0.851–0.878) | 0.860 (0.845–0.873) | 0.848 (0.833–0.861) | 0.887 (0.874–0.899) |
| Headline macro-F1, 9 labels (strict) | 0.829 (0.814–0.843) | 0.863 (0.848–0.877) | 0.861 (0.846–0.875) | 0.868 (0.853–0.881) | 0.861 (0.846–0.875) | 0.850 (0.835–0.865) | 0.883 (0.869–0.895) |
| Pooled rare micro-F1 (v1) | 0.742 (0.677–0.805) | 0.831 (0.771–0.882) | 0.838 (0.777–0.889) | 0.829 (0.769–0.882) | 0.838 (0.777–0.889) | 0.824 (0.764–0.875) | 0.783 (0.723–0.832) |
| Abnormal subset: headline macro-F1 (v1) | 0.761 (0.748–0.773) | 0.767 (0.754–0.781) | 0.765 (0.752–0.778) | 0.771 (0.758–0.783) | 0.765 (0.752–0.778) | 0.757 (0.744–0.770) | 0.792 (0.780–0.804) |
| negation_only FP rate (pooled) | 41 / 6164 (0.0067) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 14 / 6164 (0.0023) |
| *Sensitivity, not headline:* macro-F1 (v1) with `uncertain` = positive for all labels | 0.839 (0.825–0.852) | 0.853 (0.839–0.866) | 0.853 (0.839–0.866) | 0.861 (0.848–0.874) | 0.853 (0.839–0.866) | 0.841 (0.828–0.855) | 0.880 (0.867–0.893) |
| *Sensitivity, not headline:* macro-F1 (v1), all reports incl. Tier 1 pilot | 0.837 (0.823–0.850) | 0.862 (0.848–0.876) | 0.860 (0.846–0.873) | 0.866 (0.852–0.878) | 0.860 (0.846–0.873) | 0.848 (0.834–0.861) | 0.889 (0.876–0.900) |
| *Sensitivity, not headline:* macro-F1 (v1), `suggested` labels ignored | – | – | – | – | – | – | 0.875 (0.862–0.888) |

Paired differences (headline macro-F1, v1): llm_only − rule_baseline 0.025 (0.010–0.040); llm_verifier − llm_only -0.002 (-0.004–-0.001); tier2 − llm_verifier 0.006 (0.003–0.009); tier2 − rule_baseline 0.028 (0.013–0.043); tier2 − llm_only 0.003 (0.000–0.007); pipeline_clean − llm_verifier 0.000 (0.000–0.000); pipeline_varied − pipeline_clean -0.012 (-0.017–-0.007); v2 − llm_only 0.025 (0.016–0.035); v2 − tier2 0.022 (0.013–0.031); v2 − rule_baseline 0.050 (0.037–0.063)
