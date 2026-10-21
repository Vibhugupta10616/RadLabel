# Through the entry point (M6)

3,086 unique reports joined into text with headers (codes hidden) and run through `run_pipeline`; 926 of them (30.0%, seed 13) also with a varied join. Clean joins whose labels differ from the LLM + verifier column: 1. Tagger inputs that differ from M4's, so not served by the M4 cache: 1387 (no headers 309, drop section 151, clean 1, heldout headers 926; correctly parsed clean joins: 0), whose calls cost $0.81. All LLM calls so far (cost ledger): $3.37.

| Join | Reports | Sentences in the right section | Fully parsed | No sections found |
|---|---|---|---|---|
| clean | 3086 | 100.0% | 3083 (99.9%) | 0 |
| alt headers | 307 | 100.0% | 307 (100.0%) | 0 |
| no headers | 309 | 62.6% | 0 (0.0%) | 308 |
| drop section | 310 | 100.0% | 310 (100.0%) | 0 |
| heldout headers | 926 | 50.3% | 0 (0.0%) | 926 |

Dropped sections: findings 70, impression 81, indication 81, comparison 78.

Headline macro-F1 (v1) on the varied reports: the same reports with the clean vs the varied join:

| Variant | Scored reports | Clean join | Varied join |
|---|---|---|---|
| alt headers | 267 | 0.815 (0.751–0.862) | 0.815 (0.751–0.862) |
| no headers | 263 | 0.858 (0.810–0.899) | 0.864 (0.818–0.904) |
| drop section | 276 | 0.873 (0.825–0.907) | 0.756 (0.690–0.807) |
| heldout headers | 806 | 0.850 (0.822–0.873) | 0.850 (0.822–0.874) |

Paired: pipeline clean − llm verifier 0.000 (0.000–0.000); pipeline varied − pipeline clean -0.012 (-0.017–-0.007)

Section subsets (as parsed; headline macro-F1, v1, hedged + pilot excluded):

| Subset | Clean: reports (scored) | Clean macro-F1 | Varied: reports (scored) | Varied macro-F1 |
|---|---|---|---|---|
| empty findings | 426 (371) | 0.827 (0.769–0.864) | 452 (396) | 0.777 (0.716–0.819) |
| empty impression | 6 (5) | 0.633 (0.500–1.000) | 396 (337) | 0.820 (0.773–0.861) |
| sections not identified | 0 (0) | – | 308 (263) | 0.864 (0.818–0.904) |

**Normal-claim count.** 1302 unique reports have an Impression made only of "no acute"-type statements; the expert codes are normal-only for 467, ignored-only for 2, and **not normal for 833 (64.0%)**. Positive labels among those: Cardiomegaly 30, Lung Opacity 48, Lung Lesion 28, Atelectasis 40, Pleural Effusion 1, Fracture 31, Support Devices 111, Other Abnormality 742, Pleural Other 4, Pneumothorax 2. The tagger predicted No Finding for 3 of the 833 (LLM only; after the verifier 3) and for 418 of the 467 normal-only ones.

**Hedge-check fix** ("borderline"/"mild" are not a hedge where the label definition counts them as present), v1 results from cache, before → after:

| Metric | Before | After |
|---|---|---|
| Hedge conversions (present → uncertain) | 147 | 125 |
| LLM + verifier: headline macro-F1 (v1) | 0.857 (0.842–0.870) | 0.860 (0.845–0.873) |
| LLM + verifier: Cardiomegaly F1 | 0.914 (0.890–0.937) | 0.944 (0.924–0.961) |
| LLM + verifier − LLM only | -0.006 (-0.008–-0.003) | -0.002 (-0.004–-0.001) |
| LLM + verifier + Tier 2: headline macro-F1 (v1) | 0.862 (0.848–0.875) | 0.866 (0.851–0.878) |
| LLM + verifier + Tier 2 − LLM only | 0.000 (-0.004–0.004) | 0.003 (0.000–0.007) |
| v1 review rate | 30.9% | 30.5% |
