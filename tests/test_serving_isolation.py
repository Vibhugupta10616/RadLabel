"""Invariant: serving code never reads expert labels (CLAUDE.md ground rule 1, README §5)."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "radlabel"
FORBIDDEN = re.compile(
    r"^\s*(from|import)\s+(data_prep|eval|training)\b"   # modules that read expert codes
    r"|expert_labels|\"major\"|'major'|MeSH|automatic",   # expert files / fields
    re.M,
)


def test_src_never_touches_expert_labels() -> None:
    offenders = [
        f"{p.relative_to(SRC)}:{text[: m.start()].count(chr(10)) + 1}: {m.group(0).strip()}"
        for p in SRC.rglob("*.py")
        for text in [p.read_text(encoding="utf-8")]
        for m in FORBIDDEN.finditer(text)
    ]
    assert not offenders, offenders
