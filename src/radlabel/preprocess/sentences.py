"""Sentence splitting with stable IDs: F1..Fn (Findings), I1..In (Impression)."""

import re

from pydantic import BaseModel

from radlabel.preprocess.text import redact

# Split after . ! ? preceded by a letter/bracket (not "2.5 cm" or "1. Cardiomegaly"),
# when the next sentence starts with a capital, digit or "[REDACTED]".
_SPLIT = re.compile(r"(?<=[A-Za-z\]\)%][.!?])\s+(?=[A-Z0-9\[])")


class Sentence(BaseModel):
    id: str
    section: str  # "findings" | "impression"
    text: str


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(text.strip()) if s.strip()]


def report_sentences(findings: str, impression: str) -> list[Sentence]:
    """Redacted sentences with IDs. The model only ever sees these."""
    out = []
    for prefix, section, text in (("F", "findings", findings), ("I", "impression", impression)):
        for i, s in enumerate(split_sentences(redact(text)), 1):
            out.append(Sentence(id=f"{prefix}{i}", section=section, text=s))
    return out
