"""Sentence splitting with stable IDs: F1..Fn (Findings), I1..In (Impression)."""

import re

from pydantic import BaseModel

from radlabel.preprocess.text import redact

# Split after . ! ? preceded by a letter, "]", ")" or "%" (never "2.5 cm" or "1. Cardiomegaly"), when
#  - whitespace follows and the next sentence starts with a capital, digit or "[REDACTED]", or
#  - an uppercase letter follows directly ("[REDACTED].In the left ...").
# No split after a known abbreviation ("vs.", "e.g.", "Dr.").
_SPLIT = re.compile(r"(?<=[A-Za-z\]\)%][.!?])(?:\s+(?=[A-Z0-9\[])|(?=[A-Z]))")
_ABBREV = re.compile(r"(?:^|\W)(?:vs|e\.g|i\.e|dr|mr|mrs|ms|approx)\.$", re.I)


class Sentence(BaseModel):
    id: str
    section: str  # "findings" | "impression"
    text: str


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in _SPLIT.split(text.strip()):
        part = part.strip()
        if not part:
            continue
        if out and _ABBREV.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def report_sentences(findings: str, impression: str) -> list[Sentence]:
    """Redacted sentences with IDs. The model only ever sees these."""
    out = []
    for prefix, section, text in (("F", "findings", findings), ("I", "impression", impression)):
        for i, s in enumerate(split_sentences(redact(text)), 1):
            out.append(Sentence(id=f"{prefix}{i}", section=section, text=s))
    return out
