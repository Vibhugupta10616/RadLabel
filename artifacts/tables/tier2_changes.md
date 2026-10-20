# Tier 2 repair agent (M5)

211 reports with a verifier FAIL; attempted 211, fix accepted (passes re-verification) 78 (37.0%); mean tool calls 1.97; stop reasons {'submitted': 211}; cost of the Tier 2 calls $0.260 (new spend in this run $0.000; reruns are served from the cache).

Decision rule: keep iff Tier 2 − LLM + verifier is not significantly negative (CI hi >= 0) -> keep Tier 2: **True**

## Label changes (agent labels vs LLM + verifier; present = positive vs v1 expert codes)

### all_211

| Label | Status changed | Wrong → right | Right → wrong | No score effect |
|---|---|---|---|---|
| No Finding | 2 | 0 | 2 | 0 |
| Cardiomegaly | 2 | 1 | 0 | 1 |
| Lung Opacity | 7 | 5 | 0 | 2 |
| Lung Lesion | 13 | 6 | 0 | 7 |
| Atelectasis | 4 | 3 | 0 | 1 |
| Fracture | 6 | 2 | 0 | 4 |
| Support Devices | 12 | 11 | 1 | 0 |
| Edema | 2 | 0 | 0 | 2 |
| Pleural Other | 1 | 0 | 1 | 0 |
| Consolidation | 26 | 1 | 1 | 24 |
| **total** | 75 | 29 | 5 | 41 |

### scored_only

| Label | Status changed | Wrong → right | Right → wrong | No score effect |
|---|---|---|---|---|
| No Finding | 2 | 0 | 2 | 0 |
| Cardiomegaly | 1 | 0 | 0 | 1 |
| Lung Opacity | 6 | 5 | 0 | 1 |
| Lung Lesion | 12 | 6 | 0 | 6 |
| Atelectasis | 3 | 2 | 0 | 1 |
| Fracture | 6 | 2 | 0 | 4 |
| Support Devices | 11 | 10 | 1 | 0 |
| Edema | 2 | 0 | 0 | 2 |
| Pleural Other | 1 | 0 | 1 | 0 |
| Consolidation | 11 | 0 | 1 | 10 |
| **total** | 55 | 25 | 5 | 25 |

## Routing

- tier distribution: {'tier1_accepted': 2090, 'review': 954, 'tier2_repaired': 42}
- review rate: hedged 58.1% (n = 279), clear 28.2% (n = 2807)
- escalation precision: Tier 2 64.9%, review 51.7% (base rate 25.5%)
