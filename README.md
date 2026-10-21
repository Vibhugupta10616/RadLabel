# RadLabel

**Radiology report intelligence: a verified labelling pipeline, negation-aware hybrid search and a tool-using query agent over chest X-ray reports.**

**Status:** done: M0–M5 (data, folds, rule baseline, Tier 1 LLM labelling + verifier, Tier 2 repair agent; these are the v1 results in §10). Planned (v2, from 21 Oct 2026): report parser and single `run_pipeline` entry point, ReAct verifier agent (replaces Tier 2 repair and the human-review queue), search, embedding fine-tuning, query agent, serving. See the roadmap (§12).

> Engineering and research project. **Not a medical device and not for clinical use.** Labels are derived from report text, not from images.

---

## 1. What this project is

Hospitals and research teams store thousands of chest X-ray reports as free text. They need to:
- **structure** them into findings,
- **search** them by meaning ("reports like this one"), and
- **ask questions** ("how many reports show effusion together with cardiomegaly?").

RadLabel does all three:

| Component | What it does |
|---|---|
| **Labelling pipeline** | Takes raw report text, splits it into sections, and extracts findings with sentence-level evidence. Free deterministic checks and a rule-based second reader check every label; a **ReAct verifier agent** handles only the reports where they fail or disagree, and marks every label **verified, corrected, suggested or unverified**. |
| **Negation-aware search** | Hybrid dense + BM25 search over reports and sentences. The embedding model is **fine-tuned so that "no effusion" is not retrieved for "effusion"**. |
| **Query agent** | Chooses between SQL (counts and filters) and filtered vector search, uses the indication ("why was this exam done?"), cites `report_id:sentence_id` for every claim, and refuses when the evidence is weak. |
| **Serving** | FastAPI, Docker Compose, Redis cache and rate limit, a queue-based ingestion worker, tracing, CI with cached regression evals, and a Gradio demo. |

Every component is evaluated against **expert-coded ground truth** using **stratified 5-fold cross-validation**.

## 2. Research context

- **Report retrieval and labelling** (FAU AIBE, IDEA Lab): Nützel, Dombrowski & Kainz, *Ontology-Based Concept Distillation for Radiology Report Retrieval and Labeling* (MLMI @ MICCAI 2025, arXiv:2508.19915). They compare reports through UMLS concepts, with a similarity measure that handles synonymy, negation and hierarchy, and report gains over embedding-based retrieval, especially for long-tail findings. RadLabel takes the engineering route to the same weakness: it teaches a dense embedding model about negation and measures the effect.
- **Expert entity schema:** Jain et al., *RadGraph* (arXiv:2106.14463).

> Before citing any specific result from these papers, re-read the paper and quote only what it states.

---

## 3. Data card (verified on the original files, 19 Oct 2026)

All numbers come from `data_prep/` (`parse_iu.py`, `map_and_stats.py`, `coding_policy.py`, `subset_stats.py`), run on the original Open-i XML. The data pipeline must reproduce them (§12, milestone M1).

### 3.1 Source
| Item | Value |
|---|---|
| Download | `https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz`, 1,112,632 bytes, no login. **Use this, not the Kaggle mirror.** If Open-i is down (it sometimes serves an HTML maintenance page), use the Wayback Machine raw copy of the same URL or the Academic Torrents copy ("Indiana University - Chest X-Rays (XML Reports)"). |
| **Checksum (required)** | SHA-256 `8fb6de7eec73d8c3665067ad4bb003ccd57f971ae316d2642e1627ac7268667a`. The download script verifies it **whatever the source**, rejects anything else (e.g. an HTML page), and records the source URL used. |
| Content | 3,955 XML reports (`ecgen-radiology/*.xml`) with COMPARISON, INDICATION, FINDINGS, IMPRESSION |
| Licence | **CC BY-NC-ND 4.0** on all 3,955 reports (`<ccLicense>byncnd</ccLicense>`) |
| Citation | Demner-Fushman D. et al., JAMIA 23(2):304–310, 2016 |

### 3.2 Ground-truth field
- `<MeSH><major>` holds the **manual expert codes**, e.g. `Calcified Granuloma/lung/upper lobe/right`. **This is the only ground truth.**
- `<MeSH><automatic>` holds machine-generated codes (2,182 reports). **Never used anywhere.**

### 3.3 Corpus numbers
| Item | Count |
|---|---|
| XML reports | 3,955 |
| Coded only `No Indexing` (never coded) | 95 → excluded |
| Empty Findings **and** Impression | excluded |
| **Usable reports** | **3,832** |
| **Unique texts** (normalised: lowercase, `XXXX` removed, punctuation removed) | **3,086** |
| Reports sharing exact text with another | 897 (23.4%); largest group = 50 |
| **Duplicate clusters** (exact text + exact pairwise Jaccard ≥ 0.9) | 3,073 (used for fold assignment only, §4.2) |
| Coded `normal` only | 1,363 usable → 650 unique (duplicates are almost all normal boilerplate) |
| Unique reports with a hedged finding sentence | 279 (9.0% of unique texts) |
| Unique reports with `XXXX` in Findings/Impression | 1,579 (51.2% of unique texts) |
| Reports with `XXXX` within 2 words of a finding term | 415 (10.8% of **all usable** reports; 407 on unique texts) |
| Usable reports with ≥ 1 code outside the standard labels | 54.5% (with the dropped labels mapped; slightly higher without) |

The three subset counts above are defined **exactly** by `data_prep/subset_stats.py` (fixed regexes, documented counting bases). `eval/subsets.py` must import or copy those definitions unchanged. The broader hedge list in `coding_policy.py` is only for the coding-policy check in §3.4 and gives different counts.

### 3.4 Coding policy (measured with a heuristic sentence-level check)
| Mention type in text | Coded by the experts |
|---|---|
| Clearly stated finding | 84–100% for most labels (Pneumonia 73%) |
| Negated ("no effusion") | 0–4% (one outlier: 1 of 8 atelectasis cases) |
| Hedged ("possible", "question", "versus", "may represent") | 6–44% for most labels; inconsistent |

So expert codes are reliable for **present** and **negated** findings, but **not for hedged** ones.

---

## 4. Data problems and how they are handled

| # | Problem | Handling | Section |
|---|---|---|---|
| D1 | Licence forbids sharing derived material | Train on IU, **keep models and processed data private**, serve only through the API | §4.1 |
| D2 | Rare labels give tiny test sets | **Stratified 5-fold CV** over duplicate clusters (iterative stratification), CIs, pooled rare score | §4.2, §8 |
| D3 | Hedged findings coded inconsistently | Excluded from headline metrics; uncertainty is kept in the output and used to **escalate to the verifier agent**, with verification metrics | §4.3 |
| D4 | "No Finding" trap: abnormal reports with no standard label | New **Other Abnormality** label; No Finding = expert `normal` code | §4.4 |
| D5 | Mapping choices can distort scores | Versioned mapping, automatic per-rule audit, **strict-mapping sensitivity analysis** | §4.4, §4.5 |
| D6 | Experts sometimes missed clearly stated findings | Report **raw** scores; **noise-adjusted** scores are deferred (stretch, decision D7) | §4.6 |
| D7 | Over-redaction (`XXXX`) next to findings | `[REDACTED]` token, verifier exemption, separate subset | §4.7 |
| D8 | Duplicate boilerplate reports | Duplicate clusters stay within one fold; each text counted once | §4.2 |
| D9 | Uncoded or empty reports | Excluded (§3.3) | — |

### 4.1 Licence (D1)
**Code** in this repository: MIT (`LICENSE`). **Data:** the IU report data and anything derived from it (labels, caches, models) are CC BY-NC-ND 4.0 and are **not included** in this repository.

CC BY-NC-ND allows using and adapting the data privately, but not **sharing** adapted material. Therefore:
- **Never committed or published:** `data/raw/`, `data/processed/`, mapped labels, splits containing text, trained model weights, and LLM output caches containing report text. All are git-ignored.
- **Model storage:** a private location only. Configurable via `MODEL_STORE`:
  - a local `models/` volume mounted into the API container (default)
  - a private S3 / Azure Blob / Modal volume
  - a **private** Hugging Face repo

  Never a public registry or public image.
- **Allowed through the API and demo:** labels, answers, report IDs, and **unchanged** report text with attribution. The attribution notice is shown in the demo footer and in API responses (`source_attribution` field): *"Indiana University Chest X-ray Collection (Open-i, NLM), CC BY-NC-ND 4.0."* Evidence highlighting is a UI overlay on unchanged text. The demo is free (non-commercial).
- A public **model card without weights** (`docs/model_card.md`) documents training data, method, results and why the weights are private.
- Not legal advice; this is the cautious reading of the licence.

