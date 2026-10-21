"""Index and Postgres rows (README §6.3, M8), including the leakage rules: payloads hold predicted labels only, no
codes from the dataset, folds, eval mentions or the indication."""

import json
import subprocess
import sys
from pathlib import Path

from test_extractor import answer
from test_repair_leakage import FORBIDDEN_MODULES, FORBIDDEN_TEXT

from radlabel.db.store import rows
from radlabel.index import bm25, store
from radlabel.index.points import REPORT_KEYS, SENTENCE_KEYS, context_prefix, report_points
from radlabel.llm import FakeLLM
from radlabel.pipeline import PipelineResult, run_pipeline

ROOT = Path(__file__).resolve().parents[1]
TEXT = ("INDICATION: persistent cough and fever for two weeks.\nFINDINGS: Mild cardiomegaly. No pleural effusion.\n"
        "IMPRESSION: Mild cardiomegaly.")


def result(tmp_path: Path) -> PipelineResult:
    return run_pipeline(TEXT, FakeLLM(lambda m: answer(Cardiomegaly=("present", ["F1", "I1"]),
                                                       Pleural_Effusion=("absent", ["F2"])), tmp_path), "42")


def test_points_payloads_whitelisted_and_no_indication(tmp_path: Path) -> None:
    pts = report_points(result(tmp_path))
    assert [p.kind for p in pts] == ["report", "sentence", "sentence", "sentence"]
    for p in pts:
        assert set(p.payload) <= (REPORT_KEYS if p.kind == "report" else SENTENCE_KEYS)
        blob = (p.text + json.dumps(p.payload)).lower()
        assert "cough" not in blob and "fever" not in blob and "fold" not in blob
    assert set(pts[0].payload["labels"]) == {"Cardiomegaly", "Pleural Effusion"}  # not_mentioned left out
    assert pts[0].payload["labels"]["Cardiomegaly"]["verification"] == "verified_rules"


def test_contextual_prefix_and_negation_tags(tmp_path: Path) -> None:
    pts = {p.payload.get("sentence_id"): p for p in report_points(result(tmp_path))}
    assert pts["F2"].text == "[Findings | report also mentions: cardiomegaly] No pleural effusion."
    assert pts["F2"].payload["negation_only"] and pts["F2"].payload["negated"] == ["Pleural Effusion"]
    assert pts["F1"].payload["affirmed"] == ["Cardiomegaly"] and not pts["F1"].payload["negation_only"]
    assert context_prefix("unknown", []) == "[Unknown] "


def test_postgres_rows_hold_predicted_labels_and_the_indication_separately(tmp_path: Path) -> None:
    rep, labs = rows(result(tmp_path))
    assert rep.indication == "persistent cough and fever for two weeks." and "cough" not in rep.findings
    assert {x.label for x in labs} == {f.label for f in result(tmp_path / "b").final}
    cardio = next(x for x in labs if x.label == "Cardiomegaly")
    assert (cardio.status, cardio.verification, cardio.evidence) == ("present", "verified_rules", ["F1", "I1"])


def test_bm25_weights_and_rrf() -> None:
    idfs = bm25.idf(["effusion effusion small", "small heart", "small lungs"])
    idx, val = bm25.doc_vector("effusion effusion small", avgdl=3.0, idfs=idfs)
    w = dict(zip(idx, val, strict=True))
    assert w[bm25.term_id("effusion")] > w[bm25.term_id("small")] > 0  # higher tf and rarer term
    assert bm25.query_vector("Small small effusion")[1] == [1.0, 1.0]
    fused = store.rrf([("a", 9.0), ("b", 8.0)], [("b", 0.9), ("c", 0.8)], top=3)
    assert [r for r, _ in fused] == ["b", "a", "c"]


def test_index_and_db_import_closure_excludes_eval_and_ground_truth() -> None:
    code = ("import sys, json; import radlabel.index.points, radlabel.index.store, radlabel.db.store; "
            "print(json.dumps(sorted(sys.modules)))")
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)
    assert not [m for m in mods if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_MODULES)]
    files = [Path(f) for m in mods if m.startswith("radlabel") and (f := getattr(__import__(m, fromlist=["x"]),
                                                                                  "__file__", None))]
    assert not [(f.name, w) for f in files for w in FORBIDDEN_TEXT if w in f.read_text(encoding="utf-8")]


def test_store_writes_reports_before_labels_and_is_idempotent(tmp_path: Path) -> None:
    from sqlalchemy import create_engine, event, select

    from radlabel.db.models import Base, Label, Report
    from radlabel.db.store import store as store_db

    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    event.listen(eng, "connect", lambda c, _: c.execute("pragma foreign_keys=ON"))  # enforce the FK like Postgres
    Base.metadata.create_all(eng)
    r = result(tmp_path / "r")
    assert store_db(eng, [r, r.model_copy(update={"report_id": "43"})]) == 2
    assert store_db(eng, [r]) == 1  # rerun replaces the report's rows
    from sqlalchemy.orm import Session
    with Session(eng) as s:
        assert len(s.scalars(select(Report)).all()) == 2 and len(s.scalars(select(Label)).all()) == 26


def test_ties_are_broken_deterministically() -> None:
    """Qdrant returns tied scores in no fixed order; the top k must not depend on it (found after M8)."""
    import random
    from types import SimpleNamespace

    pts = [SimpleNamespace(id=f"p{i}", score=s, payload={"report_id": str(i)}) for i, s in
           enumerate([0.9, 0.5, 0.5000000001, 0.4999999999, 0.5, 0.1])]  # ties up to float noise

    class Fake:
        def query_points(self, name: str, *, limit: int, score_threshold: float | None = None, **kw: object) -> object:
            hits = [p for p in pts if score_threshold is None or p.score >= score_threshold]
            random.shuffle(hits)  # arbitrary order, including among ties
            return SimpleNamespace(points=sorted(hits, key=lambda p: -round(p.score, 6))[:limit])

    tops = {tuple(store._top(Fake(), "c", [0.0], "dense", store._kind("report"), 3)) for _ in range(20)}  # type: ignore[arg-type]
    assert tops == {(("0", "p0", 0.9), ("1", "p1", 0.5), ("2", "p2", 0.5))}
