# Labelling: rule_baseline

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.833 (0.819–0.846)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.772 (0.743–0.798) | 0.803 | 0.742 | 628 |
| Cardiomegaly | 0.789 (0.754–0.823) | 0.758 | 0.822 | 320 |
| Lung Opacity | 0.794 (0.762–0.821) | 0.707 | 0.905 | 400 |
| Lung Lesion | 0.655 (0.576–0.726) | 0.581 | 0.750 | 96 |
| Atelectasis | 0.969 (0.952–0.983) | 0.969 | 0.969 | 257 |
| Pleural Effusion | 0.950 (0.918–0.977) | 0.946 | 0.955 | 110 |
| Fracture | 0.906 (0.853–0.953) | 0.863 | 0.955 | 66 |
| Support Devices | 0.795 (0.756–0.830) | 0.888 | 0.720 | 318 |
| Other Abnormality | 0.879 (0.868–0.891) | 0.885 | 0.874 | 1807 |
| Edema (rare) | 0.688 (0.568–0.792) | 0.533 | 0.970 | 33 |
| Pleural Other (rare) | 0.612 (0.480–0.729) | 0.510 | 0.765 | 34 |
| Consolidation (rare) | 0.960 (0.889–1.000) | 0.923 | 1.000 | 24 |
| Pneumothorax (rare) | 0.872 (0.733–0.973) | 0.895 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.834 (0.820–0.847)  
**Pooled rare micro-F1:** 0.742 (0.677–0.805)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.772 (0.743–0.798) | 0.803 | 0.742 | 628 |
| Cardiomegaly | 0.788 (0.753–0.823) | 0.752 | 0.828 | 308 |
| Lung Opacity | 0.737 (0.694–0.774) | 0.607 | 0.935 | 248 |
| Lung Lesion | 0.654 (0.576–0.726) | 0.574 | 0.761 | 92 |
| Atelectasis | 0.969 (0.952–0.983) | 0.969 | 0.969 | 257 |
| Pleural Effusion | 0.955 (0.925–0.980) | 0.946 | 0.963 | 109 |
| Fracture | 0.906 (0.853–0.953) | 0.863 | 0.955 | 66 |
| Support Devices | 0.768 (0.718–0.813) | 0.844 | 0.704 | 223 |
| Other Abnormality | 0.879 (0.868–0.891) | 0.885 | 0.874 | 1807 |
| Edema (rare) | 0.688 (0.568–0.792) | 0.533 | 0.970 | 33 |
| Pleural Other (rare) | 0.634 (0.506–0.755) | 0.510 | 0.839 | 31 |
| Consolidation (rare) | 0.960 (0.889–1.000) | 0.923 | 1.000 | 24 |
| Pneumothorax (rare) | 0.882 (0.727–0.979) | 0.882 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.825 (0.810–0.839)  
**Pooled rare micro-F1:** 0.749 (0.684–0.808)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.759 (0.745–0.771) |
| redaction_adjacent | 0.840 (0.797–0.874) |
| hedged, uncertain = absent | 0.664 (0.624–0.769) |
| hedged, uncertain = present | 0.687 (0.653–0.787) |

## negation_only false-positive rate

| Label | All: FP / pairs (rate) | Abnormal only |
|---|---|---|
| Cardiomegaly | 0 / 5 (0.000) | 0 / 5 (0.000) |
| Lung Opacity | 34 / 688 (0.049) | 34 / 500 (0.068) |
| Lung Lesion | 2 / 137 (0.015) | 2 / 98 (0.020) |
| Atelectasis | 1 / 4 (0.250) | 1 / 3 (0.333) |
| Pleural Effusion | 0 / 2172 (0.000) | 0 / 1640 (0.000) |
| Fracture | 0 / 85 (0.000) | 0 / 47 (0.000) |
| Support Devices | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Edema | 5 / 211 (0.024) | 5 / 170 (0.029) |
| Consolidation | 1 / 982 (0.001) | 1 / 754 (0.001) |
| Pneumothorax | 0 / 2081 (0.000) | 0 / 1588 (0.000) |
| pooled | 43 / 6369 (0.007) | 43 / 4808 (0.009) |
