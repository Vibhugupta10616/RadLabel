"""Labelling evaluation (README §8.1) on out-of-fold predictions.

Unit: one report per exact normalised text (3,086); 95% CIs by bootstrap over duplicate clusters.
- The 102 Tier 1 pilot reports (data/splits/pilot_ids.txt) are excluded from every score here (owner, M4);
  the all-reports headline macro-F1 is reported once as a sensitivity check.
- Headline: per-label F1 / precision / recall for the 9 headline labels + macro-F1, `hedged` excluded,
  under v1 and strict (strict: v1-only positives of a label are left out of that label's scoring).
- Rare: each rare label (CI, n) + pooled rare micro-F1. `hedged` is excluded here too (same rule as headline).
- No Finding: reports coded only with ignored codes are left out of No Finding scoring.
- Subsets: abnormal, redaction_adjacent (hedged excluded), hedged (both uncertainty policies),
  negation_only false-positive rate per label and pooled, all and abnormal-only.
Scoring: `present` = positive; on `hedged`, policy "uncertain_as_present" also counts `uncertain`.

Usage: python -m eval.labelling rule_baseline
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from eval.bootstrap import bootstrap_ci, f1
from eval.cv import load_folds
from radlabel.labels import HEADLINE, LABELS, NO_FINDING, RARE
from radlabel.results import write_result

PROC = Path("data/processed")
SUBSETS = Path("data/splits/subsets")
PRED_DIR = Path("artifacts/predictions")
TABLES = Path("artifacts/tables")
N_BOOT = 1000


class Items:
    """Exact-text representatives with gold labels, subsets, cluster and fold (eval only)."""

    def __init__(self) -> None:
        reports = [json.loads(x) for x in (PROC / "reports.jsonl").open(encoding="utf-8")]
        reps = [r for r in reports if r["id"] == r["group_rep"]]
        self.ids = [r["id"] for r in reps]
        self.cluster = np.array([r["cluster"] for r in reps])
        fold, _ = load_folds()
        self.fold = np.array([fold[c] for c in self.cluster])
        exp = {e["id"]: e for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8"))}
        sub = {n: {int(x) for x in (SUBSETS / f"{n}.txt").read_text().split()}
               for n in ("abnormal", "hedged", "redaction_adjacent")}
        self.subset = {n: np.array([i in s for i in self.ids]) for n, s in sub.items()}
        # Tier 1 pilot reports (M4): used for model choice, so excluded from headline out-of-fold metrics
        pilot_file = SUBSETS.parent / "pilot_ids.txt"
        pilot = {int(x) for x in pilot_file.read_text().split()} if pilot_file.exists() else set()
        self.pilot = np.array([i in pilot for i in self.ids])
        self.ignored_only = np.array([exp[i]["ignored_only"] for i in self.ids])
        def col(key: str, lab: str) -> np.ndarray:
            return np.array([lab in exp[i][key] for i in self.ids])

        self.gold = {m: {lab: col(m, lab) for lab in LABELS} for m in ("v1", "strict")}
        self.excluded = {"v1": {lab: np.zeros(len(self.ids), bool) for lab in LABELS},
                         "strict": {lab: col("strict_excluded", lab) for lab in LABELS}}
        pos = {i: k for k, i in enumerate(self.ids)}
        self.neg_pairs = [(pos[int(a)], b) for a, b in
                          (ln.split("\t") for ln in (SUBSETS / "negation_only.tsv").read_text().splitlines())
                          if int(a) in pos]


def _scores(t: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    tp, fp, fn = int(np.sum(t & p)), int(np.sum(~t & p)), int(np.sum(t & ~p))
    return {"precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "n_pos": int(t.sum()), "n_items": int(len(t)), "tp": tp, "fp": fp, "fn": fn}


def _ci(metric: Callable[[np.ndarray], float], clusters: np.ndarray) -> dict[str, float]:
    point, lo, hi = bootstrap_ci(metric, clusters.tolist(), n=N_BOOT)
    return {"value": point, "lo": lo, "hi": hi}


def score_block(it: Items, pred: dict[str, np.ndarray], mapping: str, keep: np.ndarray,
                labels: list[str]) -> dict[str, Any]:
    """Per-label F1 (+CI), headline macro-F1 (+CI) and pooled rare micro-F1 (+CI) over items `keep`."""
    none = np.zeros(len(it.ids), bool)
    elig = {lab: keep & ~it.excluded[mapping][lab] & ~(it.ignored_only if lab == NO_FINDING else none)
            for lab in labels}
    gold = it.gold[mapping]
    out: dict[str, Any] = {"labels": {}}
    for lab in labels:
        m = elig[lab]
        t, p = gold[lab], pred[lab]
        out["labels"][lab] = {"f1": _ci(lambda i, t=t, p=p, m=m: f1(t[i][m[i]], p[i][m[i]]), it.cluster),
                              **_scores(t[m], p[m])}
    head = [lab for lab in HEADLINE if lab in labels]
    if head:
        out["macro_f1_headline"] = _ci(
            lambda i: float(np.nanmean([f1(gold[lab][i][elig[lab][i]], pred[lab][i][elig[lab][i]]) for lab in head])),
            it.cluster)
    rare = [lab for lab in RARE if lab in labels]
    if rare:
        out["rare_micro_f1"] = _ci(
            lambda i: f1(np.concatenate([gold[lab][i][elig[lab][i]] for lab in rare]),
                         np.concatenate([pred[lab][i][elig[lab][i]] for lab in rare])), it.cluster)
    return out


def evaluate(it: Items, statuses: dict[int, dict[str, str]]) -> dict[str, Any]:
    present = {lab: np.array([statuses[i].get(lab) == "present" for i in it.ids]) for lab in LABELS}
    pres_unc = {lab: np.array([statuses[i].get(lab) in ("present", "uncertain") for i in it.ids]) for lab in LABELS}
    clear = ~it.subset["hedged"] & ~it.pilot  # pilot reports excluded (owner, M4); sensitivity below
    res: dict[str, Any] = {m: score_block(it, present, m, clear, LABELS) for m in ("v1", "strict")}
    res["sensitivity_all_reports_incl_pilot"] = {
        "v1_macro_f1_headline": score_block(it, present, "v1", ~it.subset["hedged"], HEADLINE)["macro_f1_headline"]}
    res["n_pilot_excluded"] = int((it.pilot & ~it.subset["hedged"]).sum())
    res["subsets"] = {
        "abnormal": score_block(it, present, "v1", clear & it.subset["abnormal"], HEADLINE),
        "redaction_adjacent": score_block(it, present, "v1", clear & it.subset["redaction_adjacent"], HEADLINE),
        "hedged": {"uncertain_as_absent": score_block(it, present, "v1", it.subset["hedged"], HEADLINE),
                   "uncertain_as_present": score_block(it, pres_unc, "v1", it.subset["hedged"], HEADLINE)},
    }
    abn = it.subset["abnormal"]
    neg: dict[str, Any] = {}
    for scope in ("all", "abnormal"):
        pairs = [(k, lab) for k, lab in it.neg_pairs if scope == "all" or abn[k]]
        per = {lab: [present[lab][k] for k, la in pairs if la == lab] for lab in sorted({la for _, la in pairs})}
        neg[scope] = {lab: {"n_pairs": len(v), "fp": int(sum(v)), "fp_rate": sum(v) / len(v) if v else None}
                      for lab, v in per.items()}
        allv = [x for v in per.values() for x in v]
        neg[scope]["_pooled"] = {"n_pairs": len(allv), "fp": int(sum(allv)), "fp_rate": sum(allv) / len(allv)}
    res["negation_only_fp"] = neg
    res["status_counts"] = {lab: {s: sum(statuses[i].get(lab) == s for i in it.ids)
                                  for s in ("present", "absent", "uncertain", "not_mentioned")} for lab in LABELS}
    res["n_items"] = len(it.ids)
    res["n_hedged_excluded"] = int(it.subset["hedged"].sum())
    return res


def _fmt(d: dict[str, float]) -> str:
    return "–" if d["value"] != d["value"] else f"{d['value']:.3f} ({d['lo']:.3f}–{d['hi']:.3f})"


def render(name: str, res: dict[str, Any]) -> str:
    lines = [f"# Labelling: {name}", "",
             f"Out-of-fold, one report per exact text (n = {res['n_items']}; {res['n_hedged_excluded']} hedged and "
             f"{res['n_pilot_excluded']} Tier 1 pilot reports excluded); 95% bootstrap CIs over clusters.", "",
             "Sensitivity, all reports incl. pilot: v1 headline macro-F1 "
             f"{_fmt(res['sensitivity_all_reports_incl_pilot']['v1_macro_f1_headline'])}", ""]
    for m in ("v1", "strict"):
        b = res[m]
        lines += [f"## Mapping {m}", "", "| Label | F1 (95% CI) | Precision | Recall | n |", "|---|---|---|---|---|"]
        for lab in LABELS:
            x = b["labels"][lab]
            p = "–" if x["precision"] is None else f"{x['precision']:.3f}"
            r = "–" if x["recall"] is None else f"{x['recall']:.3f}"
            lines.append(f"| {lab}{' (rare)' if lab in RARE else ''} | {_fmt(x['f1'])} | {p} | {r} | {x['n_pos']} |")
        lines += ["", f"**Macro-F1, 9 headline labels:** {_fmt(b['macro_f1_headline'])}  ",
                  f"**Pooled rare micro-F1:** {_fmt(b['rare_micro_f1'])}", ""]
    s = res["subsets"]
    lines += ["## Subsets (v1, headline macro-F1)", "", "| Subset | Macro-F1 (95% CI) |", "|---|---|",
              f"| abnormal | {_fmt(s['abnormal']['macro_f1_headline'])} |",
              f"| redaction_adjacent | {_fmt(s['redaction_adjacent']['macro_f1_headline'])} |",
              f"| hedged, uncertain = absent | {_fmt(s['hedged']['uncertain_as_absent']['macro_f1_headline'])} |",
              f"| hedged, uncertain = present | {_fmt(s['hedged']['uncertain_as_present']['macro_f1_headline'])} |",
              "", "## negation_only false-positive rate", "", "| Label | All: FP / pairs (rate) | Abnormal only |",
              "|---|---|---|"]
    neg = res["negation_only_fp"]
    for lab in [la for la in LABELS if la in neg["all"]] + ["_pooled"]:
        a, b = neg["all"][lab], neg["abnormal"].get(lab, {"fp": 0, "n_pairs": 0, "fp_rate": None})

        def cell(x: dict) -> str:
            return f"{x['fp']} / {x['n_pairs']} ({x['fp_rate']:.3f})" if x["n_pairs"] else "–"
        lines.append(f"| {'pooled' if lab == '_pooled' else lab} | {cell(a)} | {cell(b)} |")
    return "\n".join(lines) + "\n"


def run_rule_baseline() -> dict[int, dict[str, str]]:
    from eval.baselines.rule_baseline import label_report
    from radlabel.preprocess.sentences import Sentence

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, dict[str, str]] = {}
    with (PRED_DIR / "rule_baseline.jsonl").open("w", encoding="utf-8") as f:
        for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")):
            if r["id"] != r["group_rep"]:
                continue
            lab = label_report(str(r["id"]), [Sentence(**s) for s in r["sentences"]])
            f.write(lab.model_dump_json() + "\n")
            out[r["id"]] = {x.label: x.status for x in lab.labels}
    return out


def run_tier1() -> tuple[dict[int, dict[str, str]], dict[int, dict[str, str]], dict[str, Any]]:
    """Tier 1 (gpt-4.1-mini, prompt tier1-v1, temperature 0) over every exact-text representative. Zero-shot,
    so every prediction is out-of-fold. Returns (LLM-only statuses, LLM+verifier statuses, run stats)."""
    from concurrent.futures import ThreadPoolExecutor

    from radlabel.config import get_settings
    from radlabel.labelling.extractor import PROMPT_VERSION, TIER1_DEPLOYMENT, extract
    from radlabel.labelling.verifier import passed, verify
    from radlabel.llm import LLMClient
    from radlabel.preprocess.sentences import Sentence

    s = get_settings()
    if s.azure_openai_deployment != TIER1_DEPLOYMENT:
        raise SystemExit(f"Tier 1 is locked to {TIER1_DEPLOYMENT}; .env has {s.azure_openai_deployment}")
    reps = [r for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] == r["group_rep"]]
    llm = LLMClient()
    spend0 = llm.spent
    # Azure counts prompt + max_tokens against TPM; ~2,400 tokens/request, ~40 requests/min per worker
    workers = max(1, min(s.llm_max_concurrency, s.tier1_tpm // (2400 * 40)))

    def one(r: dict) -> tuple[int, Any, Any, list[Sentence]]:
        sents = [Sentence(**x) for x in r["sentences"]]
        out, resp = extract(llm, str(r["id"]), sents, temperature=0.0)
        return r["id"], out, resp, sents

    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(one, reps))
    raw: dict[int, dict[str, str]] = {}
    ver: dict[int, dict[str, str]] = {}
    fails: dict[str, int] = {}
    flags: dict[str, int] = {}
    n_invalid = n_fail = n_flag = n_review = 0
    models = set()
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    with (PRED_DIR / "tier1.jsonl").open("w", encoding="utf-8") as f:
        for rid, out, resp, sents in rows:
            models.add(resp.model)
            if out is None:
                n_invalid += 1
                raw[rid] = ver[rid] = {}
                f.write(json.dumps({"report_id": str(rid), "invalid": True}) + "\n")
                continue
            v = verify(out, sents)
            raw[rid] = {x.label: x.status for x in out.labels}
            ver[rid] = {x.label: x.status for x in v.labels}
            fl = [m for m in v.verifier_messages if m.level == "fail"]
            fg = [m for m in v.verifier_messages if m.level == "flag"]
            for m in fl:
                fails[m.check] = fails.get(m.check, 0) + 1
            for m in fg:
                flags[m.check] = flags.get(m.check, 0) + 1
            n_fail += not passed(v)
            n_flag += bool(fg)
            # review escalation: section_rule disagreement (rule C) or hedging, on reports that pass
            n_review += passed(v) and any(m.check in ("section_rule", "hedge_consistency") for m in fg)
            f.write(json.dumps({"raw": json.loads(out.model_dump_json()), "verified": json.loads(v.model_dump_json())})
                    + "\n")
    n = len(rows)
    stats = {"deployment": TIER1_DEPLOYMENT, "prompt_version": PROMPT_VERSION, "models_returned": sorted(models),
             "n_reports": n, "workers": workers, "invalid_outputs": n_invalid, "invalid_rate": n_invalid / n,
             "reports_with_fail": n_fail, "report_fail_rate": n_fail / n, "reports_with_flag": n_flag,
             "report_flag_rate": n_flag / n, "tier2_reports": n_fail + n_invalid, "review_escalations": n_review,
             "fails_by_check": dict(sorted(fails.items())), "flags_by_check": dict(sorted(flags.items())),
             "spend_this_run_usd": llm.spent - spend0, "llm_spend_total_usd": llm.spent,
             "cached_responses": sum(r.cached for _, _, r, _ in rows)}
    return raw, ver, stats


def verifier_counts(path: Path) -> dict[str, int]:
    c: dict[str, int] = {}
    for line in path.open(encoding="utf-8"):
        for m in json.loads(line)["verifier_messages"]:
            k = f"{m['check']}:{m['level']}"
            c[k] = c.get(k, 0) + 1
    return dict(sorted(c.items()))


def _save(system: str, res: dict[str, Any], **extra: Any) -> None:
    write_result(f"labelling_{system}", res, fold="oof", mapping_version="v1+strict", system=system,
                 eval_version="eval_v1.2", **extra)
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / f"labelling_{system}.md").write_text(render(system, res), encoding="utf-8")


def main(system: str) -> dict[str, Any]:
    it = Items()
    if system == "rule_baseline":
        statuses = run_rule_baseline()  # no training: fold-independent, so every prediction is out-of-fold
        res = evaluate(it, statuses)
        res["verifier_messages"] = verifier_counts(PRED_DIR / "rule_baseline.jsonl")
        _save(system, res, llm="none")
        return res
    if system == "tier1":
        raw, ver, stats = run_tier1()
        llm_only = {**evaluate(it, raw), "run": stats}
        llm_ver = {**evaluate(it, ver), "run": stats}
        _save("llm_only", llm_only, llm=stats["deployment"], prompt=stats["prompt_version"])
        _save("llm_verifier", llm_ver, llm=stats["deployment"], prompt=stats["prompt_version"])
        return {"llm_only": llm_only, "llm_verifier": llm_ver, "run": stats}
    raise SystemExit(f"unknown system {system!r}")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "rule_baseline"
    r = main(name)
    if name == "tier1":
        print(json.dumps(r["run"], indent=1))
    else:
        print((TABLES / f"labelling_{name}.md").read_text(encoding="utf-8"))
