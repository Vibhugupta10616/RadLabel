"""Leakage (owner, M5): the repair agent never sees MeSH ground truth, eval mentions, fold assignments or metrics."""

import builtins
import inspect
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_repair_agent import FAILING, SENTS, call, script

from radlabel.labelling import repair_agent
from radlabel.labelling.repair_agent import repair
from radlabel.llm import FakeLLM

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODULES = ("eval", "data_prep", "training", "radlabel.results")
# files holding expert codes, eval-detector mentions, folds/subsets, metrics or predictions with scores
FORBIDDEN_PATHS = ("expert_labels", "eval_mentions", "data/splits", "artifacts/results", "artifacts/tables",
                   "artifacts/predictions", "iu.jsonl", "iu_mapped")
FORBIDDEN_TEXT = ("expert_labels", "eval_mentions", "folds.csv", "inner_val", "data/splits",
                  "macro_f1", "bootstrap", "MeSH", "major")


def test_import_closure_excludes_eval_and_ground_truth_modules() -> None:
    code = ("import sys, json; import radlabel.labelling.repair_agent; "
            "print(json.dumps(sorted(m for m in sys.modules)))")
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)
    bad = [m for m in mods if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_MODULES)]
    assert not bad, bad
    src = [m for m in mods if m.startswith("radlabel")]
    hits = [(m, w) for m in src for w in FORBIDDEN_TEXT
            if (f := getattr(sys.modules.get(m) or __import__(m, fromlist=["x"]), "__file__", None))
            and w in Path(f).read_text(encoding="utf-8")]
    assert not hits, hits


def test_inputs_are_report_and_tier1_output_only() -> None:
    assert list(inspect.signature(repair).parameters) == ["llm", "report_id", "sentences", "verified"]


def test_tools_and_messages_never_open_ground_truth_files(tmp_path: Path, monkeypatch: Any) -> None:
    repair_agent.definitions.cache_clear()
    opened: list[str] = []
    real = io.open

    def spy(file: Any, *a: Any, **k: Any) -> Any:
        opened.append(str(file).replace("\\", "/"))
        return real(file, *a, **k)
    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    seen: list[str] = []

    def responder(messages: list[dict[str, Any]]) -> Any:
        seen.append(json.dumps(messages))
        return script([call("get_sentence", sentence_id="F1")], [call("check_negation", sentence_id="I1")],
                      [call("get_label_rules", label="Cardiomegaly")], [call("compare_sections", label="Cardiomegaly")],
                      [call("submit_fix", labels=[], reason="x")])(messages)

    repair(FakeLLM(responder, tmp_path), "1", SENTS, FAILING)
    bad = [p for p in opened if any(f in p for f in FORBIDDEN_PATHS)]
    assert not bad, bad
    text = " ".join(seen)
    assert not [w for w in ("MeSH", "expert", "fold", "macro", "ground truth", "F1 score") if w in text]
