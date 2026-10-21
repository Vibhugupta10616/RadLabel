"""Evaluation subsets, exact definitions (SPEC §4.8). Eval-only: never imported by serving code.

- `hedged`, `redaction_adjacent`: imported unchanged from `data_prep/subset_stats.py`.
- Mentions for `negation_only` (and the mapping audit / noise adjustment): negspacy over the
  eval lexicon (`eval/lexicon.yaml`) with the frozen termset (`eval/negex_termset.yaml`), same eval
  version, independent of the pipeline's `negation.py`. Aliases match on lemmas of the lower-cased
  text (spaCy lookup lemmatizer), so singular/plural variants match; overlapping aliases of different
  labels (e.g. "air-fluid level") are kept for every label.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from data_prep.subset_stats import HEDGE, has_xxxx, is_hedged, is_redaction_adjacent

__all__ = ["has_xxxx", "is_hedged", "is_redaction_adjacent", "mentions", "clear_mention", "LEXICON",
           "negation_only_labels"]

HERE = Path(__file__).parent
_LEX = yaml.safe_load((HERE / "lexicon.yaml").read_text(encoding="utf-8"))
_TERMSET = yaml.safe_load((HERE / "negex_termset.yaml").read_text(encoding="utf-8"))
EVAL_VERSION: str = _LEX["version"]
assert _TERMSET["version"] == EVAL_VERSION
LEXICON: dict[str, list[str]] = _LEX["labels"]
_ENT = {f"L{i}": lab for i, lab in enumerate(LEXICON)}
SPANS = "eval_mentions"


@lru_cache
def _nlp() -> Any:
    import spacy
    from negspacy.negation import Negex  # noqa: F401  (registers the "negex" factory)

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    nlp.add_pipe("lemmatizer", config={"mode": "lookup"})
    nlp.initialize()  # loads the lookup tables (spacy-lookups-data)
    # SpanRuler (not EntityRuler): spans may overlap across labels; patterns are lemmatised too.
    ruler = nlp.add_pipe("span_ruler", config={"spans_key": SPANS, "phrase_matcher_attr": "LEMMA"})
    ruler.add_patterns([{"label": e, "pattern": p.lower()} for e, lab in _ENT.items() for p in LEXICON[lab]])
    nlp.add_pipe("negex", config={"neg_termset": _TERMSET["patterns"], "ent_types": list(_ENT),
                                  "span_keys": [SPANS]})
    return nlp


def mentions(findings: str, impression: str) -> dict[str, list[tuple[bool, bool]]]:
    """label -> one (negated, hedged) per mention. negated: negspacy; hedged: subset_stats HEDGE on its sentence."""
    out: dict[str, list[tuple[bool, bool]]] = {}
    for doc in _nlp().pipe([findings.lower(), impression.lower()]):
        for s in doc.spans[SPANS]:
            out.setdefault(_ENT[s.label_], []).append((bool(s._.negex), bool(HEDGE.search(s.sent.text))))
    return out


def clear_mention(ments: dict[str, list[tuple[bool, bool]]], label: str) -> bool:
    """A non-negated, non-hedged mention of the label."""
    return any(not neg and not hed for neg, hed in ments.get(label, []))


def negation_only_labels(ments: dict[str, list[tuple[bool, bool]]], expert: set[str]) -> list[str]:
    """Labels forming a negation_only pair: mentioned, every mention negated, no mention in a hedged
    sentence, expert code absent."""
    return sorted(lab for lab, ms in ments.items()
                  if all(neg and not hed for neg, hed in ms) and lab not in expert)


def is_abnormal(expert: set[str]) -> bool:
    return bool(expert - {"No Finding"})
