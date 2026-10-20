"""CLAUDE.md: every LLM call goes through src/radlabel/llm/. Nothing else may import the openai SDK."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ROOT / "src" / "radlabel" / "llm"
IMPORT = re.compile(r"^\s*(import openai|from openai\b)|^\s+import openai", re.M)


def test_openai_imported_only_in_llm_module() -> None:
    offenders = [str(p.relative_to(ROOT)) for d in ("src", "eval", "data_prep", "training", "demo", "deploy", "tests")
                 for p in (ROOT / d).rglob("*.py") if ALLOWED not in p.parents and IMPORT.search(p.read_text("utf-8"))]
    assert not offenders, offenders
