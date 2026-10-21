"""Leakage (owner hard stop, M7): the verifier agent never sees codes from the dataset, eval mentions, folds or
metrics."""

import builtins
import inspect
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_repair_agent import call, script
from test_repair_leakage import FORBIDDEN_MODULES, FORBIDDEN_PATHS, FORBIDDEN_TEXT
from test_verifier_agent import fake_encoder, run  # noqa: F401  (autouse fixture: no model download)

from radlabel.labelling import verifier_agent as va

ROOT = Path(__file__).resolve().parents[1]


def test_import_closure_excludes_eval_and_ground_truth_modules() -> None:
    code = "import sys, json; import radlabel.labelling.verifier_agent; print(json.dumps(sorted(sys.modules)))"
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)
    assert not [m for m in mods if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_MODULES)]
    files = [Path(f) for m in mods if m.startswith("radlabel") and (f := getattr(__import__(m, fromlist=["x"]),
                                                                                  "__file__", None))]
    assert not [(f.name, w) for f in files for w in FORBIDDEN_TEXT if w in f.read_text(encoding="utf-8")]


def test_inputs_are_report_tagger_statuses_and_escalations_only() -> None:
    assert list(inspect.signature(va.run_agent).parameters) == [
        "llm", "report_id", "sentences", "tagger", "esc", "sections_identified"]


def test_blind_first_and_no_ground_truth_in_messages_or_files(tmp_path: Path, monkeypatch: Any) -> None:
    opened: list[str] = []
    real = io.open

    def spy(file: Any, *a: Any, **k: Any) -> Any:
        opened.append(str(file).replace("\\", "/"))
        return real(file, *a, **k)
    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    seen: list[str] = []
    steps = script(*[[call(n, **a)] for n, a in (
        ("find_by_alias", {"label": "Pleural Effusion"}), ("find_by_meaning", {"label": "Pleural Effusion"}),
        ("check_negation", {"sentence_id": "F1"}), ("compare_sections", {"label": "Pleural Effusion"}),
        ("check_redaction", {"sentence_id": "F1"}), ("get_label_definition", {"label": "Pleural Effusion"}),
        ("normal_check", {}), ("submit", {"labels": []}))])

    def responder(messages: list[dict[str, Any]]) -> Any:
        seen.append(json.dumps(messages))
        return steps(messages)
    run(responder, tmp_path, "Small left pleural effusion.", "", Pleural_Effusion=("present", ["F1"]))
    assert not [p for p in opened if any(f in p for f in FORBIDDEN_PATHS)]
    first_user = json.loads(seen[0])[1]["content"]
    assert "Pleural Effusion: present" in first_user and "['F1']" not in first_user  # statuses, no evidence
    assert not [w for w in ("MeSH", "expert", "fold", "macro", "ground truth") if w in " ".join(seen)]
