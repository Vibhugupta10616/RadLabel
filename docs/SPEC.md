# RadLabel

**Chest X-ray report intelligence: verified findings with evidence, and questions answered with citations, over the user's own reports. Full specification for development; the short overview is the [README](../README.md).**

**Status:** done: M0–M9 (v1 labelling M3–M5; v2 parser, single `run_pipeline` entry point and ReAct verifier agent M6–M7; evaluation search index and retrieval evaluation M8; negation-aware embedding fine-tuning M9, used for search). Next: M10 website (M10a backend, M10b evaluation, M10c frontend, started on branch `m9c-frontend`), M11 deployment (Vercel + Hugging Face). Results: [RESULTS.md](RESULTS.md); roadmap §12.

> Engineering and research project. **Not a medical device and not for clinical use.** Labels are derived from report text, not from images.

---

## 1. What this project is

**Product.** A user uploads one chest X-ray report or a patient series. For each report RadLabel returns the 13 findings (§4.4) with sentence-level evidence and a verification badge per label. The user can then ask questions about one report, or across all of their own uploads (RAG over the session), answered with report-and-sentence citations. **Uploads are processed in memory and never stored.** The Indiana University (IU) reports and their index are the **evaluation test bed only**; users never search them.

| Component | What it does |
|---|---|
| **Labelling pipeline** | Takes raw report text, splits it into sections, and extracts findings with sentence-level evidence. Free deterministic checks and a rule-based second reader check every label; a **ReAct verifier agent** handles only the reports where they fail or disagree, and marks every label **verified, corrected, suggested or unverified**. |
| **Questions** | About one report: the LLM answers from that report's sentences. Across all uploads: **session RAG** retrieves the user's own sentences (dense embeddings + BM25) and the LLM answers from them. Every answer cites `report_no:sentence_id`, checked in code, or refuses. |
| **Negation-aware embeddings** (M9) | bge-small fine-tuned on plain sentences so that "no effusion" is not retrieved for "effusion"; evaluated on the IU test bed (§8.2). It passed the pre-committed use rule, so search and session RAG use it ([RESULTS.md](RESULTS.md)); the verifier agent keeps the base model. |
| **Website** | FastAPI session API and a React frontend (§6.5, M10); deployed on Vercel (frontend) and a Hugging Face Docker Space (backend) (M11). |

Every component is evaluated against **expert-coded ground truth** on the IU reports using **stratified 5-fold cross-validation**.

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
- **The website serves the user's own uploads only.** IU material appears only in the built-in sample (unchanged report text, with attribution) and in aggregate results. The attribution notice is shown in the website footer: *"Indiana University Chest X-ray Collection (Open-i, NLM), CC BY-NC-ND 4.0."* Evidence highlighting is a UI overlay on unchanged text. The website is free (non-commercial).
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
  - v1 (M5) measured the same with a review queue (the v1 review rate in [RESULTS.md](RESULTS.md)).
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
- M1 writes the pair counts per label (all, and abnormal-only) to `data_card.json`. There are no SPEC reference numbers for these, so they become the reference once the owner approves them.

---

## 5. Architecture

```
upload (one report or a series: pasted text, .txt or .pdf) ──► session (in memory, expires; nothing stored)
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
     └───────────────────────────────────┬──────────────────────────────────────┘
                                         ▼
     session: reports, sentences, final labels (status, evidence, verification, corroboration)
            │                                              │
            ▼                                              ▼
   question, scope "report"                        question, scope "all"
   → LLM over that report's sentences              → session RAG: dense (bge-small; fine-tuned after
     and labels                                       M9 if it passes §8.2) + BM25 over the session's
            │                                         sentences, RRF → top sentences → LLM
            └──────────────────┬───────────────────────────┘
                               ▼
            answer with citations (report_no:sentence_id, checked in code), or a refusal
                               ▼
     FastAPI session API (Hugging Face Docker Space)  ◄──►  React frontend (Vercel)

Evaluation test bed (offline, never served): IU reports → Postgres `labels` + Qdrant index (M8)
→ retrieval evaluation (§8.2) and embedding fine-tuning (§6.3).
```

