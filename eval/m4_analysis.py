"""M4 error analysis (owner request), from stored predictions only: no LLM client, $0.

- why LLM+verifier < LLM only (the verifier's status changes vs ground truth)
- Atelectasis: LLM vs rule baseline FP/FN, LLM status on ground-truth positives, hedged phrasing
- verifier fails: evidence_mentions_label by label, negation_consistency vs ground truth

Counts -> artifacts/results/m4_analysis.json (committed). Example sentences hold report text, so they go to
artifacts/analysis/ (git-ignored, licence) and are never committed.

Usage: python -m eval.m4_analysis
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from eval.labelling import PRED_DIR, PROC, Items
from radlabel.labels import LABELS
from radlabel.preprocess.negation import mentions
from radlabel.results import write_result

OUT_TEXT = Path("artifacts/analysis")
ATEL = "Atelectasis"
# hedged / non-committal phrasings the owner asked about; "or scarring" etc. are not in subset_stats' HEDGE
PHRASES = {
    "likely/probable/possible": re.compile(r"\b(likely|probabl[ey]|possibl[ey]|may|might|could|suspect)\w*", re.I),
    "or/versus scarring": re.compile(r"\b(or|versus|vs\.?|and/or)\s+(\w+\s+){0,2}(scar|fibros)", re.I),
    "scarring/atelectasis pair": re.compile(r"(scar\w*|fibros\w*)\s+(or|versus|vs\.?|and/or)\s+atelecta", re.I),
    "subsegmental": re.compile(r"\bsubsegmental\b", re.I),
    "minimal/mild/small": re.compile(r"\b(minimal|mild|small|minor|trace)\b", re.I),
    "linear/discoid/plate": re.compile(r"\b(linear|discoid|plate|bandlike|band-like|streaky)\b", re.I),
}


def _load() -> tuple[Items, dict[int, dict], dict[int, dict], dict[int, dict], dict[int, dict[str, str]]]:
    it = Items()
    rows = {int(r["raw"]["report_id"]): r for r in map(json.loads, (PRED_DIR / "tier1.jsonl").open(encoding="utf-8"))
            if "raw" in r}
    raw = {i: {x["label"]: x for x in r["raw"]["labels"]} for i, r in rows.items()}
    ver = {i: r["verified"] for i, r in rows.items()}
    rule = {int(x["report_id"]): {y["label"]: y["status"] for y in x["labels"]}
            for x in map(json.loads, (PRED_DIR / "rule_baseline.jsonl").open(encoding="utf-8"))}
    sents = {r["id"]: {s["id"]: s["text"] for s in r["sentences"]}
             for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] == r["group_rep"]}
    return it, raw, ver, sents, rule


def _label_sentences(sents: dict[str, str], lab: str) -> list[str]:
    return [t for t in sents.values() if any(m.label == lab for m in mentions(t))]


def verifier_effect(it: Items, raw: dict, ver: dict) -> dict[str, Any]:
    """Status changes made by the verifier on scored reports (hedge_consistency: present -> uncertain)."""
    scored = {i for k, i in enumerate(it.ids) if not it.subset["hedged"][k] and not it.pilot[k]}
    pos = {i: k for k, i in enumerate(it.ids)}
    by: dict[str, Counter] = {}
    for i in scored & set(ver):
        for x in ver[i]["labels"]:
            a, b = raw[i][x["label"]]["status"], x["status"]
            if a != b and x["label"] != "No Finding":
                gt = bool(it.gold["v1"][x["label"]][pos[i]])
                by.setdefault(x["label"], Counter())[f"{a}->{b}:{'gt_pos' if gt else 'gt_neg'}"] += 1
    total = Counter()
    for c in by.values():
        total.update(c)
    return {"scored_reports": len(scored), "by_label": {k: dict(v) for k, v in sorted(by.items())},
            "total": dict(total)}


def atelectasis(it: Items, raw: dict, sents: dict, rule: dict) -> tuple[dict[str, Any], dict[str, list[str]]]:
    gold = it.gold["v1"][ATEL]
    res: dict[str, Any] = {}
    ex: dict[str, list[str]] = {}
    for scope in ("scored", "hedged"):
        idx = [k for k, i in enumerate(it.ids) if not it.pilot[k] and i in raw
               and bool(it.subset["hedged"][k]) == (scope == "hedged")]
        llm = {it.ids[k]: raw[it.ids[k]][ATEL]["status"] for k in idx}
        rb = {it.ids[k]: rule[it.ids[k]].get(ATEL, "not_mentioned") for k in idx}
        gt = {it.ids[k]: bool(gold[k]) for k in idx}
        d: dict[str, Any] = {"n_reports": len(idx), "gt_positive": sum(gt.values())}
        for name, p in (("llm", llm), ("rule_baseline", rb)):
            d[name] = {"tp": sum(gt[i] and p[i] == "present" for i in idx_ids(idx, it)),
                       "fp": sum(not gt[i] and p[i] == "present" for i in idx_ids(idx, it)),
                       "fn": sum(gt[i] and p[i] != "present" for i in idx_ids(idx, it))}
        d["llm_status_on_gt_positive"] = dict(Counter(llm[i] for i in gt if gt[i]))
        d["rule_status_on_gt_positive"] = dict(Counter(rb[i] for i in gt if gt[i]))
        # who is right where they disagree
        d["llm_fn_rule_tp"] = sum(gt[i] and llm[i] != "present" and rb[i] == "present" for i in gt)
        d["llm_fp_rule_tn"] = sum(not gt[i] and llm[i] == "present" and rb[i] != "present" for i in gt)
        # hedged phrasing on GT-positive reports, by LLM status (phrases in the sentences that mention Atelectasis)
        ph: dict[str, Counter] = {}
        for i in gt:
            if not gt[i]:
                continue
            text = " ".join(_label_sentences(sents[i], ATEL))
            for name, rx in PHRASES.items():
                if rx.search(text):
                    ph.setdefault(name, Counter())[llm[i]] += 1
        d["phrases_on_gt_positive_by_llm_status"] = {k: dict(v) for k, v in ph.items()}
        res[scope] = d
        if scope == "scored":
            rng = random.Random(13)
            groups = {
                "llm_fn_uncertain": [i for i in gt if gt[i] and llm[i] == "uncertain"],
                "llm_fn_absent_or_not_mentioned": [i for i in gt if gt[i] and llm[i] in ("absent", "not_mentioned")],
                "llm_fp": [i for i in gt if not gt[i] and llm[i] == "present"],
                "rule_fn": [i for i in gt if gt[i] and rb[i] != "present"],
                "rule_fp": [i for i in gt if not gt[i] and rb[i] == "present"],
            }
            d["error_report_ids"] = {k: sorted(v) for k, v in groups.items()}
            for k, v in groups.items():
                ex[k] = [f"[{i}] LLM={llm[i]} rule={rb[i]} :: " + " | ".join(_label_sentences(sents[i], ATEL)
                                                                             or list(sents[i].values())[:3])
                         for i in rng.sample(sorted(v), min(10, len(v)))]
    return res, ex


def idx_ids(idx: list[int], it: Items) -> list[int]:
    return [it.ids[k] for k in idx]


def verifier_fails(it: Items, raw: dict, ver: dict, sents: dict) -> tuple[dict[str, Any], dict[str, list[str]]]:
    pos = {i: k for k, i in enumerate(it.ids)}
    eml: Counter = Counter()
    eml_status: Counter = Counter()
    eml_gt: dict[str, Counter] = {}
    eml_ex: list[str] = []
    neg_rows: list[dict[str, Any]] = []
    neg_ex: list[str] = []
    for i in sorted(ver):
        for m in ver[i]["verifier_messages"]:
            if m["level"] != "fail" and m["check"] != "negation_consistency":  # a flag since M4, still analysed
                continue
            x = raw[i][m["label"]]
            cited = [sents[i].get(e, "?") for e in x["evidence"]]
            k = pos[i]
            gt = bool(it.gold["v1"][m["label"]][k])
            if m["check"] == "evidence_mentions_label":
                eml[m["label"]] += 1
                eml_status[x["status"]] += 1
                eml_gt.setdefault(m["label"], Counter())[f"{x['status']}:{'gt_pos' if gt else 'gt_neg'}"] += 1
                eml_ex.append(f"[{i}] {m['label']}={x['status']} gt={'pos' if gt else 'neg'} :: " + " | ".join(cited))
            elif m["check"] == "negation_consistency":
                # LLM said present, pipeline says every cited mention is negated
                neg_rows.append({"report_id": i, "label": m["label"], "gt_v1": gt,
                                 "right": "llm" if gt else "pipeline", "hedged_report": bool(it.subset["hedged"][k]),
                                 "pilot": bool(it.pilot[k])})
                neg_ex.append(f"[{i}] {m['label']} LLM=present gt={'pos' if gt else 'neg'} :: " + " | ".join(cited))
    rng = random.Random(13)
    right = Counter(r["right"] for r in neg_rows)
    res = {"evidence_mentions_label": {"fails": sum(eml.values()), "by_label": dict(eml.most_common()),
                                       "by_llm_status": dict(eml_status),
                                       "by_label_status_gt": {k: dict(v) for k, v in eml_gt.items()}},
           "negation_consistency": {"fails": len(neg_rows), "right": dict(right), "rows": neg_rows,
                                    "pipeline_wrong_in_majority": right["llm"] > len(neg_rows) / 2}}
    return res, {"evidence_mentions_label": rng.sample(eml_ex, min(10, len(eml_ex))), "negation_consistency": neg_ex}


def main() -> dict[str, Any]:
    it, raw, ver, sents, rule = _load()
    atel, atel_ex = atelectasis(it, raw, sents, rule)
    vf, vf_ex = verifier_fails(it, raw, ver, sents)
    out = {"verifier_effect": verifier_effect(it, raw, ver), "atelectasis": atel, "verifier_fails": vf,
           "labels": LABELS, "llm_calls": 0}
    write_result("m4_analysis", out, fold="oof", mapping_version="v1", eval_version="eval_v1.2")
    OUT_TEXT.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in {**{f"atelectasis/{a}": b for a, b in atel_ex.items()},
                 **{f"verifier/{a}": b for a, b in vf_ex.items()}}.items():
        lines += [f"## {k}", *v, ""]
    (OUT_TEXT / "m4_examples.md").write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
