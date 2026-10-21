"""Invariant: serving code never reads expert labels (SPEC §5, invariant 1)."""

import json
import re
import subprocess
import sys
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


def test_src_never_imports_eval_at_runtime() -> None:
    """Import every radlabel module; none may pull in eval/, data_prep/ or training/ (also catches dynamic imports
    that the regex above can't see, e.g. inside functions)."""
    code = ("import importlib, json, pkgutil, sys, radlabel\n"
            "for m in pkgutil.walk_packages(radlabel.__path__, 'radlabel.'): importlib.import_module(m.name)\n"
            "print(json.dumps(sorted(sys.modules)))")
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=SRC.parents[1]).stdout)
    assert "radlabel.pipeline" in mods
    assert not [m for m in mods if m.split(".")[0] in ("eval", "data_prep", "training")]
