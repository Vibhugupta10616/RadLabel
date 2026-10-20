# Labelling: llm_verifier

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.857 (0.842–0.870)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.853 (0.839–0.866)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.914 (0.890–0.937) | 0.996 | 0.844 | 320 |
| Lung Opacity | 0.830 (0.799–0.859) | 0.937 | 0.745 | 400 |
| Lung Lesion | 0.593 (0.510–0.667) | 0.628 | 0.562 | 96 |
| Atelectasis | 0.852 (0.816–0.884) | 0.970 | 0.759 | 257 |
| Pleural Effusion | 0.932 (0.893–0.966) | 1.000 | 0.873 | 110 |
| Fracture | 0.872 (0.809–0.923) | 0.783 | 0.985 | 66 |
| Support Devices | 0.851 (0.822–0.879) | 0.764 | 0.959 | 318 |
| Other Abnormality | 0.937 (0.929–0.945) | 0.944 | 0.931 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.690 (0.571–0.795) | 0.580 | 0.853 | 34 |
| Consolidation (rare) | 0.941 (0.857–1.000) | 0.889 | 1.000 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.857 (0.842–0.870)  
**Pooled rare micro-F1:** 0.838 (0.777–0.889)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.918 (0.894–0.940) | 0.996 | 0.851 | 308 |
| Lung Opacity | 0.881 (0.849–0.911) | 0.913 | 0.851 | 248 |
| Lung Lesion | 0.591 (0.506–0.667) | 0.619 | 0.565 | 92 |
| Atelectasis | 0.852 (0.816–0.884) | 0.970 | 0.759 | 257 |
| Pleural Effusion | 0.937 (0.899–0.968) | 1.000 | 0.881 | 109 |
| Fracture | 0.872 (0.809–0.923) | 0.783 | 0.985 | 66 |
| Support Devices | 0.808 (0.770–0.846) | 0.696 | 0.964 | 223 |
| Other Abnormality | 0.937 (0.929–0.945) | 0.944 | 0.931 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.700 (0.571–0.809) | 0.571 | 0.903 | 31 |
| Consolidation (rare) | 0.941 (0.857–1.000) | 0.889 | 1.000 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.858 (0.843–0.872)  
**Pooled rare micro-F1:** 0.844 (0.789–0.898)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.762 (0.748–0.774) |
| redaction_adjacent | 0.846 (0.810–0.875) |
| hedged, uncertain = absent | 0.651 (0.612–0.764) |
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
