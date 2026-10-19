"""Per-rule mapping audit (README §4.5) + unmapped-code log (README §4.4).

For every rule of v1 and strict: among exact-text representatives with a code matching the rule,
the share whose text has a clear (non-negated, non-hedged) mention of the label per the eval-only
detector. Rules below 60% are flagged. No Finding: share with no clear mention of any label.
Other Abnormality is a catch-all with no terms, so it is not audited per rule; its codes are listed
in unmapped.csv instead. Outputs hold codes and counts only, never report text.
"""

from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

from data_prep.mapping import load_mapping, parse_parts
from eval.subsets import EVAL_VERSION, LEXICON, clear_mention
from radlabel.results import write_result

PROC = Path("data/processed")
OUT = Path("artifacts/mapping")
THRESHOLD = 0.6


def main() -> None:
    reports = [json.loads(line) for line in (PROC / "reports.jsonl").open(encoding="utf-8")]
    reps = {r["id"] for r in reports if r["id"] == r["group_rep"]}
    exp = {e["id"]: e for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8"))
           if e["id"] in reps}
    ments = {m["id"]: {k: [tuple(x) for x in v] for k, v in m["mentions"].items()}
             for m in map(json.loads, (PROC / "eval_mentions.jsonl").open(encoding="utf-8")) if m["id"] in reps}

    rows = []
    for version in ("v1", "strict"):
        m = load_mapping(version)
        normal = [i for i in reps if exp[i]["major"] == [m.no_finding_code]]
        agree = sum(not any(clear_mention(ments[i], lab) for lab in LEXICON) for i in normal)
        rows.append([version, "No Finding", m.no_finding_code, len(normal), agree])
        for lab, rules in m.rules.items():
            for rule in rules:
                hit = [i for i in reps if any(rule.matches(c) for c in exp[i]["major"])]
                rows.append([version, lab, str(rule), len(hit), sum(clear_mention(ments[i], lab) for i in hit)])

    OUT.mkdir(parents=True, exist_ok=True)
    flagged = []
    with (OUT / "audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mapping", "label", "rule", "n_reports", "n_clear_mention", "agreement", "flag"])
        for version, lab, rule, n, a in rows:
            rate = a / n if n else float("nan")
            flag = n > 0 and rate < THRESHOLD
            w.writerow([version, lab, rule, n, a, f"{rate:.3f}", "FLAG" if flag else ""])
            if flag:
                flagged.append({"mapping": version, "label": lab, "rule": rule, "n": n, "agreement": round(rate, 3)})

    v1 = load_mapping("v1")
    unm: collections.Counter[str] = collections.Counter()
    for i in reps:
        for c in exp[i]["major"]:
            head = parse_parts(c)[0]
            if head != v1.no_finding_code and head not in v1.ignore_codes and not v1.match(c):
                unm[c] += 1
    with (OUT / "unmapped.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "n_unique_reports"])
        w.writerows(unm.most_common())

    write_result("mapping_audit", {"eval_version": EVAL_VERSION, "threshold": THRESHOLD, "rules_audited": len(rows),
                                   "flagged": flagged, "distinct_unmapped_codes": len(unm)},
                 fold=None, mapping_version="v1+strict")
    print(f"{len(rows)} rules audited, {len(flagged)} flagged (<{THRESHOLD:.0%}):")
    for fl in flagged:
        print("  ", fl)


if __name__ == "__main__":
    main()
