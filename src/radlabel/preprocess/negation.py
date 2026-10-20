"""Pipeline NegEx-style mention detection (README §6.1). Independent of the eval-only detector
(`eval/subsets.py`, negspacy): own cue lists, written from the NegEx literature (Chapman et al. 2001).

Per sentence: tokens -> clauses (boundaries: but, however, although, though, except, whereas, yet, which, ";")
-> alias mentions (aliases.py). A mention is
- negated: a strong negation cue earlier in its clause ("no", "without", "negative for", ...), a weak cue
  ("normal") at most 3 tokens before it, or a following cue ("has resolved", "is normal", ...) at most
  6 tokens after it in the clause; pseudo-negations ("no change", "not only", ...) never trigger;
- hedged: a hedge cue anywhere in its clause ("possible", "may", "versus", "?", ...);
- asserted: anchors (anatomy-only aliases) assert only with an enlargement word in the clause.
Overlapping matches keep only the longest span.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from radlabel.preprocess.aliases import Alias, aliases, normalise

BOUNDARIES = {"but", "however", "although", "though", "except", "whereas", "yet", "which", ";"}
STRONG_NEG = ["no", "not", "without", "negative for", "free of", "absence of", "absent", "no evidence of",
              "no sign of", "no signs of", "resolution of", "resolved", "clear of", "nor", "never"]
WEAK_NEG = ["normal"]
WEAK_SCOPE = 3
FOLLOW_NEG = ["is not seen", "are not seen", "not seen", "not identified", "not visualized", "not present",
              "has resolved", "have resolved", "resolved", "is normal", "are normal", "within normal limits",
              "is unremarkable", "unremarkable", "not enlarged", "is clear", "are clear", "removed",
              "has been removed", "no longer seen", "no longer visualized", "is negative"]
FOLLOW_SCOPE = 6
PSEUDO_NEG = ["no change", "no interval change", "no significant change", "not only", "no increase",
              "no significant interval change", "not necessarily", "no further"]
HEDGE = ["possible", "possibly", "probable", "probably", "likely", "may", "might", "could", "suggest",
         "suggests", "suggestive", "suspicious", "suspected", "concerning for", "cannot be excluded",
         "cannot exclude", "not excluded", "questionable", "question of", "?", "versus", "vs", "differential",
         "consider", "equivocal", "borderline", "may represent", "can not be excluded"]
ENLARGE = ["enlarged", "enlargement", "enlarging", "increased", "cardiomegaly", "prominent", "upper limits"]


@dataclass(frozen=True)
class Mention:
    label: str
    alias: str
    start: int  # token index
    end: int    # exclusive
    negated: bool
    hedged: bool
    asserted: bool  # False for an anchor without an enlargement word

    @property
    def affirmed(self) -> bool:
        return self.asserted and not self.negated and not self.hedged


def _find(tokens: list[str], phrase: list[str], start: int = 0) -> list[int]:
    n = len(phrase)
    return [i for i in range(start, len(tokens) - n + 1) if tokens[i : i + n] == phrase]


def _match(tokens: list[str], a: Alias) -> list[tuple[int, int]]:
    p = a.tokens
    if not p:
        return []
    out = []
    for i in range(len(tokens) - len(p) + 1):
        if tokens[i : i + len(p) - 1] != p[:-1]:
            continue
        last = tokens[i + len(p) - 1]
        if a.source == "chexpert":
            ok = last == p[-1] if a.text.endswith("_") else last.startswith(p[-1])
        else:
            ok = last in (p[-1], p[-1] + "s", p[-1] + "es")
        if ok:
            out.append((i, i + len(p)))
    return out


def _cue_positions(tokens: list[str], cues: list[str]) -> list[tuple[int, int]]:
    return [(i, i + len(c.split())) for c in cues for i in _find(tokens, c.split())]


def clauses(tokens: list[str]) -> list[tuple[int, int]]:
    out, s = [], 0
    for i, t in enumerate(tokens):
        if t in BOUNDARIES:
            out.append((s, i))
            s = i + 1
    out.append((s, len(tokens)))
    return [(a, b) for a, b in out if b > a]


def mentions(text: str) -> list[Mention]:
    return list(_mentions(text))


@lru_cache(maxsize=65536)  # ponytail: per-process memo keyed on sentence text; the verifier re-scans sentences
def _mentions(text: str) -> tuple[Mention, ...]:
    tokens = normalise(text).split()
    labels = aliases()
    pseudo = _cue_positions(tokens, PSEUDO_NEG)

    def is_pseudo(a: int, b: int) -> bool:
        return any(pa <= a and b <= pb for pa, pb in pseudo)

    strong = [(a, b) for a, b in _cue_positions(tokens, STRONG_NEG) if not is_pseudo(a, b)]
    weak = _cue_positions(tokens, WEAK_NEG)
    follow = [(a, b) for a, b in _cue_positions(tokens, FOLLOW_NEG) if not is_pseudo(a, b)]
    hedge = _cue_positions(tokens, HEDGE)
    enlarge = _cue_positions(tokens, ENLARGE)

    raw: list[tuple[Alias, int, int]] = [
        (a, s, e) for als in labels.values() for a in als for s, e in _match(tokens, a)]
    # a span inside a strictly longer span is dropped: "pleural thickening" beats "thickening" (Other),
    # "airspace consolidation" beats "consolidation"
    raw = [(a, s, e) for a, s, e in raw
           if not any(bs <= s and e <= be and (be - bs) > (e - s) for _, bs, be in raw)]
    out: list[Mention] = []
    seen: set[tuple[str, int, int]] = set()
    for c0, c1 in clauses(tokens):
        for a, s, e in raw:
            if not (c0 <= s < c1) or (a.label, s, e) in seen:
                continue
            seen.add((a.label, s, e))
            neg = (any(c0 <= cs and ce <= s for cs, ce in strong)
                   or any(s - WEAK_SCOPE <= cs and ce <= s for cs, ce in weak)
                   or any(e <= cs and ce <= min(c1, e + FOLLOW_SCOPE) for cs, ce in follow))
            hed = any(c0 <= cs and ce <= c1 for cs, ce in hedge)
            asserted = not a.anchor or any(c0 <= cs and ce <= c1 for cs, ce in enlarge)
            out.append(Mention(a.label, a.text, s, e, neg, hed, asserted))
    return tuple(sorted(out, key=lambda m: (m.start, m.label)))


def redaction_adjacent(text: str, window: int = 2) -> bool:
    """[REDACTED] within `window` tokens of any alias mention (README §4.7)."""
    tokens = normalise(text).split()
    red = [i for i, t in enumerate(tokens) if t == "[redacted]"]
    return any(m.start - window <= r < m.end + window for m in mentions(text) for r in red)