### 4.2 Rare labels and duplicates: stratified 5-fold cross-validation (D2, D8)
- **Duplicate clusters:** reports are grouped into clusters by exact normalised text plus near-duplicates found by **exact pairwise Jaccard ≥ 0.9** on word shingles (deterministic; under 3 s on this corpus). MinHash was dropped because it missed 4 true merges, which could split near-duplicates across folds. **Each cluster is treated as one item when splitting**, so the same boilerplate never appears in both training and testing.
- **Multi-label stratification:** a report can have several labels, so ordinary stratification doesn't work. Use **iterative stratification** over cluster-level label vectors (`skmultilearn.model_selection.IterativeStratification`; fallback `iterstrat.ml_stratifiers.MultilabelStratifiedKFold`). Fixed seed, fold assignment saved to `data/splits/folds.csv` (cluster id → fold).
- **Per fold:** 4 folds are train, 1 fold is test. Inside the 4 training folds, a stratified 10% slice is the **inner validation set** for thresholds and checkpoint selection. Nothing is ever tuned on its own test fold.
- **Out-of-fold predictions:** every report is predicted exactly once, by a version that never saw it.
- **Counting unit (decided):** clusters decide **fold assignment only**. Metrics count **one report per exact normalised text** (3,086), so the data card numbers in §4.4 are exactly the evaluation counts. Near-duplicates are kept as separate items because they often differ by exactly one word, typically a negation ("no effusion" vs "small effusion"), which are the cases this project cares about most.
- **Near-duplicate report:** M1 writes the number of near-duplicate clusters whose members have **different** expert label sets to `artifacts/results/data_card.json`, as a data-quality fact.
- **Rare-label reporting:** every label gets a score with a **95% bootstrap CI** (1,000 resamples **over clusters**, so near-duplicates are resampled together) and its count, e.g. *"Pneumothorax F1 0.81 (0.65–0.92), n = 27"*. A pooled **rare-findings micro-F1** is also reported over the four rare labels (Edema, Pleural Other, Consolidation, Pneumothorax; about 150 positives), which is much more stable.

### 4.3 Hedged findings: uncertainty for verification, not for accuracy claims (D3)
- No public expert labels for uncertainty are available without PhysioNet credentialing, so **uncertainty accuracy is not claimed**.
- The `hedged` subset is defined by the **evaluation-only** regexes in `data_prep/subset_stats.py` (imported unchanged by `eval/subsets.py`; **not** the broader list in `coding_policy.py`), independent of the pipeline's own uncertainty logic. It is **excluded from headline metrics**.
- On `hedged`, label scores are reported under both policies (uncertain counted as absent, and as present).
- In the product (v2), uncertainty's job is **escalation to the verifier agent** (§6.2). There is no human-review queue: a label the agent can't confirm stays in the output marked `unverified`. Measured:
  - **escalation rate and unverified rate on hedged vs clear reports** (should be much higher on hedged)
  - **escalation precision**: the share of escalated reports where the Tier 1 answer disagreed with the expert codes
  - v1 (M5) measured the same with a review queue (the v1 review rate in §10).
- Future work: RadGraph's radiologist-annotated test set (PhysioNet) for real uncertainty and span accuracy.

### 4.4 Label set and mapping v1 (D4, D5)
Codes are parsed as `head/sub/...`. A rule matches on `head`, plus the first `sub` if given. The table lives in `data/mapping/mesh_to_labels_v1.yaml`; every unmatched code is logged to `artifacts/mapping/unmapped.csv`.

