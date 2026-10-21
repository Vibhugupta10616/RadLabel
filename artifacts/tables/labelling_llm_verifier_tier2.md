# Labelling: llm_verifier_tier2

Out-of-fold, one report per exact text (n = 3086; 279 hedged and 96 Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.

Sensitivity, all reports incl. pilot: v1 headline macro-F1 0.866 (0.852–0.878)  
Sensitivity analysis (not the headline metric), `uncertain` counts as positive for all labels: v1 headline macro-F1 0.861 (0.848–0.874)

## Mapping v1

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.926 (0.910–0.941) | 0.987 | 0.873 | 628 |
| Cardiomegaly | 0.944 (0.924–0.961) | 0.993 | 0.900 | 320 |
| Lung Opacity | 0.836 (0.805–0.866) | 0.949 | 0.748 | 400 |
| Lung Lesion | 0.614 (0.533–0.689) | 0.675 | 0.562 | 96 |
| Atelectasis | 0.855 (0.820–0.888) | 0.980 | 0.759 | 257 |
| Pleural Effusion | 0.932 (0.893–0.966) | 1.000 | 0.873 | 110 |
| Fracture | 0.884 (0.821–0.933) | 0.802 | 0.985 | 66 |
| Support Devices | 0.861 (0.835–0.889) | 0.784 | 0.956 | 318 |
| Other Abnormality | 0.937 (0.929–0.945) | 0.944 | 0.931 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.675 (0.549–0.781) | 0.571 | 0.824 | 34 |
| Consolidation (rare) | 0.923 (0.829–0.984) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.919 (0.800–1.000) | 1.000 | 0.850 | 20 |

**Macro-F1, 9 headline labels:** 0.866 (0.851–0.878)  
**Pooled rare micro-F1:** 0.829 (0.769–0.882)

## Mapping strict

| Label | F1 (95% CI) | Precision | Recall | n |
|---|---|---|---|---|
| No Finding | 0.926 (0.910–0.941) | 0.987 | 0.873 | 628 |
| Cardiomegaly | 0.947 (0.928–0.965) | 0.993 | 0.906 | 308 |
| Lung Opacity | 0.891 (0.858–0.919) | 0.930 | 0.855 | 248 |
| Lung Lesion | 0.612 (0.529–0.688) | 0.667 | 0.565 | 92 |
| Atelectasis | 0.855 (0.820–0.888) | 0.980 | 0.759 | 257 |
| Pleural Effusion | 0.937 (0.899–0.968) | 1.000 | 0.881 | 109 |
| Fracture | 0.884 (0.821–0.933) | 0.802 | 0.985 | 66 |
| Support Devices | 0.824 (0.788–0.859) | 0.719 | 0.964 | 223 |
| Other Abnormality | 0.937 (0.929–0.945) | 0.944 | 0.931 | 1807 |
| Edema (rare) | 0.903 (0.814–0.967) | 0.966 | 0.848 | 33 |
| Pleural Other (rare) | 0.700 (0.571–0.809) | 0.571 | 0.903 | 31 |
| Consolidation (rare) | 0.923 (0.829–0.984) | 0.857 | 1.000 | 24 |
| Pneumothorax (rare) | 0.938 (0.824–1.000) | 1.000 | 0.882 | 17 |

**Macro-F1, 9 headline labels:** 0.868 (0.853–0.881)  
**Pooled rare micro-F1:** 0.841 (0.783–0.893)

## Subsets (v1, headline macro-F1)

| Subset | Macro-F1 (95% CI) |
|---|---|
| abnormal | 0.771 (0.758–0.783) |
| redaction_adjacent | 0.852 (0.815–0.881) |
| hedged, uncertain = absent | 0.653 (0.614–0.766) |
| hedged, uncertain = present | 0.700 (0.671–0.813) |

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
