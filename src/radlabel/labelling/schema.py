"""Labelling output schema (README §6.2); also the LLM structured-output schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from radlabel.labels import LABELS, NO_FINDING

Status = Literal["present", "absent", "uncertain", "not_mentioned"]
LabelName = Literal[tuple(LABELS)]  # type: ignore[valid-type]  # enum in the JSON schema


class LabelOut(BaseModel):
    label: LabelName  # type: ignore[valid-type]
    status: Status
    evidence: list[str] = Field(default_factory=list)  # sentence IDs, e.g. ["F1", "I2"]


class VerifierMessage(BaseModel):
    check: str
    label: str
    level: Literal["fail", "flag"]
    detail: str


class ReportLabels(BaseModel):
    report_id: str
    labels: list[LabelOut]
    tier: int = 1
    route: Literal["accepted", "repaired", "review"] = "accepted"
    verifier_messages: list[VerifierMessage] = Field(default_factory=list)

    def status(self, label: str) -> Status:
        return next((x.status for x in self.labels if x.label == label), "not_mentioned")


def derive_no_finding(out: ReportLabels) -> ReportLabels:
    """No Finding is derived in code, never taken from a model (owner decision, M4): present iff no other label
    is present or uncertain, else not_mentioned. Any model-provided No Finding value is ignored."""
    others = [x for x in out.labels if x.label != NO_FINDING]
    normal = not any(x.status in ("present", "uncertain") for x in others)
    nf = LabelOut(label=NO_FINDING, status="present" if normal else "not_mentioned")
    return out.model_copy(update={"labels": [nf, *others]})
