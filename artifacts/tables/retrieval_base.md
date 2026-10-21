**seen label** (40 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.466 (0.354–0.575) | 0.483 (0.369–0.591) | 0.402 (0.287–0.512) |
| base bge-small, report-level | 0.643 (0.549–0.741) | 0.672 (0.581–0.764) | 0.310 (0.205–0.415) |
| base bge-small, contextual sentences | 0.647 (0.562–0.734) | 0.637 (0.549–0.725) | 0.310 (0.205–0.410) |
| base bge-small + negated-sentence payload filter (no training) | 0.868 (0.831–0.908) | 0.871 (0.830–0.913) | 0.070 (0.032–0.118) |
| base contextual sentences + BM25 (RRF) | 0.657 (0.555–0.752) | 0.676 (0.572–0.770) | 0.315 (0.207–0.420) |

**heldout label** (15 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.253 (0.160–0.360) | 0.257 (0.158–0.368) | 0.140 (0.060–0.227) |
| base bge-small, report-level | 0.260 (0.187–0.327) | 0.265 (0.193–0.340) | 0.120 (0.047–0.220) |
| base bge-small, contextual sentences | 0.633 (0.540–0.733) | 0.638 (0.527–0.751) | 0.033 (0.013–0.060) |
| base bge-small + negated-sentence payload filter (no training) | 0.633 (0.533–0.733) | 0.643 (0.532–0.759) | 0.013 (0.000–0.033) |
| base contextual sentences + BM25 (RRF) | 0.433 (0.333–0.540) | 0.465 (0.350–0.578) | 0.053 (0.007–0.107) |

**heldout alias** (90 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.437 (0.367–0.502) | 0.489 (0.418–0.554) | 0.141 (0.089–0.196) |
| base bge-small, report-level | 0.619 (0.552–0.677) | 0.644 (0.581–0.700) | 0.089 (0.049–0.132) |
| base bge-small, contextual sentences | 0.625 (0.555–0.691) | 0.647 (0.581–0.710) | 0.108 (0.068–0.151) |
| base bge-small + negated-sentence payload filter (no training) | 0.651 (0.580–0.719) | 0.671 (0.602–0.737) | 0.073 (0.040–0.111) |
| base contextual sentences + BM25 (RRF) | 0.630 (0.561–0.691) | 0.663 (0.595–0.721) | 0.087 (0.050–0.124) |

**attribute** (100 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.721 (0.678–0.763) | 0.718 (0.677–0.758) | 0.123 (0.083–0.166) |
| base bge-small, report-level | 0.599 (0.552–0.648) | 0.613 (0.569–0.662) | 0.131 (0.089–0.177) |
| base bge-small, contextual sentences | 0.786 (0.746–0.823) | 0.777 (0.739–0.813) | 0.075 (0.051–0.103) |
| base bge-small + negated-sentence payload filter (no training) | 0.802 (0.763–0.836) | 0.792 (0.754–0.826) | 0.023 (0.011–0.037) |
| base contextual sentences + BM25 (RRF) | 0.822 (0.787–0.855) | 0.803 (0.769–0.836) | 0.060 (0.034–0.091) |

**compositional** (49 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.296 (0.227–0.363) | 0.294 (0.223–0.365) | 0.355 (0.245–0.467) |
| base bge-small, report-level | 0.304 (0.230–0.386) | 0.293 (0.219–0.376) | 0.316 (0.218–0.416) |
| base bge-small, contextual sentences | 0.377 (0.294–0.465) | 0.394 (0.310–0.484) | 0.308 (0.204–0.414) |
| base bge-small + negated-sentence payload filter (no training) | 0.534 (0.438–0.625) | 0.523 (0.426–0.616) | 0.163 (0.106–0.222) |
| base contextual sentences + BM25 (RRF) | 0.343 (0.264–0.426) | 0.355 (0.275–0.442) | 0.341 (0.231–0.449) |

**report to report** (200 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.700 (0.659–0.738) | 0.463 (0.432–0.493) | – |
| base bge-small, report-level | 0.590 (0.546–0.632) | 0.392 (0.358–0.427) | – |
| base bge-small, contextual sentences | 0.442 (0.394–0.494) | 0.262 (0.230–0.297) | – |
| base bge-small + negated-sentence payload filter (no training) | 0.432 (0.383–0.482) | 0.257 (0.224–0.294) | – |
| base contextual sentences + BM25 (RRF) | 0.546 (0.499–0.595) | 0.342 (0.309–0.376) | – |

**all** (494 query–fold pairs)

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | 0.584 (0.554–0.614) | 0.498 (0.469–0.525) | 0.217 (0.180–0.257) |
| base bge-small, report-level | 0.563 (0.534–0.593) | 0.492 (0.465–0.518) | 0.178 (0.146–0.213) |
| base bge-small, contextual sentences | 0.561 (0.531–0.592) | 0.491 (0.462–0.519) | 0.164 (0.134–0.198) |
| base bge-small + negated-sentence payload filter (no training) | 0.598 (0.567–0.630) | 0.528 (0.497–0.559) | 0.074 (0.056–0.092) |
| base contextual sentences + BM25 (RRF) | 0.603 (0.575–0.632) | 0.526 (0.498–0.555) | 0.161 (0.129–0.195) |
