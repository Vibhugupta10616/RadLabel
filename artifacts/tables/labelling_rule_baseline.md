# Labelling: rule_baseline

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.837 (0.823–0.850)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.839 (0.825–0.852)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.775 (0.746–0.801) | 0.810 | 0.742 | 628 |
| Cardiomegaly | 0.789 (0.754–0.823) | 0.758 | 0.822 | 320 |
| Lung Opacity | 0.794 (0.762–0.821) | 0.707 | 0.905 | 400 |
| Lung Lesion | 0.661 (0.584–0.733) | 0.584 | 0.760 | 96 |
| Atelectasis | 0.973 (0.957–0.986) | 0.969 | 0.977 | 257 |
| Pleural Effusion | 0.955 (0.925–0.980) | 0.946 | 0.964 | 110 |
| Fracture | 0.914 (0.862–0.959) | 0.865 | 0.970 | 66 |
| Support Devices | 0.797 (0.758–0.832) | 0.888 | 0.723 | 318 |
| Other Abnormality | 0.880 (0.869–0.891) | 0.884 | 0.877 | 1807 |
| Edema (rare) | 0.688 (0.568–0.792) | 0.533 | 0.970 | 33 |
| Pleural Other (rare) | 0.612 (0.480–0.729) | 0.510 | 0.765 | 34 |
| Consolidation (rare) | 0.960 (0.889–1.000) | 0.923 | 1.000 | 24 |
| Pneumothorax (rare) | 0.872 (0.733–0.973) | 0.895 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.838 (0.823–0.850)  
**Pooled rare micro-F1:** 0.742 (0.677–0.805)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.775 (0.746–0.801) | 0.810 | 0.742 | 628 |
| Cardiomegaly | 0.788 (0.753–0.823) | 0.752 | 0.828 | 308 |
| Lung Opacity | 0.737 (0.694–0.774) | 0.607 | 0.935 | 248 |
| Lung Lesion | 0.660 (0.580–0.735) | 0.577 | 0.772 | 92 |
| Atelectasis | 0.973 (0.957–0.986) | 0.969 | 0.977 | 257 |
| Pleural Effusion | 0.959 (0.929–0.983) | 0.946 | 0.972 | 109 |
| Fracture | 0.914 (0.862–0.959) | 0.865 | 0.970 | 66 |
| Support Devices | 0.771 (0.720–0.815) | 0.845 | 0.709 | 223 |
| Other Abnormality | 0.880 (0.869–0.891) | 0.884 | 0.877 | 1807 |
| Edema (rare) | 0.688 (0.568–0.792) | 0.533 | 0.970 | 33 |
| Pleural Other (rare) | 0.634 (0.506–0.755) | 0.510 | 0.839 | 31 |
| Consolidation (rare) | 0.960 (0.889–1.000) | 0.923 | 1.000 | 24 |
| Pneumothorax (rare) | 0.882 (0.727–0.979) | 0.882 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.829 (0.814–0.843)  
**Pooled rare micro-F1:** 0.749 (0.684–0.808)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.761 (0.748–0.773) |
| redaction_adjacent | 0.842 (0.799–0.876) |
| hedged, uncertain = absent | 0.664 (0.628–0.781) |
| hedged, uncertain = present | 0.687 (0.656–0.799) |

## negation_only false-positive rate

| Label | All: FP / pairs (rate) | Abnormal only |
|---|---|---|
| Cardiomegaly | 0 / 4 (0.000) | 0 / 4 (0.000) |
| Lung Opacity | 32 / 668 (0.048) | 32 / 483 (0.066) |
| Lung Lesion | 2 / 132 (0.015) | 2 / 94 (0.021) |
| Atelectasis | 1 / 4 (0.250) | 1 / 3 (0.333) |
| Pleural Effusion | 0 / 2100 (0.000) | 0 / 1585 (0.000) |
| Fracture | 0 / 83 (0.000) | 0 / 45 (0.000) |
| Support Devices | 0 / 4 (0.000) | 0 / 3 (0.000) |
| Edema | 5 / 208 (0.024) | 5 / 168 (0.030) |
| Consolidation | 1 / 953 (0.001) | 1 / 733 (0.001) |
| Pneumothorax | 0 / 2008 (0.000) | 0 / 1531 (0.000) |
| pooled | 41 / 6164 (0.007) | 41 / 4649 (0.009) |
