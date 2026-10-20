"""M5: Tier 2 repair agent on the Tier 1 reports with a verifier FAIL, out-of-fold evaluation and routing metrics.

Pre-committed (owner, M5; docs/evaluation_notes.md) before the run:
- Scope: only reports whose verified Tier 1 output has a FAIL (211). Flag-only and content-filtered reports never
  reach Tier 2.
- Column "LLM + verifier + Tier 2": LLM + verifier labels, with the agent's labels for reports whose fix passes
  re-verification. A fix that still fails, or no fix (limits, refusal), keeps the Tier 1 labels -> review.
- Paired bootstrap: Tier 2 − LLM + verifier and Tier 2 − rule baseline (v1 headline macro-F1, hedged + pilot
  excluded). Tier 2 stays in the pipeline iff Tier 2 − LLM + verifier is not significantly negative (CI hi >= 0).
- Budget: new spend for this run stops at M5_NEW_SPEND_CAP; reports not reached keep Tier 1 labels -> review.
  The client's own 50%-of-MAX_LLM_USD stop applies too. The agent prompt is not tuned on these results.

The agent sees only sentences + verified Tier 1 labels + FAIL messages; expert codes are used here, in eval/, for
scoring only (tests/test_repair_leakage.py).

Usage: python -m eval.repair [--cache-only] [--smoke N]
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from eval.labelling import (
    PRED_DIR,
    PROC,
    TABLES,
    Items,
    _save,
    evaluate,
    paired_diff,
    run_tier0,
    run_tier1,
    write_summary,
)
from radlabel.labelling.repair_agent import (
    MAX_REPORT_TOKENS,
    MAX_TOOL_CALLS,
    PROMPT_VERSION,
    REASONING_EFFORT,
    RepairResult,
    repair,
)
from radlabel.labelling.schema import ReportLabels
from radlabel.labelling.verifier import passed
from radlabel.labels import LABELS, NO_FINDING
from radlabel.llm import BudgetExceeded, CacheMiss, LLMClient
from radlabel.preprocess.sentences import Sentence
from radlabel.results import write_result

log = logging.getLogger(__name__)
M5_NEW_SPEND_CAP = 3.0  # USD of new spend for the whole M5 run (owner)
WORKERS = 4  # REPAIR_TPM 375K / (~8K tokens counted per request incl. max_tokens) / ~10 requests/min
REVIEW_FLAGS = ("section_rule", "hedge_consistency", "negation_consistency")
REVIEW_DIR = PRED_DIR.parent / "review"  # git-ignored


def review_reasons(out: ReportLabels | None, tier2: RepairResult | None, filtered: bool) -> list[str]:
    """Tier 3 routing (README §6.2): still failing after Tier 2, or escalated by a review flag."""
    if filtered:
        return ["content_filtered"]
    assert out is not None
    reasons = [f"tier2_not_accepted:{tier2.stop}"] if tier2 is not None and not tier2.accepted else []
    if not passed(out) and tier2 is None:
        reasons.append("tier2_not_run")
    reasons += sorted({m.check for m in out.verifier_messages if m.level == "flag" and m.check in REVIEW_FLAGS})
    return reasons


def _changes(it: Items, before: dict[int, dict[str, str]], after: dict[int, dict[str, str]], ids: list[int],
             keep: np.ndarray) -> dict[str, Any]:
    """Per label: status changes, and present-ness flips scored against v1 ground truth (present = positive)."""
    pos = {i: k for k, i in enumerate(it.ids)}
    by: dict[str, Counter] = {lab: Counter() for lab in LABELS}
    for i in ids:
        k = pos[i]
        if not keep[k]:
            continue
        for lab in LABELS:
            a, b = before[i].get(lab, "not_mentioned"), after[i].get(lab, "not_mentioned")
            if a == b:
                continue
            c = by[lab]
            c["status_changed"] += 1
            if lab == NO_FINDING and it.ignored_only[k]:
                c["not_scored"] += 1
                continue
            g, pa, pb = bool(it.gold["v1"][lab][k]), a == "present", b == "present"
            if pa == pb:
                c["no_effect_on_score"] += 1
            elif pb == g:
                c["wrong_to_right"] += 1
            else:
                c["right_to_wrong"] += 1
    total: Counter = Counter()
    for c in by.values():
        total.update(c)
    return {"by_label": {lab: dict(c) for lab, c in by.items() if c}, "total": dict(total)}


def _disagrees(it: Items, statuses: dict[str, str], k: int) -> bool:
    return any((statuses.get(lab) == "present") != bool(it.gold["v1"][lab][k]) for lab in LABELS
               if not (lab == NO_FINDING and it.ignored_only[k]))


def run_repairs(llm: LLMClient, todo: list[tuple[int, list[Sentence], ReportLabels]]
                ) -> tuple[dict[int, RepairResult], dict[int, str]]:
    spend0, lock, results, skipped = llm.spent, threading.Lock(), {}, {}

    def one(item: tuple[int, list[Sentence], ReportLabels]) -> None:
        rid, sents, v = item
        if llm.spent - spend0 >= M5_NEW_SPEND_CAP:
            with lock:
                skipped[rid] = "m5_spend_cap"
            return
        for attempt in range(3):
            try:
                r = repair(llm, str(rid), sents, v)
                with lock:
                    results[rid] = r
                return
            except (CacheMiss, BudgetExceeded) as e:
                with lock:
                    skipped[rid] = type(e).__name__
                return
            except Exception as e:  # network trouble after the client's retries: retry; never counted as a fail
                log.warning("report %s repair attempt %d: %s", rid, attempt + 1, type(e).__name__)
        with lock:
            skipped[rid] = "error"

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(one, todo))
    return results, skipped


def main(cache_only: bool = False, smoke: int = 0) -> dict[str, Any]:
    it = Items()
    pos = {i: k for k, i in enumerate(it.ids)}
    keep = ~it.subset["hedged"] & ~it.pilot
    t0, _ = run_tier0(it)
    raw, ver, t1_stats = run_tier1(cache_only=True, skip=frozenset(t0))  # Tier 1 is fixed: cache only
    ver = {**ver, **t0}
    sents = {r["id"]: [Sentence(**s) for s in r["sentences"]]
             for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] == r["group_rep"]}
    verified: dict[int, ReportLabels] = {}
    filtered: set[int] = set()
    for line in (PRED_DIR / "tier1.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("content_filtered"):
            filtered.add(int(d["report_id"]))
        elif "verified" in d:
            verified[int(d["verified"]["report_id"])] = ReportLabels(**d["verified"])
    fail_ids = sorted(i for i, v in verified.items() if not passed(v))
    assert len(fail_ids) == t1_stats["tier2_reports"], (len(fail_ids), t1_stats["tier2_reports"])

    llm = LLMClient(cache_only=cache_only)
    spend0 = llm.spent
    todo = [(i, sents[i], verified[i]) for i in fail_ids]
    if smoke:  # plumbing/cost check on reports that are never scored (pilot or hedged); not used for tuning
        todo = [x for x in todo if not keep[pos[x[0]]]][:smoke]
    results, skipped = run_repairs(llm, todo)
    spend = llm.spent - spend0
    if smoke:
        out = {i: {"stop": r.stop, "accepted": r.accepted, "tool_calls": r.tool_calls, "tokens": r.tokens,
                   "cost_usd": r.cost_usd} for i, r in results.items()}
        return {"smoke": out, "skipped": skipped, "spend_usd": spend}

    tier2 = {i: dict(s) for i, s in ver.items()}
    for i, r in results.items():
        if r.accepted:
            tier2[i] = {x.label: x.status for x in r.final.labels}
    res = evaluate(it, tier2)

    # routing (README §4.3, §8.1 pipeline metrics) over all exact-text representatives
    review: list[dict[str, Any]] = []
    route: dict[int, str] = {}
    for i in it.ids:
        r = results.get(i)
        out = r.final if r is not None else verified.get(i)
        reasons = review_reasons(out, r, i in filtered)
        route[i] = "review" if reasons else ("tier2_repaired" if r is not None and r.accepted else
                                             ("tier0" if i in t0 else "tier1_accepted"))
        if reasons:
            review.append({"report_id": i, "reasons": reasons})
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "review.jsonl").write_text("".join(json.dumps(x) + "\n" for x in review), encoding="utf-8")
    hedged = it.subset["hedged"]
    rev = np.array([route[i] == "review" for i in it.ids])
    t1_dis = np.array([_disagrees(it, ver[i], pos[i]) for i in it.ids])
    fin_dis = np.array([_disagrees(it, tier2[i], pos[i]) for i in it.ids])
    esc = np.isin(np.array(it.ids), fail_ids)
    rr = list(results.values())
    tier2_stats = {
        "deployment": llm.s.azure_openai_repair_deployment, "prompt_version": PROMPT_VERSION,
        "reasoning_effort": REASONING_EFFORT, "max_tool_calls": MAX_TOOL_CALLS, "max_report_tokens": MAX_REPORT_TOKENS,
        "models_returned": sorted({m for m in llm._models.values()}) or "all cached",
        "tier2_reports": len(fail_ids), "attempted": len(rr), "not_run": dict(Counter(skipped.values())),
        "accepted": sum(r.accepted for r in rr), "repair_success_rate": sum(r.accepted for r in rr) / len(fail_ids),
        "stop_reasons": dict(Counter(r.stop for r in rr)), "content_filtered": sum(r.stop == "content_filtered"
                                                                              for r in rr),
        "mean_tool_calls": float(np.mean([r.tool_calls for r in rr])) if rr else None,
        "tool_usage": dict(Counter(n for r in rr for n in r.tool_names)),
        "ignored_changes_to_non_failing_labels": sum(r.ignored_changes for r in rr),
        "submitted_but_failed_reverification": sum(r.submitted is not None and not r.accepted for r in rr),
        "llm_calls": sum(r.llm_calls for r in rr), "cached_calls": sum(r.cached_calls for r in rr),
        "new_spend_usd": spend, "llm_spend_total_usd": llm.spent, "m5_new_spend_cap_usd": M5_NEW_SPEND_CAP}
    routing = {
        "tier_distribution": dict(Counter(route.values())),
        "review_rate_hedged": float(rev[hedged].mean()), "review_rate_clear": float(rev[~hedged].mean()),
        "n_hedged": int(hedged.sum()), "n_clear": int((~hedged).sum()),
        "escalation_precision_tier2": float(t1_dis[esc].mean()),
        "escalation_precision_review": float(t1_dis[rev].mean()),
        "tier1_disagreement_base_rate": float(t1_dis.mean()),
        "final_disagreement_rate_on_review": float(fin_dis[rev].mean()),
        "definition": "escalation precision = share of escalated reports whose Tier 1 (+verifier) labels disagree "
                      "with v1 expert codes on >= 1 label (present = positive); base rate = same over all reports",
        "review_reasons": dict(Counter(x for r in review for x in r["reasons"])),
    }
    changes = {"all_211": _changes(it, ver, tier2, fail_ids, np.ones(len(it.ids), bool)),
               "scored_only": _changes(it, ver, tier2, fail_ids, keep)}
    res.update({"run": t1_stats, "tier2": tier2_stats, "routing": routing, "tier2_label_changes": changes})
    _save("llm_verifier_tier2", res, llm=f"{t1_stats['deployment']}+{tier2_stats['deployment']}",
          prompt=f"{t1_stats['prompt_version']}+{PROMPT_VERSION}")
    rule = {int(x["report_id"]): {y["label"]: y["status"] for y in x["labels"]}
            for x in map(json.loads, (PRED_DIR / "rule_baseline.jsonl").open(encoding="utf-8"))}
    paired = {"tier2_minus_llm_verifier": paired_diff(it, tier2, ver),
              "tier2_minus_rule_baseline": paired_diff(it, tier2, rule)}
    d = paired["tier2_minus_llm_verifier"]
    paired["decision"] = {"keep_tier2_in_pipeline": bool(d["hi"] >= 0),
                          "rule": "keep iff Tier 2 − LLM + verifier is not significantly negative (CI hi >= 0)"}
    write_result("labelling_tier2_paired_diffs", {k: v for k, v in paired.items() if k != "decision"},
                 fold="oof", mapping_version="v1", eval_version="eval_v1.2", decision=paired["decision"],
                 metric="headline macro-F1 (9 labels), hedged + pilot excluded")
    write_summary()
    with (PRED_DIR / "tier2.jsonl").open("w", encoding="utf-8") as f:
        for r in rr:
            f.write(r.model_dump_json() + "\n")
    (TABLES / "tier2_changes.md").write_text(render_changes(changes, tier2_stats, routing, paired), encoding="utf-8")
    return {"tier2": tier2_stats, "routing": routing, "changes": changes, "paired": paired}


def render_changes(changes: dict[str, Any], st: dict[str, Any], routing: dict[str, Any],
                   paired: dict[str, Any]) -> str:
    lines = ["# Tier 2 repair agent (M5)", "",
             f"{st['tier2_reports']} reports with a verifier FAIL; attempted {st['attempted']}, fix accepted "
             f"(passes re-verification) {st['accepted']} ({st['repair_success_rate']:.1%}); mean tool calls "
             f"{st['mean_tool_calls']:.2f}; stop reasons {st['stop_reasons']}; new spend ${st['new_spend_usd']:.3f}.",
             "", f"Decision rule: {paired['decision']['rule']} -> keep Tier 2: "
             f"**{paired['decision']['keep_tier2_in_pipeline']}**", "",
             "## Label changes (agent labels vs LLM + verifier; present = positive vs v1 expert codes)", ""]
    for scope, c in changes.items():
        lines += [f"### {scope}", "", "| Label | Status changed | Wrong → right | Right → wrong | No score effect |",
                  "|---|---|---|---|---|"]
        for lab, x in [*c["by_label"].items(), ("**total**", c["total"])]:
            lines.append(f"| {lab} | {x.get('status_changed', 0)} | {x.get('wrong_to_right', 0)} | "
                         f"{x.get('right_to_wrong', 0)} | {x.get('no_effect_on_score', 0)} |")
        lines.append("")
    lines += ["## Routing", "", f"- tier distribution: {routing['tier_distribution']}",
              f"- review rate: hedged {routing['review_rate_hedged']:.1%} (n = {routing['n_hedged']}), clear "
              f"{routing['review_rate_clear']:.1%} (n = {routing['n_clear']})",
              f"- escalation precision: Tier 2 {routing['escalation_precision_tier2']:.1%}, review "
              f"{routing['escalation_precision_review']:.1%} (base rate {routing['tier1_disagreement_base_rate']:.1%})",
              ""]
    return "\n".join(lines)


if __name__ == "__main__":
    smoke = int(sys.argv[sys.argv.index("--smoke") + 1]) if "--smoke" in sys.argv else 0
    out = main(cache_only="--cache-only" in sys.argv, smoke=smoke)
    print(json.dumps(out if smoke else {"tier2": out["tier2"], "routing": out["routing"]}, indent=1, default=str))
