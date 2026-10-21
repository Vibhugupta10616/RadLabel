"""Leakage (README §5, invariant 1; owner hard stop, extended to M6): run_pipeline sees report text only."""

import builtins
import inspect
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_extractor import answer
from test_repair_leakage import FORBIDDEN_MODULES, FORBIDDEN_PATHS, FORBIDDEN_TEXT

from radlabel.llm import FakeLLM
from radlabel.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_import_closure_excludes_eval_and_ground_truth_modules() -> None:
    code = "import sys, json; import radlabel.pipeline; print(json.dumps(sorted(sys.modules)))"
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)
    assert not [m for m in mods if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_MODULES)]
    files = [Path(f) for m in mods if m.startswith("radlabel") and (f := getattr(__import__(m, fromlist=["x"]),
                                                                                  "__file__", None))]
    assert not [(f.name, w) for f in files for w in FORBIDDEN_TEXT if w in f.read_text(encoding="utf-8")]


def test_inputs_are_raw_text_only() -> None:
    assert list(inspect.signature(run_pipeline).parameters) == ["raw_text", "llm", "report_id", "agent"]


def test_run_never_opens_ground_truth_files(tmp_path: Path, monkeypatch: Any) -> None:
    opened: list[str] = []
    real = io.open

    def spy(file: Any, *a: Any, **k: Any) -> Any:
        opened.append(str(file).replace("\\", "/"))
        return real(file, *a, **k)
    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    seen: list[str] = []

    def responder(messages: list[dict[str, Any]]) -> str:
        seen.append(json.dumps(messages))
        return answer(Cardiomegaly=("present", ["F1"]))

    run_pipeline("FINDINGS: Mild cardiomegaly. IMPRESSION: No acute disease.", FakeLLM(responder, tmp_path), "7")
    assert not [p for p in opened if any(f in p for f in FORBIDDEN_PATHS)]
    assert not [w for w in ("MeSH", "expert", "fold", "macro", "ground truth") if w in " ".join(seen)]
