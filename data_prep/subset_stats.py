"""Reference definitions for the README §3.3 subset counts (hedged, XXXX, redaction-adjacent).

Usage: python -I subset_stats.py iu_mapped.jsonl
Input: the usable-reports JSONL written by map_and_stats.py (3,832 rows).

Counting bases (they differ on purpose, and the README reports them this way):
  - hedged finding sentence ............ UNIQUE texts (3,086)   -> 279 (9.0%)
  - XXXX in Findings/Impression ........ UNIQUE texts (3,086)   -> 1,579 (51.2%)
  - XXXX within 2 words of finding term  ALL usable reports (3,832) -> 415 (10.8%)

These are heuristic, evaluation-only definitions. eval/subsets.py must use exactly
these regexes so the subsets are fixed and documented.
"""
import hashlib
import json
import re
import sys

HEDGE = re.compile(
    r"(\?|\b(question(able)?|suspicion|suspect(ed)?|differential|could|might|possibl[ey]|"
    r"may represent|cannot be excluded|cannot exclude|not excluded|suspicious for|"
    r"suggestive of|likely|probable|concerning for|versus)\b)"
)
FINDING_TERMS = re.compile(
    r"effusion|pneumonia|atelectasis|cardiomegaly|pneumothorax|edema|consolidation|"
    r"opacit|infiltrat|nodule|mass|fracture"
)
ADJ_TERMS = (r"(effusion|pneumonia|atelectasis|cardiomegaly|pneumothorax|edema|consolidation|"
             r"opacit\w*|infiltrat\w*|nodule|mass|fracture|silhouette|density)")
REDACTION_ADJACENT = re.compile(
    r"XXXX(\s+\w+){0,2}\s+" + ADJ_TERMS + r"|" + ADJ_TERMS + r"(\s+\w+){0,2}\s+XXXX", re.I
)
SENT_SPLIT = re.compile(r"(?<=[.;])\s+")


def norm(t: str) -> str:
    t = t.lower().replace("xxxx", " ")
    t = re.sub(r"[^a-z ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def text_of(r: dict) -> str:
    return r["findings"] + " " + r["impression"]


def is_hedged(r: dict) -> bool:
    """True if any sentence (raw text, lowercased) has both a hedge cue and a finding term."""
    for s in SENT_SPLIT.split(text_of(r)):
        sl = s.lower()
        if HEDGE.search(sl) and FINDING_TERMS.search(sl):
            return True
    return False


def has_xxxx(r: dict) -> bool:
    return "XXXX" in (r["findings"] + r["impression"])


def is_redaction_adjacent(r: dict) -> bool:
    return REDACTION_ADJACENT.search(text_of(r)) is not None


def unique_reports(rows: list[dict]) -> list[dict]:
    """First report per normalised text (same rule as map_and_stats.py)."""
    seen, out = set(), []
    for r in rows:
        k = hashlib.md5(norm(text_of(r)).encode()).hexdigest()
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def main(path: str) -> None:
    rows = [json.loads(l) for l in open(path)]
    uniq = unique_reports(rows)
    h = sum(is_hedged(r) for r in uniq)
    x = sum(has_xxxx(r) for r in uniq)
    a = sum(is_redaction_adjacent(r) for r in rows)
    print(f"usable reports: {len(rows)} | unique texts: {len(uniq)}")
    print(f"hedged (unique): {h} ({h/len(uniq):.1%})")
    print(f"XXXX in findings/impression (unique): {x} ({x/len(uniq):.1%})")
    print(f"redaction-adjacent (all usable): {a} ({a/len(rows):.1%})")
    print(f"redaction-adjacent (unique, for reference): {sum(is_redaction_adjacent(r) for r in uniq)}")


if __name__ == "__main__":
    main(sys.argv[1])
