# Labelling: llm_only

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.862 (0.848–0.876)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.853 (0.839–0.866)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.946 (0.926–0.962) | 0.993 | 0.903 | 320 |
| Lung Opacity | 0.835 (0.804–0.864) | 0.938 | 0.752 | 400 |
| Lung Lesion | 0.590 (0.508–0.667) | 0.621 | 0.562 | 96 |
| Atelectasis | 0.857 (0.823–0.888) | 0.966 | 0.770 | 257 |
| Pleural Effusion | 0.932 (0.893–0.966) | 1.000 | 0.873 | 110 |
| Fracture | 0.872 (0.809–0.923) | 0.783 | 0.985 | 66 |
| Support Devices | 0.856 (0.829–0.883) | 0.765 | 0.972 | 318 |
| Other Abnormality | 0.944 (0.936–0.951) | 0.941 | 0.946 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.682 (0.560–0.787) | 0.569 | 0.853 | 34 |
| Consolidation (rare) | 0.923 (0.828–0.983) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.862 (0.848–0.875)  
**Pooled rare micro-F1:** 0.831 (0.771–0.882)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.949 (0.930–0.965) | 0.993 | 0.909 | 308 |
| Lung Opacity | 0.883 (0.852–0.913) | 0.914 | 0.855 | 248 |
| Lung Lesion | 0.588 (0.503–0.667) | 0.612 | 0.565 | 92 |
| Atelectasis | 0.857 (0.823–0.888) | 0.966 | 0.770 | 257 |
| Pleural Effusion | 0.937 (0.899–0.968) | 1.000 | 0.881 | 109 |
| Fracture | 0.872 (0.809–0.923) | 0.783 | 0.985 | 66 |
| Support Devices | 0.813 (0.777–0.849) | 0.696 | 0.978 | 223 |
| Other Abnormality | 0.944 (0.936–0.951) | 0.941 | 0.946 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.691 (0.567–0.800) | 0.560 | 0.903 | 31 |
| Consolidation (rare) | 0.923 (0.828–0.983) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.863 (0.848–0.877)  
**Pooled rare micro-F1:** 0.837 (0.780–0.890)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.767 (0.754–0.781) |
| redaction_adjacent | 0.849 (0.813–0.878) |
| hedged, uncertain = absent | 0.708 (0.675–0.827) |
| hedged, uncertain = present | 0.698 (0.668–0.810) |

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
