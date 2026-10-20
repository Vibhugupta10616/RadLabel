# Labelling: rule_baseline

Out-of-fold, one report per exact text (n = 3086, 279 hedged excluded); 95% bootstrap CIs over clusters.

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.773 (0.745–0.799) | 0.799 | 0.749 | 649 |
| Cardiomegaly | 0.790 (0.756–0.822) | 0.760 | 0.822 | 331 |
| Lung Opacity | 0.793 (0.763–0.820) | 0.705 | 0.906 | 415 |
| Lung Lesion | 0.658 (0.581–0.728) | 0.583 | 0.755 | 98 |
| Atelectasis | 0.966 (0.948–0.980) | 0.970 | 0.963 | 267 |
| Pleural Effusion | 0.948 (0.917–0.974) | 0.948 | 0.948 | 115 |
| Fracture | 0.904 (0.847–0.949) | 0.857 | 0.957 | 69 |
| Support Devices | 0.786 (0.748–0.820) | 0.883 | 0.708 | 329 |
| Other Abnormality | 0.880 (0.868–0.890) | 0.887 | 0.872 | 1873 |
| Edema (rare) | 0.688 (0.579–0.790) | 0.532 | 0.971 | 34 |
| Pleural Other (rare) | 0.622 (0.500–0.738) | 0.519 | 0.778 | 36 |
| Consolidation (rare) | 0.962 (0.895–1.000) | 0.926 | 1.000 | 25 |
| Pneumothorax (rare) | 0.878 (0.750–0.974) | 0.900 | 0.857 | 21 |

**Macro-F1, 9 headline labels:** 0.833 (0.818–0.846)  
**Pooled rare micro-F1:** 0.746 (0.684–0.804)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.773 (0.745–0.799) | 0.799 | 0.749 | 649 |
| Cardiomegaly | 0.789 (0.756–0.822) | 0.754 | 0.828 | 319 |
| Lung Opacity | 0.736 (0.694–0.774) | 0.607 | 0.934 | 259 |
| Lung Lesion | 0.658 (0.581–0.729) | 0.576 | 0.766 | 94 |
| Atelectasis | 0.966 (0.948–0.980) | 0.970 | 0.963 | 267 |
| Pleural Effusion | 0.952 (0.921–0.977) | 0.948 | 0.956 | 114 |
| Fracture | 0.904 (0.847–0.949) | 0.857 | 0.957 | 69 |
| Support Devices | 0.758 (0.710–0.801) | 0.839 | 0.691 | 233 |
| Other Abnormality | 0.880 (0.868–0.890) | 0.887 | 0.872 | 1873 |
| Edema (rare) | 0.688 (0.579–0.790) | 0.532 | 0.971 | 34 |
| Pleural Other (rare) | 0.644 (0.519–0.760) | 0.519 | 0.848 | 33 |
| Consolidation (rare) | 0.962 (0.895–1.000) | 0.926 | 1.000 | 25 |
| Pneumothorax (rare) | 0.889 (0.750–0.982) | 0.889 | 0.889 | 18 |

**Macro-F1, 9 headline labels:** 0.824 (0.809–0.838)  
**Pooled rare micro-F1:** 0.753 (0.690–0.811)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.757 (0.743–0.769) |
| redaction_adjacent | 0.841 (0.799–0.874) |
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
