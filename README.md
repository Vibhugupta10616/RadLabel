# RadLabel

**Radiology report intelligence: a guardrailed labelling pipeline, negation-aware hybrid search and a tool-using query agent over chest X-ray reports.**

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
| **Labelling pipeline** | Extracts findings with sentence-level evidence. Deterministic checks verify every label; failures go to a tool-using repair agent, then to a human review table. |
| **Negation-aware search** | Hybrid dense + BM25 search over reports and sentences. The embedding model is **fine-tuned so that "no effusion" is not retrieved for "effusion"**. |
| **Query agent** | Chooses between SQL (counts and filters) and filtered vector search, cites `report_id:sentence_id` for every claim, and refuses when the evidence is weak. |
| **Serving** | FastAPI, Docker Compose, Redis cache and rate limit, a queue-based ingestion worker, tracing, CI with cached regression evals, and a Gradio demo. |

Every component is evaluated against **expert-coded ground truth** using **stratified 5-fold cross-validation**.

## 2. Research context

- **Report retrieval and labelling** (FAU AIBE, IDEA Lab): Nützel, Dombrowski & Kainz, *Ontology-Based Concept Distillation for Radiology Report Retrieval and Labeling* (MLMI @ MICCAI 2025, arXiv:2508.19915). They compare reports through UMLS concepts, with a similarity measure that handles synonymy, negation and hierarchy, and report gains over embedding-based retrieval, especially for long-tail findings. RadLabel takes the engineering route to the same weakness: it teaches a dense embedding model about negation and measures the effect.
- **Parameter-efficient fine-tuning:** Jimenez-Gutierrez, Zuazua et al. (arXiv:2605.13936) benchmark LoRA, QLoRA and IA3 for adapting LLMs to private data. This motivates the optional local-model extension (§13).
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

The three subset counts above are defined **exactly** by `data_prep/subset_stats.py` (fixed regexes, documented counting bases). `eval/subsets.py` must import or copy those definitions unchanged. The broader hedge list in `coding_policy.py` is only for the coding-policy check in §3.4 and gives different counts.
| Usable reports with ≥ 1 code outside the standard labels | 54.5% (with the dropped labels mapped; slightly higher without) |

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
| D3 | Hedged findings coded inconsistently | Excluded from headline metrics; uncertainty used **for routing**, with routing metrics | §4.3 |
| D4 | "No Finding" trap: abnormal reports with no standard label | New **Other Abnormality** label; No Finding = expert `normal` code | §4.4 |
| D5 | Mapping choices can distort scores | Versioned mapping, automatic per-rule audit, **strict-mapping sensitivity analysis** | §4.4, §4.5 |
| D6 | Experts sometimes missed clearly stated findings | Report **raw** and **noise-adjusted** scores | §4.6 |
| D7 | Over-redaction (`XXXX`) next to findings | `[REDACTED]` token, verifier exemption, separate subset | §4.7 |
| D8 | Duplicate boilerplate reports | Duplicate clusters stay within one fold; each text counted once | §4.2 |
| D9 | Uncoded or empty reports | Excluded (§3.3) | — |

### 4.1 Licence (D1)
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

### 4.3 Hedged findings: uncertainty for routing, not for accuracy claims (D3)
- No public expert labels for uncertainty are available without PhysioNet credentialing, so **uncertainty accuracy is not claimed**.
- The `hedged` subset is defined by the **evaluation-only** regexes in `data_prep/subset_stats.py` (imported unchanged by `eval/subsets.py`; **not** the broader list in `coding_policy.py`), independent of the pipeline's own uncertainty logic. It is **excluded from headline metrics**.
- On `hedged`, label scores are reported under both policies (uncertain counted as absent, and as present).
- In the product, uncertainty's job is **routing to human review**. Measured:
  - **review rate on hedged vs clear reports** (should be much higher on hedged)
  - **escalation precision**: the share of escalated reports where the Tier 1 answer disagreed with the expert codes
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
- **Lung Lesion requires a lung site.** Nodule, Mass, Cavitation and Cysts count only when the first sub-heading is `lung` or is not an anatomical site (e.g. none, right, left, multiple, scattered, bilateral). Codes with another site (e.g. `Cysts/humerus`, `Mass/breast`, `Nodule/heart`, `Nodule/pleura`, `Mass/mediastinum`, `Nodule/thorax`, `Mass/thorax`) go to **Other Abnormality**. Reason: `Cysts/humerus` is a bone cyst, found in the mapping audit.
- **`Pleura/…/blunted` is not Pleural Other.** A blunted pleural angle usually hints at effusion but isn't a confirmed effusion, so it goes to **Other Abnormality**, like `Costophrenic Angle/blunted`. Found in the mapping audit (n = 3).
- The positive counts marked *(rerun)* are regenerated by M1 after these two fixes and written into this table from `data_card.json`.
- **Hierarchy:** scoring uses these **leaf** definitions only, with no closure, so Lung Opacity is scored against its own direct codes. The extractor prompt and verifier use the same definitions, so propagated parent labels can't create false positives.

