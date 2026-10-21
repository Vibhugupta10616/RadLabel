"""Negation-aware fine-tuning of bge-small (SPEC §6.3, M9).

Per fold k: CachedGISTEmbedLoss (the base model as guide; it filters in-batch false negatives) on fold k's training
triplets (training/build_pairs.py), 1-3 epochs, the epoch kept = the best inner-validation nDCG@10 (report level,
max over sentences, the training labels' queries; fold k is never seen). Fixed seed; --device auto (CUDA with
bf16/fp16 when available, else CPU). Models go to MODEL_STORE (private, git-ignored): eval/fold_{k}, serving.

Usage:
  python -m training.train_embeddings --timing 2000          # time a short run on fold 0, estimate the full run
  python -m training.train_embeddings --folds 0 1 2 3 4      # evaluation models
  python -m training.train_embeddings --serving --epochs E   # serving model on all reports (after evaluation)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from datasets import Dataset
from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
from sentence_transformers.evaluation import SentenceEvaluator
from sentence_transformers.losses import CachedGISTEmbedLoss
from sentence_transformers.training_args import BatchSamplers

from radlabel.config import get_settings
from radlabel.embeddings import QUERY_PREFIX
from radlabel.results import write_result
from training.build_pairs import Report, build, build_all, load_reports, queries

EPOCHS, BATCH, MINI_BATCH, LR = 3, 128, 32, 2e-5


def device(arg: str) -> str:
    return ("cuda" if torch.cuda.is_available() else "cpu") if arg == "auto" else arg


def compute_info(dev: str) -> dict[str, Any]:
    info: dict[str, Any] = {"device": dev, "torch": torch.__version__, "cuda": torch.version.cuda}
    if dev == "cuda":
        info["gpu"] = torch.cuda.get_device_name(0)
        info["bf16"] = torch.cuda.is_bf16_supported()
        try:
            info["driver"] = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                            capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            info["driver"] = None
    return info


class InnerValNDCG(SentenceEvaluator):
    """Report-level nDCG@10 on inner-validation reports: each query against every sentence, max per report;
    relevant = the query's label coded (v1). Training-label queries only (held-out ones never used)."""

    def __init__(self, reports: list[Report]) -> None:
        super().__init__()
        self.name, self.primary_metric, self.greater_is_better = "innerval", "ndcg@10", True
        self.reports = reports
        self.qs = [(q, lab) for lab, qs in queries().items() for q in qs if any(lab in r.labels for r in reports)]

    def score(self, model: SentenceTransformer) -> float:
        sents = [(k, s) for k, r in enumerate(self.reports) for s in r.sentences]
        owner = np.array([k for k, _ in sents])
        s = model.encode([t for _, t in sents], normalize_embeddings=True, batch_size=256)
        q = model.encode([QUERY_PREFIX + t for t, _ in self.qs], normalize_embeddings=True, batch_size=256)
        sims = q @ s.T
        out = []
        for (_, lab), row in zip(self.qs, sims, strict=True):
            best = np.full(len(self.reports), -np.inf)
            np.maximum.at(best, owner, row)
            top = np.argsort(-best, kind="stable")[:10]
            rel = np.array([lab in r.labels for r in self.reports])
            dcg = sum(rel[i] / np.log2(n + 2) for n, i in enumerate(top))
            ideal = sum(1 / np.log2(n + 2) for n in range(min(10, int(rel.sum()))))
            out.append(dcg / ideal)
        return float(np.mean(out))

    def __call__(self, model: SentenceTransformer, output_path: str | None = None, epoch: int = -1,
                 steps: int = -1) -> dict[str, float]:
        return self.prefix_name_to_metrics({"ndcg@10": self.score(model)}, self.name)


