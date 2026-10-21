"""Index points (SPEC §6.3, M8), built from a PipelineResult only.

- One report point (Findings + Impression) and one point per sentence, with its section ("unknown" when the parser
  found no sections). Sentence text gets a contextual prefix from the PREDICTED labels:
  "[Findings | report also mentions: cardiomegaly] No pleural effusion."
- Payload: report_id, kind, predicted v2 labels (status, verification, evidence; not_mentioned left out), section,
  and the pipeline negation tags of the sentence. Never codes from the dataset, folds, eval mentions or the
  indication (tests/test_index_leakage.py); the indication lives only in Postgres (`reports.indication`).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from radlabel.labels import NO_FINDING
from radlabel.pipeline import PipelineResult
from radlabel.preprocess.negation import mentions

REPORT_KEYS = {"report_id", "kind", "labels", "sections_identified"}
SENTENCE_KEYS = {"report_id", "kind", "sentence_id", "section", "labels", "affirmed", "negated", "hedged",
                 "negation_only"}
_NS = uuid.UUID("7b6c3f4e-5d1a-4c2b-9e8f-0a1b2c3d4e5f")


class IndexPoint(BaseModel):
    id: str  # uuid5(report_id[:sentence_id])
    kind: str  # "report" | "sentence"
    text: str  # what gets embedded (and, for reports, BM25-indexed)
    payload: dict[str, Any]


def predicted_labels(r: PipelineResult) -> dict[str, dict[str, Any]]:
    return {f.label: {"status": f.status, "verification": f.verification, "evidence": f.evidence}
            for f in r.final if f.status != "not_mentioned"}


def context_prefix(section: str, present: list[str]) -> str:
    return f"[{section.capitalize()}{' | report also mentions: ' + ', '.join(present) if present else ''}] "


def report_points(r: PipelineResult) -> list[IndexPoint]:
    labels = predicted_labels(r)
    present = [lab.lower() for lab, x in labels.items() if x["status"] == "present" and lab != NO_FINDING]
    out = [IndexPoint(id=str(uuid.uuid5(_NS, r.report_id)), kind="report",
                      text=" ".join(s.text for s in r.sentences),
                      payload={"report_id": r.report_id, "kind": "report", "labels": labels,
                               "sections_identified": r.sections_identified})]
    for s in r.sentences:
        section = s.section if r.sections_identified else "unknown"
        ms = mentions(s.text)
        out.append(IndexPoint(
            id=str(uuid.uuid5(_NS, f"{r.report_id}:{s.id}")), kind="sentence",
            text=context_prefix(section, present) + s.text,
            payload={"report_id": r.report_id, "kind": "sentence", "sentence_id": s.id, "section": section,
                     "labels": labels, "affirmed": sorted({m.label for m in ms if m.affirmed}),
                     "negated": sorted({m.label for m in ms if m.negated}),
                     "hedged": sorted({m.label for m in ms if m.hedged and not m.negated}),
                     "negation_only": bool(ms) and all(m.negated for m in ms)}))
    return out
