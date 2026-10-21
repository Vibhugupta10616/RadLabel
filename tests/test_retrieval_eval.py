"""Best base combination rule (owner, before M9): top pooled nDCG@10; tied top two -> the simpler one."""

from eval.retrieval import best_base


def ci(v: float, lo: float, hi: float) -> dict:
    return {"all": {"ndcg": {"value": v, "lo": lo, "hi": hi}}}


def test_tied_top_two_prefer_the_simpler() -> None:
    r = best_base({"dense_sentence": ci(0.56, 0.53, 0.59), "rrf_plain": ci(0.57, 0.54, 0.60),
                   "bm25": ci(0.5, 0.4, 0.6)})
    assert r["tied"] and r["variant"] == "dense_sentence" and r["top_two"] == ["rrf_plain", "dense_sentence"]


def test_clear_winner_is_kept() -> None:
    r = best_base({"dense_sentence": ci(0.50, 0.47, 0.53), "rrf_plain": ci(0.60, 0.58, 0.62)})
    assert not r["tied"] and r["variant"] == "rrf_plain"
