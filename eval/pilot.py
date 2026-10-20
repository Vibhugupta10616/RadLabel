"""Tier 1 model-selection pilot (README §7.1, M4a): ~100 reports from training folds only.

Sample: 100 exact-text representatives from the inner-validation clusters of fold 0 (= fold 0's training
folds), multilabel-stratified (iterstrat, seed SEED). Each candidate runs at temperature 0 (GPT-5.x with
reasoning_effort="none"), max_tokens TIER1_MAX_TOKENS. Scored like §8.1 (hedged excluded) on the sample.
Compared: headline macro-F1, invalid-output rate, verifier fail rate, cost per report (fresh calls).

Usage: python -m eval.pilot
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit

from eval.baselines.rule_baseline import label_report
from eval.cv import load_folds
from eval.labelling import Items, score_block
from radlabel.config import get_settings
from radlabel.labelling.extractor import PROMPT_VERSION, extract
from radlabel.labelling.verifier import passed, verify
from radlabel.labels import LABELS
from radlabel.llm import PRICES, LLMClient
from radlabel.preprocess.sentences import Sentence
from radlabel.results import write_result

PROC = Path("data/processed")
N_PILOT = 100
WORKERS = 8


def pilot_ids(it: Items, seed: int) -> list[int]:
    _, inner = load_folds()
    pool = [k for k, c in enumerate(it.cluster) if c in inner[0]]
    y = np.array([[it.gold["v1"][lab][k] for lab in LABELS] for k in pool], dtype=int)
    _, pick = next(MultilabelStratifiedShuffleSplit(n_splits=1, test_size=N_PILOT, random_state=seed)
                   .split(np.zeros((len(pool), 1)), y))
    return sorted(it.ids[pool[i]] for i in pick)


def run_model(llm: LLMClient, dep: str, reports: dict[int, list[Sentence]]) -> dict[str, Any]:
    gpt5 = dep.startswith("gpt-5")
    before = llm.spent

    def one(rid: int) -> tuple[int, Any, Any]:
        out, r = extract(llm, str(rid), reports[rid], deployment=dep, temperature=0.0,
                         reasoning_effort="none" if gpt5 else None)
        return rid, out, r

    with ThreadPoolExecutor(WORKERS) as ex:
        rows = list(ex.map(one, sorted(reports)))
    statuses, invalid, fails, models = {}, 0, 0, set()
    tok_in = tok_out = 0
    for rid, out, r in rows:
        models.add(r.model)
        tok_in += r.input_tokens
        tok_out += r.output_tokens
        if out is None:
            invalid += 1
            statuses[rid] = {}
            continue
        statuses[rid] = {x.label: x.status for x in out.labels}  # LLM only
        fails += not passed(verify(out, reports[rid]))
    cost = sum(r.cost_usd for _, _, r in rows)
    n = len(rows)
    return {"statuses": statuses, "invalid_rate": invalid / n, "verifier_fail_rate": fails / max(1, n - invalid),
            "cost_usd": cost, "cost_per_report_usd": cost / n, "mean_input_tokens": tok_in / n,
            "mean_output_tokens": tok_out / n, "models_returned": sorted(models),
            "settings": {"temperature": 0.0, "reasoning_effort": "none" if gpt5 else None},
            "spent_this_model_usd": llm.spent - before}


def main() -> dict[str, Any]:
    s = get_settings()
    it = Items()
    ids = pilot_ids(it, s.seed)
    rep = {r["id"]: [Sentence(**x) for x in r["sentences"]]
           for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] in set(ids)}
    keep = np.isin(np.array(it.ids), ids) & ~it.subset["hedged"]
    llm = LLMClient()
    spend0 = llm.spent

    def score(statuses: dict[int, dict[str, str]]) -> dict[str, Any]:
        full = {i: statuses.get(i, {}) for i in it.ids}
        pres = {lab: np.array([full[i].get(lab) == "present" for i in it.ids]) for lab in LABELS}
        return score_block(it, pres, "v1", keep, LABELS)

    out: dict[str, Any] = {"n_reports": len(ids), "n_scored_non_hedged": int(keep.sum()),
                           "sample": "fold-0 inner-validation clusters (training folds of fold 0)",
                           "prompt_version": PROMPT_VERSION, "candidates": {}}
    rb = {i: {x.label: x.status for x in label_report(str(i), rep[i]).labels} for i in ids}
    out["rule_baseline"] = {"macro_f1_headline": score(rb)["macro_f1_headline"]}
    for dep in s.pilot_list:
        if dep not in PRICES:
            out["candidates"][dep] = {"skipped": "no verified price"}
            continue
        try:
            res = run_model(llm, dep, rep)
        except Exception as e:  # e.g. 404 DeploymentNotFound: skip, as decided (D2)
            out["candidates"][dep] = {"skipped": f"{type(e).__name__}: {str(e)[:120]}"}
            continue
        sc = score(res.pop("statuses"))
        out["candidates"][dep] = {**res, "macro_f1_headline": sc["macro_f1_headline"],
                                  "per_label_f1": {lab: sc["labels"][lab]["f1"]["value"] for lab in LABELS}}
    out["pilot_spend_usd"] = llm.spent - spend0
    out["llm_spend_total_usd"] = llm.spent
    write_result("model_pilot", out, fold="pilot:fold0-inner-val", mapping_version="v1")
    return out


def followup() -> dict[str, Any]:
    """Owner follow-up (M4): No Finding derived in code + new absent-evidence rule. Re-runs ONLY the verifier on
    the stored pilot outputs (cache_only: a cache miss raises instead of calling), plus a paired bootstrap of the
    headline macro-F1 difference vs the rule baseline on the same scored reports."""
    import collections

    from eval.bootstrap import bootstrap_ci, f1
    from radlabel.labels import HEADLINE, NO_FINDING

    s = get_settings()
    it = Items()
    ids = pilot_ids(it, s.seed)
    rep = {r["id"]: [Sentence(**x) for x in r["sentences"]]
           for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] in set(ids)}
    keep = np.isin(np.array(it.ids), ids) & ~it.subset["hedged"]
    llm = LLMClient(cache_only=True)
    spend0 = llm.spent

    def arrays(statuses: dict[int, dict[str, str]]) -> dict[str, np.ndarray]:
        return {lab: np.array([statuses.get(i, {}).get(lab) == "present" for i in it.ids]) for lab in LABELS}

    def macro(pred: dict[str, np.ndarray], idx: np.ndarray) -> float:
        k = idx[keep[idx]]
        scores = []
        for lab in HEADLINE:
            m = ~it.ignored_only[k] if lab == NO_FINDING else np.ones(len(k), bool)  # as in eval.labelling
            scores.append(f1(it.gold["v1"][lab][k][m], pred[lab][k][m]))
        return float(np.nanmean(scores))

    rb = arrays({i: {x.label: x.status for x in label_report(str(i), rep[i]).labels} for i in ids})
    out: dict[str, Any] = {"n_reports": len(ids), "n_scored_non_hedged": int(keep.sum()),
                           "chosen_tier1": "gpt-4.1-mini", "choice_note": "chosen on pilot, CIs overlap",
                           "lung_lesion_positive_support_scored": int(it.gold["v1"]["Lung Lesion"][keep].sum()),
                           "candidates": {}}
    sub = np.flatnonzero(keep)
    for dep in s.pilot_list:
        gpt5 = dep.startswith("gpt-5")
        raw, ver, fails, flags = {}, {}, collections.Counter(), collections.Counter()
        n_fail = n_flag = 0
        for rid in ids:
            o, r = extract(llm, str(rid), rep[rid], deployment=dep, temperature=0.0,
                           reasoning_effort="none" if gpt5 else None)
            assert r.cached and o is not None
            raw[rid] = {x.label: x.status for x in o.labels}
            v = verify(o, rep[rid])
            ver[rid] = {x.label: x.status for x in v.labels}
            f = [m for m in v.verifier_messages if m.level == "fail"]
            g = [m for m in v.verifier_messages if m.level == "flag"]
            n_fail += bool(f)
            n_flag += bool(g)
            fails.update(m.check for m in f)
            flags.update(m.check for m in g)
        p_raw, p_ver = arrays(raw), arrays(ver)
        diff = bootstrap_ci(lambda i, p=p_raw: macro(p, sub[i]) - macro(rb, sub[i]), it.cluster[sub].tolist(), n=1000)
        out["candidates"][dep] = {
            "macro_f1_llm_only": macro(p_raw, sub), "macro_f1_llm_verifier": macro(p_ver, sub),
            "paired_diff_vs_rule_baseline": {"value": diff[0], "lo": diff[1], "hi": diff[2]},
            "report_fail_rate": n_fail / len(ids), "report_flag_rate": n_flag / len(ids),
            "fails_by_check": dict(fails), "flags_by_check": dict(flags)}
    out["rule_baseline_macro_f1"] = macro(rb, sub)
    out["new_llm_spend_usd"] = llm.spent - spend0  # must be 0: cache only
    write_result("model_pilot_followup", out, fold="pilot:fold0-inner-val", mapping_version="v1")
    return out


def section_rule_check() -> dict[str, Any]:
    """Owner's pre-committed test for rule C (M4): for every section_rule fail on the pilot (all candidates,
    cache only), compare LLM and pipeline against the MeSH v1 ground truth. LLM right in >= half -> apply C."""
    s = get_settings()
    it = Items()
    ids = pilot_ids(it, s.seed)
    pos = {i: k for k, i in enumerate(it.ids)}
    rep = {r["id"]: [Sentence(**x) for x in r["sentences"]]
           for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] in set(ids)}
    llm = LLMClient(cache_only=True)
    rows = []
    for dep in s.pilot_list:
        for rid in ids:
            o, r = extract(llm, str(rid), rep[rid], deployment=dep, temperature=0.0,
                           reasoning_effort="none" if dep.startswith("gpt-5") else None)
            assert r.cached and o is not None
            v = verify(o, rep[rid])
            for m in v.verifier_messages:
                if m.check != "section_rule":
                    continue
                llm_val = v.status(m.label)
                pipe_present = llm_val != "present"  # section_rule fires when LLM and pipeline disagree on presence
                gt = bool(it.gold["v1"][m.label][pos[rid]])
                rows.append({"model": dep, "report": rid, "label": m.label, "llm": llm_val,
                             "pipeline": "present" if pipe_present else "absent", "ground_truth": gt,
                             "hedged_report": bool(it.subset["hedged"][pos[rid]]),
                             "right": "llm" if (llm_val == "present") == gt else "pipeline"})
    n = len(rows)
    llm_right = sum(r["right"] == "llm" for r in rows)
    out = {"n_disagreements": n, "llm_right": llm_right, "pipeline_right": n - llm_right,
           "decision": "apply C (section_rule -> flag)" if n and llm_right >= n / 2 else "keep section_rule as fail",
           "rule": "pre-committed by owner: LLM right in >= half of the disagreements -> apply C", "rows": rows}
    write_result("section_rule_check", out, fold="pilot:fold0-inner-val", mapping_version="v1")
    return out


if __name__ == "__main__" and sys.argv[1:] == ["section-rule"]:
    sr = section_rule_check()
    print({k: v for k, v in sr.items() if k != "rows"})
    for row in sr["rows"]:
        print(row)
elif __name__ == "__main__" and sys.argv[1:] == ["followup"]:
    f = followup()
    print(json.dumps({k: v for k, v in f.items() if k != "candidates"}, indent=1))
    for dep, c in f["candidates"].items():
        print(dep, json.dumps(c))
elif __name__ == "__main__":
    r = main()
    print(f"pilot n={r['n_reports']} (scored {r['n_scored_non_hedged']}); spend ${r['pilot_spend_usd']:.4f}")
    rb = r["rule_baseline"]["macro_f1_headline"]
    print(f"rule baseline macro-F1 {rb['value']:.3f} ({rb['lo']:.3f}-{rb['hi']:.3f})")
    for dep, c in r["candidates"].items():
        if "skipped" in c:
            print(dep, "SKIPPED", c["skipped"])
            continue
        m = c["macro_f1_headline"]
        print(f"{dep:14s} macroF1 {m['value']:.3f} ({m['lo']:.3f}-{m['hi']:.3f}) invalid {c['invalid_rate']:.2%} "
              f"verifier-fail {c['verifier_fail_rate']:.2%} $/report {c['cost_per_report_usd']:.5f} "
              f"tokens {c['mean_input_tokens']:.0f}/{c['mean_output_tokens']:.0f} model {c['models_returned']}")
