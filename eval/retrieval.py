"""Retrieval evaluation (README §8.2, M8): base models, per fold and pooled. Spec: eval/queries/retrieval_v1.yaml
(frozen before any run). Relevance comes from the v1 expert codes, here on the eval side only; the index (built by
radlabel.index from the M7 predictions) never sees them.

Per fold k: a temporary Qdrant collection holds only the fold-k representatives (same point builder as serving, no
fold field anywhere); every query runs against it; metrics per (query, fold); pooled = mean over the pairs with
>= 1 relevant report, 95% bootstrap CIs over those pairs.

Usage: python -m eval.retrieval materialize | run   (QDRANT_URL must reach the compose service, e.g. localhost)
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from qdrant_client import QdrantClient

from eval.labelling import PRED_DIR, PROC, TABLES, Items
from radlabel.config import get_settings
from radlabel.embeddings import QUERY_PREFIX, encode
from radlabel.index import store
from radlabel.index.points import REPORT_KEYS, SENTENCE_KEYS, IndexPoint, report_points
from radlabel.labels import FINDING_LABELS, NO_FINDING
from radlabel.pipeline import PipelineResult
from radlabel.preprocess.aliases import aliases, normalise
from radlabel.results import write_result

SPEC = Path("eval/queries/retrieval_v1.yaml")
MATERIALIZED = Path("eval/queries/retrieval_v1_queries.json")  # query texts and query report ids only, committed
TMP, TMP_PLAIN = "radlabel_eval_tmp", "radlabel_eval_tmp_plain"
VARIANTS = ("bm25", "dense_report", "dense_sentence", "dense_sentence_ctx", "dense_sentence_ctx_filter", "rrf")
SETS = ("seen_label", "heldout_label", "heldout_alias", "attribute", "compositional", "report_to_report")
K, DEEP, N_BOOT = 10, 100, 1000


def spec() -> dict[str, Any]:
    return dict(yaml.safe_load(SPEC.read_text(encoding="utf-8")))


def findings_snippet(sentences: list[dict[str, Any]]) -> str:
    return " ".join([s["text"] for s in sentences if s["section"] == "findings"][:2])


def materialize(it: Items, sp: dict[str, Any]) -> list[dict[str, Any]]:
    """Every query, fixed by the spec: label / alias / hand-written texts and report-to-report query report ids."""
    held = sp["label_queries"]["heldout_labels"]
    seen = [lab for lab in FINDING_LABELS if lab not in held]
    qs: list[dict[str, Any]] = []
    qs += [{"id": f"L:{lab}", "set": "seen_label", "text": lab.lower(), "label": lab, "target": lab} for lab in seen]
    qs += [{"id": f"H:{lab}", "set": "heldout_label", "text": lab.lower(), "label": lab, "target": lab}
           for lab in held]
    for lab in seen:
        for a in aliases()[lab]:
            t = a.text.replace("_", " ").strip()
            if a.heldout and a.source == "hand" and not a.anchor and normalise(t) != normalise(lab):
                qs.append({"id": f"HA:{lab}:{t}", "set": "heldout_alias", "text": t, "label": lab, "target": lab})
    for h in sp["handwritten"]:
        qs.append({"id": h["id"], "set": h["type"], "text": h["text"], "target": h.get("target"),
                   **{k: h[k] for k in ("code", "labels", "none_codes") if k in h}})
    r2r = sp["report_to_report"]
    sents = {r["id"]: r["sentences"] for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8"))}
    fold = dict(zip(it.ids, it.fold.tolist(), strict=True))
    abn = dict(zip(it.ids, it.subset["abnormal"].tolist(), strict=True))
    for k in sorted(set(fold.values())):
        pool = sorted(i for i in it.ids if fold[i] == k and abn[i]
                      and any(s["section"] == "findings" for s in sents[i]))
        qs += [{"id": f"R:{i}", "set": "report_to_report", "fold": k, "report_id": i, "target": None}
               for i in sorted(random.Random(r2r["seed"] + k).sample(pool, r2r["per_fold"]))]
    return qs


class Relevance:
    """Eval side only: expert codes and the eval detector's mentions."""

    def __init__(self, it: Items) -> None:
        self.it = it
        codes = {e["id"]: e["major"] for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8"))}
        self.codes = {i: [[p.strip().lower() for p in c.split("/")] for c in codes[i]] for i in it.ids}
        pos = {i: k for k, i in enumerate(it.ids)}
        self.labels = {i: {lab for lab, v in it.gold["v1"].items() if v[pos[i]]} for i in it.ids}
        self.ments = {m["id"]: m["mentions"] for m in map(json.loads, (PROC / "eval_mentions.jsonl").open(
            encoding="utf-8"))}

    def gains(self, q: dict[str, Any], ids: list[int]) -> dict[int, float]:
        if q["set"] == "report_to_report":
            a = self.labels[q["report_id"]] - {NO_FINDING}
            out = {}
            for i in ids:
                b = self.labels[i] - {NO_FINDING}
                if i != q["report_id"] and a & b:
                    out[i] = len(a & b) / len(a | b)
            return out
        return {i: 1.0 for i in ids if self.relevant(q, i)}

    def relevant(self, q: dict[str, Any], i: int) -> bool:
        if "label" in q:
            return q["label"] in self.labels[i]
        ok = True
        if "code" in q:
            head, subs = q["code"]["head"].lower(), {s.lower() for s in q["code"]["subs"]}
            ok = any(c[0] == head and subs <= set(c[1:]) for c in self.codes[i])
        if "labels" in q:
            ok = ok and set(q["labels"].get("all_of", [])) <= self.labels[i] and not (
                set(q["labels"].get("none_of", [])) & self.labels[i])
        if "none_codes" in q:
            ok = ok and not any(c[0] in [h.lower() for h in q["none_codes"]] for c in self.codes[i])
        return ok

    def contaminated(self, target: str, i: int) -> bool:
        ms = self.ments.get(i, {}).get(target, [])
        return bool(ms) and all(neg for neg, _ in ms)


def metrics(ranked: list[int], gains: dict[int, float], target: str | None, rel: Relevance) -> dict[str, Any]:
    top = ranked[:K]
    dcg = sum(gains.get(d, 0.0) / math.log2(r + 2) for r, d in enumerate(top))
    ideal = sum(g / math.log2(r + 2) for r, g in enumerate(sorted(gains.values(), reverse=True)[:K]))
    return {"recall": sum(d in gains for d in top) / min(K, len(gains)), "ndcg": dcg / ideal,
            "contamination": (sum(rel.contaminated(target, d) for d in top) / len(top))
            if target in FINDING_LABELS and top else None}


def _ci(values: list[float], seed: int = 13) -> dict[str, float] | None:
    if not values:
        return None
    v = np.array(values)
    rng = np.random.default_rng(seed)
    boots = [float(v[rng.integers(0, len(v), len(v))].mean()) for _ in range(N_BOOT)]
    return {"value": float(v.mean()), "lo": float(np.percentile(boots, 2.5)), "hi": float(np.percentile(boots, 97.5))}


def load_results() -> dict[int, PipelineResult]:
    return {int(r.report_id): r for r in (PipelineResult.model_validate_json(x) for x in
                                         (PRED_DIR / "verifier_agent_full.jsonl").open(encoding="utf-8"))}


def check_points(points: list[IndexPoint]) -> None:
    """Leakage guard on every point before it is indexed (tests cover the builder; this covers the real data)."""
    for p in points:
        allowed = REPORT_KEYS if p.kind == "report" else SENTENCE_KEYS
        assert set(p.payload) <= allowed, (p.id, set(p.payload) - allowed)


def run() -> dict[str, Any]:
    it, sp = Items(), spec()
    queries = json.loads(MATERIALIZED.read_text(encoding="utf-8"))["queries"]
    assert queries == materialize(it, sp), "materialized queries differ from the frozen spec"
    rel = Relevance(it)
    res = load_results()
    points = {i: report_points(res[i]) for i in it.ids}
    flat = [p for i in it.ids for p in points[i]]
    check_points(flat)
    vec = dict(zip([p.id for p in flat], encode([p.text for p in flat]), strict=True))
    # pure-embedding row: the same sentence points without the predicted-label prefix
    raw = {i: {s.id: s.text for s in res[i].sentences} for i in it.ids}
    plain = {i: [p.model_copy(update={"text": raw[i][p.payload["sentence_id"]]}) for p in points[i]
                 if p.kind == "sentence"] for i in it.ids}
    flat_plain = [p for i in it.ids for p in plain[i]]
    vec_plain = dict(zip([p.id for p in flat_plain], encode([p.text for p in flat_plain]), strict=True))
    sents = {r["id"]: r["sentences"] for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8"))}
    qtext = {q["id"]: q["text"] if q["set"] != "report_to_report" else findings_snippet(sents[q["report_id"]])
             for q in queries}
    qvec = dict(zip(qtext, encode([qtext[q["id"]] if q["set"] == "report_to_report" else QUERY_PREFIX + qtext[q["id"]]
                                   for q in queries]), strict=True))
    client = QdrantClient(url=get_settings().qdrant_url, timeout=120)
    fold = dict(zip(it.ids, it.fold.tolist(), strict=True))
    pairs: dict[str, dict[str, list[dict[str, Any]]]] = {v: {s: [] for s in SETS} for v in VARIANTS}
    skipped = {s: 0 for s in SETS}
    for k in sorted(set(fold.values())):
        ids = [i for i in it.ids if fold[i] == k]
        fp = [p for i in ids for p in points[i]]
        store.create(client, TMP, len(next(iter(vec.values()))))
        store.upsert(client, TMP, fp, np.array([vec[p.id] for p in fp]))
        pp = [p for i in ids for p in plain[i]]
        store.create(client, TMP_PLAIN, len(next(iter(vec.values()))))
        store.upsert(client, TMP_PLAIN, pp, np.array([vec_plain[p.id] for p in pp]))
        for q in queries:
            if q["set"] == "report_to_report" and q["fold"] != k:
                continue
            gains = rel.gains(q, ids)
            if not gains:
                skipped[q["set"]] += 1
                continue
            drop = str(q.get("report_id", ""))
            text, v = qtext[q["id"]], np.asarray(qvec[q["id"]])
            bm = store.search_bm25(client, TMP, text, DEEP + 1)
            dn = store.search_sentences(client, TMP, v, DEEP + 1)
            ranked = {"bm25": bm, "dense_report": store.search_reports(client, TMP, v, K + 1),
                      "dense_sentence": store.search_sentences(client, TMP_PLAIN, v, K + 1), "dense_sentence_ctx": dn,
                      "dense_sentence_ctx_filter": store.search_sentences(client, TMP, v, K + 1,
                                                                          exclude_negation_only=True),
                      "rrf": store.rrf([x for x in bm if x[0] != drop], [x for x in dn if x[0] != drop], top=K + 1)}
            for name, rk in ranked.items():
                order = [int(r) for r, _ in rk if r != drop]
                pairs[name][q["set"]].append({"query": q["id"], "fold": k, **metrics(order, gains, q["target"], rel)})
    client.delete_collection(TMP)
    client.delete_collection(TMP_PLAIN)

    out: dict[str, Any] = {"n_queries": dict(sorted({s: sum(q["set"] == s for q in queries) for s in SETS}.items())),
                           "skipped_pairs_no_relevant": skipped,
                           "index": {"report_points": sum(p.kind == "report" for p in flat),
                                     "sentence_points": sum(p.kind == "sentence" for p in flat),
                                     "negation_only_sentences": sum(bool(p.payload.get("negation_only"))
                                                                    for p in flat)},
                           "embedding_model": get_settings().embed_base_model, "variants": {}}
    for name in VARIANTS:
        block: dict[str, Any] = {}
        for s in (*SETS, "all"):
            rows = [x for ss in SETS for x in pairs[name][ss]] if s == "all" else pairs[name][s]
            per_fold = {str(k): {m: (float(np.mean(vals)) if (vals := [x[m] for x in rows if x["fold"] == k
                                                                       and x[m] is not None]) else None)
                                 for m in ("recall", "ndcg", "contamination")} for k in sorted(set(fold.values()))}
            block[s] = {"n_pairs": len(rows), "recall": _ci([x["recall"] for x in rows]),
                        "ndcg": _ci([x["ndcg"] for x in rows]),
                        "contamination": _ci([x["contamination"] for x in rows if x["contamination"] is not None]),
                        "per_fold": per_fold}
        out["variants"][name] = block
    write_result("retrieval_base", out, fold="per fold + pooled", mapping_version="v1", eval_version="eval_v1.2",
                 retrieval_spec=sp["version"], llm="none")
    (TABLES / "retrieval_base.md").write_text(render(out), encoding="utf-8")
    return out


NAMES = {"bm25": "BM25", "dense_report": "base bge-small, report-level",
         "dense_sentence": "base bge-small, sentences without prefix (pure embedding)",
         "dense_sentence_ctx": "base bge-small, contextual sentences",
         "dense_sentence_ctx_filter": "base bge-small + negated-sentence payload filter (no training)",
         "rrf": "base contextual sentences + BM25 (RRF)"}


def reading(out: dict[str, Any]) -> str:
    """Plain-language reading for README §10: the best variant per query set by nDCG@10, from the results."""
    v = out["variants"]
    best = {s: max(VARIANTS, key=lambda x: v[x][s]["ndcg"]["value"]) for s in (*SETS, "all")}
    seen = v["dense_sentence_ctx_filter"]["seen_label"], v["dense_sentence_ctx"]["seen_label"]
    return ("**Reading (M8).** Best variant by nDCG@10: " + "; ".join(
        f"{s.replace('_', ' ')} {NAMES[b]} ({v[b][s]['ndcg']['value']:.3f})" for s, b in best.items()) + ". "
        "The negated-sentence filter lowers negation contamination on the label queries (seen labels "
        f"{seen[1]['contamination']['value']:.3f} → {seen[0]['contamination']['value']:.3f}). Part of its gain comes "
        "from the contextual prefix, which names the PREDICTED v2 labels: once the \"No X\" sentences are filtered "
        "out, sentences whose prefix mentions X come from reports predicted positive for X, so this row partly "
        "measures the labelling pipeline, not only the embeddings. It is the baseline the fine-tuned model must "
        "beat (M10, judged two ways, README §8.2). Base models only; no held-out effect is expected before "
        "fine-tuning.")


def render(out: dict[str, Any], sets: tuple[str, ...] = (*SETS, "all")) -> str:
    def f(d: dict[str, float] | None) -> str:
        return "–" if d is None else f"{d['value']:.3f} ({d['lo']:.3f}–{d['hi']:.3f})"
    lines = []
    for s in sets:
        n = out["variants"]["bm25"][s]["n_pairs"]
        lines += [f"**{s.replace('_', ' ')}** ({n} query–fold pairs)", "",
                  "| Variant | Recall@10 | nDCG@10 | Neg. contam.@10 |", "|---|---|---|---|"]
        lines += [f"| {NAMES[v]} | {f(out['variants'][v][s]['recall'])} | {f(out['variants'][v][s]['ndcg'])} | "
                  f"{f(out['variants'][v][s]['contamination'])} |" for v in VARIANTS]
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    if sys.argv[1:] == ["materialize"]:
        qs = materialize(Items(), spec())
        MATERIALIZED.write_text(json.dumps({"spec": spec()["version"], "queries": qs}, indent=1) + "\n",
                                encoding="utf-8")
        print({s: sum(q["set"] == s for q in qs) for s in SETS})
    else:
        r = run()
        print(json.dumps(r["n_queries"]), json.dumps(r["skipped_pairs_no_relevant"]))
