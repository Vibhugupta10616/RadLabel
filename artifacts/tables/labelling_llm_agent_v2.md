# Labelling: llm_agent_v2

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.889 (0.876–0.900)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.880 (0.867–0.893)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.934 (0.917–0.948) | 0.991 | 0.884 | 628 |
| Cardiomegaly | 0.943 (0.924–0.960) | 0.983 | 0.906 | 320 |
| Lung Opacity | 0.863 (0.837–0.889) | 0.844 | 0.882 | 400 |
| Lung Lesion | 0.731 (0.663–0.796) | 0.679 | 0.792 | 96 |
| Atelectasis | 0.880 (0.849–0.910) | 0.959 | 0.813 | 257 |
| Pleural Effusion | 0.962 (0.935–0.987) | 1.000 | 0.927 | 110 |
| Fracture | 0.850 (0.780–0.904) | 0.747 | 0.985 | 66 |
| Support Devices | 0.879 (0.854–0.903) | 0.796 | 0.981 | 318 |
| Other Abnormality | 0.945 (0.937–0.952) | 0.933 | 0.957 | 1807 |
| Edema (rare) | 0.923 (0.846–0.982) | 0.938 | 0.909 | 33 |
| Pleural Other (rare) | 0.674 (0.548–0.779) | 0.558 | 0.853 | 34 |
| Consolidation (rare) | 0.696 (0.545–0.808) | 0.533 | 1.000 | 24 |
| Pneumothorax (rare) | 0.947 (0.857–1.000) | 1.000 | 0.900 | 20 |

**Macro-F1, 9 headline labels:** 0.887 (0.874–0.899)  
**Pooled rare micro-F1:** 0.783 (0.723–0.832)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.934 (0.917–0.948) | 0.991 | 0.884 | 628 |
| Cardiomegaly | 0.946 (0.927–0.963) | 0.983 | 0.912 | 308 |
| Lung Opacity | 0.860 (0.827–0.889) | 0.784 | 0.952 | 248 |
| Lung Lesion | 0.726 (0.655–0.793) | 0.670 | 0.793 | 92 |
| Atelectasis | 0.880 (0.849–0.910) | 0.959 | 0.813 | 257 |
| Pleural Effusion | 0.967 (0.940–0.990) | 1.000 | 0.936 | 109 |
| Fracture | 0.850 (0.780–0.904) | 0.747 | 0.985 | 66 |
| Support Devices | 0.837 (0.803–0.870) | 0.732 | 0.978 | 223 |
| Other Abnormality | 0.945 (0.937–0.952) | 0.933 | 0.957 | 1807 |
| Edema (rare) | 0.923 (0.846–0.982) | 0.938 | 0.909 | 33 |
| Pleural Other (rare) | 0.683 (0.553–0.792) | 0.549 | 0.903 | 31 |
| Consolidation (rare) | 0.696 (0.545–0.808) | 0.533 | 1.000 | 24 |
| Pneumothorax (rare) | 0.970 (0.900–1.000) | 1.000 | 0.941 | 17 |

**Macro-F1, 9 headline labels:** 0.883 (0.869–0.895)  
**Pooled rare micro-F1:** 0.787 (0.726–0.839)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.792 (0.780–0.804) |
| redaction_adjacent | 0.889 (0.856–0.915) |
| hedged, uncertain = absent | 0.712 (0.678–0.831) |
| hedged, uncertain = present | 0.707 (0.678–0.820) |

## negation_only false-positive rate

| Label | All: FP / pairs (rate) | Abnormal only |
|---|---|---|
| Cardiomegaly | 0 / 4 (0.000) | 0 / 4 (0.000) |
| Lung Opacity | 10 / 668 (0.015) | 10 / 483 (0.021) |
| Lung Lesion | 2 / 132 (0.015) | 2 / 94 (0.021) |
| Atelectasis | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Pleural Effusion | 0 / 2100 (0.000) | 0 / 1585 (0.000) |
| Fracture | 2 / 83 (0.024) | 1 / 45 (0.022) |
| Support Devices | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Edema | 0 / 208 (0.000) | 0 / 168 (0.000) |
| Consolidation | 0 / 953 (0.000) | 0 / 733 (0.000) |
| Pneumothorax | 0 / 2008 (0.000) | 0 / 1531 (0.000) |
| pooled | 14 / 6164 (0.002) | 13 / 4649 (0.003) |
