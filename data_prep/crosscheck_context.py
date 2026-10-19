"""Mapping cross-check with context (owner request, replaces the plain re-ask): for every pattern that
still disagrees in `mapping_crosscheck.json`, ask the REPAIR deployment (gpt-5-mini) again with the full
code strings, 2-3 real example sentences ([REDACTED] applied, sentence only), the label definitions and
the CheXpert labeler mention phrases. Read-only: never changes the mapping.

Usage: python -m data_prep.crosscheck_context
Writes artifacts/mapping/crosscheck_context.json (holds sentences: git-ignored, licence D1) and
artifacts/results/mapping_crosscheck_context.json (codes, counts, labels only; committed).
Stops before any call that could push this run over RUN_CAP_USD.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from data_prep.crosscheck_mapping import DEFINITIONS, IGNORE
from data_prep.mapping import parse_parts
from radlabel.labels import LABELS
from radlabel.llm import PRICES, LLMClient, spent_usd
from radlabel.llm.client import deployment_for
from radlabel.results import write_result

PROC = Path("data/processed")
RUN_CAP_USD = 0.50
MAX_TOKENS = 4000
N_EXAMPLES = 3
CHEXPERT = json.loads((Path(__file__).parent / "reference" / "chexpert_mentions.json").read_text(encoding="utf-8"))
CHEXPERT_FOR = {  # RadLabel label -> CheXpert mention files
    "Cardiomegaly": ["cardiomegaly"], "Lung Opacity": ["lung_opacity"], "Lung Lesion": ["lung_lesion"],
    "Atelectasis": ["atelectasis"], "Pleural Effusion": ["pleural_effusion"], "Fracture": ["fracture"],
    "Support Devices": ["support_devices"], "Edema": ["edema"], "Pleural Other": ["pleural_other"],
    "Consolidation": ["consolidation"], "Pneumothorax": ["pneumothorax"],
    # CheXpert's no_finding list = other abnormal terms; dropped labels fall into Other Abnormality here
    "Other Abnormality": ["no_finding", "pneumonia", "enlarged_cardiomediastinum"],
}

SYSTEM = DEFINITIONS.split("Return every input pattern")[0] + """
CheXpert labeler mention phrases per label (prefix matches; for reference, from stanfordmlgroup/chexpert-labeler):
""" + "\n".join(f"- {lab}: " + ", ".join(p for f in files for p in CHEXPERT["mentions"][f])
                for lab, files in CHEXPERT_FOR.items()) + """

You get one code pattern: its full code strings (all sub-headings, with counts) and real example sentences
from reports carrying that code. Decide which ONE label the code should map to, or "ignore".
Give a one-sentence reason that quotes (in double quotes) words from one of the example sentences."""

SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": LABELS + [IGNORE]}, "reason": {"type": "string"}},
    "required": ["label", "reason"], "additionalProperties": False,
}


def _stems(pattern: str) -> list[str]:
    return [w[:4] for w in re.findall(r"[a-z]+", pattern.lower()) if len(w) >= 4]


def examples(pattern: str, reports: dict[int, dict], experts: dict[int, dict]) -> tuple[dict[str, int], list[str]]:
    """Full codes (with counts) for the pattern, and up to N_EXAMPLES sentences from different reports:
    the sentence sharing the most word stems with that report's full code(s), else the first Impression one."""
    codes: collections.Counter[str] = collections.Counter()
    sents: list[str] = []
    for rid in sorted(experts):
        hit = [c for c in experts[rid]["major"] if "/".join(parse_parts(c)[:2]) == pattern]
        if not hit:
            continue
        codes.update(hit)
        if len(sents) < N_EXAMPLES:
            stems = set(_stems(" ".join(hit)))
            ss = reports[rid]["sentences"]
            scored = [(sum(st in s["text"].lower() for st in stems), -i, s["text"]) for i, s in enumerate(ss)]
            best = max(scored, default=(0, 0, ""))
            pick = best[2] if best[0] else next((s["text"] for s in ss if s["section"] == "impression"),
                                                ss[0]["text"] if ss else "")
            if pick and pick not in sents:
                sents.append(pick)
    return dict(codes.most_common()), sents


def quote_ok(reason: str, sents: list[str]) -> bool:
    quotes = re.findall(r"\"([^\"]{4,})\"|“([^”]{4,})”", reason)
    return any(q.strip().lower() in s.lower() for pair in quotes for q in pair if q for s in sents)


def main(llm: LLMClient | None = None) -> dict:
    llm = llm or LLMClient()
    prev = json.loads(Path("artifacts/results/mapping_crosscheck.json").read_text(encoding="utf-8"))["results"]
    reports = {r["id"]: r for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8"))}
    experts = {e["id"]: e for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8"))
               if reports[e["id"]]["group_rep"] == e["id"]}  # one report per exact text
    dep, _ = deployment_for("repair", llm.s)
    p_in, _, p_out = PRICES[dep]
    rows, run_cost, stopped = [], 0.0, None
    for d in prev["disagreements"]:
        codes, sents = examples(d["pattern"], reports, experts)
        user = ("Code pattern: " + d["pattern"]
                + "\nFull codes:\n" + "\n".join(f"- {c} (n={n})" for c, n in codes.items())
                + "\nExample sentences:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(sents, 1)))
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        worst = (len(SYSTEM) + len(user)) / 3 * p_in / 1e6 + MAX_TOKENS * p_out / 1e6
        if run_cost + worst > RUN_CAP_USD:
            stopped = d["pattern"]
            break
        r = llm.complete(msgs, "repair", json_schema=SCHEMA, max_tokens=MAX_TOKENS, temperature=None,
                         purpose="mapping-crosscheck-context")
        run_cost += r.cost_usd
        ans = r.json_obj()
        rows.append({**d, "full_codes": codes, "examples": sents, "llm_context": ans["label"],
                     "reason": ans["reason"], "quote_verified": quote_ok(ans["reason"], sents)})
    remaining = [r for r in rows if r["llm_context"] not in r["rule"]]
    Path("artifacts/mapping").mkdir(parents=True, exist_ok=True)
    Path("artifacts/mapping/crosscheck_context.json").write_text(json.dumps(remaining, indent=1), encoding="utf-8")
    out = {
        "deployment": dep, "asked": len(rows), "stopped_before": stopped, "remaining_disagreements": len(remaining),
        "remaining_code_instances": sum(r["count"] for r in remaining),
        "remaining": [{k: r[k] for k in ("pattern", "count", "rule", "llm", "llm_context", "quote_verified")}
                      for r in remaining],
        "cost_usd_this_run": round(run_cost, 6), "llm_spend_total_usd": round(spent_usd(llm.cache_dir), 6),
    }
    write_result("mapping_crosscheck_context", out, fold=None)
    return {**out, "rows": remaining}


if __name__ == "__main__":
    res = main()
    print(f"asked {res['asked']}, remaining {res['remaining_disagreements']} "
          f"({res['remaining_code_instances']} codes); cost ${res['cost_usd_this_run']:.4f}; "
          f"stopped_before={res['stopped_before']}")