### 4.5 Mapping audit and sensitivity (D5)
- **Automatic per-rule audit** (`data_prep/audit_mapping.py`): for every mapping rule, the share of matched reports whose text has a clear, non-negated, non-hedged mention of the label's terms. Rules below 60% agreement are flagged in `artifacts/mapping/audit.csv` and reviewed before modelling.
- **Strict mapping** (`mesh_to_labels_strict.yaml`): only the primary head per label (Cardiomegaly; Opacity/lung; Nodule + Mass; Pulmonary Atelectasis; Pleural Effusion; Fractures, Bone; Catheters, Indwelling + Tube, Inserted + Medical Device + Implanted Medical Device; Pulmonary Edema; Thickening/pleura; Consolidation; Pneumothorax).
  - **Other Abnormality and No Finding are identical under v1 and strict.** Strict changes only the 11 pathology labels, so the comparison isolates the effect of the looser rules.
  - Reports that are positive for a label under v1 but **not** under strict (e.g. only `Density/lung`) are **excluded from that label's strict scoring**, counted neither positive nor negative, because they're ambiguous rather than negative. Their counts per label are reported.
- Headline labelling results are reported under **both** v1 and strict. Conclusions must hold under both.

### 4.6 Label noise (D6)
- **Raw score:** against the expert codes. This is the official number.
- **Noise-adjusted score:** a case is set aside when the model says `present`, the code is absent, and an **independent** evaluation-only detector (negspacy + the eval lexicon, not the pipeline's negation module) finds a clear, non-negated, non-hedged mention in the text. Reported as an estimate, with the number of cases set aside.
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
reports ──► Ingestion worker: asyncio queue + Postgres `jobs`/`report_status` tables
            (status, attempts, tenacity retries with backoff, cost ledger, resumable)
                 │  each report = one LangGraph run with its own thread_id
                 ▼
     ┌──────────────── Labelling pipeline (per report) ───────────────┐
     │ preprocess: [REDACTED], sentence split with IDs (F1.., I1..),   │
     │             pipeline negation/hedge tags, alias candidates       │
     │ Tier 0  boilerplate normals (patterns learned on training folds)│
     │ Tier 1  extractor LLM (pinned snapshot, structured output)      │
     │ verifier  deterministic consistency checks                      │
     │ Tier 2  repair agent with tools (bounded loop)                  │
     │ Tier 3  review table (report waits, job continues)              │
     └──────────────┬──────────────────────────────┬──────────────────┘
                    ▼                              ▼
     Postgres `labels` (PREDICTED only)     Qdrant collection
                    │                       - report points + contextual sentence points
                    │                       - dense (fine-tuned bge-small) + sparse BM25
                    │                       - payload: report_id, sentence_id, section,
                    │                         predicted labels, pipeline negation tag
                    └──────────────┬───────────────┘
                                   ▼
question ──► Redis cache (key: question + index_version + label_model_version)
                                   ▼
             Query agent (LangGraph): sql_count · filtered_search · get_report · get_sentences
             → hybrid retrieval (RRF) → optional reranker → optional LLM judge
             → evidence check → answer with citations, or "not enough evidence"
                                   ▼
             FastAPI · Docker Compose · rate limit · tracing · CI · Gradio demo
```

Invariants:
1. **Serving never reads expert labels.** The `labels` table and the Qdrant payloads hold pipeline predictions only. A unit test enforces this.
2. **Evaluation models vs serving model.** CV trains 5 evaluation models (one per fold) for honest metrics. The serving model is trained once on all reports after evaluation and stored privately.
3. **Every LLM call is cached**, keyed by (model snapshot, prompt hash, input hash), so evaluation is reproducible and CI needs no API calls.

## 6. Component specifications

### 6.1 Preprocessing (`src/radlabel/preprocess/`)
- `text.py`: `[REDACTED]` substitution and normalisation; the Findings/Impression split is taken from the XML fields.
- `sentences.py`: sentence splitting with IDs `F1..Fn`, `I1..In`.
- `negation.py`: **pipeline** NegEx-style rules (negation and hedge cues, clause boundaries at "but", "however", ";"). Kept separate from the eval detector.
- `aliases.py`: alias dictionary per label (hand-written + CheXpert labeler mention phrases). Fixed, not tuned on data. 30% of the aliases are tagged `heldout: true` for embedding evaluation.
- `dedup.py`: exact-text clusters + exact pairwise Jaccard ≥ 0.9 near-duplicate merging.

### 6.2 Labelling (`src/radlabel/labelling/`)
**Output schema** (Pydantic, also the structured-output schema):
```json
{
  "report_id": "CXR123",
  "labels": [
    {"label": "Pleural Effusion", "status": "absent",  "evidence": ["F2"]},
    {"label": "Cardiomegaly",     "status": "present", "evidence": ["F1", "I1"]}
  ],
  "tier": 1,
  "route": "accepted | repaired | review",
  "verifier_messages": []
}
```
- `status` ∈ `present | absent | uncertain | not_mentioned`. Scoring: `present` = positive; the uncertainty policy applies only on the `hedged` subset (§4.3).

**Tiers:**
- **Tier 0:** exact normalised texts coded `normal` at least 3 times **in the training folds** → No Finding, with no LLM call.
- **Tier 1:** LLM extractor, zero-shot, with **synthetic** in-prompt examples (written by hand, never IU text, so there is no leakage). Provider configurable (OpenAI or Azure OpenAI); the dated model snapshot is pinned in config and recorded in every result file.
- **Verifier checks** (`verifier.py`, all unit-tested):

| Check | Rule |
|---|---|
| Evidence exists | every `present`/`absent`/`uncertain` label cites ≥ 1 valid sentence ID |
| Evidence mentions label | a cited sentence contains an alias of the label (`[REDACTED]`-adjacent → flag, not fail) |
| Negation consistency | a `present` label whose only cited sentences are negated in the same clause → fail |
| Hedge consistency | a `present` label whose only evidence is hedged → convert to `uncertain` and flag |
| No Finding exclusivity | No Finding `present` ⇒ every other label ≠ `present` |
| Section rule | Impression overrides Findings **only on an explicit same-label contradiction**. "No acute cardiopulmonary abnormality" does **not** cancel specific Findings. Unit test: Findings "mild cardiomegaly" + Impression "no acute disease" → Cardiomegaly stays `present`. |

- **Tier 2 repair agent** (`repair_agent.py`, LangGraph): receives the verifier messages and uses tools `get_sentence(id)`, `check_negation(id)`, `get_label_rules(label)`, `compare_sections(label)` and `submit_fix(labels)`. At most 6 tool calls and a token budget per report; uses a larger model if configured. The result is re-verified.
- **Tier 3:** still failing, or escalated because of hedging → row in the `review` table; `POST /review/{id}` resumes that report's thread.

**Baselines** (`eval/baselines/`):
- `rule_baseline.py`: alias match + pipeline negation, no LLM. Always available.
- `chexpert_labeler/`: the CheXpert labeler in its own Docker image. **Stretch:** if its dependencies fail to build, document the attempt and continue.
- LLM extractor without the verifier and repair (ablation).

### 6.3 Index and embeddings (`src/radlabel/index/`, `training/`)
- **Points:** one per report (Findings + Impression) and one per sentence. Sentence text is prefixed with a context line built from **predicted** labels: `"[Findings | report also mentions: cardiomegaly] No pleural effusion."`
- **Retrieval:** dense (cosine) + BM25 sparse in Qdrant, fused with RRF (k = 60). Optional cross-encoder `BAAI/bge-reranker-base` over the top 50. Optional LLM judge over the top 10, which reads the full reports and keeps those it can justify with a cited sentence.
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
| `sql_count(filters: {label: status}, section?)` | parameterised read-only SQL over `labels`; returns count + up to 20 example report IDs |
| `filtered_search(query, filters?, k=10)` | the hybrid retrieval of §6.3; returns `report_id`, `sentence_id`, score, text |
| `get_report(report_id)` | unchanged report text + attribution |
| `get_sentences(report_id, ids)` | the cited sentences |

**Guardrails:**
- Every claim cites `report_id:sentence_id`, and a post-check verifies each citation exists and mentions the finding asked about.
- Refusal ("not enough evidence") below a relevance threshold **tuned on inner validation**.
- Out-of-scope refusal (CT, age, which is redacted, treatment or diagnosis advice).
- Schema-validated tool arguments; read-only database role; input length limit.

### 6.5 Ingestion, API, operations (`src/radlabel/ingest/`, `src/radlabel/api/`)
- **Ingestion worker:** asyncio queue with bounded concurrency, tenacity retries with exponential backoff, a Postgres status per report, a `MAX_LLM_USD` cost cap (stops escalation to Tier 2 when reached), and resume-from-status after a crash.
- **API:** `POST /ingest`, `GET /jobs/{id}`, `POST /label`, `POST /ask`, `GET /review`, `POST /review/{id}`, `GET /health`.
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
- **Demo** (`demo/app.py`, Gradio): ask a question, see the answer with clickable citations, view the unchanged report with evidence highlighted as an overlay, and the attribution footer.

---

## 7. Configuration

All settings live in **`.env.example`** at the repo root (committed, no secrets). Copy it to `.env` (git-ignored) and fill in the key, the API version, the model versions and the per-deployment TPM. `src/radlabel/config.py` loads them with pydantic-settings and **fails fast with a clear message** if a required value is missing.

| Group | Variables |
|---|---|
| Provider | `LLM_PROVIDER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `OPENAI_API_KEY` |
| Deployments per role (§7.1) | `AZURE_OPENAI_DEPLOYMENT` (Tier 1), `…_FALLBACK_DEPLOYMENT`, `…_REPAIR_DEPLOYMENT` (agents), `…_CHEAP_DEPLOYMENT` (paraphrasing), `…_EMBED_DEPLOYMENT` (baseline row only), plus a `…_VERSION` for each |
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
- `MAX_LLM_USD` is enforced in code, and the owner sets an Azure Cost Management budget alert (e.g. $20) as a second safeguard.

**Version pinning.** Each deployment uses version update policy **"Upgrade when expired"** (`OnceCurrentVersionExpired`). The version stays fixed for the whole project, and only at retirement does the deployment move to the new default instead of failing with HTTP 410. ("No auto upgrade" would make the demo break at retirement.) The LLM client also logs the `model` field returned by **every response** and raises a warning if it changes between calls, which catches silent upgrades. Retirement dates are checked in each deploy dialog before use.

**LLM deployments** (all Global Standard; the model version is recorded in every results file):

| Deployment | Quota (TPM) | Used for | Why |
|---|---|---|---|
| `gpt-4.1-mini` | 5M | Tier 1 labelling (~3,100 reports), RAGAS judge | Non-reasoning, temperature 0, reliable structured output, cheap → reproducible bulk work |
| `gpt-5-mini` (already deployed, 375K TPM allocated) | 1M | Tier 2 repair agent, query agent, LLM judge | Reasoning model, better at multi-step tool use; runs on a small share of traffic |
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
- **Third-party models on Azure** (Claude, Grok, DeepSeek): small quotas, possibly billed outside student credit.

**Expected LLM spend** (approximate; check current Azure prices): Tier 1 over all reports ≈ $3–5. The verifier is code, so "LLM only" and "LLM + verifier" reuse the same cached outputs. Agents and agent evaluation ≈ $5–15.

**GPU accelerator quota** (8 each of A100 80GB, H100 80GB, H200 141GB, MI300 192GB). **The quota isn't the constraint; the credit is**, since GPU time costs several dollars per hour. Policy:

| Task | Compute | Note |
|---|---|---|
| Embedding fine-tuning (bge-small, 5 folds + serving model) | CPU or Kaggle T4 by default; **optionally 1× A100 80GB** as an Azure ML job | Small model; an A100 finishes all runs in minutes. Use a compute cluster with **min nodes = 0**, so it scales to zero after the job. |
| Extension: QLoRA of Qwen2.5-1.5B/7B + vLLM evaluation (§13) | **1× A100 80GB** | bf16 support (unlike a T4), ample memory; the cheapest of the four. Run as a job; never leave an endpoint running. |
| Serving the API and demo | **No GPU** | The deployed system uses the Azure OpenAI APIs and CPU embeddings. |
| H100, H200 | Not used | Overkill for these model sizes, and pricier. |
| MI300 (AMD) | Not used | ROCm support for bitsandbytes/QLoRA and vLLM is more fiddly; not worth the setup time. |

Even with quota shown, a specific GPU VM size may be unavailable in a region; test with one short job first. Every GPU job writes its runtime and estimated cost to `artifacts/results/compute_log.json`.

---

## 8. Evaluation protocol

All metrics use **out-of-fold predictions** from the stratified 5-fold CV (§4.2), counted once per exact normalised text, with 95% bootstrap CIs resampled over duplicate clusters. Subsets are defined exactly in §4.8.

### 8.1 Labelling
- **Headline:** per-label F1, precision and recall for the 9 headline labels, plus their macro-F1, excluding `hedged`, under mapping v1 **and** strict.
- **Rare:** each rare label with CI and n; plus pooled rare micro-F1.
- **Subsets:** `abnormal`, `negation_only` (selected with the **eval-only** detector), `hedged` (both policies), `redaction_adjacent`.
- Raw vs noise-adjusted (§4.6).
- Pipeline metrics: tier distribution, repair success rate, mean repair tool calls, escalation precision, review rate on hedged vs clear reports.
- **Ablation:** rule baseline | CheXpert labeler (if built) | LLM only | LLM + verifier | LLM + verifier + repair.

### 8.2 Retrieval
- For each fold k: index the fold-k reports with evaluation model k (and with the base model), run the query sets, aggregate across folds.
- **Relevance from expert codes:** a report is relevant to a label query if the label is coded. **Attribute queries** ("small left effusion") are judged from code modifiers, e.g. `Pleural Effusion/left/small`. **Compositional queries** ("effusion without cardiomegaly") are judged by label logic.
- **Query sets:**
  - seen-label queries
  - **held-out-label** queries
  - **held-out-alias** queries
  - 30 hand-written attribute and compositional queries in `eval/queries/handwritten.yaml`
- **Metrics:** recall@10, nDCG@10, and **negation contamination@10** (the share of top-10 results whose only mentions of the finding are negated, per the eval detector). Measured **after each stage**: dense, +BM25, +rerank, +LLM judge.

| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |
|---|---|---|---|
| BM25 | | | |
| base bge-small, report-level | | | |
| base bge-small, contextual sentences | | | |
| base bge-small + negated-sentence payload filter (no training) | | | |
| fine-tuned, contextual sentences | | | |
| fine-tuned + BM25 (RRF) | | | |
| + reranker | | | |
| + LLM judge | | | |

The **filter baseline** is the row fine-tuning must justify itself against. It is expected to help most on held-out and free-text queries and on report-to-report similarity.

### 8.3 Agent
- **Question set** (`eval/agent_questions/`):
  - templates for counts, filters, similarity and unanswerable questions, each LLM-paraphrased into 3–5 variants
  - **40 hand-written** questions, including borderline unanswerable ones (age is redacted)
- Run twice: against an **expert-label** table (isolates agent errors) and against the **out-of-fold predicted-label** table (end-to-end).
- **Metrics:** exact-answer accuracy, tool-choice accuracy, citation validity, refusal precision/recall. RAGAS faithfulness and context precision are reported as a **secondary**, LLM-judged signal.

### 8.4 System
- Cost per 1,000 reports, tiered vs "LLM for everything", on **all** and on **abnormal** reports.
- p50/p95 latency per endpoint.
- Crash-and-resume log: kill the worker mid-job and restart it.

**Null results** are reported as they are. Headline claims focus on the abnormal and negation subsets.

---

## 9. Repository structure

```
radlabel/
├── data_prep/              # parse_iu.py, map_and_stats.py, coding_policy.py, audit_mapping.py
├── data/                   # git-ignored except mapping/*.yaml
│   ├── raw/  processed/  splits/
│   └── mapping/            # mesh_to_labels_v1.yaml, mesh_to_labels_strict.yaml (no report text)
├── src/radlabel/
│   ├── preprocess/  labelling/  index/  agent/  ingest/  api/  llm/  db/
│   └── config.py
├── training/               # build_pairs.py, train_embeddings.py
├── eval/                   # cv.py, labelling.py, retrieval.py, agent.py, system.py, bootstrap.py,
│   │                       # subsets.py, baselines/, queries/, agent_questions/
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

_Filled in automatically from `artifacts/results/*.json` by `make report`. No number appears here without a script that reproduces it._

## 11. Limitations

- Single institution (Indiana), reports from around 2013.
- Expert codes are positive-only; hedged findings are coded inconsistently. Uncertainty accuracy and evidence-span accuracy are **not claimed**.
- Mapping v1 is lossy, and two standard labels are dropped. Results are shown under v1 and strict.
- Some clearly stated findings were not coded, so the raw scores are a lower bound (§4.6).
- About 11% of reports have redactions next to finding terms.
- Subsets and noise adjustment depend on a rule-based eval detector, deliberately separate from the pipeline's own.
- Rare labels have 27–49 positives in total, hence wide CIs.
- Labels describe the report text, not the image.
- The CC BY-NC-ND licence keeps models and processed data private.

---

## 12. Implementation guide (for Claude Code)

Build in this order. Each milestone ends with its acceptance check passing and a commit.

- **Missing access only** (API keys, cloud credentials): build fully against the fake/offline mode, note the blocker in `docs/STATUS.md`, and continue.
- **Everything else is a hard stop**: mismatched data numbers, failing invariant tests, implausible results, spec ambiguity, budget at 50%, or an acceptance check that would need weakening. Stop, report the cause and options, and wait for the owner. The full list is in the internal working rules, which are kept in a private file.

### Ground rules
1. **Never use expert labels in serving code** (`src/radlabel/api`, `agent`, `index`). Only `eval/`, `training/` and `data_prep/` may read them.
2. **No tuning on test folds.** Anything learned (Tier 0 patterns, thresholds, embedding checkpoints) uses training folds or inner validation only.
3. **Never commit** raw data, processed data, report text, LLM caches or model weights. Check `.gitignore` before the first commit.
4. **Cache every LLM call**; respect `MAX_LLM_USD`; record the model snapshot in every results file.
5. **Every rule in §6.2 has a unit test**, including the Impression rule case.
6. Write results as JSON to `artifacts/results/` and render the tables with `make report`.
7. Keep `docs/STATUS.md` current: done, blocked, and next.
8. **Respect the student budget** (§7.1): use the deployment assigned to each role, handle 429s by waiting rather than failing, and run GPU work only as scale-to-zero jobs, never as always-on endpoints or VMs. Training scripts must run on CPU too (`--device auto`).

### Milestones
| ID | Build | Acceptance check |
|---|---|---|
| **M0** | Repo skeleton, `pyproject.toml`, `Makefile`, `.gitignore` (must ignore `.env`), `config.py` matching the provided `.env.example`, Docker Compose (postgres, qdrant, redis), CI running lint + tests | `make test` passes; `docker compose up` is healthy. **The Docker check may be deferred until the owner installs Docker, but must pass before M5** (the first milestone that needs Postgres). |
| **M1** | `make data`: download with SHA-256 check, parse, exclusions, `[REDACTED]`, sentences, dedup clusters, mapping v1 + strict, Other Abnormality, mapping audit, subsets (§4.8), `data_card.json` | Numbers match §3.3 and §4.4 exactly on exact texts; cluster count 3,073; subset counts match `subset_stats.py`; `audit.csv` written |
| **M2** | `eval/cv.py`: iterative stratification over clusters, 5 folds + inner validation, `folds.csv`; bootstrap CI utility | Every label's positives spread across folds within ±2 of equal share; no cluster spans two folds (test) |
| **M3** | Pipeline preprocessing + negation, Pydantic schema, verifier + unit tests, rule baseline, labelling eval on out-of-fold rule-baseline predictions | §8.1 table produced for the rule baseline |
| **M4** | LLM client (OpenAI/Azure, cache, cost ledger, FakeLLM), Tier 0 (per fold), Tier 1 extractor, labelling eval for LLM and LLM+verifier | §8.1 rows for both; reruns cost $0 from cache |
| **M5** | Tier 2 repair agent (LangGraph, tools, limits), review table, routing metrics | Repair success rate, escalation precision, hedged vs clear review rates in results |
| **M6** | Postgres `labels` from out-of-fold predictions, Qdrant indexing (report + contextual sentences, BM25), RRF, aggregation, retrieval eval for BM25/base/filter rows | First 4 rows of §8.2 filled in; test asserting no expert labels in the index |
| **M7** | Pair building, `CachedGISTEmbedLoss` training per fold, held-out evaluation, serving model on all data (stored privately) | Fine-tuned rows of §8.2 filled in, with seen vs held-out split |
| **M8** | Reranker and LLM-judge stages, contamination measured per stage | Remaining §8.2 rows filled in |
| **M9** | Query agent + tools + guardrails, question set (templates, paraphrases, 40 hand-written), agent eval on both label tables, RAGAS secondary | §8.3 table produced |
| **M10** | Ingestion worker (queue, retries, cost cap, resume), FastAPI endpoints, Redis cache + rate limit, tracing | End-to-end: ingest 200 reports, kill and restart the worker, job completes; `/ask` returns a cited answer |
| **M11** | Gradio demo, attribution, deploy files, model card, CI regression eval on frozen cached outputs, `make report`, README §10 filled in | CI green; demo runs locally; results tables in the README |
| *Stretch* | CheXpert labeler Docker baseline; noise-adjusted scores; CheXpert Plus scale ingest (machine labels, **throughput and cost only**, never accuracy) | — |

### Make targets
`make setup` · `make data` · `make folds` · `make label-eval` · `make index` · `make train-embeddings` · `make retrieval-eval` · `make agent-eval` · `make up` · `make test` · `make report`

---

## 13. Extensions

- **Local-first labelling:** QLoRA-tune Qwen2.5-1.5B-Instruct (or 7B) as the Tier 1 extractor, using silver targets (expert positives + teacher status/evidence, filtered by the verifier, built from training folds only). Compare base vs fine-tuned vs API model, served with vLLM guided JSON decoding. Run on **1× A100 80GB** as a scale-to-zero Azure ML job (§7.1); adapters are stored privately (§4.1). Motivation: hospitals often can't send reports to external APIs.
- **RadGraph (PhysioNet):** radiologist-annotated uncertainty and spans, evaluated with local models only.
- **MCP server** exposing the agent tools for reuse from other agents.

## 14. References

- Demner-Fushman D. et al. *Preparing a collection of radiology examinations for distribution and retrieval.* JAMIA 23(2):304–310, 2016.
- Irvin J. et al. *CheXpert.* AAAI 2019.
- Jain S. et al. *RadGraph.* NeurIPS Datasets & Benchmarks 2021. arXiv:2106.14463.
- Nützel F., Dombrowski M., Kainz B. *Ontology-Based Concept Distillation for Radiology Report Retrieval and Labeling.* MLMI @ MICCAI 2025. arXiv:2508.19915.
- Jimenez-Gutierrez D. M., Zuazua E. et al. *Towards the Next Frontier of LLMs, Training on Private Data.* arXiv:2605.13936, 2026.
- Sechidis K., Tsoumakas G., Vlahavas I. *On the Stratification of Multi-Label Data.* ECML PKDD 2011.
- Anthropic. *Introducing Contextual Retrieval* (engineering blog).
- Reimers N., Gurevych I. *Sentence-BERT.* EMNLP 2019.
- Solatorio A. *GISTEmbed: Guided In-sample Selection of Training Negatives.* 2024.
- Es S. et al. *RAGAS.* 2023.
- Chapman W. et al. *A Simple Algorithm for Identifying Negated Findings and Diseases in Discharge Summaries (NegEx).* J Biomed Inform, 2001.
