"""Website sessions (SPEC §6.5, M10a). Everything lives in process memory: nothing is written to disk, logs, the
evaluation cache or the IU index. A session expires after SESSION_TTL idle seconds or on DELETE.

- Reports are converted to the frontend contract (`web/src/contract.ts` on branch m9c-frontend).
- Session index: every sentence of every report (indication and comparison included, tagged with their section;
  the indication is for questions only, never a labelling input) embedded with the search model on plain sentences
  (D21: fine-tuned plain sentences, no negation filter, no BM25), with report_no, sentence_id, section and the
  report's labels + verification states.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel

from radlabel.embeddings import QUERY_PREFIX, search_encode
from radlabel.labels import LABELS, NO_FINDING
from radlabel.pipeline import PipelineResult
from radlabel.preprocess.sentences import split_sentences
from radlabel.preprocess.text import redact

SECTIONS = ("indication", "comparison", "findings", "impression")
ID_PREFIX = {"indication": "N", "comparison": "C"}


class SentenceOut(BaseModel):
    id: str
    text: str


class EvidenceOut(BaseModel):
    sentence_id: str
    text: str


class LabelOut(BaseModel):
    label: str
    status: str
    verification: str
    corroboration: str | None
    evidence: list[EvidenceOut]
    reason: str


class ReportOut(BaseModel):
    report_no: int
    filename: str
    sections: dict[str, list[SentenceOut]]
    sections_identified: bool
    labels: list[LabelOut]
    rules_only: bool


def sections_of(r: PipelineResult) -> dict[str, list[SentenceOut]]:
    """Contract sections: Findings / Impression are the pipeline's sentences (F1.., I1..; all Findings when no
    sections were found); indication and comparison get N1.. and C1.. so questions can cite them."""
    out: dict[str, list[SentenceOut]] = {s: [] for s in SECTIONS}
    for name in ("indication", "comparison"):
        text = getattr(r.parse, name)
        out[name] = [SentenceOut(id=f"{ID_PREFIX[name]}{i}", text=t)
                     for i, t in enumerate(split_sentences(redact(text)), 1)] if text else []
    for s in r.sentences:
        out["impression" if s.section == "impression" else "findings"].append(SentenceOut(id=s.id, text=s.text))
    return out


def to_report(report_no: int, filename: str, r: PipelineResult) -> ReportOut:
    sections = sections_of(r)
    text = {s.id: s.text for ss in sections.values() for s in ss}
    order = {lab: k for k, lab in enumerate(LABELS)}
    labels = [LabelOut(label=f.label, status=f.status, verification=f.verification, corroboration=f.corroboration,
                       evidence=[EvidenceOut(sentence_id=e, text=text[e]) for e in f.evidence if e in text],
                       reason=f.reason) for f in sorted(r.final, key=lambda f: order[f.label])]
    return ReportOut(report_no=report_no, filename=filename, sections=sections,
                     sections_identified=r.sections_identified, labels=labels, rules_only=r.rules_only)


@dataclass
class Entry:
    report_no: int
    sentence_id: str
    section: str
    text: str


@dataclass
class Session:
    id: str
    last_used: float = field(default_factory=time.monotonic)
    reports: list[ReportOut] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    vectors: np.ndarray | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, report: ReportOut) -> None:
        """Add a report and index its sentences (search model, plain text)."""
        new = [Entry(report.report_no, s.id, name, s.text) for name in SECTIONS for s in report.sections[name]]
        vec = search_encode([e.text for e in new]) if new else None
        with self.lock:
            self.reports.append(report)
            self.entries += new
            if vec is not None:
                self.vectors = vec if self.vectors is None else np.vstack([self.vectors, vec])

    def report(self, report_no: int) -> ReportOut | None:
        return next((r for r in self.reports if r.report_no == report_no), None)

    def retrieve(self, question: str, k: int, report_nos: list[int] | None = None,
                 labels: list[str] | None = None) -> list[Entry]:
        """Top-k sentences by cosine (ties: report_no, sentence_id); optional filters: these reports only, and/or
        reports where one of these labels is present or uncertain."""
        if self.vectors is None or not self.entries:
            return []
        keep = np.ones(len(self.entries), bool)
        if report_nos:
            keep &= np.array([e.report_no in report_nos for e in self.entries])
        if labels:
            hit = {r.report_no for r in self.reports
                   if any(x.label in labels and x.status in ("present", "uncertain") for x in r.labels)}
            keep &= np.array([e.report_no in hit for e in self.entries])
        q = search_encode([QUERY_PREFIX + question])[0]
        sims = np.round(self.vectors @ q, 6)
        idx = [i for i in sorted(range(len(self.entries)), key=lambda i: (-sims[i], self.entries[i].report_no,
                                                                            self.entries[i].sentence_id)) if keep[i]]
        return [self.entries[i] for i in idx[:k]]

    def timeline(self) -> list[dict[str, object]]:
        """Labels present or uncertain in at least one report (No Finding left out), status per report."""
        rows: list[dict[str, object]] = []
        for lab in LABELS:
            if lab == NO_FINDING:
                continue
            st = {str(r.report_no): next(x.status for x in r.labels if x.label == lab) for r in self.reports}
            if any(s in ("present", "uncertain") for s in st.values()):
                rows.append({"label": lab, "statuses": st})
        return rows


class SessionStore:
    def __init__(self, ttl_s: float) -> None:
        self.ttl_s = ttl_s
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def sweep(self) -> None:
        now = time.monotonic()
        with self._lock:
            for sid in [s for s, x in self._sessions.items() if now - x.last_used > self.ttl_s]:
                del self._sessions[sid]

    def create(self) -> Session:
        self.sweep()
        s = Session(secrets.token_urlsafe(16))
        with self._lock:
            self._sessions[s.id] = s
        return s

    def get(self, sid: str) -> Session | None:
        self.sweep()
        with self._lock:
            s = self._sessions.get(sid)
        if s is not None:
            s.last_used = time.monotonic()
        return s

    def delete(self, sid: str) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None

    def __len__(self) -> int:
        return len(self._sessions)