Invariants:
1. **Serving never reads expert labels.** The session API, `run_pipeline`, the verifier agent and session RAG see report text and pipeline predictions only; so do the evaluation index's tables and payloads. Unit tests enforce this.
2. **One entry point.** `run_pipeline(raw_text)` is the only way labels are produced: the evaluation scripts and the session API both call it. Evaluation feeds it joined report text with the expert codes hidden (§8.1).
3. **Evaluation models vs serving model.** CV trains 5 evaluation embedding models (one per fold) for honest metrics (M9). The serving model is trained once on all reports after evaluation and stored privately. The verifier agent always uses the base model.
4. **Every LLM call is cached**, keyed by (model snapshot, prompt hash, input hash), so evaluation is reproducible and CI needs no API calls.
5. **No separate LLM-judge steps** anywhere in the pipeline or in retrieval. Judgment happens inside the verifier agent (with its tools) and in the answer step, whose citations are checked in code.
6. **Uploads are never stored.** Sessions live in process memory and expire; no database writes and no logs of report text.

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
     "verification": "verified", "corroboration": "both"},
    {"label": "Atelectasis",      "status": "present", "evidence": ["F3"],
     "verification": "suggested", "corroboration": "findings",
     "reason": "tagger said not_mentioned; F3 'atelectasis at the left base'"}
  ],
  "tier": 1,
  "agent_used": true,
  "check_messages": []
}
```
`verification` per label (v2). "Verified" means **checked to faithfully reflect the report text**; it says nothing about the image or about whether the report itself is right (§11).
- `verified_rules`: all free checks passed; no agent call.
- `verified`: the agent found supporting evidence itself.
- `verified_impression_only`: as `verified`, but the report has no Findings, so only the Impression could be checked.
- `corrected`: the agent changed the tagger's status.
- `suggested`: a finding the tagger missed, added by the agent.
- `unverified`: the agent could not confirm the label (with `reason`). This replaces v1's human-review queue.

`corroboration` (M7, code only; never used for routing), for every `present` or `suggested` label: whether its evidence comes from `both` sections, `findings` only, `impression` only, or `none` (no evidence sentence). Precision by level is reported in [RESULTS.md](RESULTS.md).

Evidence is always sentence IDs that exist in the report, and the sentence text is returned verbatim (string-checked), so evidence can't be invented. Evidence proves the sentence exists, not that it caused the label.
- **Output vs evaluation policy.**
  - System output is four-valued: `present | uncertain | absent | not_mentioned`, representing what the report text says.
  - Headline evaluation binarises it: `present` = positive, everything else = negative, against the expert codes. The "`uncertain` = positive" row in [RESULTS.md](RESULTS.md) is a sensitivity check, not the headline metric (on the `hedged` subset both policies are reported, §4.3).
  - The verifier's hedge downgrade (`present` → `uncertain`) is product policy. In v1 its cost in the headline metric (LLM + verifier − LLM only in [RESULTS.md](RESULTS.md)) came mostly from "borderline cardiomegaly". The Tier 1 label definitions state that mild or borderline enlargement **is** Cardiomegaly, so in v2 the hedge check no longer treats wording that a label's definition counts as present ("borderline", "mild") as a hedge. This is a consistency fix between two existing rules, not tuning on test results.
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

- **Free checks, part 2: recall scan** (v2, M7). The rule labeller (`src/radlabel/labelling/rules.py`, also the rule baseline: aliases + pipeline negation, no LLM) runs on every report as a cheap second reader. For each label where the rules say `present` and the tagger says `absent` or `not_mentioned`, the report escalates. This targets the tagger's real weakness: its precision is ~0.99 on several labels, but its recall is lower ([RESULTS.md](RESULTS.md)). The rules have their own errors (e.g. "upper limits of normal" read as enlargement), which is why the agent decides, not the rules.
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
  - **Tools:** `find_by_alias(label)`, `find_by_meaning(label)` (sentence embeddings; always the base model, since the agent is frozen), `check_negation(sentence_id)`, `compare_sections(label)`, `check_redaction(sentence_id)`, `get_label_definition(label)` (the frozen label policy, the same definitions as the tagger prompt), `normal_check()` (the same check as free-check part 3, returning which regions are covered and which sentences look abnormal), `submit(labels)`.
  - **Output:** for each label it was asked about: `verified`, `corrected`, `suggested` or `unverified`, with evidence IDs (string-checked) and a one-line reason. Labels it wasn't asked about keep `verified_rules`.
  - **Limits:** at most 8 tool calls and a token cap per report; on hitting a cap, or the budget, the open labels end `unverified` with the reason.
  - **Empty Findings:** it uses the text that exists; No Finding confirmed from the Impression alone is `verified_impression_only`.
  - **Prompt development** only on the **dev slice** (the 102 Tier 1 pilot reports, already excluded from headline metrics). The prompt is frozen (hash test) before the full run. Label definitions come from the frozen policy; no rule is added from looking at test-fold errors.
  - **Independence:** the agent shares the report text with the tagger, so `verified` is a consistency check by a second model with different tools, not independent proof. Reported: how often the agent's evidence matches the tagger's.
- **v1, historical (M5):** a Tier 2 repair agent (`repair_agent.py`) fixed FAIL labels only, and anything still failing or flagged went to a `review` table (Tier 3). Its results stay in [RESULTS.md](RESULTS.md) as the comparison column. v2 replaces both with the verifier agent.

**Baselines** (`eval/baselines/`):
- `rule_baseline.py`: alias match + pipeline negation, no LLM. Always available. A thin wrapper around `src/radlabel/labelling/rules.py`, so pipeline code never imports from `eval/`.
- `chexpert_labeler/`: the CheXpert labeler in its own Docker image. **Stretch:** if its dependencies fail to build, document the attempt and continue.
- LLM extractor without the verifier and repair (ablation).
- No QLoRA / local-model tagger (dropped 21 Oct 2026).

### 6.3 Index, embeddings and fine-tuning (`src/radlabel/index/`, `training/`)
The IU index is the **evaluation test bed** (M8, §8.2) and the source of training pairs; users never search it.
- **Points:** one per report (Findings + Impression) and one per sentence, each with its section name (`unknown` if the parser found no sections). **Sentences are embedded without the predicted-label prefix**: in M8, plain sentences scored pooled nDCG@10 0.564 vs 0.491 with the prefix ([RESULTS.md](RESULTS.md)). The prefix and filter rows stay in the evaluation as comparisons. The index builder writes plain sentence points by default since M9 (`INDEX_SENTENCE_PREFIX` keeps the M8 option).
- **Payload:** report_id, sentence_id, section, predicted labels with their `verification` state, pipeline negation tags, and the evidence sentence IDs per label.
- **Indication:** stored only in Postgres (`reports.indication`); never embedded, never in an index point, never in a retrieval-evaluation query.
- **Retrieval:** dense (cosine) + BM25 (sparse vectors with IDF computed at index time), fused with RRF (k = 60); deterministic tie-breaking. Optional cross-encoder reranker. No LLM-judge stage.
- **Aggregation:** sentence hits → reports by **max score per report**.

**Embedding fine-tuning (M9, done)** (`training/build_pairs.py`, `training/train_embeddings.py`):
- Base model `BAAI/bge-small-en-v1.5`; `--device auto` (CPU works; GPU is faster).
- Pairs are built **from training folds only**, on **plain sentences (no prefix)**, with expert codes for relevance and the pipeline negation tags for hard negatives:
  - query → report: positive = coded finding; hard negative = report mentioning it only negated
  - query → sentence
  - report → report, sampled **from abnormal reports only**: positive = same label set; hard negative = similar wording with a negated key finding
- Queries come from label names plus **non-held-out** aliases. **Held-out labels** (Fracture, Lung Lesion, Pleural Other) are never used in training, and neither is any alias text that is held out for **any** label (the same words can serve two labels).
- Report → report pairs (optional) were not built.
- **Loss:** `CachedGISTEmbedLoss` with the base model as guide, which filters in-batch false negatives. Fallback: `MultipleNegativesRankingLoss` with a sampler allowing each label once per batch.
- 1–3 epochs, selected by inner-validation nDCG@10 (report level, training-label queries); fixed seed; `--device auto` (CUDA with bf16 when available). The serving model uses the most frequent best epoch across folds.
- Output: `models/eval/fold_{k}/` and `models/serving/`, **private, git-ignored**.
- **Use:** the fine-tuned model is for **search and session RAG only**, and only if it passes the pre-committed rule of §8.2. The verifier agent's `find_by_meaning` stays on the base model.

### 6.4 Questions: one report or session RAG (`src/radlabel/api/`)
- **Scope "report":** the question, that report's sentences (with IDs) and its final labels go to the LLM (the Tier 1 deployment, gpt-4.1-mini); it answers or refuses, citing sentence IDs.
- **Scope "all":** **session RAG** over the user's own uploads: the session's sentences are embedded (plain, no prefix; base bge-small, or the fine-tuned model once M9 passes §8.2) and BM25-indexed in memory, fused with RRF; the top sentences, with their `report_no`, go to the LLM, which answers with `report_no:sentence_id` citations or refuses.
- **Guardrails:** every citation is checked in code (the sentence exists in that report; otherwise the answer becomes a refusal); refusal when retrieval finds nothing relevant; out-of-scope refusal (CT, age, which is redacted, treatment or diagnosis advice); questions of at most 500 characters; every LLM call through `radlabel.llm` (cached, cost-capped).
- There is no query agent over the IU corpus and no SQL over the evaluation tables.

### 6.5 Session API, frontend, deployment (`src/radlabel/api/`, `web/`)
- **Session API** (FastAPI). The contract is in `web/README.md` on branch `m9c-frontend`:
  - `POST /api/session` → `{session_id}`
  - `POST /api/session/{id}/reports` (multipart: pasted text, `.txt` / `.pdf` files up to 50, or the built-in sample) → the reports with their sections, sentences and all 13 labels (status, verification, corroboration, evidence, reason)
  - `POST /api/session/{id}/ask` with `scope: "report" | "all"` (`report_no` for scope "report") → an answer or a refusal, with citations
  - `GET /api/session/{id}/timeline` → each label's status across the session's reports
  - `GET /health`, `GET /ready`; errors as `{detail}` in plain language
- **In memory, nothing stored:** sessions are held in process memory and expire; no Postgres or Redis writes of report text; logs carry no report text.
- **Cost:** every LLM call goes through `radlabel.llm` with the `MAX_LLM_USD` cap. When the cap is reached, a report gets the rule labeller's labels (`unverified`, `rules_only: true`) instead of LLM calls.
- **Limits:** per-client rate limits and request-size limits.
- **Frontend** (React + Vite + TypeScript + Tailwind; branch `m9c-frontend`, M10c): landing, upload and results pages; labels with verification badges and evidence highlighted on the unchanged text; findings over time across a series; questions with clickable citations; attribution footer and a "not a medical device" notice.
- **Deployment (M11):** frontend on **Vercel**; backend on a **Hugging Face Docker Space** (FastAPI). Azure OpenAI keys are **Space secrets**, never in the image or the repository. Private models (fine-tuned weights) are **never baked into the image**; they are pulled at startup from a private store. The IU data and the LLM caches are never deployed.
- **Production checklist:** multi-stage slim Dockerfile, non-root user, `HEALTHCHECK` on `/health`, no data or weights in the image; config via pydantic-settings; CI with ruff, mypy, tests and the cached regression evaluation; smoke test after deploy (`/health`, one upload, one ask).

---

## 7. Configuration

All settings live in **`.env.example`** at the repo root (committed, no secrets). Copy it to `.env` (git-ignored) and fill in the key, the API version, the model versions and the per-deployment TPM. `src/radlabel/config.py` loads them with pydantic-settings and **fails fast with a clear message** if a required value is missing.

| Group | Variables |
|---|---|
| Provider | `LLM_PROVIDER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `OPENAI_API_KEY` |
| Deployments per role (§7.1) | `AZURE_OPENAI_DEPLOYMENT` (Tier 1), `…_FALLBACK_DEPLOYMENT`, `…_REPAIR_DEPLOYMENT` (the verifier agent; the name is kept from v1), `…_CHEAP_DEPLOYMENT` (paraphrasing), `…_EMBED_DEPLOYMENT` (baseline row only), plus a `…_VERSION` for each |
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

