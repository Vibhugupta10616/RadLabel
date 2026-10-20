# Labelling: llm_only

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.861 (0.846–0.874)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.944 (0.924–0.961) | 0.993 | 0.900 | 320 |
| Lung Opacity | 0.836 (0.804–0.864) | 0.941 | 0.752 | 400 |
| Lung Lesion | 0.582 (0.503–0.659) | 0.616 | 0.552 | 96 |
| Atelectasis | 0.857 (0.823–0.888) | 0.966 | 0.770 | 257 |
| Pleural Effusion | 0.932 (0.893–0.966) | 1.000 | 0.873 | 110 |
| Fracture | 0.863 (0.797–0.916) | 0.787 | 0.955 | 66 |
| Support Devices | 0.858 (0.831–0.885) | 0.769 | 0.972 | 318 |
| Other Abnormality | 0.943 (0.935–0.951) | 0.941 | 0.945 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.682 (0.560–0.787) | 0.569 | 0.853 | 34 |
| Consolidation (rare) | 0.923 (0.828–0.983) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.860 (0.845–0.873)  
**Pooled rare micro-F1:** 0.831 (0.771–0.882)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.928 (0.912–0.942) | 0.991 | 0.873 | 628 |
| Cardiomegaly | 0.947 (0.928–0.965) | 0.993 | 0.906 | 308 |
| Lung Opacity | 0.885 (0.853–0.915) | 0.918 | 0.855 | 248 |
| Lung Lesion | 0.580 (0.495–0.658) | 0.607 | 0.554 | 92 |
| Atelectasis | 0.857 (0.823–0.888) | 0.966 | 0.770 | 257 |
| Pleural Effusion | 0.937 (0.899–0.968) | 1.000 | 0.881 | 109 |
| Fracture | 0.863 (0.797–0.916) | 0.787 | 0.955 | 66 |
| Support Devices | 0.816 (0.781–0.852) | 0.701 | 0.978 | 223 |
| Other Abnormality | 0.943 (0.935–0.951) | 0.941 | 0.945 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.691 (0.567–0.800) | 0.560 | 0.903 | 31 |
| Consolidation (rare) | 0.923 (0.828–0.983) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.862 (0.846–0.875)  
**Pooled rare micro-F1:** 0.837 (0.780–0.890)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.766 (0.752–0.779) |
| redaction_adjacent | 0.842 (0.803–0.872) |
| hedged, uncertain = absent | 0.700 (0.666–0.818) |
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
