"""Build the serving index (SPEC §6.3, M8) from the M7 out-of-fold v2 outputs, then check it for leakage.

- Input: artifacts/predictions/verifier_agent_full.jsonl (one PipelineResult per unique report; v2 is zero-shot, so
  each report's labels come from a run that never saw its codes). Nothing else is read.
- Postgres: `alembic upgrade head`, then `reports` (sections as parsed; indication in its own column) and `labels`
  (predicted v2 labels with verification state, evidence, corroboration).
- Qdrant collection COLLECTION: report points (dense + BM25) and contextual sentence points (dense).
- Checks on the built index (results file): payload keys whitelisted on every stored point; no indication text in
  any point's text or payload; no fold, code or eval field; row counts.

Usage: python -m eval.index_build   (DATABASE_URL / QDRANT_URL must reach the compose services)
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from sqlalchemy import text as sql

from eval.retrieval import check_points, load_results
from radlabel.config import get_settings
from radlabel.db.store import engine
from radlabel.db.store import store as store_db
from radlabel.embeddings import search_encode
from radlabel.index import store
from radlabel.index.points import REPORT_KEYS, SENTENCE_KEYS, report_points
from radlabel.preprocess.aliases import normalise
from radlabel.results import write_result

COLLECTION = "radlabel_reports"
MIN_INDICATION_CHARS = 15  # shorter indications ("cough") can occur in findings text by coincidence


def main() -> dict[str, Any]:
    s = get_settings()
    res = load_results()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    eng = engine()
    n_db = store_db(eng, res.values())
    points = [p for i in sorted(res) for p in report_points(res[i])]
    check_points(points)
    client = QdrantClient(url=s.qdrant_url, timeout=120)
    vec = search_encode([p.text for p in points])  # the fine-tuned serving model once M9 selects it
    store.create(client, COLLECTION, vec.shape[1])
    store.upsert(client, COLLECTION, points, np.asarray(vec))

    stored, offset = [], None
    while True:
        batch, offset = client.scroll(COLLECTION, limit=1000, offset=offset, with_payload=True, with_vectors=False)
        stored += batch
        if offset is None:
            break
    text = {p.id: p.text for p in points}
    bad_keys = [str(p.id) for p in stored if p.payload is None or not set(p.payload) <= (
        REPORT_KEYS if p.payload.get("kind") == "report" else SENTENCE_KEYS)]
    forbidden = ("fold", "mesh", "major", "expert", "indication", "eval_")
    bad_words = [str(p.id) for p in stored if any(w in json.dumps(p.payload).lower() for w in forbidden)]
    indication_hits = 0
    by_report: dict[str, list[str]] = {}
    for p in stored:
        if p.payload:
            by_report.setdefault(p.payload["report_id"], []).append(
                normalise(text[str(p.id)] + " " + json.dumps(p.payload)))
    checked = coincidental = 0
    for i, r in res.items():
        ind = normalise(r.parse.indication.replace("XXXX", " "))
        if len(ind) >= MIN_INDICATION_CHARS and r.sections_identified:
            checked += 1
            found = any(ind in blob for blob in by_report.get(str(i), []))
            # the report's own Findings / Impression may repeat the indication's words: that is report text, not
            # the indication field leaking into the index
            own = ind in normalise(r.parse.findings + " " + r.parse.impression)
            indication_hits += found and not own
            coincidental += found and own
    with eng.connect() as c:
        counts = {t: c.execute(sql(f"select count(*) from {t}")).scalar_one() for t in ("reports", "labels")}
        cols = {t: [r[0] for r in c.execute(sql(
            "select column_name from information_schema.columns where table_name = :t order by ordinal_position"),
            {"t": t})] for t in ("reports", "labels")}
    out = {"reports_written": n_db, "postgres_rows": counts, "postgres_columns": cols,
           "qdrant_collection": COLLECTION, "points": len(stored),
           "report_points": sum(p.payload.get("kind") == "report" for p in stored if p.payload),
           "sentence_points": sum(p.payload.get("kind") == "sentence" for p in stored if p.payload),
           "check_payload_keys_whitelisted": not bad_keys, "check_no_forbidden_words_in_payloads": not bad_words,
           "check_indications_tested": checked, "check_indication_found_in_points": indication_hits,
           "indication_phrase_also_in_own_findings_or_impression": coincidental,
           "embedding_model": s.search_embed_model or s.embed_base_model,
           "source": "artifacts/predictions/verifier_agent_full.jsonl (M7 v2)"}
    assert not bad_keys and not bad_words and not indication_hits, out
    write_result("index_build", out, fold=None, mapping_version="v1", llm="none")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
