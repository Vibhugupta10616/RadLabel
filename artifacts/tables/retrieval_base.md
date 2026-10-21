**seen label** (40 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.463 (0.347–0.573) | 0.481 (0.367–0.592) | 0.407 (0.290–0.515) |
| base bge-small, report-level | 0.643 (0.549–0.741) | 0.672 (0.581–0.764) | 0.310 (0.205–0.415) |
| base bge-small, sentences without prefix (pure embedding) | 0.729 (0.650–0.805) | 0.731 (0.655–0.804) | 0.208 (0.120–0.300) |
| base bge-small, contextual sentences | 0.647 (0.562–0.734) | 0.637 (0.549–0.725) | 0.310 (0.205–0.410) |
| base bge-small + negated-sentence payload filter (no training) | 0.868 (0.831–0.908) | 0.871 (0.830–0.913) | 0.070 (0.032–0.118) |
| base contextual sentences + BM25 (RRF) | 0.659 (0.559–0.756) | 0.683 (0.581–0.779) | 0.310 (0.202–0.415) |

**heldout label** (15 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.253 (0.160–0.360) | 0.253 (0.154–0.363) | 0.140 (0.060–0.227) |
| base bge-small, report-level | 0.260 (0.187–0.327) | 0.265 (0.193–0.340) | 0.120 (0.047–0.220) |
| base bge-small, sentences without prefix (pure embedding) | 0.387 (0.287–0.500) | 0.406 (0.306–0.525) | 0.053 (0.007–0.113) |
| base bge-small, contextual sentences | 0.633 (0.540–0.733) | 0.638 (0.527–0.751) | 0.033 (0.013–0.060) |
| base bge-small + negated-sentence payload filter (no training) | 0.633 (0.533–0.733) | 0.643 (0.532–0.759) | 0.013 (0.000–0.033) |
| base contextual sentences + BM25 (RRF) | 0.433 (0.333–0.540) | 0.463 (0.349–0.573) | 0.053 (0.007–0.107) |

**heldout alias** (90 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.450 (0.380–0.514) | 0.494 (0.422–0.558) | 0.148 (0.096–0.204) |
| base bge-small, report-level | 0.619 (0.552–0.677) | 0.644 (0.581–0.700) | 0.089 (0.049–0.132) |
| base bge-small, sentences without prefix (pure embedding) | 0.643 (0.577–0.703) | 0.670 (0.607–0.728) | 0.104 (0.061–0.151) |
| base bge-small, contextual sentences | 0.625 (0.555–0.691) | 0.647 (0.581–0.710) | 0.108 (0.068–0.151) |
| base bge-small + negated-sentence payload filter (no training) | 0.651 (0.580–0.719) | 0.671 (0.602–0.737) | 0.073 (0.040–0.111) |
| base contextual sentences + BM25 (RRF) | 0.641 (0.569–0.700) | 0.669 (0.601–0.727) | 0.108 (0.067–0.151) |

**attribute** (100 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.739 (0.700–0.779) | 0.734 (0.695–0.772) | 0.135 (0.095–0.182) |
| base bge-small, report-level | 0.599 (0.552–0.648) | 0.613 (0.569–0.662) | 0.131 (0.089–0.177) |
| base bge-small, sentences without prefix (pure embedding) | 0.787 (0.746–0.826) | 0.803 (0.768–0.840) | 0.038 (0.022–0.058) |
| base bge-small, contextual sentences | 0.786 (0.746–0.823) | 0.777 (0.739–0.813) | 0.075 (0.051–0.103) |
| base bge-small + negated-sentence payload filter (no training) | 0.802 (0.763–0.836) | 0.792 (0.754–0.826) | 0.023 (0.011–0.037) |
| base contextual sentences + BM25 (RRF) | 0.825 (0.789–0.859) | 0.816 (0.783–0.847) | 0.062 (0.035–0.094) |

**compositional** (49 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.285 (0.215–0.354) | 0.288 (0.216–0.359) | 0.355 (0.249–0.463) |
| base bge-small, report-level | 0.304 (0.230–0.386) | 0.293 (0.219–0.376) | 0.316 (0.218–0.416) |
| base bge-small, sentences without prefix (pure embedding) | 0.343 (0.258–0.428) | 0.370 (0.283–0.458) | 0.310 (0.212–0.412) |
| base bge-small, contextual sentences | 0.379 (0.295–0.469) | 0.395 (0.310–0.485) | 0.308 (0.204–0.414) |
| base bge-small + negated-sentence payload filter (no training) | 0.534 (0.438–0.625) | 0.523 (0.426–0.616) | 0.163 (0.106–0.222) |
| base contextual sentences + BM25 (RRF) | 0.341 (0.265–0.421) | 0.352 (0.270–0.436) | 0.343 (0.235–0.447) |

**report to report** (200 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.720 (0.681–0.760) | 0.470 (0.439–0.502) | – |
| base bge-small, report-level | 0.590 (0.546–0.632) | 0.392 (0.358–0.427) | – |
| base bge-small, sentences without prefix (pure embedding) | 0.674 (0.636–0.712) | 0.421 (0.392–0.450) | – |
| base bge-small, contextual sentences | 0.442 (0.394–0.494) | 0.262 (0.230–0.297) | – |
| base bge-small + negated-sentence payload filter (no training) | 0.432 (0.383–0.482) | 0.257 (0.224–0.294) | – |
| base contextual sentences + BM25 (RRF) | 0.579 (0.531–0.627) | 0.360 (0.329–0.394) | – |

**all** (494 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.597 (0.565–0.627) | 0.504 (0.476–0.531) | 0.224 (0.185–0.263) |
| base bge-small, report-level | 0.563 (0.534–0.593) | 0.492 (0.465–0.518) | 0.178 (0.146–0.213) |
| base bge-small, sentences without prefix (pure embedding) | 0.654 (0.627–0.681) | 0.564 (0.537–0.589) | 0.140 (0.108–0.174) |
| base bge-small, contextual sentences | 0.561 (0.531–0.592) | 0.491 (0.462–0.519) | 0.164 (0.134–0.198) |
| base bge-small + negated-sentence payload filter (no training) | 0.598 (0.567–0.630) | 0.528 (0.497–0.559) | 0.074 (0.056–0.092) |
| base contextual sentences + BM25 (RRF) | 0.618 (0.589–0.649) | 0.537 (0.511–0.567) | 0.169 (0.135–0.203) |
