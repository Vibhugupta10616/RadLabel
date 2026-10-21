"""Build processed data from the parsed XML (`data/processed/iu.jsonl`, from parse_iu.py).

Writes (all git-ignored, licence D1):
  data/processed/reports.jsonl        text + sentences + exact group + cluster; NO expert codes (serving may read)
  data/processed/expert_labels.jsonl  expert codes + v1 / strict labels (eval/training only)
  data/processed/eval_mentions.jsonl  eval-only negspacy mentions per label
  data/splits/subsets/*.txt           subset id lists (SPEC §4.8); negation_only as "id<TAB>label"
  artifacts/results/data_card.json    counts only (committed)

Counting unit (SPEC §4.2): one report per exact normalised text (lowest id); clusters (exact
pairwise Jaccard >= 0.9) are only for fold assignment.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from data_prep.mapping import crosscheck_note, expert_labels, load_mapping, parse_parts
from eval.subsets import (
    EVAL_VERSION,
    has_xxxx,
    is_abnormal,
    is_hedged,
    is_redaction_adjacent,
    mentions,
    negation_only_labels,
)
from radlabel.labels import FINDING_LABELS, LABELS, NO_FINDING, OTHER
from radlabel.preprocess.dedup import cluster
from radlabel.preprocess.sentences import report_sentences
from radlabel.preprocess.text import norm_text
from radlabel.results import write_result

RAW = Path("data/raw")
PROC = Path("data/processed")
SUBSETS = Path("data/splits/subsets")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main() -> None:
    raw = [json.loads(line) for line in (PROC / "iu.jsonl").open(encoding="utf-8")]
    assert all(r["licence"] == "byncnd" for r in raw)
    usable = [r for r in raw if r["major"] != ["No Indexing"] and (r["findings"] or r["impression"])]

    text = {r["id"]: r["findings"] + " " + r["impression"] for r in usable}
    clusters = {int(k): v for k, v in cluster({str(k): t for k, t in text.items()}).items()}
    groups: dict[str, list[int]] = collections.defaultdict(list)
    for r in usable:
        groups[norm_text(text[r["id"]])].append(r["id"])
    group_rep = {i: min(ids) for ids in groups.values() for i in ids}

    v1, strict = load_mapping("v1"), load_mapping("strict")
    reports, experts, ments = [], [], {}
    for r in usable:
        rid = r["id"]
        reports.append({
            "id": rid,
            "findings": r["findings"],
            "impression": r["impression"],
            "sentences": [s.model_dump() for s in report_sentences(r["findings"], r["impression"])],
            "group_rep": group_rep[rid],
            "cluster": clusters[rid],
        })
        # coded only with ignored codes (Technical Quality, Contrast Media): no label, excluded from No Finding scoring
        ignored_only = all(parse_parts(c)[0] in v1.ignore_codes for c in r["major"])
        experts.append({"id": rid, "major": r["major"], "ignored_only": ignored_only,
                        **expert_labels(r["major"], v1, strict)})
        ments[rid] = mentions(r["findings"], r["impression"])

    write_jsonl(PROC / "reports.jsonl", reports)
    write_jsonl(PROC / "expert_labels.jsonl", experts)
    write_jsonl(PROC / "eval_mentions.jsonl", [{"id": i, "mentions": m} for i, m in ments.items()])

    # ---- subsets (SPEC §4.8), on all usable reports; metrics later restrict to exact-text reps
    by_id = {r["id"]: r for r in usable}
    exp = {e["id"]: e for e in experts}
    unique_ids = sorted(set(group_rep.values()))
    sub = {
        "abnormal": [i for i in by_id if is_abnormal(set(exp[i]["v1"]))],
        "hedged": [i for i in by_id if is_hedged(by_id[i])],
        "redaction_adjacent": [i for i in by_id if is_redaction_adjacent(by_id[i])],
    }
    neg_pairs = [(i, lab) for i in by_id for lab in negation_only_labels(ments[i], set(exp[i]["v1"]))]
    SUBSETS.mkdir(parents=True, exist_ok=True)
    for name, ids in sub.items():
        (SUBSETS / f"{name}.txt").write_text("".join(f"{i}\n" for i in sorted(ids)), encoding="utf-8")
    (SUBSETS / "negation_only.tsv").write_text("".join(f"{i}\t{lab}\n" for i, lab in sorted(neg_pairs)),
                                              encoding="utf-8")

    # ---- data card (SPEC §3.3, §4.4, §4.5, §4.8)
    uniq = set(unique_ids)
    abn = set(sub["abnormal"])
    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    members: dict[int, list[int]] = collections.defaultdict(list)
    for i, c in clusters.items():
        members[c].append(i)
    near_dup = [m for m in members.values() if len({group_rep[i] for i in m}) > 1]
    exact_conflicts = sum(len({tuple(exp[i]["v1"]) for i in ids}) > 1 for ids in groups.values())

    def count(ids: set[int], key: str) -> dict[str, int]:
        return {lab: sum(lab in exp[i][key] for i in ids) for lab in LABELS}

    card = {
        "eval_version": EVAL_VERSION,
        "source_url": json.loads((RAW / "source.json").read_text())["url"],
        "xml_reports": len(raw),
        "no_indexing_only": sum(r["major"] == ["No Indexing"] for r in raw),
        "usable_reports": len(usable),
        "unique_texts": len(groups),
        "duplicate_clusters": len(members),
        "near_duplicate_clusters": len(near_dup),
        "near_duplicate_clusters_with_different_label_sets": sum(
            len({tuple(exp[i]["v1"]) for i in m}) > 1 for m in near_dup),
        "exact_text_groups_with_different_label_sets": exact_conflicts,
        "reports_sharing_text": sum(n for n in sizes if n > 1),
        "largest_duplicate_group": sizes[0],
        "normal_only": {"usable": sum(exp[i]["v1"] == [NO_FINDING] for i in by_id),
                        "unique": sum(exp[i]["v1"] == [NO_FINDING] for i in uniq)},
        "ignored_codes_only": {"usable": sum(e["ignored_only"] for e in experts),
                               "unique": sum(exp[i]["ignored_only"] for i in uniq)},
        "hedged_unique": len(uniq & set(sub["hedged"])),
        "xxxx_unique": sum(has_xxxx(by_id[i]) for i in uniq),
        "redaction_adjacent": {"usable": len(sub["redaction_adjacent"]),
                               "unique": len(uniq & set(sub["redaction_adjacent"]))},
        "abnormal_unique": len(uniq & abn),
        "unique_positives_v1": count(uniq, "v1"),
        "unique_positives_strict": count(uniq, "strict"),
        "strict_excluded_unique": {lab: sum(lab in exp[i]["strict_excluded"] for i in uniq)
                                   for lab in FINDING_LABELS},
        "negation_only_pairs_unique": {
            lab: {"all": sum(1 for i, la in neg_pairs if la == lab and i in uniq),
                  "abnormal": sum(1 for i, la in neg_pairs if la == lab and i in uniq and i in abn)}
            for lab in FINDING_LABELS},
    }
    card["mapping_crosscheck"] = crosscheck_note()
    pairs = card["negation_only_pairs_unique"]
    card["negation_only_pairs_unique"]["_total"] = {
        k: sum(v[k] for v in pairs.values()) for k in ("all", "abnormal")}
    assert OTHER in card["unique_positives_v1"]
    write_result("data_card", card, fold=None, mapping_version="v1+strict")
    print(json.dumps(card, indent=1))


if __name__ == "__main__":
    main()
