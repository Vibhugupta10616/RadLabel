"""Mapping cross-check (owner request after M1): ask the Tier 1 deployment to assign every distinct expert
code pattern (head/first sub-heading) to one of the 13 labels or "ignore", and compare with mapping v1.
Read-only: never changes the mapping. Sends MeSH code strings only, no report text.

Usage: python -m data_prep.crosscheck_mapping
Writes artifacts/results/mapping_crosscheck.json (codes + counts only).
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from data_prep.mapping import load_mapping, parse_parts
from radlabel.labels import LABELS
from radlabel.llm import LLMClient, spent_usd
from radlabel.results import write_result

PROC = Path("data/processed")
BATCH = 25
IGNORE = "ignore"

DEFINITIONS = """You map expert MeSH-style codes from chest X-ray reports to report labels.
A code pattern is `head` or `head/first sub-heading` (e.g. `Opacity/lung`, `Cysts/humerus`).
Assign each pattern to exactly ONE of these labels, or "ignore":
- No Finding: the code `normal` (the report describes no abnormality of any kind).
- Cardiomegaly: enlarged heart / cardiac silhouette.
- Lung Opacity: opacity, density, airspace disease or infiltrate in the lung (incl. retrocardiac).
- Lung Lesion: nodule, mass or cavitation at a lung site (lung, or no anatomical site given).
  Lesions at other sites (bone, breast, heart, mediastinum, pleura, thorax) are Other Abnormality.
  Calcified granuloma and granulomatous disease (benign, chronic) are Other Abnormality.
- Atelectasis: pulmonary atelectasis / collapse.
- Pleural Effusion: pleural effusion, hydropneumothorax, hemothorax.
- Fracture: bone fractures.
- Support Devices: catheters, implanted or medical devices, inserted tubes, stents, surgical instruments.
- Edema: pulmonary edema only (not congestion, not heart failure).
- Pleural Other: pleural thickening or other pleural abnormality (a blunted pleural angle is NOT this).
- Consolidation: consolidation.
- Pneumothorax: pneumothorax, hydropneumothorax, hemopneumothorax.
- Other Abnormality: any other abnormality (e.g. scoliosis, calcified granuloma, hypoinflation,
  degenerative spine, tortuous aorta, pneumonia, congestion, prominent mediastinum).
- ignore: not a finding (`No Indexing`, `Technical Quality of Image Unsatisfactory`).
Return every input pattern exactly once, in the same spelling."""

SCHEMA = {
    "type": "object",
    "properties": {"assignments": {"type": "array", "items": {
        "type": "object",
        "properties": {"pattern": {"type": "string"}, "label": {"type": "string", "enum": LABELS + [IGNORE]}},
        "required": ["pattern", "label"], "additionalProperties": False}}},
    "required": ["assignments"], "additionalProperties": False,
}


def patterns() -> tuple[collections.Counter[str], dict[str, set[str]]]:
    """pattern -> code count, and pattern -> labels mapping v1 gives its full codes."""
    v1 = load_mapping("v1")
    count: collections.Counter[str] = collections.Counter()
    rule: dict[str, set[str]] = collections.defaultdict(set)
    for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8")):
        for code in e["major"]:
            parts = parse_parts(code)
            pat = "/".join(parts[:2])
            count[pat] += 1
            if parts[0] == v1.no_finding_code:
                rule[pat].add("No Finding")
            elif parts[0] in v1.ignore_codes:
                rule[pat].add(IGNORE)
            else:
                rule[pat].update(v1.match(code) or [v1.other_label])
    return count, rule


def main(llm: LLMClient | None = None) -> dict:
    llm = llm or LLMClient()
    count, rule = patterns()
    pats = sorted(count)
    llm_says: dict[str, str] = {}
    cost = 0.0
    for i in range(0, len(pats), BATCH):
        batch = pats[i : i + BATCH]
        r = llm.complete(
            [{"role": "system", "content": DEFINITIONS},
             {"role": "user", "content": "Patterns:\n" + "\n".join(batch)}],
            "tier1", json_schema=SCHEMA, max_tokens=1500, temperature=0.0, purpose="mapping-crosscheck",
        )
        cost += r.cost_usd
        got = {a["pattern"]: a["label"] for a in r.json_obj()["assignments"]}
        for p in batch:
            llm_says[p] = got.get(p, "<missing>")
    rows = [{"pattern": p, "count": count[p], "rule": sorted(rule[p]), "llm": llm_says[p]} for p in pats]
    dis = sorted((r for r in rows if r["llm"] not in r["rule"]), key=lambda r: -r["count"])
    out = {"patterns": len(rows), "code_instances": sum(count.values()), "disagreements": dis,
           "disagreement_patterns": len(dis), "disagreement_code_instances": sum(r["count"] for r in dis),
           "cost_usd_this_run": round(cost, 6), "llm_spend_total_usd": round(spent_usd(llm.cache_dir), 6)}
    write_result("mapping_crosscheck", out, fold=None)
    return out


if __name__ == "__main__":
    res = main()
    print(f"{res['patterns']} patterns, {res['disagreement_patterns']} disagree "
          f"({res['disagreement_code_instances']} code instances); cost ${res['cost_usd_this_run']:.4f}")
    for r in res["disagreements"]:
        print(f"  {r['pattern']:45s} n={r['count']:4d}  rule={'+'.join(r['rule']):30s} llm={r['llm']}")
