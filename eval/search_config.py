"""Website search configuration (owner rule after M9): between the fine-tuned candidates, the highest pooled nDCG@10;
if the top two are within each other's 95% CI, the simpler one. Reads retrieval_finetuned.json, writes
search_config.json. No retrieval is rerun.

Usage: python -m eval.search_config
"""

from __future__ import annotations

import json

from eval.labelling import load_result
from eval.retrieval import best_base
from radlabel.results import write_result

CANDIDATES = ("ft_sentence", "ft_sentence_filter")  # simplest first: the filter adds a step


def main() -> dict[str, object]:
    ft = load_result("retrieval_finetuned")
    if ft is None:
        raise SystemExit("run `python -m eval.retrieval run --finetuned` first")
    pick = best_base({v: ft["variants"][v] for v in CANDIDATES}, CANDIDATES)
    out = {**pick, "negation_filter": pick["variant"] == "ft_sentence_filter", "bm25": False,
           "candidates": {v: {"ndcg": ft["variants"][v]["all"]["ndcg"],
                              "contamination": ft["variants"][v]["all"]["contamination"]} for v in CANDIDATES}}
    write_result("search_config", out, fold="pooled", retrieval_spec="retrieval_v1")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