**Version pinning.** Each deployment uses version update policy **"Upgrade when expired"** (`OnceCurrentVersionExpired`). The version stays fixed for the whole project, and only at retirement does the deployment move to the new default instead of failing with HTTP 410. ("No auto upgrade" would make the website break at retirement.) The LLM client also logs the `model` field returned by **every response** and raises a warning if it changes between calls, which catches silent upgrades. Retirement dates are checked in each deploy dialog before use.

**LLM deployments** (all Global Standard; the model version is recorded in every results file):

| Deployment | Quota (TPM) | Used for | Why |
|---|---|---|---|
| `gpt-4.1-mini` | 5M | Tier 1 labelling (~3,100 reports) and answers to questions (ask) | Non-reasoning, temperature 0, reliable structured output, cheap → reproducible bulk work |
| `gpt-5-mini` (already deployed, 375K TPM allocated) | 1M | Verifier agent (v2; Tier 2 repair agent in v1) | Reasoning model, better at multi-step tool use; runs only on escalated reports |
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

**LLM spend:** $5.43 in total, from the cost ledger (`artifacts/llm_cache/ledger.jsonl`), all milestones up to M8 (M8 made no LLM calls). The free checks are code, so they reuse cached outputs. The website evaluation (M10b) is estimated before any paid run. Hard stop: $10 total (above).