def train(triplets: list[tuple[str, str, str]], out_dir: Path, dev: str, seed: int, epochs: int = EPOCHS,
          inner: list[Report] | None = None) -> dict[str, Any]:
    base = get_settings().embed_base_model
    model = SentenceTransformer(base, device=dev)
    guide = SentenceTransformer(base, device=dev)
    ds = Dataset.from_dict({"anchor": [QUERY_PREFIX + q for q, _, _ in triplets],
                            "positive": [p for _, p, _ in triplets], "negative": [n for _, _, n in triplets]})
    ev = InnerValNDCG(inner) if inner else None
    cuda = dev == "cuda"
    bf16 = cuda and torch.cuda.is_bf16_supported()
    args = SentenceTransformerTrainingArguments(
        output_dir=str(out_dir / "checkpoints"), num_train_epochs=epochs, per_device_train_batch_size=BATCH,
        learning_rate=LR, warmup_steps=0.1, seed=seed,  # a float warmup_steps = warmup ratio (Transformers v5)
        data_seed=seed, bf16=bf16, fp16=cuda and not bf16,
        batch_sampler=BatchSamplers.NO_DUPLICATES, logging_steps=50, report_to="none",
        eval_strategy="epoch" if ev else "no", save_strategy="epoch" if ev else "no", save_total_limit=epochs,
        load_best_model_at_end=bool(ev), metric_for_best_model="eval_innerval_ndcg@10" if ev else None,
        greater_is_better=True)
    trainer = SentenceTransformerTrainer(model=model, args=args, train_dataset=ds,
                                         loss=CachedGISTEmbedLoss(model, guide, mini_batch_size=MINI_BATCH),
                                         evaluator=ev)
    t0 = time.time()
    base_score = ev.score(model) if ev else None
    trainer.train()
    seconds = time.time() - t0
    hist = [x["eval_innerval_ndcg@10"] for x in trainer.state.log_history if "eval_innerval_ndcg@10" in x]
    model.save(str(out_dir / "model"))
    shutil.rmtree(out_dir / "checkpoints", ignore_errors=True)
    return {"triplets": len(triplets), "epochs_trained": epochs, "inner_val_ndcg_base": base_score,
            "inner_val_ndcg_by_epoch": hist, "best_epoch": int(np.argmax(hist)) + 1 if hist else epochs,
            "seconds": seconds}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, nargs="*", default=[])
    ap.add_argument("--timing", type=int, default=0, help="train fold 0 on this many triplets, 1 epoch, and estimate")
    ap.add_argument("--serving", action="store_true")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    s, dev = get_settings(), device(a.device)
    store = Path(s.model_store)
    reports = load_reports()
    if a.timing:
        f = build(0, reports, s.seed)
        r = train(f.triplets[: a.timing], store / "timing", dev, s.seed, epochs=1)
        shutil.rmtree(store / "timing", ignore_errors=True)
        per = r["seconds"] / a.timing
        sizes = [len(build(k, reports, s.seed).triplets) for k in range(5)]
        est = per * sum(sizes) * EPOCHS
        print(json.dumps({"compute": compute_info(dev), "seconds_per_triplet_epoch": per, "triplets_per_fold": sizes,
                          "estimated_5_fold_minutes_3_epochs": est / 60}, indent=1))
        return
    if a.serving:
        trips, _ = build_all(reports, s.seed)
        r = train(trips, store / "serving", dev, s.seed, epochs=a.epochs)
        write_result("embedding_serving_model", {**r, "compute": compute_info(dev)}, fold="all reports",
                     base_model=s.embed_base_model)
        return
    out: dict[str, Any] = {"compute": compute_info(dev), "folds": {}}
    for k in a.folds:
        f = build(k, reports, s.seed)
        out["folds"][str(k)] = {**train(f.triplets, store / "eval" / f"fold_{k}", dev, s.seed + k, inner=f.inner),
                                "train_reports": len(f.train_ids), "inner_val_reports": len(f.inner),
                                "source_reports": len(f.sources)}
        print(k, json.dumps(out["folds"][str(k)]))
    write_result("embedding_training", out, fold="per fold", base_model=s.embed_base_model, loss="CachedGISTEmbedLoss",
                 batch=BATCH, mini_batch=MINI_BATCH, lr=LR, max_epochs=EPOCHS)


if __name__ == "__main__":
    main()
