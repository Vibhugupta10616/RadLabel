"""M6: evaluation through the single entry point (README §8.1), parser accuracy, section subsets, the normal-claim
count and the hedge-fix before/after.

Pre-committed here, before the run:
- Clean join: every exact-text representative (3,086) is joined from its IU sections (indication, comparison,
  findings, impression; empty ones left out) as "HEADER: text" lines, expert codes hidden, and run through
  `run_pipeline` like an upload.
- Varied joins: VARIED_FRACTION of the reports (seed SEED) get one variant, chosen uniformly: alternative header
  names (ALT_HEADERS, random case/punctuation FORMATS), no headers (sections as plain lines), or one non-empty
  section dropped. Column "varied" = clean labels with those reports replaced by their varied run.
- Parser accuracy per join: share of the included sections' gold sentences (section, text) found in the parsed
  output, and share of reports fully parsed (every included section's text recovered exactly, nothing else).
- New calls: a cache-only pass first; misses are priced at the mean Tier 1 call cost in the ledger and the run
  stops if that estimate exceeds NEW_SPEND_CAP.
- Normal-claim count (data fact, all unique texts): Impression made only of general "no acute"-type statements
  (NORMAL_SENTENCE) while the expert codes are not normal-only; per label.
- Hedge fix (M6): v1 results before (HEDGE_FIX_BEFORE, read from git) and after.

Usage: python -m eval.entry_point [--cache-only]
"""

from __future__ import annotations

import json
import logging
import random
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from eval.labelling import (
    PRED_DIR,
    PROC,
    TABLES,
    Items,
    _fmt,
    _present,
    _save,
    evaluate,
    paired_diff,
    score_block,
    write_summary,
)
from radlabel.config import get_settings
from radlabel.labelling.extractor import PROMPT_VERSION, TIER1_DEPLOYMENT
from radlabel.labels import HEADLINE, LABELS, NO_FINDING
from radlabel.llm import CacheMiss, LLMClient
from radlabel.pipeline import PipelineResult, run_pipeline
from radlabel.preprocess.parser import SECTIONS
from radlabel.preprocess.sentences import Sentence, report_sentences
from radlabel.results import RESULTS_DIR, write_result

log = logging.getLogger(__name__)
VARIED_FRACTION = 0.3
NEW_SPEND_CAP = 1.0  # USD; above this, stop and ask the owner
WORKERS = 8
VARIANTS = ("alt_headers", "no_headers", "drop_section")
CLEAN_HEADERS = {"indication": "INDICATION", "comparison": "COMPARISON", "findings": "FINDINGS",
                 "impression": "IMPRESSION"}
ALT_HEADERS = {"indication": ["Clinical history", "History", "Reason for exam"],
               "comparison": ["Comparisons", "Prior studies"], "findings": ["Finding", "Findings"],
               "impression": ["Conclusion", "Opinion", "Summary"]}
# Held-out header names (owner decision 5, written 2026-10-22 before any run): NOT in the parser's list and never
# added to it afterwards. Run once on the varied reports; parser accuracy reported separately.
HELDOUT_HEADERS = {"indication": ["Clinical details", "Hx", "Indications for exam"],
                   "comparison": ["Prior exam", "Compared with"],
                   "findings": ["Report", "Observations", "Description"],
                   "impression": ["Interpretation", "Assessment"]}
FORMATS = ("{h}: {t}","{H}\n{t}", "{low} - {t}")
NORMAL_SENTENCE = re.compile(
    r"^(\d+\.\s*)?(?:(?:no|negative for)\s+(?:\S+\s+){0,3}?(?:acute|active)\b"
    r"|(?:normal|negative|unremarkable)\s+(?:chest|exam|examination|study|radiograph)\b|negative\.?$)")
HEDGE_FIX_BEFORE = "c328247"  # last commit before the M6 hedge fix
SUBSETS = {"empty_findings": lambda r: not r.parse.findings, "empty_impression": lambda r: not r.parse.impression,
           "sections_not_identified": lambda r: not r.parse.sections_identified}


