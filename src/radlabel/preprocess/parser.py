"""Report parser (README §6.1, M6): raw report text -> indication / comparison / findings / impression.

Header matching, case-insensitive, with common variants ("Clinical history", "Reason for exam", "Conclusion", ...).
A header counts at the start of the text, of a line or of a sentence, followed by ":" or "-" (or alone on its
line). Repeated sections are joined. Text before the first header goes to Findings when there is no Findings header,
else it is kept as `unassigned` (reported, not labelled). No header at all -> the whole text is one block, read as
Findings, with `sections_identified = False` (the section rule then has no Impression to work with).
Section text is only stripped (line breaks become spaces), so a clean upload gives the tagger exactly the IU fields.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

SECTIONS = ("indication", "comparison", "findings", "impression")
HEADERS: dict[str, list[str]] = {
    "indication": ["indication", "indications", "clinical indication", "clinical history", "clinical information",
                   "history", "reason for exam", "reason for examination", "reason for study"],
    "comparison": ["comparison", "comparisons", "prior studies", "prior study"],
    "findings": ["findings", "finding"],
    "impression": ["impression", "impressions", "conclusion", "conclusions", "opinion", "summary"],
}
_SECTION_OF = {h: s for s, hs in HEADERS.items() for h in hs}
_ALTS = "|".join(r"[\s_-]+".join(map(re.escape, h.split())) for h in sorted(_SECTION_OF, key=len, reverse=True))
_HEADER = re.compile(rf"(?:^|(?<=[\n.!?]))[ \t]*(?P<h>{_ALTS})[ \t]*(?::|-(?=\s)|[ \t]*$)", re.I | re.M)


class ParsedReport(BaseModel):
    indication: str = ""
    comparison: str = ""
    findings: str = ""
    impression: str = ""
    sections_identified: bool
    headers: list[str] = []  # headers found, in order, as written
    unassigned: str = ""  # text before the first header, when a Findings header exists


def _clean(text: str) -> str:
    return re.sub(r"[ \t]*\n\s*", " ", text).strip()


def parse_report(raw_text: str) -> ParsedReport:
    found = list(_HEADER.finditer(raw_text))
    if not found:
        return ParsedReport(findings=_clean(raw_text), sections_identified=False)
    parts: dict[str, list[str]] = {s: [] for s in SECTIONS}
    for m, nxt in zip(found, [*found[1:], None], strict=True):
        section = _SECTION_OF[re.sub(r"[\s_-]+", " ", m["h"]).lower()]
        parts[section].append(_clean(raw_text[m.end():nxt.start() if nxt else len(raw_text)]))
    out = {s: " ".join(p for p in v if p) for s, v in parts.items()}
    pre = _clean(raw_text[:found[0].start()])
    has_findings = bool(parts["findings"])
    if pre and not has_findings:
        out["findings"] = pre
    return ParsedReport(**out, sections_identified=True, headers=[m["h"] for m in found],
                        unassigned=pre if has_findings else "")
