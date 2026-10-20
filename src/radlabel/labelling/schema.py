"""Labelling output schema (README §6.2); also the LLM structured-output schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from radlabel.labels import LABELS

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