def join(sec: dict[str, str], variant: str, rng: random.Random) -> tuple[str, dict[str, str]]:
    """Joined text and the sections it includes."""
    inc = {s: sec[s] for s in SECTIONS if sec[s]}
    if variant == "drop_section":
        del inc[rng.choice(list(inc))]
    if variant == "no_headers":
        return "\n".join(inc.values()), inc
    if variant in ("alt_headers", "heldout_headers"):
        names = ALT_HEADERS if variant == "alt_headers" else HELDOUT_HEADERS
        lines = []
        for s, t in inc.items():
            h = rng.choice(names[s])
            lines.append(rng.choice(FORMATS).format(h=h, H=h.upper(), low=h.lower(), t=t))
        return "\n".join(lines), inc
    return "\n".join(f"{CLEAN_HEADERS[s]}: {t}" for s, t in inc.items()), inc


def parse_scores(r: PipelineResult, inc: dict[str, str]) -> tuple[int, int, bool]:
    gold = Counter((s.section, s.text) for s in report_sentences(inc.get("findings", ""), inc.get("impression", "")))
    got = Counter((s.section, s.text) for s in r.sentences)
    full = all(getattr(r.parse, s) == inc.get(s, "") for s in SECTIONS)
    return sum((gold & got).values()), sum(gold.values()), full


def run_jobs(jobs: dict[tuple[int, str], str], llm: LLMClient) -> dict[tuple[int, str], PipelineResult]:
    def one(key: tuple[int, str]) -> PipelineResult | None:
        try:
            return run_pipeline(jobs[key], llm, str(key[0]), agent=False)  # M6: no agent
        except CacheMiss:
            return None
        except Exception as e:  # network trouble after the client's retries: retried in the next pass
            log.warning("report %s (%s) not labelled yet: %s", key[0], key[1], e)
            return None

    done: dict[tuple[int, str], PipelineResult] = {}
    todo = list(jobs)
    for attempt in range(1 if llm.cache_only else 3):
        with ThreadPoolExecutor(WORKERS if attempt == 0 else 1) as ex:
            got = list(ex.map(one, todo))
        done.update({k: r for k, r in zip(todo, got, strict=True) if r is not None})
        todo = [k for k in todo if k not in done]
    return done


def mean_tier1_call_usd(llm: LLMClient) -> float:
    rows = [json.loads(x) for x in (llm.cache_dir / "ledger.jsonl").open(encoding="utf-8")]
    t1 = [x["cost_usd"] for x in rows if x["deployment"] == TIER1_DEPLOYMENT and x["purpose"].startswith("tier1:")]
    return float(np.mean(t1))


def statuses(r: PipelineResult) -> dict[str, str]:
    return {x.label: x.status for x in r.labels.labels}


def normal_claim(it: Items, clean: dict[int, dict[str, str]]) -> dict[str, Any]:
    reps = {r["id"]: r for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8"))
            if r["id"] == r["group_rep"]}
    raw = {int(d["raw"]["report_id"]): {x["label"]: x["status"] for x in d["raw"]["labels"]}
           for d in map(json.loads, (PRED_DIR / "tier1.jsonl").open(encoding="utf-8")) if "raw" in d}

    def normal_imp(r: dict[str, Any]) -> bool:
        imp = [s["text"].lower() for s in r["sentences"] if s["section"] == "impression"]
        return bool(imp) and all(NORMAL_SENTENCE.match(t) for t in imp)

    pos = {i: k for k, i in enumerate(it.ids)}
    ni = [i for i in it.ids if normal_imp(reps[i])]
    gold = it.gold["v1"]
    normal = [i for i in ni if gold[NO_FINDING][pos[i]]]
    ignored = [i for i in ni if it.ignored_only[pos[i]]]
    other = [i for i in ni if not gold[NO_FINDING][pos[i]] and not it.ignored_only[pos[i]]]

    def nf(ids: list[int], st: dict[int, dict[str, str]]) -> int:
        return sum(st.get(i, {}).get(NO_FINDING) == "present" for i in ids)
    return {
        "definition": "every Impression sentence matches NORMAL_SENTENCE (eval/entry_point.py); all unique texts",
        "normal_impression_reports": len(ni), "codes_normal_only": len(normal), "codes_ignored_only": len(ignored),
        "codes_not_normal_only": len(other), "rate_not_normal_only": len(other) / len(ni) if ni else None,
        "per_label_positive_in_not_normal_only": {lab: int(sum(gold[lab][pos[i]] for i in other))
                                                  for lab in LABELS if lab != NO_FINDING},
        "no_finding_predicted": {
            "llm_only": {"in_not_normal_only": nf(other, raw), "in_normal_only": nf(normal, raw)},
            "pipeline_clean": {"in_not_normal_only": nf(other, clean), "in_normal_only": nf(normal, clean)}},
    }


