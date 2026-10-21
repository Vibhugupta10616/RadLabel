"""Fine-tuning pairs (SPEC §6.3, M9): fold k never contributes to fold k's pairs; held-out labels and aliases are
never queries; the eval-only detector is never used."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from radlabel.preprocess.aliases import aliases, normalise
from radlabel.preprocess.negation import mentions
from training import build_pairs as bp
from training.build_pairs import Report

ROOT = Path(__file__).resolve().parents[1]


def reports() -> list[Report]:
    """Cluster c is in fold c % 5; fold 0's inner validation is cluster 6 (fold 1). Sentences carry a unique tag."""
    out = []
    for c in range(20):
        tag = f"zzfold{c % 5}c{c}"
        out.append(Report(c, c, [f"Small left pleural effusion {tag}.", f"No pneumothorax {tag}.",
                                 f"Heart size is enlarged {tag}.", f"Possible atelectasis {tag}."],
                          {"Pleural Effusion", "Cardiomegaly"}))
    return out


def test_fold_k_never_reaches_fold_k_pairs(monkeypatch: Any) -> None:
    monkeypatch.setattr(bp, "load_folds", lambda: ({c: c % 5 for c in range(20)}, {0: {6}}))
    f = bp.build(0, reports())
    fold0 = {r.id for r in reports() if r.cluster % 5 == 0}
    assert f.triplets and not (f.sources & fold0) and not (f.train_ids & fold0)
    text = " ".join(" ".join(t) for t in f.triplets)
    assert "zzfold0" not in text  # no fold-0 sentence text in fold 0's pairs
    assert "zzfold1c6." not in text and [r.id for r in f.inner] == [6]  # inner validation held out of training


def test_queries_exclude_heldout_labels_and_aliases() -> None:
    qs = bp.queries()
    assert not set(qs) & set(bp.HELDOUT_LABELS)
    held = {normalise(a.text.replace("_", " ")) for als in aliases().values() for a in als if a.heldout}
    assert not {normalise(q) for v in qs.values() for q in v} & held
    spec = yaml.safe_load((ROOT / "eval/queries/retrieval_v1.yaml").read_text(encoding="utf-8"))
    assert tuple(spec["label_queries"]["heldout_labels"]) == bp.HELDOUT_LABELS


def test_positives_state_the_finding_negatives_do_not() -> None:
    trips, _ = bp.triplets(reports(), seed=1)
    for q, p, n in trips:
        lab = next(lab for lab, qs in bp.queries().items() if q in qs)
        assert any(m.label == lab and m.affirmed for m in mentions(p))
        assert not any(m.label == lab and m.affirmed for m in mentions(n))


def test_pairs_never_use_the_eval_detector() -> None:
    code = "import sys, json; import training.build_pairs; print(json.dumps(sorted(sys.modules)))"
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)
    assert not [m for m in mods if m in ("eval.subsets", "negspacy", "spacy") or m.startswith("negspacy.")]
    src = (ROOT / "training/build_pairs.py").read_text(encoding="utf-8")
    assert "eval.subsets" not in src and 'lexicon.yaml")' not in src and "negspacy import" not in src
