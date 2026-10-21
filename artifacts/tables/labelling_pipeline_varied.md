# Labelling: pipeline_varied

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.848 (0.834–0.861)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.841 (0.828–0.855)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.894 (0.875–0.910) | 0.922 | 0.868 | 628 |
| Cardiomegaly | 0.934 (0.914–0.953) | 0.986 | 0.887 | 320 |
| Lung Opacity | 0.826 (0.794–0.856) | 0.934 | 0.740 | 400 |
| Lung Lesion | 0.581 (0.497–0.659) | 0.627 | 0.542 | 96 |
| Atelectasis | 0.854 (0.819–0.886) | 0.970 | 0.763 | 257 |
| Pleural Effusion | 0.922 (0.882–0.957) | 1.000 | 0.855 | 110 |
| Fracture | 0.863 (0.797–0.918) | 0.787 | 0.955 | 66 |
| Support Devices | 0.833 (0.802–0.862) | 0.758 | 0.925 | 318 |
| Other Abnormality | 0.924 (0.915–0.932) | 0.940 | 0.908 | 1807 |
| Edema (rare) | 0.871 (0.762–0.949) | 0.931 | 0.818 | 33 |
| Pleural Other (rare) | 0.690 (0.571–0.795) | 0.580 | 0.853 | 34 |
| Consolidation (rare) | 0.920 (0.829–0.983) | 0.885 | 0.958 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.848 (0.833–0.861)  
**Pooled rare micro-F1:** 0.824 (0.764–0.875)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.894 (0.875–0.910) | 0.922 | 0.868 | 628 |
| Cardiomegaly | 0.937 (0.915–0.956) | 0.986 | 0.893 | 308 |
| Lung Opacity | 0.877 (0.844–0.907) | 0.909 | 0.847 | 248 |
| Lung Lesion | 0.578 (0.494–0.657) | 0.617 | 0.543 | 92 |
| Atelectasis | 0.854 (0.819–0.886) | 0.970 | 0.763 | 257 |
| Pleural Effusion | 0.926 (0.886–0.960) | 1.000 | 0.862 | 109 |
| Fracture | 0.863 (0.797–0.918) | 0.787 | 0.955 | 66 |
| Support Devices | 0.797 (0.755–0.832) | 0.691 | 0.942 | 223 |
| Other Abnormality | 0.924 (0.915–0.932) | 0.940 | 0.908 | 1807 |
| Edema (rare) | 0.871 (0.762–0.949) | 0.931 | 0.818 | 33 |
| Pleural Other (rare) | 0.700 (0.571–0.809) | 0.571 | 0.903 | 31 |
| Consolidation (rare) | 0.920 (0.829–0.983) | 0.885 | 0.958 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.850 (0.835–0.865)  
**Pooled rare micro-F1:** 0.830 (0.773–0.881)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.757 (0.744–0.770) |
| redaction_adjacent | 0.830 (0.790–0.859) |
| hedged, uncertain = absent | 0.649 (0.606–0.730) |
| hedged, uncertain = present | 0.699 (0.668–0.788) |

## negation_only false-positive rate

| Label | All: FP / pairs (rate) | Abnormal only |
|---|---|---|
| Cardiomegaly | 0 / 4 (0.000) | 0 / 4 (0.000) |
| Lung Opacity | 2 / 668 (0.003) | 2 / 483 (0.004) |
| Lung Lesion | 3 / 132 (0.023) | 3 / 94 (0.032) |
| Atelectasis | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Pleural Effusion | 0 / 2100 (0.000) | 0 / 1585 (0.000) |
| Fracture | 1 / 83 (0.012) | 0 / 45 (0.000) |
| Support Devices | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Edema | 0 / 208 (0.000) | 0 / 168 (0.000) |
| Consolidation | 0 / 953 (0.000) | 0 / 733 (0.000) |
| Pneumothorax | 0 / 2008 (0.000) | 0 / 1531 (0.000) |
| pooled | 6 / 6164 (0.001) | 5 / 4649 (0.001) |
