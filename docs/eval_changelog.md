# Eval detector changelog

The eval lexicon (`eval/lexicon.yaml`) and negspacy termset (`eval/negex_termset.yaml`) are frozen per
version. Any change needs owner approval, an entry here, and new hashes in `tests/test_eval_freeze.py`.

## eval_v1 (M1, 2026-10-19; before any model output exists)
- Lexicon: hand-written aliases for the 11 pathology labels, plus additions pre-registered in README §4.8
  from the M1 mapping audit: devices (icd, aicd, prosthetic valve, valve replacement, monitor leads,
  ecg leads, spinal stimulator; pacemaker, port, picc, sternotomy wires were already present) and
  pneumothorax variants (hydropneumothorax, hemopneumothorax).
- Termset: negspacy 1.1.0 `en_clinical`, plus following negations "has resolved", "have resolved",
  "resolved", "no longer seen", "no longer visualized", "has cleared", "have cleared", "removed".
- Pinned: spacy 3.8.16, negspacy 1.1.0.

## eval_v1.1 (M1, 2026-10-20; audit-driven, before any model output; owner-approved)
- Matching: aliases match on spaCy lookup **lemmas** of the lower-cased text (`spacy-lookups-data` 1.0.5,
  pinned), so singular/plural variants match automatically. Mentions are collected with a SpanRuler, so an
  alias shared by two labels counts for both.
- Lexicon: Pleural Effusion + "hydropneumothorax", "air-fluid level"; Pneumothorax + "air-fluid level";
  Pleural Other + "pleural abnormality". "air fluid level" (unhyphenated) added next to each "air-fluid
  level", because lemmas don't bridge the hyphen token and the audit examples use both spellings. (owner-approved
  2026-10-20).
- Lexicon: "sutures" removed from Support Devices (owner-approved 2026-10-20), because the mapping sends Sutures
  codes to Other Abnormality (not in the CheXpert labeler support_devices mention list).
- Termset: content unchanged; version bumped to stay in lockstep with the lexicon.
- `data_prep/subset_stats.py` regexes unchanged (hedged 279, redaction-adjacent 415).

## eval_v1.2 (M1, 2026-10-20; audit-driven, before any model output; owner-approved FINAL change)
- Lexicon: Pleural Other + "pleural opacity", "pleural based nodule", "pleural nodule", "pleural density", for
  the opacity/lesion codes at a pleural site that the mapping now sends to Pleural Other.
- Termset: content unchanged; version bumped to stay in lockstep with the lexicon.
- **After the M1 commit the lexicon and termset are permanently frozen: any later change is a hard stop.**
