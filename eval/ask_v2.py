# ruff: noqa: E501  (long report-text lines in the renderers)
"""Ask v2 (follow-up to M10b; pre-registered in docs/evaluation_notes.md, "Ask v2"), eval side.

- Retrieval v2: the global top 12 sentences plus the top 2 of EVERY report (api/session.py, `per_report`).
- Prompt v2 (`ask-report-v2`, `ask-all-v2`, `ask-context-v2`): developed on the dev slice only (`dev`), frozen by a hash
  test, then evaluated once on NEW synthetic batches (`run`, `score`): RAG v1 (the M10b configuration), RAG v2
  (retrieval v2 + prompt v2) and all sentences in the prompt with prompt v2 (ctx2); plus single-report prompt v2 on a
  seeded subset of the M10b Part 1 questions (v1 answers are the M10b records).
- Same question templates, parser, metrics and CIs as M10b (eval/ask.py, eval/ask_score.py), plus coverage.
- The website decisions are computed by rule from the results (`decisions`), see the notes.

Usage: python -m eval.ask_v2 estimate | dev <tag> [--baseline] | run [single|rag] | score
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from eval import ask as ev
from eval import ask_score as sc
from eval.labelling import PRED_DIR
from radlabel.api import ask as ask_mod
from radlabel.api.session import Session, sections_of, to_report
from radlabel.config import get_settings
from radlabel.labels import NO_FINDING
from radlabel.llm import LLMClient
from radlabel.results import write_result

EVAL_RECORDS = PRED_DIR / "ask_v2_eval.jsonl"  # git-ignored: report text and answers
DEV_RECORDS = PRED_DIR / "ask_v2_dev.jsonl"
SIZES = ev.SIZES
REPLICATES = 3
SINGLE_FRACTION = 0.3  # share of the M10b Part 1 questions re-asked with prompt v2 (cost)
DEV_SINGLE_REPORTS = 15  # dev reports (from the M10b frozen-question sample) for the single-report dev check
DEV_BATCH_SIZES = (10, 30)  # dev-slice batches for the scope-"all" dev check
SPEND_CAP = 1.0  # USD of new spend for the whole ask-v2 work
METHODS = ("rag1", "rag2", "ctx2")


# ------------------------------------------------------------------ question sets
def v2_batches(d: ev.Data) -> list[dict[str, Any]]:
    """New synthetic patients (new seed), never the dev slice, hedged reports or a report used in an M10b batch."""
    used = {i for b in ev.batches(d) for i in b["ids"]}
    out = []
    for n in SIZES:
        for r in range(REPLICATES):
            pool = [i for i, f in zip(d.it.ids, d.it.fold, strict=True)
                    if f == r and not d.it.pilot[d.pos[i]] and not d.hedged(i) and i not in used]
            ids = random.Random(f"{get_settings().seed}-m10b-v2-batch-{n}-{r}").sample(pool, n)
            out.append({"bid": f"v{n}-{r}", "n": n, "rep": r, "fold": r, "ids": ids})
    return out


def dev_batches(d: ev.Data) -> list[dict[str, Any]]:
    """Dev-slice batches for prompt development (10 and 30 non-hedged dev reports, disjoint)."""
    ids = [i for i in d.dev if not d.hedged(i)]
    random.Random(f"{get_settings().seed}-m10b-v2-dev").shuffle(ids)
    out, at = [], 0
    for k, n in enumerate(DEV_BATCH_SIZES):
        out.append({"bid": f"dv{n}-{k}", "n": n, "rep": k, "fold": None, "ids": ids[at:at + n]})
        at += n
    return out


def dev_single_questions(d: ev.Data) -> list[dict[str, Any]]:
    """Single-report dev check: the unanswerable questions (D16-20) and the edema / negated-effusion questions on 15
    dev reports from the M10b frozen-question sample (their v1 answers exist)."""
    sample = sorted({q["rid"] for q in ev.single_questions(d) if q.get("frozen")})
    rids = set(random.Random(f"{get_settings().seed}-m10b-v2-devsingle").sample(sample, DEV_SINGLE_REPORTS))
    return [q for q in ev.single_questions(d) if q["rid"] in rids and q.get("frozen") in (7, 9, 16, 17, 18, 19, 20)]


def single_subset(d: ev.Data) -> list[dict[str, Any]]:
    qs = ev.single_questions(d)
    keep = set(random.Random(f"{get_settings().seed}-m10b-v2-single").sample(range(len(qs)), round(SINGLE_FRACTION * len(qs))))
    return [q for k, q in enumerate(qs) if k in keep]


# ------------------------------------------------------------------ running
def call2(q: dict[str, Any], method: str, llm: LLMClient, session: Session) -> dict[str, Any]:
    import time

    from radlabel.api import session as session_mod
    if getattr(session, "encode", None) is not None:
        session_mod.search_encode = session.encode  # type: ignore[assignment]
    m = ev.Meter(llm)
    t0 = time.perf_counter()
    retrieved: list[list[Any]] = []
    if method == "report2":
        res = ask_mod.ask_report(m, session, 1, q["question"], version="v2")  # type: ignore[arg-type]
    elif method in ("rag1", "rag2"):
        per = ask_mod.VERSIONS["v1" if method == "rag1" else "v2"][4]
        retrieved = [[e.report_no, e.sentence_id] for e in session.retrieve(q["question"], ask_mod.TOP_K, per_report=per)]
        res = ask_mod.ask_all(m, session, q["question"], version="v1" if method == "rag1" else "v2")  # type: ignore[arg-type]
    else:
        res = ask_mod.ask_context(m, session, q["question"])  # type: ignore[arg-type]
    dt = time.perf_counter() - t0
    raw = [json.loads(r.text) if r.text.startswith("{") else {} for r in m.responses]
    return {"qid": q["qid"], "method": method, "answer": res.answer, "refusal": res.refusal,
            "citations": [c.model_dump() for c in res.citations], "retrieved": retrieved,
            "given": res.retrieved_sentences, "raw_citations": [c for x in raw for c in x.get("citations", [])],
            "input_tokens": sum(r.input_tokens for r in m.responses),
            "output_tokens": sum(r.output_tokens for r in m.responses),
            "cost_usd": sum(r.cost_usd for r in m.responses), "cached": all(r.cached for r in m.responses),
            "latency_s": dt}


def load(path: Any) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    return {(r["qid"], r["method"]): r for r in map(json.loads, path.open(encoding="utf-8"))}


def batch_session_any(d: ev.Data, b: dict[str, Any]) -> Session:
    """Fold-k model for eval batches (out-of-fold embeddings); the serving model for dev batches (prompt development
    only: retrieval is not what is being measured there)."""
    from radlabel.api import session as session_mod
    from radlabel.embeddings import search_encode
    if b["fold"] is not None:
        s = ev.batch_session(d, b)
        s.encode = session_mod.search_encode  # type: ignore[attr-defined]  # the fold-k encoder just installed
        return s
    session_mod.search_encode = search_encode  # type: ignore[assignment]
    s = Session("dev")
    for k, i in enumerate(b["ids"], 1):
        s.add(to_report(k, f"report_{i}.txt", d.results[i]))
    s.encode = search_encode  # type: ignore[attr-defined]
    return s


def run_jobs(jobs: list[tuple[dict[str, Any], str, Any]], path: Any, llm: LLMClient, workers: int, label: str) -> None:
    done = load(path)
    spend0 = llm.spent
    out = path.open("a", encoding="utf-8")

    def one(job: tuple[dict[str, Any], str, Any]) -> None:
        q, method, session = job
        if (q["qid"], method) in done:
            return
        if llm.spent - spend0 > SPEND_CAP:
            raise SystemExit(f"new spend passed ${SPEND_CAP}: stopped (finished calls are kept)")
        out.write(json.dumps({**call2(q, method, llm, session), "part": q["part"]}) + "\n")
        out.flush()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, jobs))
    print(json.dumps({label: "done", "new_spend_usd": llm.spent - spend0}))


def single_jobs(d: ev.Data, qs: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str, Any]]:
    sessions = {i: ev.single_session(d, i) for i in d.dev}
    return [(q, "report2", sessions[q["rid"]]) for q in qs]


def batch_jobs(d: ev.Data, batches: list[dict[str, Any]], methods: tuple[str, ...]) -> list[tuple[dict[str, Any], str, Any]]:
    jobs = []
    for b in batches:
        session = batch_session_any(d, b)
        for q in ev.batch_questions(d, b):
            jobs += [(q, m, session) for m in methods]
    return jobs


def dev(tag: str, baseline: bool, llm: LLMClient) -> dict[str, Any]:
    """One prompt-development iteration on the dev slice. `baseline`: also the v1 configuration on the dev batches
    (the single-report v1 answers are the M10b records). Methods are recorded as "<method>@<tag>"."""
    d = ev.Data()
    run_single = single_jobs(d, dev_single_questions(d))
    run_batches = batch_jobs(d, dev_batches(d), ("rag1",) if baseline else ("rag2",))
    # the record key carries the tag, so iterations never overwrite each other
    jobs = [({**q, "qid": f"{tag}:{q['qid']}", "_orig": q["qid"]}, m, s) for q, m, s in (run_batches if baseline else run_single + run_batches)]
    run_jobs(jobs, DEV_RECORDS, llm, 6, f"dev {tag}")
    return dev_summary(d)


def dev_summary(d: ev.Data) -> dict[str, Any]:
    recs = load(DEV_RECORDS)
    dq = {q["qid"]: q for q in dev_single_questions(d)}
    batches = {b["bid"]: b for b in dev_batches(d)}
    bq = {q["qid"]: q for b in batches.values() for q in ev.batch_questions(d, b)}
    out: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    old = ev.load_records()
    for (qid, method), r in list(recs.items()):
        tag, _, orig = qid.partition(":")
        q = bq.get(orig) or dq.get(orig)
        if q is None:
            continue
        key = f"{method}@{tag}"
        add_dev_row(out[key], d, q, r, batches)
    for q in dq.values():  # the v1 single-report answers (M10b)
        r = old.get((q["qid"], "report"))
        if r is not None:
            add_dev_row(out["report1@m10b"], d, q, r, batches)
    return {k: dict(v) for k, v in sorted(out.items())}


def add_dev_row(acc: dict[str, float], d: ev.Data, q: dict[str, Any], r: dict[str, Any], batches: dict[str, Any]) -> None:
    c = sc.classify(q, r)
    g = q["group"]
    acc["n"] += 1
    acc[f"n_{g}"] += 1
    if q["kind"] == "refuse":
        acc["D_questions"] += 1
        acc["D_refusal_field"] += r["answer"] is None
        acc["D_lenient"] += bool(c["lenient"])
    if c["correct_codes"] is not None:
        acc["scored"] += 1
        acc["correct_codes"] += bool(c["correct_codes"])
        acc[f"scored_{g}"] += 1
        acc[f"correct_{g}"] += bool(c["correct_codes"])
    if q["kind"] == "which" and q.get("label") not in (None, NO_FINDING) and isinstance(c["cls"], list):
        ids = batches[q["bid"]]["ids"]
        for k in c["cls"]:  # a listed report that only negates the finding
            if 1 <= k <= len(ids):
                i = ids[k - 1]
                m = d.ments[i].get(q["label"], [])
                acc["which_listed"] += 1
                acc["negated_listed"] += bool(m) and all(neg for neg, _ in m) and not d.coded(i, q["label"])
    acc["unreadable"] += bool(c["unreadable"])


# ------------------------------------------------------------------ estimate
def estimate() -> dict[str, Any]:
    d = ev.Data()
    dry = ev.DryLLM()

    def cost(prompts: list[tuple[str, int]]) -> float:
        return sum(c / ev.CHARS_PER_TOKEN * ev.PRICE_IN + ev.OUT_TOKENS * ev.PRICE_OUT for _, c in prompts)

    def batch_cost(batches: list[dict[str, Any]], methods: tuple[str, ...]) -> dict[str, float]:
        res = dict.fromkeys(methods, 0.0)
        for b in batches:
            session = batch_session_any(d, b)
            qs = ev.batch_questions(d, b)
            for m in methods:
                dry.prompts.clear()
                for q in qs:
                    if m in ("rag1", "rag2"):
                        ask_mod.ask_all(dry, session, q["question"], version="v1" if m == "rag1" else "v2")  # type: ignore[arg-type]
                    else:
                        ask_mod.ask_context(dry, session, q["question"])  # type: ignore[arg-type]
                res[m] += cost(dry.prompts)
        return res
    sq = single_subset(d)
    dsq = dev_single_questions(d)
    sessions = {i: ev.single_session(d, i) for i in d.dev}
    dry.prompts.clear()
    for q in sq:
        ask_mod.ask_report(dry, sessions[q["rid"]], 1, q["question"], version="v2")  # type: ignore[arg-type]
    single = cost(dry.prompts)
    dry.prompts.clear()
    for q in dsq:
        ask_mod.ask_report(dry, sessions[q["rid"]], 1, q["question"], version="v2")  # type: ignore[arg-type]
    dev_single = cost(dry.prompts)
    evalc = batch_cost(v2_batches(d), METHODS)
    devc = batch_cost(dev_batches(d), ("rag1", "rag2", "ctx2"))
    dev_iter = dev_single + devc["rag2"]
    total = single + sum(evalc.values()) + devc["rag1"] + 2 * dev_iter
    return {"single_subset_questions": len(sq), "single_subset_usd": single, "eval_usd_by_method": evalc,
            "eval_questions": 15 * len(v2_batches(d)), "dev_single_questions": len(dsq),
            "dev_iteration_usd": dev_iter, "dev_baseline_usd": devc["rag1"], "dev_iterations_budgeted": 2,
            "total_usd": total, "assumptions": {"chars_per_token": ev.CHARS_PER_TOKEN, "output_tokens": ev.OUT_TOKENS}}


# ------------------------------------------------------------------ scoring
def rows_of(d: ev.Data, recs: dict[tuple[str, str], dict[str, Any]], qs: dict[str, dict[str, Any]],
            batch_ids: dict[str, list[int]]) -> list[dict[str, Any]]:
    rows = []
    for (qid, method), rec in sorted(recs.items()):
        q = qs[qid]
        c = sc.classify(q, rec)
        rids = {1: q["rid"]} if q["part"] == "single" else dict(enumerate(batch_ids[q["bid"]], 1))
        aff = sc.affirms(q, rec, c)
        sup = sc.cite_support(d, q, rec, rids) if aff else None
        raw = {(x["report_no"], x["sentence_id"]) for x in rec["raw_citations"]}
        rows.append({**{k: q.get(k) for k in ("qid", "part", "group", "kind", "label", "frozen", "should", "bid", "n", "question")},
                     **rec, **c, "affirms": aff, "support_any": sup[0] if sup else None, "support_all": sup[1] if sup else None,
                     "raw_n": len(raw), "valid_n": len(rec["citations"]),
                     "lost": rec["answer"] is None and rec["refusal"] == ev.ask_mod.NOT_STATED and bool(raw) and not rec["citations"],
                     "refused": rec["answer"] is None, "cluster": q["rid"] if q["part"] == "single" else q["qid"],
                     "method": method})
    return rows


def coverage(d: ev.Data, rows: list[dict[str, Any]], batch_ids: dict[str, list[int]]) -> dict[str, Any]:
    """Of the coded reports for a label question, the share with a retrieved sentence naming the finding."""
    hit = tot = 0
    for r in rows:
        if r["kind"] not in ("which", "count", "first") or r["label"] in (None, NO_FINDING):
            continue
        got = {(a, b) for a, b in r["retrieved"]}
        for k, i in enumerate(batch_ids[r["bid"]], 1):
            if not d.coded(i, r["label"]):
                continue
            tot += 1
            texts = {s.id: s.text for ss in sections_of(d.results[i]).values() for s in ss}
            hit += any((k, sid) in got and any(not neg for neg, _ in ev.sentence_mentions(t).get(r["label"], []))
                       for sid, t in texts.items())
    return {"coded_reports": tot, "with_retrieved_mention": hit, "share": hit / tot if tot else None}


def score() -> dict[str, Any]:
    d = ev.Data()
    seed = f"{get_settings().seed}-m10b-v2"
    batches = {b["bid"]: b for b in v2_batches(d)}
    batch_ids = {k: b["ids"] for k, b in batches.items()}
    qs = {q["qid"]: q for q in ev.single_questions(d)}
    for b in batches.values():
        qs.update({q["qid"]: q for q in ev.batch_questions(d, b)})
    new = load(EVAL_RECORDS)
    old = ev.load_records()
    recs = dict(new)
    for (qid, method), r in old.items():  # the M10b v1 single-report answers, for the paired comparison
        if method == "report" and (qid, "report2") in new:
            recs[(qid, "report1")] = r
    rows = rows_of(d, recs, qs, batch_ids)
    single = [r for r in rows if r["part"] == "single"]
    rag = [r for r in rows if r["part"] == "rag"]
    out: dict[str, Any] = {"records": len(new)}

    def acc(rs: list[dict[str, Any]], s: str) -> dict[str, Any]:
        return {"codes": sc.rate(rs, "correct_codes", "cluster", s + "c"), "v2": sc.rate(rs, "correct_v2", "cluster", s + "v"),
                "unreadable": sum(r["unreadable"] for r in rs), "n_questions": len(rs),
                "lenient": sc.rate(rs, "lenient", "cluster", s + "l")}
    # single report: v1 vs v2 on the same questions
    s1 = {m: [r for r in single if r["method"] == m] for m in ("report1", "report2")}
    p1: dict[str, Any] = {"questions": len(s1["report2"]), "groups": {}}
    for g in ("T1", "T2", "A", "B", "D", "all"):
        e: dict[str, Any] = {}
        for m, rs in s1.items():
            sel = rs if g == "all" else [r for r in rs if r["group"] == g]
            e[m] = acc(sel, f"{seed}{g}{m}")
            e[m]["citations"] = sc.citations(sel, f"{seed}{g}{m}")
            e[m]["refusals"] = sc.refusals(sel)
        a = [r for r in s1["report2"] if g == "all" or r["group"] == g]
        b = [r for r in s1["report1"] if g == "all" or r["group"] == g]
        e["paired_codes"] = sc.paired(a, b, "correct_codes", f"{seed}{g}pc")
        e["paired_v2"] = sc.paired(a, b, "correct_v2", f"{seed}{g}pv")
        p1["groups"][g] = e
    out["single"] = p1
    # across reports
    sizes: dict[str, Any] = {}
    for n in SIZES:
        e = {}
        by = {m: [r for r in rag if r["n"] == n and r["method"] == m] for m in METHODS}
        for m, rs in by.items():
            e[m] = {"all": acc(rs, f"{seed}{n}{m}"), "templated": acc([r for r in rs if r["group"] == "TC"], f"{seed}{n}{m}t"),
                    "hand_written_C": acc([r for r in rs if r["group"] == "C"], f"{seed}{n}{m}c"),
                    "hand_written_D": acc([r for r in rs if r["group"] == "D"], f"{seed}{n}{m}d"),
                    "citations": sc.citations(rs, f"{seed}{n}{m}"), "refusals": sc.refusals(rs), "cost": sc.costs(rs),
                    "coverage": coverage(d, rs, batch_ids) if m != "ctx2" else None}
        for a, b in (("rag2", "ctx2"), ("rag2", "rag1"), ("rag1", "ctx2")):
            e[f"paired_codes_{a}_minus_{b}"] = sc.paired(by[a], by[b], "correct_codes", f"{seed}{n}{a}{b}c")
            e[f"paired_v2_{a}_minus_{b}"] = sc.paired(by[a], by[b], "correct_v2", f"{seed}{n}{a}{b}v")
        sizes[str(n)] = e
    out["sizes"] = sizes
    fq = ev.frozen_questions()
    hw: dict[str, Any] = {}
    for n in range(11, 21):
        rs = [r for r in rag if r["frozen"] == n]
        hw[str(n)] = {"question": fq[n][0], "methods": {m: {"codes": sc.rate([r for r in rs if r["method"] == m], "correct_codes", "cluster", f"{seed}hw{n}{m}"),
                                                           "lenient": sc.rate([r for r in rs if r["method"] == m], "lenient", "cluster", f"{seed}hw{n}{m}l")}
                                                       for m in METHODS}}
    out["hand_written"] = hw
    out["decisions"] = decisions(out)
    out["new_spend_usd"] = sum(r["cost_usd"] for r in recs.values() if r["method"] != "report1")
    write_result("ask_v2_eval", out, fold="oof", mapping_version="v1", eval_version="eval_v1.2",
                 prompts=f"{ask_mod.ASK_REPORT_VERSION_V2}, {ask_mod.ASK_ALL_VERSION_V2}, {ask_mod.ASK_CONTEXT_VERSION_V2}")
    return out


def decisions(res: dict[str, Any]) -> dict[str, Any]:
    """The pre-committed website rules, applied to the results."""
    worse = {n: bool(e["paired_codes_rag2_minus_ctx2"]["n"] and e["paired_codes_rag2_minus_ctx2"]["hi"] < 0) for n, e in res["sizes"].items()}
    scope_all = "rag2" if not any(worse.values()) else "hybrid: rag2 up to 10 reports, ctx2 above 10"
    g = res["single"]["groups"]
    pooled = g["all"]["paired_codes"]
    group_worse = {k: bool(v["paired_codes"]["n"] and v["paired_codes"]["hi"] < 0) for k, v in g.items() if k != "all"}
    switch = bool(pooled["n"] and pooled["value"] >= 0 and not any(group_worse.values()))
    return {"rag2_significantly_worse_than_ctx2_by_size": worse, "scope_all": scope_all,
            "single_report_pooled_paired_v2_minus_v1": pooled, "single_report_groups_significantly_worse": group_worse,
            "single_report_uses_v2": switch}


# ------------------------------------------------------------------ rendering
def render(res: dict[str, Any]) -> str:
    L = ["Pre-registered in [evaluation_notes.md](evaluation_notes.md) (\"Ask v2\"). New synthetic batches (new seed, never "
         "the dev slice or an M10b batch), same questions, parser and metrics as M10b. RAG v1 = the M10b configuration "
         "(top 12, prompt v1); RAG v2 = per-report coverage (top 12 plus the top 2 of every report) and prompt v2; "
         "all in prompt = every sentence, prompt v2. Cells: share correct (95% bootstrap CI) n.", "",
         f"New spend {res['new_spend_usd']:.3f} USD (evaluation answers).", "",
         "| Reports | Method | Correct vs codes (all) | Templated | Frozen C | Frozen D (refuse) | D, post-hoc lenient | Correct vs v2 | Unreadable | Mean input tokens | Cost / request | Latency p50 / p95 s | Coverage |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    names = {"rag1": "RAG v1", "rag2": "RAG v2", "ctx2": "all in prompt (v2)"}
    for n, e in res["sizes"].items():
        for m in METHODS:
            x, co = e[m], e[m]["cost"]
            cv = x["coverage"]
            L.append(f"| {n} | {names[m]} | {sc.pcts(x['all']['codes'])} | {sc.pcts(x['templated']['codes'])} | {sc.pcts(x['hand_written_C']['codes'])} | "
                     f"{sc.pcts(x['hand_written_D']['codes'])} | {sc.pcts(x['hand_written_D']['lenient'])} | {sc.pcts(x['all']['v2'])} | "
                     f"{x['all']['unreadable']} of {x['all']['n_questions']} | {co['mean_input_tokens']:.0f} | ${co['mean_cost_usd']:.5f} | "
                     f"{sc._c(co['latency_p50_s'], 2)} / {sc._c(co['latency_p95_s'], 2)} | "
                     f"{'–' if cv is None else sc.pct(cv['share'] or float('nan')) + ' of ' + str(cv['coded_reports'])} |")

    def fmt(dd: dict[str, Any]) -> str:
        return "–" if dd["n"] == 0 else f"{100 * dd['value']:+.1f} pts ({100 * dd['lo']:+.1f} to {100 * dd['hi']:+.1f})"
    L += ["", "Paired differences in accuracy vs the codes (same questions; bootstrap over questions; \"worse\" / \"better\" only where the CI excludes zero):", "",
          "| Reports | RAG v2 − all in prompt (v2) | RAG v2 − RAG v1 | RAG v1 − all in prompt (v2) |", "|---|---|---|---|"]
    for n, e in res["sizes"].items():
        cells = []
        for k in ("rag2_minus_ctx2", "rag2_minus_rag1", "rag1_minus_ctx2"):
            p = e[f"paired_codes_{k}"]
            tag = "" if not p["excludes_zero"] else (" better" if p["value"] > 0 else " worse")
            cells.append(fmt(p) + tag)
        L.append(f"| {n} | " + " | ".join(cells) + " |")
    L += ["", "Citations and refusals (Part 2 style): structural validity, support by the eval detector (≥1 / every cited sentence), refusal precision / recall:", "",
          "| Reports | Method | Cited sentences that existed | Affirming answers | Support (≥1) | Support (all) | Refusal precision / recall |", "|---|---|---|---|---|---|---|"]
    for n, e in res["sizes"].items():
        for m in METHODS:
            c, rf = e[m]["citations"], e[m]["refusals"]
            L.append(f"| {n} | {names[m]} | {sc.pct(c['structural_valid_rate'] or float('nan'))} | {c['affirming_answers_scored']} | {sc.pcts(c['support_any'])} | "
                     f"{sc.pcts(c['support_all'])} | {sc._c(rf['precision'], 2)} / {sc._c(rf['recall'], 2)} |")
    L += ["", f"**Single-report ask, prompt v2 vs v1** on the same {res['single']['questions']} dev-slice questions (a seeded subset of the M10b Part 1 questions):", "",
          "| Group | v1 vs codes | v2 vs codes | Paired v2 − v1 | v1 vs v2-labels | v2 vs v2-labels | D lenient v1 / v2 (post-hoc) |", "|---|---|---|---|---|---|---|"]
    for g, e in res["single"]["groups"].items():
        L.append(f"| {g} | {sc.pcts(e['report1']['codes'])} | {sc.pcts(e['report2']['codes'])} | {fmt(e['paired_codes'])} | {sc.pcts(e['report1']['v2'])} | "
                 f"{sc.pcts(e['report2']['v2'])} | " + (f"{sc.pcts(e['report1']['lenient'])} / {sc.pcts(e['report2']['lenient'])}" if g == "D" else "–") + " |")
    L += ["", "**Hand-written questions across reports** (frozen C and D; correct vs codes; D also post-hoc lenient):", "",
          "| # | Question | RAG v1 | RAG v2 | All in prompt (v2) |", "|---|---|---|---|---|"]
    for n, x in res["hand_written"].items():
        cells = []
        for m in METHODS:
            e = x["methods"][m]
            cells.append(sc.pcts(e["codes"]) + (f"; lenient {sc.pcts(e['lenient'])}" if int(n) >= 16 else ""))
        L.append(f"| {n} | {x['question']} | " + " | ".join(cells) + " |")
    dc = res["decisions"]
    L += ["", "**Website decisions (pre-committed rules):** RAG v2 significantly worse than all-in-prompt (v2) at: " +
          (", ".join(f"{n} reports" for n, w in dc["rag2_significantly_worse_than_ctx2_by_size"].items() if w) or "no batch size") +
          f" → scope \"all\" uses **{dc['scope_all']}**. Single-report ask uses prompt v2: **{'yes' if dc['single_report_uses_v2'] else 'no'}** "
          f"(pooled paired v2 − v1 {fmt(dc['single_report_pooled_paired_v2_minus_v1'])}; groups significantly worse: "
          f"{', '.join(k for k, w in dc['single_report_groups_significantly_worse'].items() if w) or 'none'})."]
    return "\n".join(L) + "\n"


def render_dev(dv: dict[str, Any]) -> str:
    """Prompt development on the dev slice only (one iteration, v2a): counts."""
    names = {"report1@m10b": "single report, prompt v1 (M10b answers)", "report2@v2a": "single report, prompt v2 (v2a)",
             "rag1@base": "scope all, RAG v1 (dev batches of 10 and 30)", "rag2@v2a": "scope all, RAG v2 + prompt v2 (v2a)"}
    L = ["Prompt development (dev slice only; 15 dev reports for the single-report check, two dev batches of 10 and 30 "
         "reports for scope \"all\"; one iteration, then frozen):", "",
         "| Configuration | Questions | Correct vs codes | Unanswerable questions answered in the refusal field | Reports listed that only negate the finding | Unreadable |",
         "|---|---|---|---|---|---|"]
    for k, x in dv.items():
        L.append(f"| {names.get(k, k)} | {x['n']:.0f} | {x.get('correct_codes', 0):.0f} of {x.get('scored', 0):.0f} | "
                 f"{x.get('D_refusal_field', 0):.0f} of {x.get('D_questions', 0):.0f} | "
                 f"{x.get('negated_listed', 0):.0f} of {x.get('which_listed', 0):.0f} listed | {x.get('unreadable', 0):.0f} |")
    return "\n".join(L) + "\n"


def summary_line(res: dict[str, Any]) -> str:
    big = res["sizes"][str(max(SIZES))]
    r2, c2, r1 = big["rag2"], big["ctx2"], big["rag1"]
    dc = res["decisions"]
    return (f"- Ask v2 (new batches, {max(SIZES)} reports): per-report retrieval coverage + a revised prompt answer "
            f"{sc.pct(r2['all']['codes']['value'])} of questions correctly vs {sc.pct(r1['all']['codes']['value'])} before and "
            f"{sc.pct(c2['all']['codes']['value'])} with every report in the prompt; scope \"all\" uses {dc['scope_all']}.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "estimate"
    if mode == "estimate":
        print(json.dumps(estimate(), indent=1))
    elif mode == "dev":
        print(json.dumps(dev(sys.argv[2], "--baseline" in sys.argv, LLMClient()), indent=1))
    elif mode == "run":
        parts = tuple(a for a in sys.argv[2:] if not a.startswith("-")) or ("single", "rag")
        d = ev.Data()
        client = LLMClient()
        if "single" in parts:
            run_jobs(single_jobs(d, single_subset(d)), EVAL_RECORDS, client, 6, "single")
        if "rag" in parts:  # one at a time: latency is measured per request
            run_jobs(batch_jobs(d, v2_batches(d), METHODS), EVAL_RECORDS, client, 1, "rag")
    elif mode == "score":
        print(json.dumps(score()["decisions"], indent=1))
    else:
        raise SystemExit("usage: python -m eval.ask_v2 estimate | dev <tag> [--baseline] | run [single|rag] | score")
