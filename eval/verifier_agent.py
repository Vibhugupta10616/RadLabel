"""M7: free-check escalation counts ($0) and verifier-agent development on the dev slice (README §6.2, §8.1).

- `escalation`: every exact-text representative's clean join through `run_pipeline(agent=False)` (cache only). Counts
  of escalated reports and labels, by reason, hedged vs clear, dev slice vs the rest; escalation precision (the
  tagger's labels after the deterministic verifier disagree with the v1 codes; present = positive); No Finding claims
  and the normal check. No agent call.
- `dev`: the agent on the escalated reports of the dev slice ONLY (the 102 Tier 1 pilot reports, never in headline
  metrics). Behaviour vs the v1 codes (eval side only), cost per report, and the full-run cost estimate
  (mean cost per escalated dev report x escalated reports outside the dev slice). New spend capped at DEV_SPEND_CAP.

Usage: python -m eval.verifier_agent escalation | dev
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from eval.entry_point import CLEAN_HEADERS, SECTIONS
from eval.labelling import PRED_DIR, PROC, TABLES, Items
from radlabel.labelling import verifier_agent as va
from radlabel.labels import LABELS, NO_FINDING
from radlabel.llm import LLMClient
from radlabel.pipeline import PipelineResult, run_pipeline
from radlabel.results import write_result

DEV_SPEND_CAP = 1.0  # USD of new spend per dev run
WORKERS = 4  # REPAIR_TPM 375K / (~10K tokens counted per request) / ~10 requests/min


def clean_joins(ids: list[int]) -> dict[int, str]:
    iu = {r["id"]: r for r in map(json.loads, (PROC / "iu.jsonl").open(encoding="utf-8"))}
    return {i: "\n".join(f"{CLEAN_HEADERS[s]}: {iu[i][s]}" for s in SECTIONS if iu[i][s]) for i in ids}


def run_all(texts: dict[int, str], llm: LLMClient, agent: bool) -> dict[int, PipelineResult]:
    def one(i: int) -> tuple[int, PipelineResult]:
        return i, run_pipeline(texts[i], llm, str(i), agent=agent)
    with ThreadPoolExecutor(WORKERS if agent else 8) as ex:
        return dict(ex.map(one, sorted(texts)))


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
    }
    write_result("verifier_agent_dev", out, fold="dev_slice", mapping_version="v1", eval_version="eval_v1.2",
                 llm=llm.s.azure_openai_repair_deployment, prompt=va.PROMPT_VERSION)
    with (PRED_DIR / "verifier_agent_dev.jsonl").open("w", encoding="utf-8") as f:
        for i in sorted(res):
            f.write(res[i].model_dump_json(exclude={"parse"}) + "\n")  # git-ignored: holds report text
    return out


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
    r = escalation() if mode == "escalation" else dev(cache_only="--cache-only" in sys.argv)
    print(json.dumps(r, indent=1))
