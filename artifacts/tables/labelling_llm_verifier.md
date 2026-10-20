# Labelling: llm_verifier

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.854 (0.839–0.867)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.912 (0.888–0.936) | 0.996 | 0.841 | 320 |
| Lung Opacity | 0.830 (0.797–0.859) | 0.940 | 0.743 | 400 |
| Lung Lesion | 0.578 (0.497–0.653) | 0.619 | 0.542 | 96 |
| Atelectasis | 0.852 (0.816–0.884) | 0.970 | 0.759 | 257 |
| Pleural Effusion | 0.932 (0.893–0.966) | 1.000 | 0.873 | 110 |
| Fracture | 0.863 (0.797–0.916) | 0.787 | 0.955 | 66 |
| Support Devices | 0.853 (0.825–0.881) | 0.768 | 0.959 | 318 |
| Other Abnormality | 0.937 (0.928–0.945) | 0.944 | 0.929 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.690 (0.571–0.795) | 0.580 | 0.853 | 34 |
| Consolidation (rare) | 0.941 (0.857–1.000) | 0.889 | 1.000 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.854 (0.839–0.867)  
**Pooled rare micro-F1:** 0.838 (0.777–0.889)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.916 (0.893–0.939) | 0.996 | 0.847 | 308 |
| Lung Opacity | 0.883 (0.850–0.913) | 0.917 | 0.851 | 248 |
| Lung Lesion | 0.575 (0.486–0.654) | 0.610 | 0.543 | 92 |
| Atelectasis | 0.852 (0.816–0.884) | 0.970 | 0.759 | 257 |
| Pleural Effusion | 0.937 (0.899–0.968) | 1.000 | 0.881 | 109 |
| Fracture | 0.863 (0.797–0.916) | 0.787 | 0.955 | 66 |
| Support Devices | 0.811 (0.773–0.849) | 0.700 | 0.964 | 223 |
| Other Abnormality | 0.937 (0.928–0.945) | 0.944 | 0.929 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.700 (0.571–0.809) | 0.571 | 0.903 | 31 |
| Consolidation (rare) | 0.941 (0.857–1.000) | 0.889 | 1.000 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.856 (0.840–0.870)  
**Pooled rare micro-F1:** 0.844 (0.789–0.898)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.759 (0.745–0.772) |
| redaction_adjacent | 0.838 (0.800–0.868) |
| hedged, uncertain = absent | 0.642 (0.602–0.754) |
| hedged, uncertain = present | 0.685 (0.657–0.795) |

## negation_only false-positive rate

| Label | All: FP / pairs (rate) | Abnormal only |
|---|---|---|
| Cardiomegaly | 0 / 5 (0.000) | 0 / 5 (0.000) |
| Lung Opacity | 2 / 688 (0.003) | 2 / 500 (0.004) |
| Lung Lesion | 3 / 137 (0.022) | 3 / 98 (0.031) |
| Atelectasis | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Pleural Effusion | 0 / 2172 (0.000) | 0 / 1640 (0.000) |
| Fracture | 1 / 85 (0.012) | 0 / 47 (0.000) |
| Support Devices | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Edema | 0 / 211 (0.000) | 0 / 170 (0.000) |
| Consolidation | 0 / 982 (0.000) | 0 / 754 (0.000) |
| Pneumothorax | 0 / 2081 (0.000) | 0 / 1588 (0.000) |
| pooled | 6 / 6369 (0.001) | 5 / 4808 (0.001) |