**GPU accelerator quota** (8 each of A100 80GB, H100 80GB, H200 141GB, MI300 192GB). **The quota isn't the constraint; the credit is**, since GPU time costs several dollars per hour. Policy:

| Task | Compute | Note |
|---|---|---|
| Embedding fine-tuning (bge-small, 5 folds + serving model) | CPU or Kaggle T4 by default; **optionally 1× A100 80GB** as an Azure ML job | Small model; an A100 finishes all runs in minutes. Use a compute cluster with **min nodes = 0**, so it scales to zero after the job. |
| Serving the website (API and session RAG) | **No GPU** | The deployed system uses the Azure OpenAI APIs and CPU embeddings. |
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
  - escalation rate (share of reports sent to the agent), escalation precision, and the share of labels and reports ending `unverified`, on hedged vs clear reports. This replaces the v1 review rate in [RESULTS.md](RESULTS.md).
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
  - 30 hand-written attribute and compositional queries in `eval/queries/retrieval_v1.yaml` (spec frozen before the first run; query list in `retrieval_v1_queries.json`)
  - **report-to-report ("reports like this one"):** the query is a short Findings snippet of an **abnormal** report. A result is relevant if it shares **at least one abnormal label** with the query report (No Finding doesn't count, otherwise every normal report would be relevant to every other one). nDCG gain = the overlap of the two abnormal label sets (Jaccard). The query report and its exact duplicates are removed from the results. Normal-report queries are not scored.
- **Relevance always comes from expert codes, on the evaluation side only.** Indication text is never part of a query.
- **Metrics:** recall@10, nDCG@10, and **negation contamination@10** (the share of top-10 results whose only mentions of the finding are negated, per the eval detector). Measured **after each stage**: dense, +BM25, +rerank.

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | | | |
| base bge-small, report-level | | | |
| base bge-small, sentences without prefix (pure embedding) | | | |
| base bge-small, no prefix + negated-sentence filter | | | |
| base no-prefix sentences + BM25 (RRF) | | | |
| base bge-small, contextual sentences (predicted-label prefix) | | | |
| base bge-small + prefix + negated-sentence filter | | | |
| base contextual sentences + BM25 (RRF) | | | |
| fine-tuned, sentences without prefix (pure embedding) | | | |
| fine-tuned + the best base combination's setup (full system) | | | |
| + reranker (optional) | | | |

**Best base combination** (owner rule, fixed before the run): the base row with the highest pooled nDCG@10; if the top two are within each other's 95% CI they are tied and the simpler one is chosen (order in `eval/queries/retrieval_v1.yaml`). The result is in [RESULTS.md](RESULTS.md).

**How fine-tuning (M9) is judged, two ways (owner, 22 Oct 2026):**
- **Pure embedding effect:** fine-tuned vs base, both on sentences **without** the predicted-label prefix.
- **Full system:** fine-tuned with the best base combination's setup vs the best base combination.

**Pre-committed use rule:** the fine-tuned model is used for search and session RAG only if its pooled nDCG@10 paired difference vs base (no prefix) is **not significantly negative** (95% CI upper bound ≥ 0) **and** its negation contamination@10 is **not higher**. Otherwise the base model stays, and that is reported as a negative result.

The contextual prefix names the **predicted** labels, so the prefix and filter rows partly reflect the labelling pipeline's output, not only the embeddings: once the "No X" sentences are filtered out, sentences whose prefix mentions X come from reports predicted positive for X. Fine-tuning is expected to help most on held-out and free-text queries and on report-to-report similarity.

### 8.3 Website evaluation (M10b)
- **Single-report questions** on the dev slice (the 102 Tier 1 pilot reports, never in headline metrics): the **20 frozen questions** in `docs/m9b_handwritten_questions.md` (fixed before any results), each with its expected answer derived from the expert codes (v1, `present` = positive). Scored automatically: answer accuracy, correct refusal or "not stated" on unanswerable questions, citation validity (checked in code).
- **Cross-report questions:** session RAG vs **all reports in the prompt**, on synthetic batches of **3, 10, 30 and 50** out-of-fold reports (fixed seed), with the scope-"all" questions of the same file: accuracy, citation validity, tokens and cost per request. This shows from which batch size RAG is needed.
- No LLM-judged metrics. Cost is estimated before any paid run.

### 8.4 Latency and cost
- p50/p95 latency per request: upload (per report), ask scope "report", ask scope "all" by batch size.
- Cost per request and per 1,000 reports: tiered (agent only on escalated reports, from the M7 ledger) vs the agent on every report.

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
│   ├── index/  api/  llm/  db/
│   └── config.py, embeddings.py, labels.py, results.py
├── training/               # build_pairs.py, train_embeddings.py
├── eval/                   # cv.py, labelling.py, retrieval.py, index_build.py, verifier_agent.py, bootstrap.py,
│   │                       # subsets.py, entry_point.py, report.py, pilot.py, m4_analysis.py, repair.py (v1),
│   │                       # lexicon.yaml, negex_termset.yaml, baselines/, queries/
├── web/                    # React frontend (M10c; branch m9c-frontend)
├── deploy/                 # Dockerfile for the Hugging Face Space, Vercel settings (M11)
├── docs/                   # SPEC.md, RESULTS.md (generated), evaluation_notes.md, STATUS.md, model_card.md
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

All results are generated into [RESULTS.md](RESULTS.md) by `python -m eval.report` (`make report`) from `artifacts/results/*.json`; the README carries a short generated summary. No number in either is typed by hand.

---

## 11. Limitations

- **Claim scope:** the results support, on this dataset under this evaluation protocol, that the LLM labelling pipeline improves over the implemented rule baseline, that the v2 pipeline (LLM + free checks + verifier agent) improves over v1 and over LLM only, and that verified labels are far more accurate than unverified ones ([RESULTS.md](RESULTS.md)). They do **not** support clinical reliability.
- Single institution (Indiana University, Open-i), reports from around 2013.
- Expert codes are positive-only; hedged findings are coded inconsistently. Uncertainty accuracy and evidence-span accuracy are **not claimed**.
- Hedged reports are excluded from the headline metrics (§4.3); they are reported separately under both uncertainty policies.
- Mapping v1 is lossy, and two standard labels are dropped. Results are shown under v1 and strict.
- Some clearly stated findings were not coded, so the raw scores are a lower bound (§4.6).
- Reports refused by the Azure content filter get no LLM output; they are scored with the rule baseline's labels (v1: routed to review; v2: their labels are `unverified`).
- v1 routed too many reports to human review for production use (the v1 review rate in [RESULTS.md](RESULTS.md)). v2 replaces the review queue with the verifier agent and an `unverified` mark. The mark is informative (verified labels are far more accurate than unverified ones), and far fewer reports carry it than went to v1 review, but the two rates are **not like for like**: v1 sent a whole report to review for any remaining failure or escalating flag, while v2 marks only the labels the agent could not settle after checking the report ([RESULTS.md](RESULTS.md)).
- The verifier agent changes many labels **in both directions** (more wrong → right than right → wrong, but many of both), and its `suggested` labels are right only about half the time (precision in [RESULTS.md](RESULTS.md)). Known issue: on Consolidation it breaks far more labels than it fixes ([RESULTS.md](RESULTS.md)); a candidate for a future prompt version developed on a new dev slice, not changed after seeing these results.
- The normal check does **not** separate right from wrong predicted normals ([RESULTS.md](RESULTS.md)). An ablation chosen after seeing the results (reports escalated only by the normal check skip the agent) leaves every label unchanged and saves agent calls, but would show those ~99%-correct normals as `unverified` (the share of reports with an unverified label nearly triples, [RESULTS.md](RESULTS.md)). That would mislead users, so serving keeps the evaluated v2 configuration (owner, 22 Oct 2026).
- "Blind first" is only partly blind: the recall scan's hints include the rule labeller's sentence IDs, and in some cases ([RESULTS.md](RESULTS.md)) those are sentences the tagger also cited.
- Verification cross-checks the tagger with different methods (rules, and a second model with tools), but all of them read the same report text. So it catches **reading errors**, not errors in the report text itself or in the expert coding; those are out of scope for a text-only verifier. `verified` means "checked to faithfully reflect the report text", not independent proof. Verbatim evidence shows the sentence exists, not that it caused the label.
- The evaluation joins IU's pre-split sections into one text; real uploads are messier, so the varied-join test only partly measures the parser (a held-out set of header names the parser doesn't know is reported separately, [RESULTS.md](RESULTS.md)).
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
| **M6** | Parser (`parser.py`), `run_pipeline(raw_text)` (parse → tag → current verifier until M7), evaluation through the entry point with clean and varied joins, empty-section counts and subsets, normal-claim count ("no acute" impressions with non-normal codes), hedge-check consistency fix ("borderline"/"mild" not a hedge where the label definition counts it as present) | Parser accuracy and clean vs varied macro-F1 in results; leakage test covers `run_pipeline`; correctly parsed reports hit the Tier 1 cache ($0) | done |
| **M7** | Free checks with v2 escalation rules + recall scan (rule baseline as second reader) + normal check on every predicted No Finding; ReAct verifier agent (tools, blind first, caps); dev-slice prompt development and freeze; cost estimate before the full run | §8.1 v2 rows: F1 and paired bootstrap vs v1 columns, verified vs unverified accuracy, escalation and unverified rates, change counts; leakage test for the agent | done |
| **M8** | Postgres `labels` (with verification state and evidence) from out-of-fold v2 outputs; Qdrant indexing (report + contextual sentence points, sections, indication field, BM25); RRF; aggregation; retrieval eval incl. report-to-report queries | BM25 / base / contextual / filter rows of §8.2; test asserting no expert labels or indication in the index points | done |
| **M9** | Negation-aware embedding fine-tuning on plain sentences: pairs from training folds, `CachedGISTEmbedLoss` per fold, held-out evaluation, serving model on all data (stored privately); switch the evaluation index to plain sentence points | §8.2 fine-tuned rows judged two ways (pure embedding vs base without prefix; full system vs the best base combination), seen vs held-out split; pre-committed use rule applied | done |
| **M10a** | Website backend: session API (`/api/session`, `/reports`, `/ask` with scope report or all, `/timeline`), in memory and nothing stored; single-report answers and session RAG with citations checked in code; cost cap with the rules-only fallback | Endpoints match the frontend contract (`web/README.md`); a test shows nothing is stored; leakage tests cover the API; CI green | planned |
| **M10b** | Website evaluation (§8.3, §8.4): the 20 frozen questions on the dev slice, session RAG vs all reports in the prompt on batches of 3/10/30/50, latency and cost | Results file and tables; cost estimated before any paid run | planned |
| **M10c** | Website frontend (React; started on branch `m9c-frontend`) | Runs against the real backend; end-to-end smoke test (upload → findings → question with citations) | in progress |
| **M11** | Deployment: frontend on Vercel, backend as a Hugging Face Docker Space (Azure OpenAI keys as Space secrets; no private models or data in the image), rate and size limits, cost cap, attribution, model card | Deployed URLs pass the smoke test (`/health`, one upload, one ask); budget alert set | planned |
| *Stretch* | CheXpert labeler Docker baseline; noise-adjusted scores; delete-the-cited-sentence test (does the label change?); CheXpert Plus scale ingest (machine labels, throughput and cost only, never accuracy) | — | planned |

The roadmap was revised on 21 Oct 2026 (v2): the old M6–M11 (index, embedding training, reranker + LLM judge, query agent, serving) were reordered after the new parser and verifier-agent milestones; the LLM-judge stage, the review table and the QLoRA extension were dropped. Revised again on 22 Oct 2026 (owner, after M8): M9 embedding fine-tuning, M10 website (backend, evaluation, frontend), M11 deployment on Vercel + Hugging Face. The IU-corpus query agent, the ingestion worker that stored uploads, the Redis answer cache and the Gradio demo were dropped: questions are about the user's own uploads, which are never stored.

---

## 13. Extensions

- **RadGraph (PhysioNet):** radiologist-annotated uncertainty and spans, evaluated with local models only.
- **MCP server** exposing the agent tools for reuse from other agents.
- **Image-based cross-check:** the IU collection includes the chest X-ray images. A pretrained chest X-ray classifier (e.g. TorchXRayVision) would be the only truly independent check of the labels it covers, since every text-based check reads the same report.

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
