# ruff: noqa: E501  (long report-text lines in the renderers)
"""M10b scoring (pre-registered in docs/evaluation_notes.md, "Ask evaluation"): reads the records written by
`python -m eval.ask run`, scores them by the fixed rules in eval/ask.py, writes artifacts/results/ask_eval.json
(counts, rates, CIs; no report text) and a git-ignored sample of parsed answers for reading by hand.

Usage: python -m eval.ask_score
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np

from eval import ask as ev
from radlabel.api.session import sections_of
from radlabel.config import get_settings
from radlabel.labels import NO_FINDING
from radlabel.results import RESULTS_DIR, write_result

N_BOOT = 1000
ANALYSIS = RESULTS_DIR.parent / "analysis" / "ask_parse_samples.md"  # git-ignored (answers quote report text)


# ------------------------------------------------------------------ scoring one record
def classify(q: dict[str, Any], rec: dict[str, Any]) -> dict[str, Any]:
    """Parsed class and correctness vs the codes and vs v2 (None = not scored)."""
    a, r, kind = rec["answer"], rec["refusal"], q["kind"]
    if kind in ("yn", "support"):
        cls = ev.parse_yn(a, r)
    elif kind == "certainty":
        cls = ev.parse_certainty(a, r)
    elif kind == "which":
        cls = ev.parse_which(a, r)
    elif kind == "count":
        cls = ev.parse_count(a, r)
    elif kind == "first":
        cls = ev.parse_first(a, r)
    else:
        cls = "answered" if a is not None else "refused"

    def ok(exp: Any) -> bool | None:
        if exp is None:
            return None
        if kind == "support":
            return cls not in ("notstated", "refused", "no") if exp == ["answered"] else cls in exp
        if kind in ("yn", "certainty", "refuse"):
            return cls in exp
        if kind == "which":
            return cls == set(exp)
        return cls == exp
    unreadable = cls is None or cls == "other"
    codes = None if q.get("hedged") else ok(q["codes"])
    return {"cls": "unreadable" if unreadable else (sorted(cls) if isinstance(cls, set) else cls),
            "unreadable": unreadable, "correct_codes": codes, "correct_v2": ok(q["v2"]),
            "lenient": lenient_refusal(rec) if kind == "refuse" else None}


NOT_STATED_RE = re.compile(r"\b(do(?:es)? not|don't|doesn't|cannot|can't|unable to)\b.*\b(state|specify|provide|"
                           r"mention|describe|contain|determine|include|say|give|know)\b|\bno (?:information|mention)\b|"
                           r"\bnot (?:stated|mentioned|provided|specified|available|described)\b")


def lenient_refusal(rec: dict[str, Any]) -> bool:
    """POST-HOC (not pre-registered): the frozen scoring note also accepts an answer that says the reports don't state
    it, with no invented value. True if the record is a refusal, or its answer says "not stated" and contains no
    digit and no diagnosis word (a redacted age such as "[REDACTED]-year-old" is not an invented value)."""
    a = rec["answer"]
    if a is None:
        return True
    t = a.lower().replace("[redacted]", "")
    return bool(NOT_STATED_RE.search(t)) and not re.search(r"\d|cancer|malignan|carcinoma|tumou?r", t)


def affirms(q: dict[str, Any], rec: dict[str, Any], c: dict[str, Any]) -> bool:
    """The answer asserts the finding is there (so its citations should name it)."""
    if q.get("label") in (None, NO_FINDING) or q.get("frozen") == 9:
        return False
    cls, kind = c["cls"], q["kind"]
    if kind == "yn":
        return cls in ("yes", "uncertain")
    if kind == "support":
        return cls not in ("notstated", "refused", "no")
    if kind == "certainty":
        return cls in ("certain", "possible")
    if kind == "which":
        return bool(cls) and cls != "unreadable"
    if kind == "count":
        return isinstance(cls, int) and cls > 0
    if kind == "first":
        return isinstance(cls, int)
    return False


def cite_support(d: ev.Data, q: dict[str, Any], rec: dict[str, Any], rids: dict[int, int]) -> tuple[bool, bool] | None:
    """(at least one, every) valid cited sentence has a non-negated eval-detector mention of the label."""
    if not rec["citations"]:
        return None
    ok = []
    for c in rec["citations"]:
        text = next((s.text for ss in sections_of(d.results[rids[c["report_no"]]]).values() for s in ss
                     if s.id == c["sentence_id"]), "")
        ok.append(any(not neg for neg, _ in ev.sentence_mentions(text).get(q["label"], [])))
    return any(ok), all(ok)


# ------------------------------------------------------------------ statistics
def boot(vals: list[float], clusters: list[Any], seed: str) -> dict[str, float]:
    """Mean with a 95% percentile bootstrap CI, resampling whole clusters."""
    if not vals:
        return {"n": 0, "value": float("nan"), "lo": float("nan"), "hi": float("nan")}
    by: dict[Any, list[float]] = defaultdict(list)
    for v, c in zip(vals, clusters, strict=True):
        by[c].append(v)
    sums = np.array([sum(x) for x in by.values()])
    cnt = np.array([len(x) for x in by.values()], float)
    idx = np.random.default_rng(int.from_bytes(seed.encode(), "little") % 2**32).integers(
        0, len(sums), (N_BOOT, len(sums)))
    est = sums[idx].sum(1) / cnt[idx].sum(1)
    return {"n": len(vals), "k": int(sum(vals)), "value": float(np.mean(vals)),
            "lo": float(np.percentile(est, 2.5)), "hi": float(np.percentile(est, 97.5))}


def rate(rows: list[dict[str, Any]], field: str, cluster: str, seed: str) -> dict[str, float]:
    sel = [r for r in rows if r[field] is not None]
    return boot([float(r[field]) for r in sel], [r[cluster] for r in sel], seed)


def pct(x: float, ci: bool = False) -> str:
    return "–" if x != x else f"{100 * x:.1f}%"


def pcts(d: dict[str, float]) -> str:
    return "–" if d["n"] == 0 else f"{100 * d['value']:.1f}% ({100 * d['lo']:.0f}–{100 * d['hi']:.0f}) n={d['n']}"


def quantile(xs: list[float], q: float) -> float | None:
    return float(np.percentile(xs, q)) if xs else None


# ------------------------------------------------------------------ aggregation
def costs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fresh = [r["latency_s"] for r in rows if not r["cached"]]
    n = max(1, len(rows))
    return {"requests": len(rows), "mean_input_tokens": sum(r["input_tokens"] for r in rows) / n,
            "mean_output_tokens": sum(r["output_tokens"] for r in rows) / n,
            "mean_cost_usd": sum(r["cost_usd"] for r in rows) / n, "total_cost_usd": sum(r["cost_usd"] for r in rows),
            "latency_fresh_requests": len(fresh), "latency_p50_s": quantile(fresh, 50),
            "latency_p95_s": quantile(fresh, 95)}


def citations(rows: list[dict[str, Any]], seed: str) -> dict[str, Any]:
    raw = sum(r["raw_n"] for r in rows)
    valid = sum(r["valid_n"] for r in rows)
    sup = [r for r in rows if r["support_any"] is not None]
    return {"raw_citations": raw, "valid_citations": valid, "structural_valid_rate": valid / raw if raw else None,
            "answers_lost_to_the_check": sum(r["lost"] for r in rows),
            "affirming_answers_scored": len(sup),
            "support_any": boot([float(r["support_any"]) for r in sup], [r["cluster"] for r in sup], seed + "a"),
            "support_all": boot([float(r["support_all"]) for r in sup], [r["cluster"] for r in sup], seed + "b")}


def refusals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    refuse = [r for r in rows if r["should"] == "refuse"]
    answer = [r for r in rows if r["should"] == "answer"]
    tp = sum(r["refused"] for r in refuse)
    fp = sum(r["refused"] for r in answer)
    fn = len(refuse) - tp
    return {"should_refuse": len(refuse), "should_answer": len(answer), "true_refusals": tp, "false_refusals": fp,
            "missed_refusals": fn, "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def paired(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], field: str, seed: str) -> dict[str, Any]:
    """RAG - baseline on the same questions, bootstrap over questions."""
    b = {r["qid"]: r for r in rows_b}
    diffs = [(float(r[field]) - float(b[r["qid"]][field]), r["qid"]) for r in rows_a
             if r["qid"] in b and r[field] is not None and b[r["qid"]][field] is not None]
    out = boot([d for d, _ in diffs], [q for _, q in diffs], seed)
    out["excludes_zero"] = bool(out["n"] and (out["lo"] > 0 or out["hi"] < 0))
    return out


def retrieval_diagnostic(d: ev.Data, rows: list[dict[str, Any]], batch_ids: dict[str, list[int]]) -> dict[str, Any]:
    """RAG only: of the coded reports for a label question, the share with a retrieved sentence naming the label."""
    hit = tot = 0
    for r in rows:
        if r["method"] != "rag" or r["kind"] not in ("which", "count", "first") or r["label"] in (None, NO_FINDING):
            continue
        ids = batch_ids[r["bid"]]
        got = {(a, b) for a, b in r["retrieved"]}
        for k, i in enumerate(ids, 1):
            if not d.coded(i, r["label"]):
                continue
            tot += 1
            texts = {s.id: s.text for ss in sections_of(d.results[i]).values() for s in ss}
            hit += any((k, sid) in got and any(not neg for neg, _ in ev.sentence_mentions(t).get(r["label"], []))
                       for sid, t in texts.items())
    return {"coded_reports": tot, "with_retrieved_mention": hit, "share": hit / tot if tot else None}


def main() -> dict[str, Any]:
    d = ev.Data()
    recs = ev.load_records()
    qs = {q["qid"]: q for q in ev.single_questions(d)}
    batches = {b["bid"]: b for b in ev.batches(d)}
    for b in batches.values():
        qs.update({q["qid"]: q for q in ev.batch_questions(d, b)})
    batch_ids = {bid: b["ids"] for bid, b in batches.items()}
    rows: list[dict[str, Any]] = []
    for (qid, method), rec in sorted(recs.items()):
        q = qs[qid]
        c = classify(q, rec)
        rids = {1: q["rid"]} if q["part"] == "single" else {k: i for k, i in enumerate(batch_ids[q["bid"]], 1)}
        aff = affirms(q, rec, c)
        sup = cite_support(d, q, rec, rids) if aff else None
        raw = {(x["report_no"], x["sentence_id"]) for x in rec["raw_citations"]}
        rows.append({**{k: q.get(k) for k in ("qid", "part", "group", "kind", "label", "frozen", "should", "bid", "n",
                                              "question")},
                     **rec, **c, "affirms": aff, "support_any": sup[0] if sup else None,
                     "support_all": sup[1] if sup else None, "raw_n": len(raw), "valid_n": len(rec["citations"]),
                     "lost": rec["answer"] is None and rec["refusal"] == ev.ask_mod.NOT_STATED and bool(raw)
                     and not rec["citations"], "refused": rec["answer"] is None,
                     "cluster": q["rid"] if q["part"] == "single" else q["qid"], "method": method})
    seed = f"{get_settings().seed}-m10b"
    single = [r for r in rows if r["part"] == "single"]
    rag = [r for r in rows if r["part"] == "rag"]
    out: dict[str, Any] = {"records": len(rows), "single_expected": sum(q["part"] == "single" for q in qs.values()),
                           "rag_expected": 2 * sum(q["part"] == "rag" for q in qs.values())}

    def acc(rs: list[dict[str, Any]], s: str) -> dict[str, Any]:
        return {"codes": rate(rs, "correct_codes", "cluster", s + "c"), "v2": rate(rs, "correct_v2", "cluster", s + "v"),
                "unreadable": sum(r["unreadable"] for r in rs), "n_questions": len(rs),
                "lenient": rate(rs, "lenient", "cluster", s + "l")}
    # Part 1
    p1: dict[str, Any] = {"groups": {g: acc([r for r in single if r["group"] == g], seed + g)
                                     for g in ("T1", "T2", "A", "B", "D")}}
    t1 = [r for r in single if r["group"] == "T1"]
    p1["t1_by_label"] = {lab: {"positives_codes": acc([r for r in t1 if r["label"] == lab
                                                       and qs[r["qid"]]["codes"] == ["yes"]], seed + lab + "p"),
                               "negatives_codes": acc([r for r in t1 if r["label"] == lab
                                                       and qs[r["qid"]]["codes"] != ["yes"]], seed + lab + "n")}
                         for lab in ev.TEMPLATE_LABELS}
    p1["citations"] = citations(single, seed + "p1")
    p1["refusals"] = refusals(single)
    p1["cost"] = {g: costs([r for r in single if r["group"] == g]) for g in ("T1", "T2", "A", "B", "D")}
    p1["cost"]["all"] = costs(single)
    out["part1"] = p1
    # Part 2
    p2: dict[str, Any] = {}
    for n in ev.SIZES:
        entry: dict[str, Any] = {}
        for method in ("rag", "full"):
            rs = [r for r in rag if r["n"] == n and r["method"] == method]
            entry[method] = {"all": acc(rs, f"{seed}{n}{method}"),
                             "templated": acc([r for r in rs if r["group"] == "TC"], f"{seed}{n}{method}t"),
                             "hand_written_C": acc([r for r in rs if r["group"] == "C"], f"{seed}{n}{method}c"),
                             "hand_written_D": acc([r for r in rs if r["group"] == "D"], f"{seed}{n}{method}d"),
                             "citations": citations(rs, f"{seed}{n}{method}"), "refusals": refusals(rs),
                             "cost": costs(rs)}
        a = [r for r in rag if r["n"] == n and r["method"] == "rag"]
        b = [r for r in rag if r["n"] == n and r["method"] == "full"]
        entry["paired_codes"] = paired(a, b, "correct_codes", f"{seed}{n}pc")
        entry["paired_v2"] = paired(a, b, "correct_v2", f"{seed}{n}pv")
        entry["retrieval"] = retrieval_diagnostic(d, [{**r, "bid": qs[r["qid"]]["bid"]} for r in a], batch_ids)
        p2[str(n)] = entry
    out["part2"] = {"sizes": p2, "replicates": ev.REPLICATES}
    # hand-written questions, separately, per question
    fq = ev.frozen_questions()
    hw: dict[str, Any] = {}
    for n in range(1, 21):
        rs = [r for r in rows if r["frozen"] == n]
        scopes = {"report": [r for r in rs if r["part"] == "single"],
                  "rag": [r for r in rs if r["method"] == "rag" and r["part"] == "rag"],
                  "full": [r for r in rs if r["method"] == "full" and r["part"] == "rag"]}
        hw[str(n)] = {"question": fq[n][0], "scopes": {k: {"n": len(v), "codes": rate(v, "correct_codes", "cluster",
                                                                                   f"{seed}hw{n}{k}c"),
                                                           "v2": rate(v, "correct_v2", "cluster", f"{seed}hw{n}{k}v"),
                                                           "lenient": rate(v, "lenient", "cluster", f"{seed}hw{n}{k}l"),
                                                           "unreadable": sum(x["unreadable"] for x in v)}
                                                       for k, v in scopes.items() if v}}
    out["hand_written"] = hw
    out["new_spend_usd"] = sum(r["cost_usd"] for r in rows)
    write_samples(rows)
    write_result("ask_eval", out, fold="oof", mapping_version="v1", eval_version="eval_v1.2",
                 prompts=f"{ev.ask_mod.ASK_REPORT_VERSION}, {ev.ask_mod.ASK_ALL_VERSION}, baseline (eval/ask.py)")
    return out


def write_samples(rows: list[dict[str, Any]]) -> None:
    """A fixed random sample of answers per question kind with the parsed class, for reading by hand."""
    rng = random.Random(f"{get_settings().seed}-m10b-samples")
    lines = ["# Parsed answers (git-ignored: quotes report text)\n"]
    by = defaultdict(list)
    for r in rows:
        by[r["kind"]].append(r)
    for kind, rs in sorted(by.items()):
        lines.append(f"\n## {kind} ({len(rs)})\n")
        for r in rng.sample(rs, min(12, len(rs))):
            lines.append(f"- [{r['method']}, {r['qid']}] Q: {r['question']} | answer: {r['answer']} | refusal: "
                         f"{r['refusal']} | parsed: {r['cls']} | codes ok: {r['correct_codes']} | v2 ok: "
                         f"{r['correct_v2']}")
    ANALYSIS.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ = (Counter, Callable)


if __name__ == "__main__":
    print(json.dumps(main(), indent=1)[:3000])


# ------------------------------------------------------------------ rendering (docs/RESULTS.md, README line)
def _c(x: float | None, nd: int = 4) -> str:
    return "–" if x is None else f"{x:.{nd}f}"


def render(res: dict[str, Any]) -> str:
    p1, p2, hw = res["part1"], res["part2"]["sizes"], res["hand_written"]
    L = ["Pre-registered in [evaluation_notes.md](evaluation_notes.md#ask-evaluation-m10b-owner-2026-10-22-pre-committed-before-any-run). "
         "Frozen website prompts through the real code, gpt-4.1-mini, one run per question; answers parsed by rules; "
         "expected answers from the expert codes (v1, `present` = positive; hedged reports left out of that column) and "
         "from the v2 labels; citations checked in code. Cells: share correct (95% bootstrap CI) n.", "",
         f"New spend {res['new_spend_usd']:.3f} USD ({res['records']:,} answers).", "",
         "**Part 1: one report, the 102 dev-slice reports** (the frozen questions of groups A, B, D on a seeded "
         f"sample of {ev.FROZEN_SINGLE_REPORTS} of them).", "",
         "| Question group | Questions | Correct vs codes | Correct vs v2 | Unreadable answers |", "|---|---|---|---|---|"]
    names = {"T1": "Is there <finding>? (6 labels)", "T2": "What supports <label>?", "A": "Frozen A (answerable)",
             "B": "Frozen B (tricky wording)", "D": "Frozen D (must refuse)"}
    for g, x in p1["groups"].items():
        L.append(f"| {names[g]} | {x['n_questions']} | {pcts(x['codes'])} | {pcts(x['v2'])} | {x['unreadable']} |")
    dl = p1["groups"]["D"]["lenient"]
    L += ["", "Frozen D is scored by the pre-registered rule (a refusal, `answer` null). Post-hoc, not pre-registered: the "
          "frozen scoring note also accepts an answer that says the reports don't state it, with no number or diagnosis "
          f"(a redacted age is not a value); on that reading {pcts(dl)}.", "",
          "Is there <finding>? by label (vs codes):", "", "| Label | Coded present | Not coded |", "|---|---|---|"]
    for lab, x in p1["t1_by_label"].items():
        L.append(f"| {lab} | {pcts(x['positives_codes']['codes'])} | {pcts(x['negatives_codes']['codes'])} |")
    c, rf = p1["citations"], p1["refusals"]
    L += ["", f"Citations (Part 1): {c['valid_citations']:,} of {c['raw_citations']:,} cited sentences existed among the "
          f"given ones ({pct(c['structural_valid_rate'] or float('nan'))}; the rest were dropped by the code check; "
          f"{c['answers_lost_to_the_check']} answers became \"not stated\" because no valid citation was left). Of "
          f"{c['affirming_answers_scored']} answers that affirm a finding, at least one cited sentence names it (eval "
          f"detector, not negated) in {pcts(c['support_any'])}; every cited sentence does in {pcts(c['support_all'])}.",
          f"Refusals (Part 1): precision {_c(rf['precision'], 3)}, recall {_c(rf['recall'], 3)} ({rf['true_refusals']} of "
          f"{rf['should_refuse']} unanswerable questions refused; {rf['false_refusals']} of {rf['should_answer']} "
          "answerable-and-positive questions wrongly refused).", "",
          "**Part 2: across reports.** Synthetic patients: 3 batches of random out-of-fold IU reports per size (never the "
          "dev slice), upload order = batch order. RAG = the website configuration (fold-k fine-tuned model, top 12 "
          "sentences); all in prompt = every sentence of every report. 15 questions per batch (5 templated, frozen C "
          "and D).", "",
          "| Reports | Method | Correct vs codes (all) | Templated | Frozen C | Frozen D (refuse) | D, post-hoc lenient | "
          "Correct vs v2 | Unreadable | Mean input tokens | Cost / request | Latency p50 / p95 s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, e in p2.items():
        for m, label in (("rag", "RAG"), ("full", "all in prompt")):
            x, co = e[m], e[m]["cost"]
            L.append(f"| {n} | {label} | {pcts(x['all']['codes'])} | {pcts(x['templated']['codes'])} | "
                     f"{pcts(x['hand_written_C']['codes'])} | {pcts(x['hand_written_D']['codes'])} | "
                     f"{pcts(x['hand_written_D']['lenient'])} | {pcts(x['all']['v2'])} | "
                     f"{x['all']['unreadable']} of {x['all']['n_questions']} | {co['mean_input_tokens']:.0f} | ${co['mean_cost_usd']:.5f} | "
                     f"{_c(co['latency_p50_s'], 2)} / {_c(co['latency_p95_s'], 2)} |")
    L += ["", "| Reports | Paired RAG − all in prompt, vs codes | vs v2 | Reading (pre-registered rule) | Retrieved mention of "
          "a coded report's label |", "|---|---|---|---|---|"]
    for n, e in p2.items():
        pc, pv, rt = e["paired_codes"], e["paired_v2"], e["retrieval"]
        read = ("no detectable difference" if not pc["excludes_zero"] else
                "RAG better" if pc["value"] > 0 else "all-in-prompt better")
        fmt = lambda d: "–" if d["n"] == 0 else f"{100 * d['value']:+.1f} pts ({100 * d['lo']:+.1f} to {100 * d['hi']:+.1f})"  # noqa: E731
        L.append(f"| {n} | {fmt(pc)} | {fmt(pv)} | {read} | {pct(rt['share'] or float('nan'))} of {rt['coded_reports']} |")
    cit = [(n, m, e[m]["citations"]) for n, e in p2.items() for m in ("rag", "full")]
    L += ["", "Citations (Part 2), structural validity and support by the eval detector (at least one / every cited "
          "sentence):", "", "| Reports | Method | Cited sentences that existed | Affirming answers | Support (≥1) | Support (all) "
          "| Refusal precision / recall |", "|---|---|---|---|---|---|---|"]
    for n, m, x in cit:
        rf = p2[n][m]["refusals"]
        L.append(f"| {n} | {'RAG' if m == 'rag' else 'all in prompt'} | {pct(x['structural_valid_rate'] or float('nan'))} "
                 f"| {x['affirming_answers_scored']} | {pcts(x['support_any'])} | {pcts(x['support_all'])} | "
                 f"{_c(rf['precision'], 2)} / {_c(rf['recall'], 2)} |")
    L += ["", "**Hand-written questions** (the 20 frozen ones, scored with their scoring notes; correct vs codes, n answers "
          "scored): ", "", "| # | Question | One report | RAG (3–50 reports) | All in prompt (3–50 reports) |", "|---|---|---|---|---|"]
    for n, x in hw.items():
        cells = []
        for k in ("report", "rag", "full"):
            s = x["scopes"].get(k)
            cells.append("–" if s is None else (f"{pcts(s['codes'])}" if s["codes"]["n"] else
                         f"{pcts(s['v2'])} (v2 only)") + (f"; post-hoc lenient {pcts(s['lenient'])}" if s["lenient"]["n"] else ""))
        L.append(f"| {n} | {x['question']} | {cells[0]} | {cells[1]} | {cells[2]} |")
    return "\n".join(L) + "\n"


def summary_line(res: dict[str, Any]) -> str:
    p1, p2 = res["part1"], res["part2"]["sizes"]
    t1, hw = p1["groups"]["T1"]["codes"], p1["citations"]
    big = p2[str(max(ev.SIZES))]
    rg, fu = big["rag"], big["full"]
    cheaper = fu["cost"]["mean_cost_usd"] / rg["cost"]["mean_cost_usd"] if rg["cost"]["mean_cost_usd"] else float("nan")
    return (f"- Questions (M10b): on {t1['n']} \"Is there …?\" questions about 102 dev reports {pct(t1['value'])} match the "
            f"expert codes, and {pct(hw['support_any']['value'])} of affirming answers cite a sentence that names the "
            f"finding. Across {max(ev.SIZES)} reports, searching the session answers {pct(rg['all']['codes']['value'])} "
            f"of questions correctly vs {pct(fu['all']['codes']['value'])} with every report in the prompt, at "
            f"{cheaper:.0f}× lower cost per request.")