def _git_result(ref: str, name: str) -> dict[str, Any]:
    out = subprocess.run(["git", "show", f"{ref}:artifacts/results/{name}.json"], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return json.loads(out)["results"]


def hedge_fix(ref: str) -> dict[str, Any]:
    """v1 results before (git `ref`) and after the M6 hedge fix (current files); hedge conversions from run stats."""
    def summary(r: dict[str, Any]) -> dict[str, Any]:
        c = r["v1"]["labels"]["Cardiomegaly"]
        return {"macro_f1_v1": r["v1"]["macro_f1_headline"], "macro_f1_strict": r["strict"]["macro_f1_headline"],
                "rare_micro_f1_v1": r["v1"]["rare_micro_f1"], "cardiomegaly_f1": c["f1"],
                "cardiomegaly_precision": c["precision"], "cardiomegaly_recall": c["recall"],
                "cardiomegaly_status_counts": r["status_counts"]["Cardiomegaly"],
                "hedge_conversions": r["run"]["flags_by_check"].get("hedge_consistency", 0)}
    out: dict[str, Any] = {"before_ref": ref}
    for name in ("llm_verifier", "llm_verifier_tier2"):
        before, after = _git_result(ref, f"labelling_{name}"), json.loads(
            (RESULTS_DIR / f"labelling_{name}.json").read_text(encoding="utf-8"))["results"]
        out[name] = {"before": summary(before), "after": summary(after)}
        if "routing" in after:
            for k, r in (("before", before), ("after", after)):
                d = r["routing"]["tier_distribution"]
                out[name][k]["review_rate"] = d.get("review", 0) / sum(d.values())
    for f, k in (("labelling_paired_diffs", "llm_verifier_minus_llm_only"),
                 ("labelling_tier2_paired_diffs", "tier2_minus_llm_only")):
        out[k] = {"before": _git_result(ref, f)[k],
                  "after": json.loads((RESULTS_DIR / f"{f}.json").read_text(encoding="utf-8"))["results"][k]}
    return out


def main(cache_only: bool = False) -> dict[str, Any]:
    it = Items()
    iu = {r["id"]: r for r in map(json.loads, (PROC / "iu.jsonl").open(encoding="utf-8"))}
    s = get_settings()
    rng = random.Random(s.seed)
    ids = sorted(it.ids)
    varied_ids = set(rng.sample(ids, round(VARIED_FRACTION * len(ids))))
    jobs: dict[tuple[int, str], str] = {}
    included: dict[tuple[int, str], dict[str, str]] = {}
    for i in ids:
        sec = {k: iu[i][k] for k in SECTIONS}
        for v in ["clean"] + ([rng.choice(VARIANTS)] if i in varied_ids else []):
            jobs[(i, v)], included[(i, v)] = join(sec, v, rng)
    held_rng = random.Random(f"{s.seed}-heldout-headers")  # own stream: the varied joins above stay unchanged
    for i in ids:
        if i in varied_ids:
            k = (i, "heldout_headers")
            jobs[k], included[k] = join({x: iu[i][x] for x in SECTIONS}, "heldout_headers", held_rng)

    llm = LLMClient(cache_only=True)
    spend0 = llm.spent
    res = run_jobs(jobs, llm)
    misses = [k for k in jobs if k not in res]
    estimate = len(misses) * mean_tier1_call_usd(llm)
    cache = {"jobs": len(jobs), "cache_misses_this_run": len(misses),
             "misses_by_join_this_run": dict(Counter(v for _, v in misses)),
             "estimated_new_spend_usd": estimate, "new_spend_cap_usd": NEW_SPEND_CAP}
    if misses and (cache_only or estimate > NEW_SPEND_CAP):
        raise SystemExit(json.dumps({**cache, "stopped": "cache-only" if cache_only else "estimate over cap"}))
    if misses:
        live = LLMClient()
        res.update(run_jobs({k: jobs[k] for k in misses}, live))
        if len(res) < len(jobs):
            raise SystemExit(f"{len(jobs) - len(res)} reports still unlabelled; rerun (finished calls are cached)")
    total = LLMClient(cache_only=True).spent
    cache["new_spend_this_run_usd"], cache["llm_spend_total_usd"] = total - spend0, total
    # tagger inputs that differ from M4's (not served by the M4 cache); stable across reruns, unlike cache misses
    m4 = {r["id"]: [Sentence(**x) for x in r["sentences"]]
          for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] == r["group_rep"]}
    new = [k for k in jobs if res[k].sentences != m4[k[0]]]
    cache.update({"new_tagger_inputs": len(new), "new_tagger_inputs_by_join": dict(Counter(v for _, v in new)),
                  "new_tagger_inputs_cost_usd": sum(res[k].tagger_cost_usd for k in new)})

    clean = {i: statuses(res[(i, "clean")]) for i in ids}
    variant = {i: v for i, v in jobs if v in VARIANTS}
    heldout = {i: statuses(res[(i, v)]) for i, v in jobs if v == "heldout_headers"}
    varied = {**clean, **{i: statuses(res[(i, v)]) for i, v in variant.items()}}

    # parser accuracy per join type, and the cache check: correctly parsed clean joins must have been cache hits
    parser: dict[str, Any] = {}
    full_clean: set[int] = set()
    for j in ("clean", *VARIANTS, "heldout_headers"):
        keys = [k for k in jobs if k[1] == j]
        sc = [parse_scores(res[k], included[k]) for k in keys]
        parser[j] = {"n": len(keys), "sentence_accuracy": sum(a for a, _, _ in sc) / max(1, sum(b for _, b, _ in sc)),
                     "fully_parsed": sum(f for _, _, f in sc), "fully_parsed_rate": float(np.mean([f for *_, f in sc])),
                     "sections_not_identified": sum(not res[k].parse.sections_identified for k in keys)}
        if j == "clean":
            full_clean = {k[0] for k, x in zip(keys, sc, strict=True) if x[2]}
    cache["clean_fully_parsed_new_inputs"] = sum(k[1] == "clean" and k[0] in full_clean for k in new)
    cache["clean_not_fully_parsed"] = sorted(set(ids) - full_clean)
    parser["drop_section_dropped"] = dict(Counter(
        next(s for s in SECTIONS if iu[i][s] and s not in included[(i, v)]) for i, v in variant.items()
        if v == "drop_section"))

    # clean join vs the LLM + verifier column (same tagger input when parsed correctly)
    ref: dict[int, dict[str, str]] = {}
    rule = {int(x["report_id"]): {y["label"]: y["status"] for y in x["labels"]}
            for x in map(json.loads, (PRED_DIR / "rule_baseline.jsonl").open(encoding="utf-8"))}
    for d in map(json.loads, (PRED_DIR / "tier1.jsonl").open(encoding="utf-8")):
        if "verified" in d:
            ref[int(d["verified"]["report_id"])] = {x["label"]: x["status"] for x in d["verified"]["labels"]}
        elif d.get("content_filtered"):
            ref[int(d["report_id"])] = rule[int(d["report_id"])]
    differ = sorted(i for i in ids if clean[i] != ref[i])

    pos = {i: k for k, i in enumerate(it.ids)}
    keep = ~it.subset["hedged"] & ~it.pilot
    by_variant: dict[str, Any] = {}
    for v in VARIANTS:
        m = np.zeros(len(it.ids), bool)
        m[[pos[i] for i, x in variant.items() if x == v]] = True
        by_variant[v] = {"n": int(m.sum()), "n_scored": int((m & keep).sum()),
                         "macro_f1_clean": score_block(it, _present(it, clean), "v1", m & keep, HEADLINE)
                         ["macro_f1_headline"],
                         "macro_f1_varied": score_block(it, _present(it, varied), "v1", m & keep, HEADLINE)
                         ["macro_f1_headline"]}
    m = np.isin(np.array(it.ids), list(heldout))
    by_variant["heldout_headers"] = {
        "n": int(m.sum()), "n_scored": int((m & keep).sum()),
        "macro_f1_clean": score_block(it, _present(it, clean), "v1", m & keep, HEADLINE)["macro_f1_headline"],
        "macro_f1_varied": score_block(it, _present(it, {**clean, **heldout}), "v1", m & keep, HEADLINE)
        ["macro_f1_headline"]}
    subsets: dict[str, Any] = {}
    for run, st in (("clean", clean), ("varied", varied)):
        subsets[run] = {}
        for name, f in SUBSETS.items():
            m = np.array([f(res[(i, variant[i] if run == "varied" and i in variant else "clean")]) for i in it.ids])
            subsets[run][name] = {"n": int(m.sum()), "n_scored": int((m & keep).sum()),
                                  "macro_f1": score_block(it, _present(it, st), "v1", m & keep, HEADLINE)
                                  ["macro_f1_headline"] if (m & keep).any() else None}

    extra = {"llm": TIER1_DEPLOYMENT, "prompt": PROMPT_VERSION, "entry_point": "radlabel.pipeline.run_pipeline"}
    clean_res, varied_res = evaluate(it, clean), evaluate(it, varied)
    _save("pipeline_clean", clean_res, **extra)
    _save("pipeline_varied", varied_res, **extra, varied_fraction=VARIED_FRACTION)
    paired = {"pipeline_clean_minus_llm_verifier": paired_diff(it, clean, ref),
              "pipeline_varied_minus_pipeline_clean": paired_diff(it, varied, clean)}
    write_result("labelling_m6_paired_diffs", paired, fold="oof", mapping_version="v1", eval_version="eval_v1.2",
                 metric="headline macro-F1 (9 labels), hedged + pilot excluded")
    m6 = {"run": {"seed": s.seed, "varied_fraction": VARIED_FRACTION, "n_reports": len(ids),
                  "n_varied": len(variant), "variants": dict(Counter(variant.values()))},
          "cache": cache, "parser": parser, "by_variant": by_variant, "subsets": subsets,
          "clean_vs_llm_verifier": {"reports_with_different_labels": len(differ), "ids": differ},
          "normal_claim": normal_claim(it, clean), "hedge_fix": hedge_fix(HEDGE_FIX_BEFORE)}
    write_result("pipeline_m6", m6, fold="oof", mapping_version="v1", eval_version="eval_v1.2", **extra)
    (TABLES / "pipeline_m6.md").write_text(render(m6, paired), encoding="utf-8")
    write_summary()
    return m6


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def render(m6: dict[str, Any], paired: dict[str, Any], standalone: bool = True) -> str:
    """M6 tables; also used for README §10 (eval/report.py)."""
    p, c, nc, hf = m6["parser"], m6["cache"], m6["normal_claim"], m6["hedge_fix"]
    lines = ["# Through the entry point (M6)", ""] if standalone else []
    lines += [f"{m6['run']['n_reports']:,} unique reports joined into text with headers (codes hidden) and run through "
              f"`run_pipeline`; {m6['run']['n_varied']} of them ({_pct(m6['run']['varied_fraction'])}, seed "
              f"{m6['run']['seed']}) also with a varied join. Clean joins whose labels differ from the LLM + verifier "
              f"column: {m6['clean_vs_llm_verifier']['reports_with_different_labels']}. Tagger inputs that differ "
              f"from M4's, so not served by the M4 cache: {c['new_tagger_inputs']} "
              f"({', '.join(f'{k.replace(chr(95), chr(32))} {n}' for k, n in c['new_tagger_inputs_by_join'].items())};"
              f" correctly parsed clean joins: {c['clean_fully_parsed_new_inputs']}), whose calls cost "
              f"${c['new_tagger_inputs_cost_usd']:.2f}. All LLM calls so far (cost ledger): "
              f"${c['llm_spend_total_usd']:.2f}.", "",
              "| Join | Reports | Sentences in the right section | Fully parsed | No sections found |",
              "|---|---|---|---|---|"]
    lines += [f"| {j.replace('_', ' ')} | {p[j]['n']} | {_pct(p[j]['sentence_accuracy'])} | "
              f"{p[j]['fully_parsed']} ({_pct(p[j]['fully_parsed_rate'])}) | {p[j]['sections_not_identified']} |"
              for j in ("clean", *VARIANTS, "heldout_headers") if j in p]
    lines += ["", "Dropped sections: " + ", ".join(f"{k} {n}" for k, n in p["drop_section_dropped"].items()) + ".", "",
              "Headline macro-F1 (v1) on the varied reports: the same reports with the clean vs the varied join:",
              "",
              "| Variant | Scored reports | Clean join | Varied join |", "|---|---|---|---|"]
    lines += [f"| {v.replace('_', ' ')} | {d['n_scored']} | {_fmt(d['macro_f1_clean'])} | "
              f"{_fmt(d['macro_f1_varied'])} |" for v, d in m6["by_variant"].items()]
    if standalone:
        lines += ["", "Paired: " + "; ".join(f"{k.replace('_minus_', ' − ').replace('_', ' ')} {_fmt(d)}"
                                            for k, d in paired.items())]
    lines += ["", "Section subsets (as parsed; headline macro-F1, v1, hedged + pilot excluded):", "",
              "| Subset | Clean: reports (scored) | Clean macro-F1 | Varied: reports (scored) | Varied macro-F1 |",
              "|---|---|---|---|---|"]
    for name in SUBSETS:
        a, b = m6["subsets"]["clean"][name], m6["subsets"]["varied"][name]
        lines.append(f"| {name.replace('_', ' ')} | {a['n']} ({a['n_scored']}) | "
                     f"{_fmt(a['macro_f1']) if a['macro_f1'] else '–'} | {b['n']} ({b['n_scored']}) | "
                     f"{_fmt(b['macro_f1']) if b['macro_f1'] else '–'} |")
    per = ", ".join(f"{lab} {n}" for lab, n in nc["per_label_positive_in_not_normal_only"].items() if n)
    nfp = nc["no_finding_predicted"]
    lines += ["", f"**Normal-claim count.** {nc['normal_impression_reports']} unique reports have an Impression made "
              f"only of \"no acute\"-type statements; the expert codes are normal-only for {nc['codes_normal_only']}, "
              f"ignored-only for {nc['codes_ignored_only']}, and **not normal for {nc['codes_not_normal_only']} "
              f"({_pct(nc['rate_not_normal_only'])})**. Positive labels among those: {per}. The tagger predicted No "
              f"Finding for {nfp['llm_only']['in_not_normal_only']} of the {nc['codes_not_normal_only']} (LLM only; "
              f"after the verifier {nfp['pipeline_clean']['in_not_normal_only']}) and for "
              f"{nfp['llm_only']['in_normal_only']} of the {nc['codes_normal_only']} normal-only ones.", ""]
    v, t = hf["llm_verifier"], hf["llm_verifier_tier2"]
    lines += ["**Hedge-check fix** (\"borderline\"/\"mild\" are not a hedge where the label definition counts them as "
              "present), v1 results from cache, before → after:", "",
              "| Metric | Before | After |", "|---|---|---|",
              f"| Hedge conversions (present → uncertain) | {v['before']['hedge_conversions']} | "
              f"{v['after']['hedge_conversions']} |",
              f"| LLM + verifier: headline macro-F1 (v1) | {_fmt(v['before']['macro_f1_v1'])} | "
              f"{_fmt(v['after']['macro_f1_v1'])} |",
              f"| LLM + verifier: Cardiomegaly F1 | {_fmt(v['before']['cardiomegaly_f1'])} | "
              f"{_fmt(v['after']['cardiomegaly_f1'])} |",
              f"| LLM + verifier − LLM only | {_fmt(hf['llm_verifier_minus_llm_only']['before'])} | "
              f"{_fmt(hf['llm_verifier_minus_llm_only']['after'])} |",
              f"| LLM + verifier + Tier 2: headline macro-F1 (v1) | {_fmt(t['before']['macro_f1_v1'])} | "
              f"{_fmt(t['after']['macro_f1_v1'])} |",
              f"| LLM + verifier + Tier 2 − LLM only | {_fmt(hf['tier2_minus_llm_only']['before'])} | "
              f"{_fmt(hf['tier2_minus_llm_only']['after'])} |",
              f"| v1 review rate | {_pct(t['before']['review_rate'])} | {_pct(t['after']['review_rate'])} |"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = main(cache_only="--cache-only" in sys.argv)
    print(json.dumps(out["cache"], indent=1))  # tables: artifacts/tables/pipeline_m6.md
