"""The built-in sample patient (data/sample/): five synthetic follow-up reports, written by hand, not IU text.

Their pipeline outputs are computed once through run_pipeline and stored in sample_results.json with the texts'
hash, so loading the sample needs no LLM call. If the texts change, results() runs the pipeline again.

Build: python -m radlabel.api.sample   (fresh LLM calls; a few cents)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from radlabel.llm import LLMClient
from radlabel.pipeline import PipelineResult, run_pipeline

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "sample"
FILES = ("R1.txt", "R2.txt", "R3.txt", "R4.txt", "R5.txt")
PRECOMPUTED = SAMPLE_DIR / "sample_results.json"


def texts() -> list[str]:
    return [(SAMPLE_DIR / f).read_text(encoding="utf-8") for f in FILES]


def digest(ts: list[str]) -> str:
    return hashlib.sha256("\x00".join(ts).encode()).hexdigest()


def results(llm: LLMClient) -> list[PipelineResult]:
    ts = texts()
    if PRECOMPUTED.exists():
        d = json.loads(PRECOMPUTED.read_text(encoding="utf-8"))
        if d["texts_sha256"] == digest(ts):
            return [PipelineResult.model_validate(r) for r in d["results"]]
    return [run_pipeline(t, llm, str(k)) for k, t in enumerate(ts, 1)]


def build(llm: LLMClient) -> list[PipelineResult]:
    ts = texts()
    out = [run_pipeline(t, llm, str(k)) for k, t in enumerate(ts, 1)]
    PRECOMPUTED.write_text(json.dumps({"texts_sha256": digest(ts),
                                       "results": [r.model_dump(mode="json", exclude={"agent": {"cached_calls"}})
                                                   for r in out]}, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    client = LLMClient(memory_cache=True)
    rs = build(client)
    print(f"{len(rs)} sample reports; LLM spend ${client.spent_today:.4f}")
