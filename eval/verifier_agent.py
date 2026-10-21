"""M7: free-check escalation counts ($0) and verifier-agent development on the dev slice (README §6.2, §8.1).

- `escalation`: every exact-text representative's clean join through `run_pipeline(agent=False)` (cache only). Counts
  of escalated reports and labels, by reason, hedged vs clear, dev slice vs the rest; escalation precision (the
  tagger's labels after the deterministic verifier disagree with the v1 codes; present = positive); No Finding claims
  and the normal check. No agent call.
- `dev`: the agent on the escalated reports of the dev slice ONLY (the 102 Tier 1 pilot reports, never in headline
  metrics). Behaviour vs the v1 codes (eval side only), cost per report, and the full-run cost estimate
  (mean cost per escalated dev report x escalated reports outside the dev slice). New spend capped at DEV_SPEND_CAP.

- `full` (M7, owner-approved 2026-10-22, pre-committed in README §8.1): every report through `run_pipeline` with the
  agent (prompt frozen), column "LLM + free checks + verifier agent (v2)", paired bootstrap vs LLM only, vs LLM +
  verifier + Tier 2 and vs the rule baseline (keep the agent iff not significantly worse than LLM + verifier + Tier 2),
  label changes, verified vs unverified accuracy, escalation / unverified rates, the normal-check table, section
  corroboration, cost and tool use. Must run with the same embedding setup as the dev runs (EMBED_SETUP_REQUIRED).

Usage: python -m eval.verifier_agent escalation | dev | full  [--cache-only]
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from eval.entry_point import CLEAN_HEADERS, SECTIONS
from eval.labelling import (
    PRED_DIR,
    PROC,
    TABLES,
    Items,
    _fmt,
    _save,
    evaluate,
    paired_diff,
    score_block,
    write_summary,
)
from eval.repair import _changes
from radlabel.labelling import verifier_agent as va
from radlabel.labels import HEADLINE, LABELS, NO_FINDING
from radlabel.llm import LLMClient
from radlabel.pipeline import PipelineResult, run_pipeline
from radlabel.results import write_result

log = logging.getLogger(__name__)
DEV_SPEND_CAP = 1.0  # USD of new spend per dev run
WORKERS = 6  # REPAIR_TPM 375K / (~8K tokens counted per request); 429s are backed off by the client
# The dev runs (prompt development and freeze) had the optional "embed" extra installed (sentence-transformers,
# base model), so find_by_meaning worked; the full run must use the same setup.
EMBED_SETUP_REQUIRED = True


def clean_joins(ids: list[int]) -> dict[int, str]:
    iu = {r["id"]: r for r in map(json.loads, (PROC / "iu.jsonl").open(encoding="utf-8"))}
    return {i: "\n".join(f"{CLEAN_HEADERS[s]}: {iu[i][s]}" for s in SECTIONS if iu[i][s]) for i in ids}


def run_all(texts: dict[int, str], llm: LLMClient, agent: bool) -> dict[int, PipelineResult]:
    """Finished reports are cached, so a retry pass only pays for what is still missing."""
    def one(i: int) -> tuple[int, PipelineResult | None]:
        try:
            return i, run_pipeline(texts[i], llm, str(i), agent=agent)
        except Exception as e:  # network trouble after the client's retries (CacheMiss included in cache-only)
            log.warning("report %s not done yet: %s", i, type(e).__name__)
            return i, None
    done: dict[int, PipelineResult] = {}
    todo = sorted(texts)
    for attempt in range(1 if llm.cache_only else 3):
        with ThreadPoolExecutor((WORKERS if agent else 8) if attempt == 0 else 1) as ex:
            done.update({i: r for i, r in ex.map(one, todo) if r is not None})
        todo = [i for i in todo if i not in done]
    if todo:
        raise SystemExit(f"{len(todo)} reports not done (first: {todo[:5]}); rerun, finished ones are cached")
    return done


def embedding_setup() -> dict[str, Any]:
    ok = importlib.util.find_spec("sentence_transformers") is not None
    return {"embed_extra_installed": ok, "model": LLMClient(cache_only=True).s.embed_base_model,
            "sentence_transformers": importlib.metadata.version("sentence-transformers") if ok else None}


def _present(st: str) -> bool:
    return st == "present"


def escalation() -> dict[str, Any]:
    it = Items()
    pos = {i: k for k, i in enumerate(it.ids)}
    res = run_all(clean_joins(it.ids), LLMClient(cache_only=True), agent=False)
    gold, hedged, pilot = it.gold["v1"], it.subset["hedged"], it.pilot

    def wrong(i: int, lab: str) -> bool:
        if lab == NO_FINDING and it.ignored_only[pos[i]]:
            return False
        return _present(res[i].labels.status(lab)) != bool(gold[lab][pos[i]])

    esc = {i: r.escalations for i, r in res.items() if r.escalations}
    filtered = [i for i, r in res.items() if r.content_filtered]
    reasons = Counter(e.reason for es in esc.values() for e in es)
    reports_by_reason = Counter(x for es in esc.values() for x in {e.reason for e in es})
    only = Counter(next(iter({e.reason for e in es})) for es in esc.values() if len({e.reason for e in es}) == 1)
    labels_by_reason = {r: dict(Counter(e.label for es in esc.values() for e in es if e.reason == r))
                        for r in sorted(reasons)}
    pairs = {(i, e.label) for i, es in esc.items() for e in es}
    is_esc = np.array([i in esc for i in it.ids])
    disagree = np.array([any(wrong(i, lab) for lab in LABELS) for i in it.ids])
    nf_pred = [i for i, r in res.items() if r.labels.status(NO_FINDING) == "present"]
    nf_fail = [i for i in nf_pred if any(e.reason == "normal_check" for e in res[i].escalations)]
    nf_pass = [i for i in nf_pred if i not in nf_fail]

    def nf_precision(ids: list[int]) -> float | None:
        ids = [i for i in ids if not it.ignored_only[pos[i]]]
        return float(np.mean([gold[NO_FINDING][pos[i]] for i in ids])) if ids else None

    out = {
        "n_reports": len(res), "content_filtered_unverified": len(filtered),
        "escalated_reports": int(is_esc.sum()), "escalation_rate": float(is_esc.mean()),
        "escalation_rate_hedged": float(is_esc[hedged].mean()), "escalation_rate_clear": float(is_esc[~hedged].mean()),
        "escalated_dev_slice": int((is_esc & pilot).sum()), "dev_slice_reports": int(pilot.sum()),
        "escalated_outside_dev_slice": int((is_esc & ~pilot).sum()),
        "escalated_labels": len(pairs), "label_escalations_by_reason": dict(reasons),
        "reports_by_reason": dict(reports_by_reason), "reports_with_a_single_reason": dict(only),
        "labels_by_reason": labels_by_reason,
        "escalation_precision_reports": float(disagree[is_esc].mean()),
        "disagreement_base_rate": float(disagree.mean()),
        "disagreement_rate_not_escalated": float(disagree[~is_esc].mean()),
        "escalation_precision_labels": float(np.mean([wrong(i, lab) for i, lab in pairs])),
        "missed_disagreements_not_escalated": int((disagree & ~is_esc).sum()),
        "no_finding": {"predicted": len(nf_pred), "normal_check_passed": len(nf_pass),
                       "normal_check_failed": len(nf_fail), "precision_passed": nf_precision(nf_pass),
                       "precision_failed": nf_precision(nf_fail)},
        "definition": "escalation precision = share of escalated reports (labels) where the tagger's labels after the "
                      "deterministic verifier disagree with the v1 codes (present = positive)",
    }
    write_result("verifier_escalation", out, fold="oof", mapping_version="v1", eval_version="eval_v1.2",
                 llm="cache only, no agent")
    return out


def prompt_sha() -> str:
    return hashlib.sha256((va.SYSTEM + json.dumps(va.TOOLS, sort_keys=True)).encode()).hexdigest()


def dev(cache_only: bool = False) -> dict[str, Any]:
    it = Items()
    pos = {i: k for k, i in enumerate(it.ids)}
    dev_ids = [i for i in it.ids if it.pilot[pos[i]]]
    texts = clean_joins(dev_ids)
    pre = run_all(texts, LLMClient(cache_only=True), agent=False)
    todo = {i: texts[i] for i, r in pre.items() if r.escalations}
    llm = LLMClient(cache_only=cache_only)
    spend0 = llm.spent
    if llm.spent + DEV_SPEND_CAP > llm.s.max_llm_usd * 0.5:
        raise SystemExit("dev run could cross the budget stop; owner approval needed")
    res = run_all(todo, llm, agent=True)
    gold = it.gold["v1"]
    ver: Counter = Counter()
    flips: Counter = Counter()
    sugg: Counter = Counter()
    per_label: dict[str, Counter] = {lab: Counter() for lab in LABELS}
    agree = []
    for i, r in res.items():
        k = pos[i]
        tag = {x.label: x for x in r.labels.labels}
        for f in r.final:
            ver[f.verification] += 1
            if f.verification in ("verified_rules",):
                continue
            per_label[f.label][f.verification] += 1
            if f.label == NO_FINDING and it.ignored_only[k]:
                continue
            g, before, after = bool(gold[f.label][k]), _present(tag[f.label].status), _present(f.status)
            if before != after:
                flips["wrong_to_right" if after == g else "right_to_wrong"] += 1
            if f.verification == "suggested":
                sugg["correct" if after == g else "wrong"] += 1
            if f.verification in ("verified", "verified_impression_only") and tag[f.label].evidence:
                agree.append(bool(set(f.evidence) & set(tag[f.label].evidence)))
    rr = [r.agent for r in res.values() if r.agent is not None]
    costs = [a.cost_usd for a in rr]
    full = escalation_counts()
    out = {
        "prompt_version": va.PROMPT_VERSION, "prompt_sha256": prompt_sha(), "dev_reports": len(dev_ids),
        "escalated_dev_reports": len(todo), "agent_runs": len(rr),
        "stop_reasons": dict(Counter(a.stop for a in rr)),
        "mean_tool_calls": float(np.mean([a.tool_calls for a in rr])) if rr else None,
        "tool_usage": dict(Counter(n for a in rr for n in a.tool_names)),
        "verification_counts": dict(ver), "per_label": {k: dict(v) for k, v in per_label.items() if v},
        "present_flips_vs_codes": dict(flips), "suggested_vs_codes": dict(sugg),
        "evidence_agreement_with_tagger": float(np.mean(agree)) if agree else None,
        "unverified_labels": ver["unverified"], "reports_with_unverified": sum(
            any(f.verification == "unverified" for f in r.final) for r in res.values()),
        "models_returned": sorted({m for a in rr for m in a.models}),
        "cost_dev_usd": sum(costs), "mean_cost_per_escalated_report_usd": float(np.mean(costs)) if costs else None,
        "new_spend_this_run_usd": llm.spent - spend0, "llm_spend_total_usd": llm.spent,
        "full_run_escalated_reports_outside_dev": full,
        "full_run_estimated_cost_usd": float(np.mean(costs)) * full if costs else None,
        "embedding_setup": embedding_setup(),
    }
    write_result("verifier_agent_dev", out, fold="dev_slice", mapping_version="v1", eval_version="eval_v1.2",
                 llm=llm.s.azure_openai_repair_deployment, prompt=va.PROMPT_VERSION)
    with (PRED_DIR / "verifier_agent_dev.jsonl").open("w", encoding="utf-8") as f:
        for i in sorted(res):
            f.write(res[i].model_dump_json(exclude={"parse"}) + "\n")  # git-ignored: holds report text
    return out


def v1_statuses() -> dict[str, dict[int, dict[str, str]]]:
    """Per-report statuses of the v1 columns, from their prediction files (content-filtered -> rule labels)."""
    def st(labels: list[dict[str, Any]]) -> dict[str, str]:
        return {x["label"]: x["status"] for x in labels}
    rule = {int(x["report_id"]): st(x["labels"]) for x in map(json.loads, (PRED_DIR / "rule_baseline.jsonl").open(
        encoding="utf-8"))}
    raw: dict[int, dict[str, str]] = {}
    ver: dict[int, dict[str, str]] = {}
    for d in map(json.loads, (PRED_DIR / "tier1.jsonl").open(encoding="utf-8")):
        if "raw" in d:
            i = int(d["raw"]["report_id"])
            raw[i], ver[i] = st(d["raw"]["labels"]), st(d["verified"]["labels"])
        else:
            raw[int(d["report_id"])] = ver[int(d["report_id"])] = rule[int(d["report_id"])]
    tier2 = dict(ver)
    for d in map(json.loads, (PRED_DIR / "tier2.jsonl").open(encoding="utf-8")):
        if d["accepted"]:
            tier2[int(d["report_id"])] = st(d["final"]["labels"])
    return {"rule": rule, "llm_only": raw, "llm_verifier": ver, "tier2": tier2}


def reason_category(reason: str) -> str:
    """Fixed categories for unverified reasons: the agent's own free-text reasons quote report wording, and results
    files are committed (licence D1), so they never go into a results file."""
    for prefix in ("agent stopped", "agent evidence failed", "derived after", "tagger output", "budget",
                   "agent not run"):
        if reason.startswith(prefix):
            return reason if prefix in ("agent stopped", "tagger output") else prefix
    return "agent: cannot_verify"


def _counts(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    """(predicted present, gold) pairs -> counts, precision, recall, F1, accuracy."""
    tp = sum(p and g for p, g in pairs)
    fp = sum(p and not g for p, g in pairs)
    fn = sum(g and not p for p, g in pairs)
    pr = tp / (tp + fp) if tp + fp else None
    rc = tp / (tp + fn) if tp + fn else None
    return {"n": len(pairs), "predicted_present": tp + fp, "tp": tp, "fp": fp, "fn": fn, "precision": pr,
            "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr and rc else None,
            "accuracy": sum(p == g for p, g in pairs) / len(pairs) if pairs else None}


def full(cache_only: bool = False) -> dict[str, Any]:
    setup = embedding_setup()
    if EMBED_SETUP_REQUIRED and not setup["embed_extra_installed"]:
        raise SystemExit("the dev runs used the 'embed' extra; install it so the full run uses the same setup")
    it = Items()
    pos = {i: k for k, i in enumerate(it.ids)}
    keep = ~it.subset["hedged"] & ~it.pilot
    hedged = it.subset["hedged"]
    llm = LLMClient(cache_only=cache_only)
    spend0 = llm.spent
    res = run_all(clean_joins(it.ids), llm, agent=True)
    with (PRED_DIR / "verifier_agent_full.jsonl").open("w", encoding="utf-8") as f:  # git-ignored: report text
        for i in sorted(res):  # deterministic: the same file on every rerun
            f.write(res[i].model_dump_json(exclude={"agent": {"cached_calls"}}) + "\n")
    gold = it.gold["v1"]
    v1 = v1_statuses()
    before = {i: {x.label: x.status for x in r.labels.labels} for i, r in res.items()}  # LLM + verifier, this run
    final = {i: {f.label: f.status for f in r.final} for i, r in res.items()}
    no_sugg = {i: {f.label: (before[i][f.label] if f.verification == "suggested" else f.status) for f in r.final}
               for i, r in res.items()}

    out = evaluate(it, final)
    sens = score_block(it, {lab: np.array([no_sugg[i].get(lab) == "present" for i in it.ids]) for lab in LABELS},
                       "v1", keep, LABELS)
    out["sensitivity_suggested_ignored"] = {"v1_macro_f1_headline": sens["macro_f1_headline"],
                                            "v1_rare_micro_f1": sens["rare_micro_f1"]}

    def scored(i: int, lab: str) -> bool:
        return bool(keep[pos[i]]) and not (lab == NO_FINDING and it.ignored_only[pos[i]])

    def g(i: int, lab: str) -> bool:
        return bool(gold[lab][pos[i]])

    labs = [(i, f) for i, r in res.items() for f in r.final if scored(i, f.label)]
    group = {"verified_rules": ("verified_rules",), "verified": ("verified", "verified_impression_only"),
             "corrected": ("corrected",), "suggested": ("suggested",), "unverified": ("unverified",),
             "verified_or_verified_rules": ("verified_rules", "verified", "verified_impression_only")}
    by_ver = {k: _counts([(f.status == "present", g(i, f.label)) for i, f in labs if f.verification in v])
              for k, v in group.items()}
    sugg = [(i, f) for i, f in labs if f.verification == "suggested"]
    suggested = {"n": len(sugg), "present": sum(f.status == "present" for _, f in sugg),
                 "uncertain": sum(f.status == "uncertain" for _, f in sugg),
                 "precision_of_present": _counts([(True, g(i, f.label)) for i, f in sugg
                                                  if f.status == "present"])["precision"]}

    # escalation and unverified rates, hedged vs clear (all reports)
    esc = np.array([bool(res[i].escalations) for i in it.ids])
    unv = np.array([any(f.verification == "unverified" for f in res[i].final) for i in it.ids])
    n_unv_labels = sum(f.verification == "unverified" for r in res.values() for f in r.final)
    t2 = json.loads((TABLES.parent / "results" / "labelling_llm_verifier_tier2.json").read_text(encoding="utf-8"))
    dist = t2["results"]["routing"]["tier_distribution"]
    v1_review = dist.get("review", 0) / sum(dist.values())
    rates = {"escalated_reports": int(esc.sum()), "escalation_rate": float(esc.mean()),
             "escalation_rate_hedged": float(esc[hedged].mean()), "escalation_rate_clear": float(esc[~hedged].mean()),
             "reports_by_reason": dict(Counter(x for r in res.values() for x in {e.reason for e in r.escalations})),
             "label_escalations_by_reason": dict(Counter(e.reason for r in res.values() for e in r.escalations)),
             "unverified_labels": n_unv_labels, "unverified_label_rate": n_unv_labels / (len(res) * len(LABELS)),
             "reports_with_unverified": int(unv.sum()), "unverified_report_rate": float(unv.mean()),
             "unverified_report_rate_hedged": float(unv[hedged].mean()),
             "unverified_report_rate_clear": float(unv[~hedged].mean()),
             "unverified_reasons": dict(Counter(reason_category(f.reason) for r in res.values() for f in r.final
                                                if f.verification == "unverified")),
             "v1_review_rate": v1_review, "reduced_vs_v1_review_rate": bool(unv.mean() < v1_review)}

    # normal check table: tagger No Finding (after the deterministic verifier) x check x tagger right/wrong
    cells: dict[str, Counter] = {}
    for i, r in res.items():
        if before[i].get(NO_FINDING) != "present" or not scored(i, NO_FINDING):
            continue
        check = "failed" if any(e.reason == "normal_check" for e in r.escalations) else "passed"
        right = g(i, NO_FINDING)
        kept = final[i].get(NO_FINDING) == "present"
        c = cells.setdefault(f"{check}|tagger_{'right' if right else 'wrong'}", Counter())
        c["n"] += 1
        c[f"{'kept' if kept else 'withheld'}_{'right' if kept == right else 'wrong'}"] += 1
    nf_before = _counts([(before[i].get(NO_FINDING) == "present", g(i, NO_FINDING)) for i in res
                         if scored(i, NO_FINDING)])
    nf_after = _counts([(final[i].get(NO_FINDING) == "present", g(i, NO_FINDING)) for i in res
                        if scored(i, NO_FINDING)])
    normal = {"cells": {k: dict(v) for k, v in sorted(cells.items())}, "no_finding_before": nf_before,
              "no_finding_after": nf_after}

    # section corroboration of final present labels (headline + rare), by level
    pres = [(i, f) for i, f in labs if f.status == "present"]

    def level(f: va.FinalLabel) -> str:
        if f.verification == "unverified":
            return "unverified"
        return {"both": "both", "findings": "single", "impression": "single"}.get(f.corroboration or "none", "none")
    corro = {lv: _counts([(True, g(i, f.label)) for i, f in pres if level(f) == lv])
             for lv in ("both", "single", "none", "unverified")}

    def micro(levels: tuple[str, ...]) -> float | None:
        """Pooled micro-F1 over the 9 headline labels if only present labels at these levels count as present."""
        return _counts([(f.status == "present" and level(f) in levels, g(i, f.label)) for i, f in labs
                        if f.label in HEADLINE])["f1"]
    corroboration = {"precision_by_level": corro,
                     "headline_micro_f1_if_only": {"both": micro(("both",)),
                                                   "both_or_single": micro(("both", "single")),
                                                   "all_but_unverified": micro(("both", "single", "none")),
                                                   "all": micro(("both", "single", "none", "unverified"))},
                     "suggested_uncertain_excluded": sum(f.verification == "suggested" and f.status != "present"
                                                         for _, f in labs)}

    rr = [r.agent for r in res.values() if r.agent is not None]
    agent = {"prompt_version": va.PROMPT_VERSION, "prompt_sha256": prompt_sha(), "embedding_setup": setup,
             "agent_runs": len(rr), "stop_reasons": dict(Counter(a.stop for a in rr)),
             "caps_hit": sum(a.stop in ("tool_cap", "token_cap") for a in rr),
             "refusals_content_filtered": sum(a.stop == "content_filtered" for a in rr),
             "budget_stops": sum(any(f.reason == "budget" for f in r.final) for r in res.values()),
             "mean_tool_calls": float(np.mean([a.tool_calls for a in rr])),
             "tool_usage": dict(sorted(Counter(n for a in rr for n in a.tool_names).items())),
             "llm_calls": sum(a.llm_calls for a in rr), "tokens": sum(a.tokens for a in rr),
             "agent_cost_usd": sum(a.cost_usd for a in rr),
             "mean_cost_per_agent_report_usd": float(np.mean([a.cost_usd for a in rr])),
             "models_returned": sorted({m for a in rr for m in a.models}),
             "tagger_reports_content_filtered": sum(r.content_filtered for r in res.values())}
    changes = {"all": _changes(it, before, final, it.ids, np.ones(len(it.ids), bool)),
               "scored_only": _changes(it, before, final, it.ids, keep)}
    clean_vs_ver = sum(before[i] != v1["llm_verifier"][i] for i in it.ids)
    out.update({"agent": agent, "rates": rates, "verification_groups": by_ver, "suggested": suggested,
                "normal_check": normal, "corroboration": corroboration, "label_changes": changes,
                "before_differs_from_llm_verifier_column": clean_vs_ver})
    new_spend = llm.spent - spend0
    _save("llm_agent_v2", out, llm=f"{llm.s.azure_openai_deployment}+{llm.s.azure_openai_repair_deployment}",
          prompt=f"tier1-v1+{va.PROMPT_VERSION}", new_spend_this_run_usd=new_spend, llm_spend_total_usd=llm.spent)
    paired = {"v2_minus_llm_only": paired_diff(it, final, v1["llm_only"]),
              "v2_minus_tier2": paired_diff(it, final, v1["tier2"]),
              "v2_minus_rule_baseline": paired_diff(it, final, v1["rule"])}
    d = paired["v2_minus_tier2"]
    decision = {"keep_verifier_agent": bool(d["hi"] >= 0),
                "rule": "keep iff v2 − LLM + verifier + Tier 2 is not significantly negative (CI hi >= 0)"}
    write_result("labelling_v2_paired_diffs", paired, fold="oof", mapping_version="v1", eval_version="eval_v1.2",
                 decision=decision, metric="headline macro-F1 (9 labels), hedged + pilot excluded")
    write_summary()
    return {"agent": agent, "rates": rates, "paired": paired, "decision": decision, "new_spend_usd": new_spend}


def render_full(v2: dict[str, Any], paired: dict[str, Any], decision: dict[str, Any] | None) -> str:
    """README §10 block for the M7 full run (eval/report.py)."""

    def pct(x: float | None) -> str:
        return "–" if x is None else f"{100 * x:.1f}%"

    def num(x: float | None) -> str:
        return "–" if x is None else f"{x:.3f}"
    a, r, ch = v2["agent"], v2["rates"], v2["label_changes"]["scored_only"]
    d = paired.get("v2_minus_tier2")
    lines = []
    if d is not None and decision is not None:
        lines += [f"**Keep/drop (pre-committed):** v2 − LLM + verifier + Tier 2 = {_fmt(d)} → keep the verifier agent: "
                  f"**{'yes' if decision['keep_verifier_agent'] else 'no'}** ({decision['rule']}).", ""]
    lines += [f"Escalated to the agent: {r['escalated_reports']:,} reports ({pct(r['escalation_rate'])}; hedged "
              f"{pct(r['escalation_rate_hedged'])} vs clear {pct(r['escalation_rate_clear'])}). Reports with any "
              f"`unverified` label: {r['reports_with_unverified']:,} ({pct(r['unverified_report_rate'])}; hedged "
              f"{pct(r['unverified_report_rate_hedged'])} vs clear {pct(r['unverified_report_rate_clear'])}); "
              f"unverified labels {r['unverified_labels']:,} ({pct(r['unverified_label_rate'])}). v1 review rate: "
              f"{pct(r['v1_review_rate'])}, so v2 **{'reduced' if r['reduced_vs_v1_review_rate'] else 'did not reduce'}"
              f"** the share of reports needing attention.", "",
              "Label changes vs LLM + verifier (scored reports; present = positive vs the codes): "
              f"{ch['total'].get('status_changed', 0)} status changes, wrong → right "
              f"{ch['total'].get('wrong_to_right', 0)}, right → wrong {ch['total'].get('right_to_wrong', 0)}. "
              "Per label: " + "; ".join(f"{lab} {c.get('wrong_to_right', 0)}/{c.get('right_to_wrong', 0)}"
                                        for lab, c in ch["by_label"].items()
                                        if c.get("wrong_to_right") or c.get("right_to_wrong")) + ".", "",
              "**Verified vs unverified** (scored reports, all labels; present = positive):", "",
              "| Verification | Labels | Predicted present | Precision | Recall | F1 | Accuracy |",
              "|---|---|---|---|---|---|---|"]
    for k, x in v2["verification_groups"].items():
        lines.append(f"| {k.replace('_', ' ')} | {x['n']:,} | {x['predicted_present']} | {num(x['precision'])} | "
                     f"{num(x['recall'])} | {num(x['f1'])} | {num(x['accuracy'])} |")
    s = v2["suggested"]
    lines += ["", f"Suggested labels: {s['n']} ({s['present']} present, {s['uncertain']} uncertain); precision of the "
              f"present ones {num(s['precision_of_present'])}.", "",
              "**Normal check** (tagger No Finding after the deterministic verifier, scored reports):", "",
              "| Check | Tagger vs codes | Reports | Kept, right | Kept, wrong | Withheld, right | Withheld, wrong |",
              "|---|---|---|---|---|---|---|"]
    for k, c in v2["normal_check"]["cells"].items():
        chk, tag = k.split("|")
        lines.append(f"| {chk} | {tag.replace('tagger_', '')} | {c['n']} | {c.get('kept_right', 0)} | "
                     f"{c.get('kept_wrong', 0)} | {c.get('withheld_right', 0)} | {c.get('withheld_wrong', 0)} |")
    nb, na = v2["normal_check"]["no_finding_before"], v2["normal_check"]["no_finding_after"]
    co = v2["corroboration"]
    lines += ["", f"No Finding precision {num(nb['precision'])} before (recall {num(nb['recall'])}) → "
              f"{num(na['precision'])} after (recall {num(na['recall'])}).", "",
              "**Section corroboration** of final `present` labels (scored reports):", "",
              "| Level | Labels | Precision |", "|---|---|---|"]
    lines += [f"| {lv} | {x['n']:,} | {num(x['precision'])} |" for lv, x in co["precision_by_level"].items()]
    mi = co["headline_micro_f1_if_only"]
    lines += ["", "Headline micro-F1 if only these levels count as present: " + ", ".join(
        f"{k.replace('_', ' ')} {num(v)}" for k, v in mi.items()) + ".", "",
              f"Agent: prompt `{a['prompt_version']}` (frozen), {a['agent_runs']:,} runs, mean tool calls "
              f"{a['mean_tool_calls']:.2f}; tools {a['tool_usage']}; stops {a['stop_reasons']}; caps hit "
              f"{a['caps_hit']}, content-filter refusals {a['refusals_content_filtered']}, budget stops "
              f"{a['budget_stops']}; cost ${a['agent_cost_usd']:.2f} (${a['mean_cost_per_agent_report_usd']:.4f} per "
              f"report); embeddings: {a['embedding_setup']['model']} (sentence-transformers "
              f"{a['embedding_setup']['sentence_transformers']})."]
    return "\n".join(lines) + "\n"


def render(esc: dict[str, Any], dev: dict[str, Any] | None) -> str:
    """README §10 block (eval/report.py): escalation before any agent call, and dev-slice behaviour."""
    def pct(x: float | None) -> str:
        return "–" if x is None else f"{100 * x:.1f}%"
    rb, nf = esc["reports_by_reason"], esc["no_finding"]
    lines = [f"Free checks on all {esc['n_reports']:,} unique reports (clean join, tagger from cache, no agent call, "
             f"$0): **{esc['escalated_reports']:,} reports escalate ({pct(esc['escalation_rate'])})**; hedged "
             f"{pct(esc['escalation_rate_hedged'])} vs clear {pct(esc['escalation_rate_clear'])}; "
             f"{esc['escalated_labels']:,} labels. {esc['content_filtered_unverified']} content-filtered reports end "
             "`unverified` without an agent call.", "",
             "| Reason | Reports | Labels | Reports with only this reason |", "|---|---|---|---|"]
    lines += [f"| {r.replace('_', ' ')} | {n} | {esc['label_escalations_by_reason'][r]} | "
              f"{esc['reports_with_a_single_reason'].get(r, 0)} |"
              for r, n in sorted(rb.items(), key=lambda x: -x[1])]
    lines += ["", f"Escalation precision (tagger labels disagree with the codes): reports "
              f"{pct(esc['escalation_precision_reports'])}, labels {pct(esc['escalation_precision_labels'])}; "
              f"base rate {pct(esc['disagreement_base_rate'])}; not escalated "
              f"{pct(esc['disagreement_rate_not_escalated'])} "
              f"({esc['missed_disagreements_not_escalated']} reports). Predicted No Finding {nf['predicted']}: normal "
              f"check passed {nf['normal_check_passed']} (precision {pct(nf['precision_passed'])}), failed "
              f"{nf['normal_check_failed']} (precision {pct(nf['precision_failed'])})."]
    if dev is not None:
        fl, sg, vc = dev["present_flips_vs_codes"], dev["suggested_vs_codes"], dev["verification_counts"]
        lines += ["", f"Verifier agent on the **dev slice only** ({dev['escalated_dev_reports']} escalated of "
                  f"{dev['dev_reports']} Tier 1 pilot reports; not a headline result), prompt `{dev['prompt_version']}`"
                  f" (frozen): labels changed vs the codes wrong → right {fl.get('wrong_to_right', 0)}, right → wrong "
                  f"{fl.get('right_to_wrong', 0)}; suggested correct {sg.get('correct', 0)}, wrong "
                  f"{sg.get('wrong', 0)}; verified {vc.get('verified', 0) + vc.get('verified_impression_only', 0)}, "
                  "corrected "
                  f"{vc.get('corrected', 0)}, unverified {vc.get('unverified', 0)}; mean tool calls "
                  f"{dev['mean_tool_calls']:.2f}; ${dev['mean_cost_per_escalated_report_usd']:.4f} per report. "
                  f"Estimated full run: {dev['full_run_escalated_reports_outside_dev']:,} reports, "
                  f"${dev['full_run_estimated_cost_usd']:.2f}."]
    return "\n".join(lines) + "\n"


def escalation_counts() -> int:
    f = json.loads((TABLES.parent / "results" / "verifier_escalation.json").read_text(encoding="utf-8"))
    return int(f["results"]["escalated_outside_dev_slice"])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "escalation"
    co = "--cache-only" in sys.argv
    r = escalation() if mode == "escalation" else dev(cache_only=co) if mode == "dev" else full(cache_only=co)
    print(json.dumps(r, indent=1))