| Label | Mapped manual codes | Unique positives | Role |
|---|---|---|---|
| No Finding | `normal` as the **only** code | 650 | headline |
| Cardiomegaly | Cardiomegaly; Cardiac Shadow/enlarged | 395 | headline |
| Lung Opacity | Opacity; Density; Airspace Disease; Infiltrate, at a **lung site** (lung, retrocardiac, sulcus, costophrenic angle, non-anatomical; see rules below) | 608 | headline |
| Lung Lesion | Nodule; Mass; Cavitation, **lung site only** (see rules below); Cysts go to Other Abnormality | 118 | headline |
| Atelectasis | Pulmonary Atelectasis | 332 | headline |
| Pleural Effusion | Pleural Effusion; Hydropneumothorax; Hemothorax | 162 | headline |
| Fracture | Fractures, Bone | 84 | headline |
| Support Devices | Catheters, Indwelling; Implanted Medical Device; Tube, Inserted; Medical Device; Stents; Surgical Instruments (Sutures go to Other Abnormality) | 376 | headline |
| **Other Abnormality** | any other code (including the dropped labels' codes) except `normal`, `No Indexing`, `Technical Quality of Image Unsatisfactory`, `Contrast Media` | 2,077 | headline |
| Edema | Pulmonary Edema **only** | 46 | rare (individual + pooled) |
| Pleural Other | Thickening/pleura; Pleura, **except** codes with a `blunted` sub-heading; opacity/lesion codes at a pleural site | 53 | rare |
| Consolidation | Consolidation | 30 | rare |
| Pneumothorax | Pneumothorax; Hydropneumothorax; Hemopneumothorax | 27 | rare |
| ~~Pneumonia~~ | — | 42 | **dropped**: clinical diagnosis, coded inconsistently |
| ~~Enlarged Cardiomediastinum~~ | — | 27 | **dropped**: rare, ambiguous source codes |

Rules that matter:
- **No Finding** = the report describes **no abnormality of any kind**; it matches only the expert `normal` code. The extractor prompt states this explicitly. The 7 reports coded only with ignored codes ("Technical Quality of Image Unsatisfactory", "Contrast Media") are excluded from No Finding scoring.
- **Other Abnormality** = any abnormality not covered by the other labels (e.g. scoliosis, calcified granuloma, hypoinflation, degenerative spine, tortuous aorta). It closes the "No Finding" gap: 28.8% of usable reports are abnormal with no standard label.
- **Not mapped to Edema:** Pulmonary Congestion and Heart Failure. Reports say "vascular congestion without edema", and mapping them created positives that contradict the text. They fall into Other Abnormality.
- **Not mapped to Lung Lesion:** Calcified Granuloma and Granulomatous Disease (benign, chronic). They fall into Other Abnormality.
- **Lung Opacity and Lung Lesion require a lung site** (mapping cross-check, 2026-10-20): a code counts when its first sub-heading is `lung`, or when it is an allowed lung region or non-anatomical word and **no** sub-heading is a non-lung site (paratracheal, mediastinum, hilum, heart, ribs, thorax, sternum, breast, humerus, clavicle, abdomen, adipose tissue, cardiophrenic angle, supracardiac, mitral valve, thoracic vertebrae → Other Abnormality) or a pleural site (pleura, pleural sinus → Pleural Other). The full lists are in `mesh_to_labels_v1.yaml`.
- **Lung Lesion requires a lung site.** Nodule, Mass and Cavitation count only when the first sub-heading is `lung` or is not an anatomical site (e.g. none, right, left, multiple, scattered, bilateral). Codes with another site (e.g. `Cysts/humerus`, `Mass/breast`, `Nodule/heart`, `Nodule/pleura`, `Mass/mediastinum`, `Nodule/thorax`, `Mass/thorax`) go to **Other Abnormality**. Cysts never count (owner decision after the M1 audit): `Cysts/humerus`, a bone cyst found in the mapping audit, showed the problem.
- **`Pleura/…/blunted` is not Pleural Other.** A blunted pleural angle usually hints at effusion but isn't a confirmed effusion, so it goes to **Other Abnormality**, like `Costophrenic Angle/blunted`. Found in the mapping audit (n = 3).
- **Hierarchy:** scoring uses these **leaf** definitions only, with no closure, so Lung Opacity is scored against its own direct codes. The extractor prompt and verifier use the same definitions, so propagated parent labels can't create false positives.

### 4.5 Mapping audit and sensitivity (D5)
- **Automatic per-rule audit** (`data_prep/audit_mapping.py`): for every mapping rule, the share of matched reports whose text has a clear, non-negated, non-hedged mention of the label's terms. Rules below 60% agreement are flagged in `artifacts/mapping/audit.csv` and reviewed before modelling.
- **Strict mapping** (`mesh_to_labels_strict.yaml`): only the primary head per label (Cardiomegaly; Opacity/lung; Nodule + Mass; Pulmonary Atelectasis; Pleural Effusion; Fractures, Bone; Catheters, Indwelling + Tube, Inserted + Medical Device + Implanted Medical Device; Pulmonary Edema; Thickening/pleura; Consolidation; Pneumothorax).
  - **Other Abnormality and No Finding are identical under v1 and strict.** Strict changes only the 11 pathology labels, so the comparison isolates the effect of the looser rules.
  - Reports that are positive for a label under v1 but **not** under strict (e.g. only `Density/lung`) are **excluded from that label's strict scoring**, counted neither positive nor negative, because they're ambiguous rather than negative. Their counts per label are reported.
- Headline labelling results are reported under **both** v1 and strict. Conclusions must hold under both.

### 4.6 Label noise (D6)
- **Raw score:** against the expert codes. This is the official number.
- **Noise-adjusted score** (deferred, stretch; owner decision D7): a case is set aside when the model says `present`, the code is absent, and an **independent** evaluation-only detector (negspacy + the eval lexicon, not the pipeline's negation module) finds a clear, non-negated, non-hedged mention in the text. Reported as an estimate, with the number of cases set aside.
- The true performance lies between the two.

### 4.7 Redactions (D7)
- `XXXX` is replaced with `[REDACTED]` before any model sees the text.
- The verifier does not fail a label solely because its cited sentence contains `[REDACTED]` within 2 words of a finding term; it flags it instead.
- `redaction_adjacent` is reported as a separate subset.

### 4.8 Evaluation subsets: exact definitions
All subsets live in `eval/subsets.py`, are computed once in M1, and are saved as id lists in `data/splits/subsets/` (git-ignored).

| Subset | Unit | Definition |
|---|---|---|
| `abnormal` | report | Not coded `normal`; at least one label other than No Finding is positive |
| `hedged` | report | `is_hedged()` from `data_prep/subset_stats.py`, unchanged (279 on unique texts) |
| `redaction_adjacent` | report | `is_redaction_adjacent()` from `subset_stats.py`, unchanged (415 on all usable reports) |
| `negation_only` | **(report, label) pair**, for the 11 pathology labels | All three hold: (1) the label's eval aliases (`eval/lexicon.yaml`, separate from the pipeline alias list) occur in Findings/Impression; (2) **every** occurrence is negated, per **negspacy** (the eval-only detector, never the pipeline's `negation.py`); (3) the expert code for that label is **absent**. Pairs where any sentence mentioning the label is hedged are excluded. |

`negation_only` is per pair, not per report: "No pneumothorax. Small left effusion." contributes a negated pair for Pneumothorax even though the report is abnormal.
- **Negation FP rate** = the share of `negation_only` pairs predicted `present`, reported **per label** and pooled.
- It is also reported **restricted to abnormal reports**, because most negated pairs come from normal boilerplate, where the task is easy.
- **negspacy termset extension (pre-registered):** the default termset doesn't treat resolution language as negation. Add these as following negations: "has resolved", "have resolved", "resolved", "no longer seen", "no longer visualized", "has cleared", "have cleared", "removed". Without them, "effusion has resolved" would count as a clear positive mention and inflate the noise-adjusted score (§4.6).
- **Eval lexicon additions (pre-registered):** the mapping audit showed missing synonyms, e.g. devices ("ICD", "AICD", "pacemaker", "prosthetic valve", "valve replacement", "monitor leads", "ECG leads", "spinal stimulator", "port", "PICC", "sternotomy wires") and pneumothorax variants ("hydropneumothorax", "hemopneumothorax"). Add these to `eval/lexicon.yaml` with a one-line reason each.
- **Freeze:** `eval/lexicon.yaml` and the negspacy termset are versioned `eval_v1` and **frozen at the end of M1, before any model output exists**. Any later change needs owner approval and a changelog entry. The pipeline's own alias list is written separately from general clinical knowledge and is **never copied from the eval lexicon**, to keep the two independent.
- M1 writes the pair counts per label (all, and abnormal-only) to `data_card.json`. There are no README reference numbers for these, so they become the reference once the owner approves them.

---

## 5. Architecture

```
raw report text ──► Ingestion worker: asyncio queue + Postgres `jobs`/`report_status` tables
                    (status, attempts, tenacity retries with backoff, cost ledger, resumable)
                         │  each report = one run_pipeline() call
                         ▼
     ┌──────────────── run_pipeline(raw_text) (per report) ─────────────────────┐
     │ Stage 0  parser: indication / comparison / findings / impression          │
     │          (header matching; no headers → one block, "sections not          │
     │          identified")                                                      │
     │ preprocess: [REDACTED], sentence split with IDs (F1.., I1..),             │
     │             pipeline negation/hedge tags, alias candidates                 │
     │ Tier 0  boilerplate normals (patterns learned on training folds)          │
     │ Tier 1  tagger LLM on Findings + Impression (pinned snapshot, frozen      │
     │         prompt, structured output). Indication is NOT an input.            │
     │ Free checks (no LLM, $0, every report):                                    │
     │   • deterministic verifier checks (evidence, negation, sections, hedge,    │
     │     [REDACTED], No Finding)                                                │
     │   • recall scan: rule baseline as a second reader                          │
     │     (rules say present, tagger says absent/not_mentioned → disagreement)   │
     │   • normal check: every predicted No Finding is a claim to confirm         │
     │     (heart + lungs covered, nothing abnormal)                              │
     │   all pass ──────────────────────────────► verified (rule checks)         │
     │   fail / escalating flag / disagreement                                    │
     │        ▼                                                                   │
     │ Verifier agent (ReAct, tools, bounded loop) → per label:                   │
     │   verified · corrected · suggested · unverified   (no human-review queue)  │
     └──────────────┬──────────────────────────────────────┬────────────────────┘
                    ▼                                      ▼
     Postgres `labels` (PREDICTED only,            Qdrant collection
     with verification state + evidence)           - report points + contextual sentence points
                    │                              - dense (fine-tuned bge-small) + sparse BM25
                    │                              - payload: report_id, sentence_id, section,
                    │                                predicted labels + verification state,
                    │                                pipeline negation tag; indication as a
                    │                                separate field (Q&A only)
                    └──────────────┬───────────────┘
                                   ▼
question ──► Redis cache (key: question + index_version + label_model_version)
                                   ▼
             Query agent (LangGraph): sql_count · filtered_search · get_report · get_sentences
             → hybrid retrieval (RRF) → optional cross-encoder reranker
             → evidence check → answer with citations, or "not enough evidence"
                                   ▼
             FastAPI · Docker Compose · rate limit · tracing · CI · Gradio demo
```

Invariants:
1. **Serving never reads expert labels.** The `labels` table, the Qdrant payloads, `run_pipeline` and the verifier agent see pipeline predictions and report text only. Unit tests enforce this.
2. **One entry point.** `run_pipeline(raw_text)` is the only way labels are produced: the evaluation script, the ingestion worker and the API all call it. Evaluation feeds it joined report text with the expert codes hidden (§8.1).
3. **Evaluation models vs serving model.** CV trains 5 evaluation embedding models (one per fold) for honest metrics. The serving model is trained once on all reports after evaluation and stored privately.
4. **Every LLM call is cached**, keyed by (model snapshot, prompt hash, input hash), so evaluation is reproducible and CI needs no API calls.
5. **No separate LLM-judge steps** anywhere in the pipeline or in retrieval. Judgment happens inside the verifier agent and the query agent, with their tools.

## 6. Component specifications

### 6.1 Preprocessing (`src/radlabel/preprocess/`)
- `parser.py` (v2, M6): splits raw text into indication / comparison / findings / impression by header matching, including variants ("Clinical history", "History", "Reason for exam", "Conclusion", "Opinion", "Summary"), case- and punctuation-insensitive. No recognisable headers → the whole text is one block, flagged `sections_not_identified`, and later stages degrade gracefully (the tagger reads the block; the verifier can't use the section rule). Returns each section plus a parse report.
- `text.py`: `[REDACTED]` substitution and normalisation. The data pipeline (M1) takes sections from the XML fields; production and v2 evaluation take them from `parser.py`.
- `sentences.py`: sentence splitting with IDs `F1..Fn`, `I1..In`.
- `negation.py`: **pipeline** NegEx-style rules (negation and hedge cues, clause boundaries at "but", "however", ";"). Kept separate from the eval detector.
- `aliases.py`: alias dictionary per label (hand-written + CheXpert labeler mention phrases). Fixed, not tuned on data. 30% of the aliases are tagged `heldout: true` for embedding evaluation.
- `dedup.py`: exact-text clusters + exact pairwise Jaccard ≥ 0.9 near-duplicate merging.

### 6.2 Labelling (`src/radlabel/labelling/`)
**Output schema** (Pydantic, also the structured-output schema):
```json
{
  "report_id": "CXR123",
  "sections_identified": true,
  "labels": [
    {"label": "Pleural Effusion", "status": "absent",  "evidence": ["F2"],
     "verification": "verified_rules"},
    {"label": "Cardiomegaly",     "status": "present", "evidence": ["F1", "I1"],
     "verification": "verified"},
    {"label": "Atelectasis",      "status": "present", "evidence": ["F3"],
     "verification": "suggested", "reason": "tagger said not_mentioned; F3 'atelectasis at the left base'"}
  ],
  "tier": 1,
  "agent_used": true,
  "check_messages": []
}
```
`verification` per label (v2):
- `verified_rules`: all free checks passed; no agent call.
- `verified`: the agent found supporting evidence itself.
- `verified_impression_only`: as `verified`, but the report has no Findings, so only the Impression could be checked.
- `corrected`: the agent changed the tagger's status.
- `suggested`: a finding the tagger missed, added by the agent.
- `unverified`: the agent could not confirm the label (with `reason`). This replaces v1's human-review queue.

Evidence is always sentence IDs that exist in the report, and the sentence text is returned verbatim (string-checked), so evidence can't be invented. Evidence proves the sentence exists, not that it caused the label.
- **Output vs evaluation policy.**
  - System output is four-valued: `present | uncertain | absent | not_mentioned`, representing what the report text says.
  - Headline evaluation binarises it: `present` = positive, everything else = negative, against the expert codes. The "`uncertain` = positive" row in §10 is a sensitivity check, not the headline metric (on the `hedged` subset both policies are reported, §4.3).
  - The verifier's hedge downgrade (`present` → `uncertain`) is product policy. In v1 its cost in the headline metric (LLM + verifier − LLM only in §10) came mostly from "borderline cardiomegaly". The Tier 1 label definitions state that mild or borderline enlargement **is** Cardiomegaly, so in v2 the hedge check no longer treats wording that a label's definition counts as present ("borderline", "mild") as a hedge. This is a consistency fix between two existing rules, not tuning on test results.
  - The `verification` field is **not** scored. It is evaluated separately: are `verified` labels more accurate than `unverified` ones (§8.1)?
  - The Atelectasis gap to the rule baseline comes from the LLM's own `uncertain` outputs (e.g. "scarring or atelectasis"), not from the verifier.
  - The absent-evidence rules (`absent` with no or generic evidence → flag) affect routing only, never scores: only `present` is scored.

**Tiers:**
- **Tier 0:** exact normalised texts coded `normal` at least 3 times **in the training folds** → No Finding, with no LLM call. Out-of-fold it matches **no** test report, by construction (identical texts share a cluster and so a fold), so it leaves every §8.1 metric unchanged and only saves calls in serving. Learned on all reports, the 96 patterns match 773 of 3,832 usable reports; that figure is **in-sample** (patterns learned and matched on the same reports), not a held-out result.
- **Tier 1 (the tagger):** LLM extractor (gpt-4.1-mini, prompt `tier1-v1`, **frozen**), zero-shot, with **synthetic** in-prompt examples (written by hand, never IU text, so there is no leakage). It reads Findings + Impression; **indication is never an input**. The prompt contains label definitions only: no pipeline alias lists, negation cues or rule outputs. The dated model snapshot is pinned in config and recorded in every result file.
- **Free checks, part 1: deterministic verifier checks** (`verifier.py`, all unit-tested). Each result is PASS, FAIL or FLAG. In v2, FAILs and the flags marked *escalates* send the report to the verifier agent; the other flags are recorded only.

| Check | Rule | v2 action |
|---|---|---|
| Evidence exists | every `present`/`absent`/`uncertain` label cites ≥ 1 valid sentence ID; invalid IDs fail; `absent` with no evidence → **flag** (implied absence; M4, owner-approved) | fail → escalates; absent-without-evidence flag → recorded only |
| Evidence mentions label | `present`/`uncertain`: a cited sentence contains an alias of the label, else **fail**. `absent`: passes if a cited sentence names the label **or** contains a label-scoped normal phrase (`src/radlabel/labelling/normal_phrases.yaml`, e.g. Consolidation ← "clear lungs", Fracture ← "no acute osseous"), else **flag**. Other Abnormality (open-ended label) → flag. A cited sentence containing `[REDACTED]` → flag (the label word may be redacted). (Changed after the M4 pilot, owner-approved.) | fail → escalates; `[REDACTED]` flag on `present`/`uncertain` → escalates; `absent` and Other Abnormality flags → recorded only |
| Negation consistency | a `present` label whose only cited sentences are negated in the same clause → **flag**, not fail: in the M4 full run the pipeline negation was wrong in 20 of 23 such cases (owner's pre-committed rule; `docs/evaluation_notes.md`) | escalates |
| Hedge consistency | a `present` label whose only evidence is hedged → convert to `uncertain` and flag. v2: wording that the label definition counts as present ("borderline", "mild") is not a hedge | escalates |
| No Finding exclusivity | No Finding `present` ⇒ every other label ≠ `present`. No Finding is **derived in code** (present iff no other label is present/uncertain, else not_mentioned); a model's No Finding value is ignored (M4). | — (by construction) |
| Section rule | Impression overrides Findings **only on an explicit same-label contradiction**. "No acute cardiopulmonary abnormality" does **not** cancel specific Findings. Unit test: Findings "mild cardiomegaly" + Impression "no acute disease" → Cardiomegaly stays `present`. A disagreement is a **flag**, not a fail: on the M4 pilot the LLM was right in 26 of 39 such disagreements (owner's pre-committed rule; `docs/evaluation_notes.md`). | escalates |

- **Free checks, part 2: recall scan** (v2, M7). The rule labeller (`src/radlabel/labelling/rules.py`, also the rule baseline: aliases + pipeline negation, no LLM) runs on every report as a cheap second reader. For each label where the rules say `present` and the tagger says `absent` or `not_mentioned`, the report escalates. This targets the tagger's real weakness: its precision is ~0.99 on several labels, but its recall is lower (§10). The rules have their own errors (e.g. "upper limits of normal" read as enlargement), which is why the agent decides, not the rules.
- **Free checks, part 3: normal check** (v2, M7; code, no LLM). A predicted No Finding is an **unconfirmed claim** and is always checked, because many reports with a "no acute" impression still carry abnormal codes (e.g. borderline cardiomegaly, granulomas). When No Finding comes out `present`:
  - **coverage:** the report has normal statements covering at least the **heart and lungs** (pleura, mediastinum and bones are recorded when stated, but not required, since many normal reports never mention them);
  - **nothing abnormal:** the rule scan finds no `present` or `uncertain` label, including Other Abnormality cues, in any sentence.
  - Both hold → No Finding is `verified_rules`, with the normal statements as its evidence.
  - Either fails → the report escalates. The agent then either confirms No Finding (`verified`), or **withholds it** (`corrected` to not_mentioned) and adds the abnormal findings it found as `suggested` labels, with evidence.
  - Reported (secondary): No Finding precision before and after the checks and the agent, and how many predicted normals were withheld.
  - **The "intermediate" state:** between the tagger and the normal check, No Finding is only a *proposed* label, not a final one. It is an internal state, not a new label: there is **no** extra training column (e.g. a derived `no_acute_findings` tag), because the dataset has no ground truth for it and the tagger already reads Findings. The M6 normal-claim count settled this (owner, 22 Oct 2026): 1,302 unique reports have an Impression made only of "no acute"-type statements, 833 of them (64.0%) have expert codes that are not normal-only, and the tagger predicted No Finding for only 3 of those 833. The tagger does not confuse "nothing acute" with "fully normal", so **no intermediate label** is added; the normal check still runs on every predicted No Finding.
- **Verifier agent** (v2, M7; `verifier_agent.py`, LangGraph ReAct): runs **only on escalated reports**. Everything else ends as `verified_rules`.
  - **Model:** the agent deployment (gpt-5-mini), with its own prompt, not the tagger's.
  - **Input:** the report's sentences, the tagger's labels **without the tagger's evidence** (blind first: the agent finds evidence itself), and the escalation reasons (check messages, recall-scan disagreements). Never expert codes, folds, eval mentions or metrics (leakage test).
  - **Tools:** `find_by_alias(label)`, `find_by_meaning(label)` (sentence embeddings; base model until M9, then the fine-tuned one), `check_negation(sentence_id)`, `compare_sections(label)`, `check_redaction(sentence_id)`, `get_label_definition(label)` (the frozen label policy, the same definitions as the tagger prompt), `normal_check()` (the same check as free-check part 3, returning which regions are covered and which sentences look abnormal), `submit(labels)`.
  - **Output:** for each label it was asked about: `verified`, `corrected`, `suggested` or `unverified`, with evidence IDs (string-checked) and a one-line reason. Labels it wasn't asked about keep `verified_rules`.
  - **Limits:** at most 8 tool calls and a token cap per report; on hitting a cap, or the budget, the open labels end `unverified` with the reason.
  - **Empty Findings:** it uses the text that exists; No Finding confirmed from the Impression alone is `verified_impression_only`.
  - **Prompt development** only on the **dev slice** (the 102 Tier 1 pilot reports, already excluded from headline metrics). The prompt is frozen (hash test) before the full run. Label definitions come from the frozen policy; no rule is added from looking at test-fold errors.
  - **Independence:** the agent shares the report text with the tagger, so `verified` is a consistency check by a second model with different tools, not independent proof. Reported: how often the agent's evidence matches the tagger's.
- **v1, historical (M5):** a Tier 2 repair agent (`repair_agent.py`) fixed FAIL labels only, and anything still failing or flagged went to a `review` table (Tier 3). Its results stay in §10 as the comparison column. v2 replaces both with the verifier agent.

**Baselines** (`eval/baselines/`):
- `rule_baseline.py`: alias match + pipeline negation, no LLM. Always available. A thin wrapper around `src/radlabel/labelling/rules.py`, so pipeline code never imports from `eval/`.
- `chexpert_labeler/`: the CheXpert labeler in its own Docker image. **Stretch:** if its dependencies fail to build, document the attempt and continue.
- LLM extractor without the verifier and repair (ablation).
- No QLoRA / local-model tagger (dropped 21 Oct 2026).

### 6.3 Index and embeddings (`src/radlabel/index/`, `training/`)
- **Points:** one per report (Findings + Impression) and one per sentence, each with its section name. Sentence text is prefixed with a context line built from **predicted** labels: `"[Findings | report also mentions: cardiomegaly] No pleural effusion."` If the parser found no sections, sentences are indexed with section `unknown`.
- **Payload:** report_id, sentence_id, section, predicted labels with their `verification` state (so filters can require verified labels), pipeline negation tag, and the evidence sentence IDs per label.
- **Indication** is stored as a separate field per report for the query agent ("why was this exam done?"; empty or mostly `[REDACTED]` → "not stated"). It is **never** embedded into report or sentence points and never used in retrieval-evaluation queries, because it can hint at the label.
- **Retrieval:** dense (cosine) + BM25 sparse in Qdrant, fused with RRF (k = 60). Optional cross-encoder `BAAI/bge-reranker-base` over the top 50. No LLM-judge stage.
- **Aggregation:** sentence hits → reports by **max score per report**, then deduplicated.

**Embedding fine-tuning** (`training/build_pairs.py`, `training/train_embeddings.py`):
- Base model `BAAI/bge-small-en-v1.5`; `--device auto` (CPU works; GPU is faster).
- Pairs are built **from training folds only**, with expert codes for relevance and the pipeline negation tags for hard negatives:
  - query → report: positive = coded finding; hard negative = report mentioning it only negated
  - query → sentence, using the **same contextual prefix format** as the index
  - report → report, sampled **from abnormal reports only**: positive = same label set; hard negative = similar wording with a negated key finding
- Queries come from label names plus **non-held-out** aliases. **Held-out labels** (Fracture, Lung Lesion, Pleural Other) are never used in training.
- **Loss:** `CachedGISTEmbedLoss` with the base model as guide, which filters in-batch false negatives. Fallback: `MultipleNegativesRankingLoss` with a sampler allowing each label once per batch.
- 1–3 epochs, selected by inner-validation nDCG@10.
- Output: `models/eval/fold_{k}/` and `models/serving/`, **private, git-ignored**.

### 6.4 Query agent (`src/radlabel/agent/`)
| Tool | Contract |
|---|---|
| `sql_count(filters: {label: status}, verified_only?, section?)` | parameterised read-only SQL over `labels`; returns count + up to 20 example report IDs |
| `filtered_search(query, filters?, verified_only?, k=10)` | the hybrid retrieval of §6.3; returns `report_id`, `sentence_id`, score, text |
| `get_report(report_id)` | unchanged report text + attribution, sections as parsed |
| `get_indication(report_id)` | the indication text, or "not stated" |
| `get_sentences(report_id, ids)` | the cited sentences |
| `get_label_evidence(report_id, label)` | the label's status, verification state and evidence sentences ("what supports cardiomegaly in this report?") |

**Guardrails:**
- Every claim cites `report_id:sentence_id`, and a post-check verifies each citation exists and mentions the finding asked about.
- Refusal ("not enough evidence") below a relevance threshold **tuned on inner validation**.
- Out-of-scope refusal (CT, age, which is redacted, treatment or diagnosis advice).
- Schema-validated tool arguments; read-only database role; input length limit.

### 6.5 Ingestion, API, operations (`src/radlabel/ingest/`, `src/radlabel/api/`)
- **Ingestion worker:** asyncio queue with bounded concurrency, tenacity retries with exponential backoff, a Postgres status per report, a `MAX_LLM_USD` cost cap (when reached, escalated labels end `unverified` with reason "budget" instead of calling the agent), and resume-from-status after a crash. Each report goes through `run_pipeline`.
- **API:** `POST /ingest`, `GET /jobs/{id}`, `POST /label` (raw report text → `run_pipeline`), `GET /reports/{id}/labels`, `POST /ask`, `GET /health`. No review endpoints: unverified labels are visible in the output and in the demo.
- Redis: answer cache (versioned key) + embedding cache + rate limiting.
- Tracing via Langfuse or Arize Phoenix (`TRACING_BACKEND`); one trace per request, with tier, tool calls, verifier messages and latency per step.
- Docker Compose services: `api`, `worker`, `postgres`, `qdrant`, `redis`, optional `phoenix`. Models are mounted from the private `MODEL_STORE`.
- Deployment files (`deploy/`), CPU-only. Default target: **Azure Container Apps** (API + demo, scale-to-zero), with Qdrant and Redis as containers and Postgres Flexible Server (Burstable). Fallback: a single small Azure VM running Docker Compose with **auto-shutdown** enabled. Actual deployment requires the owner's credentials; keep it stopped or scaled to zero when not demoing, to save student credit.
- **Production checklist** (part of M10/M11):
  - **Dockerfile:** multi-stage, slim Python base, non-root user, `HEALTHCHECK` on `/health`. The image contains **no data and no model weights**; models are mounted from `MODEL_STORE` at runtime (§4.1).
  - **Database migrations** with Alembic, not ad-hoc `CREATE TABLE`.
  - **Config** via pydantic-settings. Secrets only from environment variables (Container Apps secrets or Key Vault in Azure); never baked into images.
  - **API:** request IDs, structured JSON logs, consistent error schema, request size limits, `/health` (liveness) and `/ready` (Postgres, Qdrant and Redis reachable).
  - **CI:** lint (ruff), type check (mypy on `src/`), tests, cached regression eval, and a Docker build. **CD** (manual trigger) pushes the image to a **private** registry (GHCR private or Azure Container Registry) and updates the Container App.
  - **Smoke test** after deploy: `/health`, one `/label` and one `/ask` call against the deployed URL.
- **Demo** (`demo/app.py`, Gradio): paste a report and see its labels with verification badges (verified / corrected / suggested / unverified) and evidence highlighted; ask a question, see the answer with clickable citations, view the unchanged report with evidence highlighted as an overlay, and the attribution footer.

---

## 7. Configuration

All settings live in **`.env.example`** at the repo root (committed, no secrets). Copy it to `.env` (git-ignored) and fill in the key, the API version, the model versions and the per-deployment TPM. `src/radlabel/config.py` loads them with pydantic-settings and **fails fast with a clear message** if a required value is missing.

| Group | Variables |
|---|---|
| Provider | `LLM_PROVIDER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `OPENAI_API_KEY` |
| Deployments per role (§7.1) | `AZURE_OPENAI_DEPLOYMENT` (Tier 1), `…_FALLBACK_DEPLOYMENT`, `…_REPAIR_DEPLOYMENT` (agents: verifier agent, query agent; the name is kept from v1), `…_CHEAP_DEPLOYMENT` (paraphrasing), `…_EMBED_DEPLOYMENT` (baseline row only), plus a `…_VERSION` for each |
| Pilot | `PILOT_DEPLOYMENTS` |
| Limits and budget | `TIER1_TPM`, `REPAIR_TPM`, `CHEAP_TPM` (deployment allocations), `TIER1_MAX_TOKENS`, `LLM_MAX_CONCURRENCY`, `MAX_LLM_USD`, `LLM_CACHE_DIR` |
| Local models | `EMBED_BASE_MODEL`, `RERANKER_MODEL`, `DEVICE`, `MODEL_STORE` |
| Services | `DATABASE_URL`, `QDRANT_URL`, `REDIS_URL` |
| Tracing | `TRACING_BACKEND`, `PHOENIX_COLLECTOR_ENDPOINT`, `LANGFUSE_*` |
| App | `SEED`, `API_RATE_LIMIT`, `LOG_LEVEL` |

Keep `.env.example` in sync whenever a setting is added.
**Offline mode:** with no API key, the LLM client serves from the cache, or raises a clear error. Tests use a `FakeLLM`, so everything except fresh LLM calls runs without credentials.

### 7.1 Azure for Students resources (owner's subscription)

**Limits behave as hard stops, not extra charges.** Rate limits return HTTP 429. Azure for Students subscriptions can't get quota increases (Azure subscription limits doc). Spending is capped by the student credit. Implementation consequences:
- The LLM client retries 429s with exponential backoff, honours `Retry-After`, and keeps concurrency below the deployment's TPM. A 429 is never treated as a failed label; the report stays queued.
- `MAX_LLM_USD` is enforced in code (currently 20): fresh LLM calls stop when the cost ledger reaches **50% of it ($10)**; cache hits are always free. The owner sets an Azure Cost Management budget alert (e.g. $20) as a second safeguard.

**Version pinning.** Each deployment uses version update policy **"Upgrade when expired"** (`OnceCurrentVersionExpired`). The version stays fixed for the whole project, and only at retirement does the deployment move to the new default instead of failing with HTTP 410. ("No auto upgrade" would make the demo break at retirement.) The LLM client also logs the `model` field returned by **every response** and raises a warning if it changes between calls, which catches silent upgrades. Retirement dates are checked in each deploy dialog before use.

**LLM deployments** (all Global Standard; the model version is recorded in every results file):

| Deployment | Quota (TPM) | Used for | Why |
|---|---|---|---|
| `gpt-4.1-mini` | 5M | Tier 1 labelling (~3,100 reports) | Non-reasoning, temperature 0, reliable structured output, cheap → reproducible bulk work |
| `gpt-5-mini` (already deployed, 375K TPM allocated) | 1M | Verifier agent (v2; Tier 2 repair agent in v1), query agent | Reasoning model, better at multi-step tool use; runs only on escalated reports |
| `gpt-5.4-mini` (fallback for Tier 1) | 1M | Tier 1 if gpt-4.1-mini is unavailable or retiring | Newer; check in the pilot whether it supports temperature 0 and reliable structured output. (gpt-4o-mini 2024-07-18 was reported retired on 1 Oct 2026, so it isn't used.) |
| `gpt-4.1-nano` or `gpt-5.4-nano` | 5M | Paraphrasing agent questions | Cheapest option for simple rewriting |
| `text-embedding-3-small` | 1M | Optional retrieval baseline row ("API embeddings vs our fine-tuned model") | Not used in serving |

**Throughput is not the bottleneck.** Labelling all unique reports is about 6M tokens (~2,000 per report), which takes minutes at ≥ 1M TPM. Azure counts the requested `max_tokens` against TPM, so set `max_tokens ≈ 800` for Tier 1 (not a large default), and size concurrency from TPM / (prompt + max_tokens).

**Tier 1 model selection pilot (milestone M4):** label ~100 reports **from training folds only** with `gpt-4.1-mini`, `gpt-5.4-mini` and `gpt-5.4-nano`. Compare macro-F1, invalid-output rate and cost per report; use the winner for the full run. Results go to `artifacts/results/model_pilot.json`. This costs under $1 and documents why the model was chosen.

Not used:
- **Models with < 1M TPM** (gpt-5.4-pro 160K; gpt-5.2 and gpt-5.4 250K; gpt-4o 450K): lower limits and higher cost, with no benefit for extraction.
- **`-codex` variants** (tuned for code) and **`-chat` variants** (tuned for conversation, less parameter control).
- **Model Router**: it picks the model per request, so results aren't attributable to one model.
- **Newer models without verified pricing**: check prices before using them for bulk work.
- **Third-party models on Azure** (Anthropic, xAI, DeepSeek models): small quotas, possibly billed outside student credit.

**LLM spend:** $2.38 after M5 (Tier 1 full run $0.59 + re-run, pilots, mapping cross-checks, Tier 2 $0.26). The free checks are code, so they reuse cached outputs. The verifier agent's cost is **estimated on the dev slice before the full run** (M7); the owner decides at that point. Query agent and its evaluation: estimated before running. Hard stop: $10 total (above).

**GPU accelerator quota** (8 each of A100 80GB, H100 80GB, H200 141GB, MI300 192GB). **The quota isn't the constraint; the credit is**, since GPU time costs several dollars per hour. Policy:

| Task | Compute | Note |
|---|---|---|
| Embedding fine-tuning (bge-small, 5 folds + serving model) | CPU or Kaggle T4 by default; **optionally 1× A100 80GB** as an Azure ML job | Small model; an A100 finishes all runs in minutes. Use a compute cluster with **min nodes = 0**, so it scales to zero after the job. |
| Serving the API and demo | **No GPU** | The deployed system uses the Azure OpenAI APIs and CPU embeddings. |
| H100, H200 | Not used | Overkill for these model sizes, and pricier. |
| MI300 (AMD) | Not used | ROCm setup is more fiddly; not worth the time. |

Even with quota shown, a specific GPU VM size may be unavailable in a region; test with one short job first. Every GPU job writes its runtime and estimated cost to `artifacts/results/compute_log.json`.

---

## 8. Evaluation protocol

All metrics use **out-of-fold predictions** from the stratified 5-fold CV (§4.2), counted once per exact normalised text, with 95% bootstrap CIs resampled over duplicate clusters. Subsets are defined exactly in §4.8.

### 8.1 Labelling
- **Headline:** per-label F1, precision and recall for the 9 headline labels, plus their macro-F1, excluding `hedged`, under mapping v1 **and** strict.
- **Rare:** each rare label with CI and n; plus pooled rare micro-F1.
- **Subsets:** `abnormal`, `negation_only` (selected with the **eval-only** detector), `hedged` (both policies), `redaction_adjacent`.
- Raw vs noise-adjusted (§4.6).
- **Ablation:** rule baseline | CheXpert labeler (if built) | LLM only | LLM + verifier | LLM + verifier + repair (v1) | **LLM + free checks + verifier agent (v2)**.
- **Through the entry point (v2, M6):** for each out-of-fold report, the evaluation script joins its sections into one text with headers, **hides the expert codes**, and runs it through `run_pipeline` exactly as an upload would go. For ~30% of reports (fixed seed) the join is varied: alternative header names, no headers, or one section dropped. Reported: **parser accuracy** (share of sentences assigned to the right section, and share of reports fully parsed) and headline macro-F1 on **clean vs varied** joins. A clean, correctly parsed join gives the tagger exactly the M4 input, so it is served from the cache.
- **Subsets added in v2:** reports with empty or missing Findings; reports with empty or missing Impression; reports where the parser found no sections.
- **Normal-claim count (M6, data fact):** the number of reports whose Impression is a "no acute"-type normal statement but whose expert codes are **not** `normal` only, per label. This rate is why every predicted No Finding is checked (§6.2, free checks part 3).
- **Verifier agent (v2, M7), pre-committed:**
  - final-label macro-F1 vs LLM only and vs LLM + verifier + Tier 2 (paired bootstrap). The agent is **kept** only if its F1 vs LLM + verifier + Tier 2 is not significantly lower.
  - labels changed: wrong → right vs right → wrong, per label; `suggested` labels that are correct vs wrong (the recall effect).
  - **the key result:** precision and F1 of `verified` / `verified_rules` labels vs `unverified` labels. If unverified labels are not clearly less accurate, the verification state carries no information, and that is reported.
  - escalation rate (share of reports sent to the agent), escalation precision, and the share of labels and reports ending `unverified`, on hedged vs clear reports. This replaces the v1 review rate in §10.
  - evidence agreement: how often the agent's evidence matches the tagger's (blind-first design).
  - No Finding precision before and after the normal check and the agent, and the number of predicted normals withheld, right vs wrong (secondary).
  - cost per report and in total; tool calls per report; caps hit.
- Pipeline metrics (v1, M5): tier distribution, repair success rate, mean repair tool calls, escalation precision, review rate on hedged vs clear reports.

### 8.2 Retrieval
- For each fold k: index the fold-k reports with evaluation model k (and with the base model), run the query sets, aggregate across folds.
- **Relevance from expert codes:** a report is relevant to a label query if the label is coded. **Attribute queries** ("small left effusion") are judged from code modifiers, e.g. `Pleural Effusion/left/small`. **Compositional queries** ("effusion without cardiomegaly") are judged by label logic.
- **Query sets:**
  - seen-label queries
  - **held-out-label** queries
  - **held-out-alias** queries
  - 30 hand-written attribute and compositional queries in `eval/queries/handwritten.yaml`
  - **report-to-report ("reports like this one"):** the query is a short Findings snippet of an **abnormal** report. A result is relevant if it shares **at least one abnormal label** with the query report (No Finding doesn't count, otherwise every normal report would be relevant to every other one). nDCG gain = the overlap of the two abnormal label sets (Jaccard). The query report and its exact duplicates are removed from the results. Normal-report queries are not scored.
- **Relevance always comes from expert codes, on the evaluation side only.** Indication text is never part of a query.
- **Metrics:** recall@10, nDCG@10, and **negation contamination@10** (the share of top-10 results whose only mentions of the finding are negated, per the eval detector). Measured **after each stage**: dense, +BM25, +rerank.

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | | | |
| base bge-small, report-level | | | |
| base bge-small, contextual sentences | | | |
| base bge-small + negated-sentence payload filter (no training) | | | |
| fine-tuned, contextual sentences | | | |
| fine-tuned + BM25 (RRF) | | | |
| + reranker | | | |

The **filter baseline** is the row fine-tuning must justify itself against. If the fine-tuned model doesn't beat it, that is reported as a negative result. It is expected to help most on held-out and free-text queries and on report-to-report similarity.

### 8.3 Agent
- **Question set** (`eval/agent_questions/`):
  - templates for counts, filters, similarity and unanswerable questions, each LLM-paraphrased into 3–5 variants
  - **40 hand-written** questions, including borderline unanswerable ones (age is redacted), "why was this exam done?" (indication) and "what supports <label> in report X?" (evidence)
- Run twice: against an **expert-label** table (isolates agent errors) and against the **out-of-fold predicted-label** table (end-to-end).
- **Metrics:** exact-answer accuracy, tool-choice accuracy, citation validity (checked in code), refusal precision/recall. No LLM-judged metrics.

### 8.4 System
- Cost per 1,000 reports, tiered vs "LLM for everything", on **all** and on **abnormal** reports.
- p50/p95 latency per endpoint.
- Crash-and-resume log: kill the worker mid-job and restart it.

**Null results** are reported as they are. Headline claims focus on the abnormal and negation subsets.

---

## 9. Repository structure

```
radlabel/
├── data_prep/              # download.py, parse_iu.py, map_and_stats.py, subset_stats.py, coding_policy.py,
│                           # build_dataset.py, audit_mapping.py
├── data/                   # git-ignored except mapping/*.yaml
│   ├── raw/  processed/  splits/
│   └── mapping/            # mesh_to_labels_v1.yaml, mesh_to_labels_strict.yaml (no report text)
├── src/radlabel/
│   ├── preprocess/         # parser.py (v2), text.py, sentences.py, negation.py, aliases.py, dedup.py
│   ├── labelling/          # extractor.py, verifier.py, rules.py, verifier_agent.py (v2), repair_agent.py (v1),
│   │                       # schema.py, tier0.py, normal_phrases.yaml
│   ├── pipeline.py         # run_pipeline(raw_text), the single entry point (v2)
│   ├── index/  agent/  ingest/  api/  llm/  db/
│   └── config.py, labels.py, results.py
├── training/               # build_pairs.py, train_embeddings.py
├── eval/                   # cv.py, labelling.py, retrieval.py, agent.py, system.py, bootstrap.py,
│   │                       # subsets.py, entry_point.py, report.py, pilot.py, m4_analysis.py, repair.py (v1),
│   │                       # lexicon.yaml, negex_termset.yaml, baselines/, queries/, agent_questions/
├── demo/app.py
├── deploy/
├── docs/model_card.md
├── tests/
├── artifacts/              # results/*.json, tables/*.md, mapping audit (git-ignored if it holds text)
├── models/                 # private, git-ignored
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── .env.example
├── .github/workflows/ci.yml
└── README.md
```

---

## 10. Results

_Generated from `artifacts/results/*.json` by `python -m eval.report` (`make report`). No number in this section is typed by hand._

_The results below are the v1 pipeline (M3–M5), including its human-review routing. v2 rows (parser, verifier agent) are added by M6 and M7._

<!-- results:start: generated by `python -m eval.report` from artifacts/results/*.json; do not edit -->

**Claim scope.** Supported: the LLM labelling pipeline improves over the implemented rule baseline on this dataset under this evaluation protocol. Not supported: clinical reliability.

Limitations that bound these numbers (details in §11):
- One institution (Indiana University, Open-i); reports from around 2013.
- Expert codes are positive-only.
- Hedged reports (279 unique texts) are excluded from the headline metrics.
- The mapping from MeSH codes to the 13 labels is lossy (results under mapping v1 and strict).
- Rare labels have small support, hence wide CIs.
- 7 reports refused by the Azure content filter are scored with the rule baseline's labels.
- The ground truth misses some clearly stated findings, so scores are a lower bound.
- Labels describe the report text, not the images.
- Review volume is 30.5% of reports (hedged 57.7%, clear 27.8%), too high for production use; reducing it is future work.

### Labelling (§8.1)

Out-of-fold, one report per exact text; hedged and Tier 1 pilot reports excluded unless stated; 95% bootstrap CIs over clusters. Scoring: `present` = positive, except in the sensitivity row.

| Metric | Rule baseline | LLM only | LLM + verifier | LLM + verifier + Tier 2 | run_pipeline, clean join (M6) | run_pipeline, 30% varied joins (M6) |
|---|---|---|---|---|---|---|
| Headline macro-F1, 9 labels (v1) | 0.838 (0.823–0.850) | 0.862 (0.848–0.875) | 0.860 (0.845–0.873) | 0.866 (0.851–0.878) | 0.860 (0.845–0.873) | 0.848 (0.833–0.861) |
| Headline macro-F1, 9 labels (strict) | 0.829 (0.814–0.843) | 0.863 (0.848–0.877) | 0.861 (0.846–0.875) | 0.868 (0.853–0.881) | 0.861 (0.846–0.875) | 0.850 (0.835–0.865) |
| Pooled rare micro-F1 (v1) | 0.742 (0.677–0.805) | 0.831 (0.771–0.882) | 0.838 (0.777–0.889) | 0.829 (0.769–0.882) | 0.838 (0.777–0.889) | 0.824 (0.764–0.875) |
| negation_only FP rate (pooled) | 41 / 6164 (0.0067) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) | 6 / 6164 (0.0010) |
| *Sensitivity, not headline:* macro-F1 (v1) with `uncertain` = positive for all labels | 0.839 (0.825–0.852) | 0.853 (0.839–0.866) | 0.853 (0.839–0.866) | 0.861 (0.848–0.874) | 0.853 (0.839–0.866) | 0.841 (0.828–0.855) |
| *Sensitivity, not headline:* macro-F1 (v1), all reports incl. Tier 1 pilot | 0.837 (0.823–0.850) | 0.862 (0.848–0.876) | 0.860 (0.846–0.873) | 0.866 (0.852–0.878) | 0.860 (0.846–0.873) | 0.848 (0.834–0.861) |

Per-label tables: `artifacts/tables/labelling_*.md`.

### Paired differences

Headline macro-F1 (9 labels, v1), same out-of-fold reports and the same 1,000 cluster resamples for both systems.

| Comparison | Difference (95% CI) | CI excludes 0 |
|---|---|---|
| LLM only − rule baseline | 0.025 (0.010–0.040) | yes |
| LLM + verifier − LLM only | -0.002 (-0.004–-0.001) | yes |
| LLM + verifier + Tier 2 − LLM + verifier | 0.006 (0.003–0.009) | yes |
| LLM + verifier + Tier 2 − rule baseline | 0.028 (0.013–0.043) | yes |
| LLM + verifier + Tier 2 − LLM only | 0.003 (0.000–0.007) | no |
| run_pipeline, clean join − LLM + verifier | 0.000 (0.000–0.000) | no |
| run_pipeline, varied joins − clean join | -0.012 (-0.017–-0.007) | yes |

**Reading.** The verifier's hedge downgrade costs 0.002 macro-F1 and Tier 2 recovers 0.006, so the full pipeline **matches** LLM-only macro-F1 (difference 0.003 (0.000–0.007); the 95% CI includes 0). The guardrails do not improve F1 over LLM only. What the guardrails add is label-level correction (Tier 2: 29 labels wrong → right vs 5 right → wrong) and routing of uncertain cases to human review (30.5% of reports).

### Pipeline

- Tier 1: 3,086 unique report texts labelled by gpt-4.1-mini-2025-04-14 (prompt `tier1-v1`, temperature 0); invalid outputs 0; content-filtered 7.
- Tier 0: 0 out-of-fold matches (exact duplicates share a fold).
- Verifier FAIL → Tier 2: 211 reports (6.8%).
- Tier 2 repair agent (gpt-5-mini-2025-08-07, prompt `repair-v1`): fix accepted after re-verification for 78 of 211 (37.0%); mean tool calls 1.97; labels changed 75: wrong → right 29, right → wrong 5 (present = positive vs expert codes).
- Routing: Tier 1 accepted 2,104, Tier 2 repaired 42, review 940 (30.5%).
- Review rate: hedged 57.7% vs clear 27.8%. Escalation precision (Tier 1 labels disagree with the expert codes): Tier 2 64.9%, review 50.5%, base rate 25.0%.
- LLM spend: Tier 2 calls $0.26. Reruns are served from the cache at $0.

### Through the entry point (M6)

Labels produced by `run_pipeline(raw_text)` (parse → tag → verifier), as an upload would be. Without headers the parser can't separate sections, so the whole text, including the indication, is read as Findings.

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

### Verifier agent: escalation and dev slice (M7, before the full run)

Free checks on all 3,086 unique reports (clean join, tagger from cache, no agent call, $0): **1,290 reports escalate (41.8%)**; hedged 67.0% vs clear 39.3%; 1,777 labels. 7 content-filtered reports end `unverified` without an agent call.

| Reason | Reports | Labels | Reports with only this reason |
|---|---|---|---|
| section rule | 778 | 911 | 153 |
| recall scan | 576 | 617 | 0 |
| evidence mentions label | 424 | 463 | 265 |
| normal check | 278 | 278 | 160 |
| hedge consistency | 105 | 125 | 58 |
| negation consistency | 14 | 16 | 8 |

Escalation precision (tagger labels disagree with the codes): reports 44.3%, labels 32.6%; base rate 25.0%; not escalated 11.2% (201 reports). Predicted No Finding 577: normal check passed 299 (precision 99.0%), failed 278 (precision 99.3%).

Verifier agent on the **dev slice only** (38 escalated of 102 Tier 1 pilot reports; not a headline result), prompt `verifier-v2` (frozen): labels changed vs the codes wrong → right 11, right → wrong 3; suggested correct 3, wrong 3; verified 24, corrected 11, unverified 4; mean tool calls 1.87; $0.0017 per report. Estimated full run: 1,252 reports, $2.10.

<!-- results:end -->

## 11. Limitations

- **Claim scope:** the results support that the LLM labelling pipeline improves over the implemented rule baseline on this dataset under this evaluation protocol. They do **not** support clinical reliability.
- Single institution (Indiana University, Open-i), reports from around 2013.
- Expert codes are positive-only; hedged findings are coded inconsistently. Uncertainty accuracy and evidence-span accuracy are **not claimed**.
- Hedged reports are excluded from the headline metrics (§4.3); they are reported separately under both uncertainty policies.
- Mapping v1 is lossy, and two standard labels are dropped. Results are shown under v1 and strict.
- Some clearly stated findings were not coded, so the raw scores are a lower bound (§4.6).
- Reports refused by the Azure content filter get no LLM output; they are scored with the rule baseline's labels (v1: routed to review; v2: their labels are `unverified`).
- v1 routed too many reports to human review for production use (the v1 review rate in §10). v2 replaces the review queue with the verifier agent and an `unverified` mark; whether that mark is informative is measured in M7 (§8.1).
- The verifier agent reads the same report text as the tagger, so `verified` is a consistency check by a second model with different tools, not independent proof. Verbatim evidence shows the sentence exists, not that it caused the label.
- The evaluation joins IU's pre-split sections into one text; real uploads are messier, so the varied-join test only partly measures the parser (a held-out set of header names the parser doesn't know is reported separately, §10).
- When the parser finds no sections, the whole text is read as Findings, so the tagger **also reads the indication** (it can't be separated). Such outputs carry `sections_identified: false`, visible to the verifier agent and in the UI.
- About 11% of reports have redactions next to finding terms.
- Subsets and noise adjustment depend on a rule-based eval detector, deliberately separate from the pipeline's own.
- Rare labels have 27–53 positives in total, hence wide CIs.
- Labels describe the report text, not the image.
- The CC BY-NC-ND licence keeps models and processed data private.
- Pipeline aliases and the eval lexicon share standard vocabulary (same author); independence comes from expert-code ground truth and separate negation detectors.

---

## 12. Roadmap

| ID | Delivers | Acceptance check | Status |
|---|---|---|---|
| **M0** | Repo skeleton, `pyproject.toml`, `Makefile`, `.gitignore`, `config.py` matching `.env.example`, Docker Compose (postgres, qdrant, redis), CI running lint + tests | Tests pass; `docker compose up` is healthy | done |
| **M1** | `make data`: download with SHA-256 check, parse, exclusions, `[REDACTED]`, sentences, dedup clusters, mapping v1 + strict, Other Abnormality, mapping audit, subsets (§4.8), `data_card.json` | Numbers match §3.3 and §4.4 on exact texts; cluster count 3,073; subset counts match `subset_stats.py`; audit written | done |
| **M2** | `eval/cv.py`: iterative stratification over clusters, 5 folds + inner validation; bootstrap CI utility | Every label's positives spread across folds within ±2 of equal share; no cluster spans two folds (test) | done |
| **M3** | Pipeline preprocessing + negation, Pydantic schema, verifier + unit tests, rule baseline, labelling eval on out-of-fold rule-baseline predictions | §8.1 table for the rule baseline | done |
| **M4** | LLM client (OpenAI/Azure, cache, cost ledger, FakeLLM), Tier 0 (per fold), Tier 1 extractor, labelling eval for LLM and LLM + verifier | §8.1 rows for both; reruns cost $0 from cache | done |
| **M5** | Tier 2 repair agent (LangGraph, tools, limits), review routing, routing metrics (v1) | Repair success rate, escalation precision, hedged vs clear review rates in results | done |
| **M6** | Parser (`parser.py`), `run_pipeline(raw_text)` (parse → tag → current verifier until M7), evaluation through the entry point with clean and varied joins, empty-section counts and subsets, normal-claim count ("no acute" impressions with non-normal codes), hedge-check consistency fix ("borderline"/"mild" not a hedge where the label definition counts it as present) | Parser accuracy and clean vs varied macro-F1 in results; leakage test covers `run_pipeline`; correctly parsed reports hit the Tier 1 cache ($0) | planned |
| **M7** | Free checks with v2 escalation rules + recall scan (rule baseline as second reader) + normal check on every predicted No Finding; ReAct verifier agent (tools, blind first, caps); dev-slice prompt development and freeze; cost estimate before the full run | §8.1 v2 rows: F1 and paired bootstrap vs v1 columns, verified vs unverified accuracy, escalation and unverified rates, change counts; leakage test for the agent | planned |
| **M8** | Postgres `labels` (with verification state and evidence) from out-of-fold v2 outputs; Qdrant indexing (report + contextual sentence points, sections, indication field, BM25); RRF; aggregation; retrieval eval incl. report-to-report queries | BM25 / base / contextual / filter rows of §8.2; test asserting no expert labels or indication in the index points | planned |
| **M9** | Negation-aware embedding fine-tuning: pair building, `CachedGISTEmbedLoss` per fold, held-out evaluation, serving model on all data (stored privately); optional reranker row; switch the agent's `find_by_meaning` tool to the fine-tuned model | Fine-tuned rows of §8.2, with seen vs held-out split, compared against the filter baseline | planned |
| **M10** | Query agent + tools (incl. indication and label evidence) + guardrails, question set (templates, paraphrases, 40 hand-written), agent eval on both label tables | §8.3 table | planned |
| **M11** | Ingestion worker (queue, retries, cost cap, resume), FastAPI endpoints, Redis cache + rate limit, tracing, Gradio demo with verification badges, attribution, deploy files, model card, CI regression eval on frozen cached outputs | End-to-end: ingest 200 reports, kill and restart the worker, job completes; `/label` and `/ask` work; CI green; demo runs locally | planned |
| *Stretch* | CheXpert labeler Docker baseline; noise-adjusted scores; delete-the-cited-sentence test (does the label change?); CheXpert Plus scale ingest (machine labels, throughput and cost only, never accuracy) | — | planned |

The roadmap was revised on 21 Oct 2026 (v2): the old M6–M11 (index, embedding training, reranker + LLM judge, query agent, serving) were reordered after the new parser and verifier-agent milestones; the LLM-judge stage, the review table and the QLoRA extension were dropped.

---

## 13. Extensions

- **RadGraph (PhysioNet):** radiologist-annotated uncertainty and spans, evaluated with local models only.
- **MCP server** exposing the agent tools for reuse from other agents.

## 14. References

- Demner-Fushman D. et al. *Preparing a collection of radiology examinations for distribution and retrieval.* JAMIA 23(2):304–310, 2016.
- Irvin J. et al. *CheXpert.* AAAI 2019.
- Jain S. et al. *RadGraph.* NeurIPS Datasets & Benchmarks 2021. arXiv:2106.14463.
- Nützel F., Dombrowski M., Kainz B. *Ontology-Based Concept Distillation for Radiology Report Retrieval and Labeling.* MLMI @ MICCAI 2025. arXiv:2508.19915.
- Yao S. et al. *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023.
- Sechidis K., Tsoumakas G., Vlahavas I. *On the Stratification of Multi-Label Data.* ECML PKDD 2011.
- Anthropic. *Introducing Contextual Retrieval* (engineering blog).
- Reimers N., Gurevych I. *Sentence-BERT.* EMNLP 2019.
- Solatorio A. *GISTEmbed: Guided In-sample Selection of Training Negatives.* 2024.
- Chapman W. et al. *A Simple Algorithm for Identifying Negated Findings and Diseases in Discharge Summaries (NegEx).* J Biomed Inform, 2001.

## 15. Licence

The code is released under the MIT licence (`LICENSE`), copyright Vibhu Gupta. The Indiana University chest X-ray reports (Open-i, NLM) and anything derived from them (labels, caches, models) are CC BY-NC-ND 4.0 and are not included in this repository (§4.1).
