"""M10b: evaluation of the ask features (SPEC §8.3). Pre-registered in docs/evaluation_notes.md ("M10b").

- Part 1, single report: the 102 dev-slice reports (the Tier 1 pilot, never in headline metrics). Templated "Is there
  <finding>?" (6 labels, every report), "What supports <label>?" (positives + one control per report) and the frozen
  questions of groups A, B, D (docs/m9b_handwritten_questions.md) on a fixed sample of the dev reports.
- Part 2, across reports: synthetic patient batches of 3 / 10 / 30 / 50 out-of-fold reports (3 replicates per size,
  fixed seed, never the dev slice, hedged reports left out; upload order = batch order), the website's RAG
  configuration (fine-tuned dense model on plain sentences: the fold-k model for a fold-k batch, so the embeddings
  are out-of-fold too) vs ALL sentences of ALL reports in the prompt. Templated questions with answers known from the
  expert codes + the frozen questions of groups C and D.
- Prompts: the frozen website prompts (ask-report-v1, ask-all-v1) through the real functions; the baseline prompt
  (BASELINE_SYSTEM, evaluation only) is the ask-all-v1 rules with every sentence given. No LLM-judged metrics: answers
  are parsed by rules (parse_*), expected answers come from the expert codes (v1, present = positive) and from the v2
  labels, citations are checked in code (structurally, and against the eval-only mention detector).
- Eval-only: reads expert codes; the serving code never imports this (tests/test_api.py).

Usage: python -m eval.ask estimate | run [single|rag] | score
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from eval.labelling import PRED_DIR, PROC, Items
from radlabel.api import ask as ask_mod
from radlabel.api import session as session_mod
from radlabel.api.session import Session, to_report
from radlabel.config import get_settings
from radlabel.embeddings import load_encoder
from radlabel.labels import LABELS, NO_FINDING
from radlabel.llm import LLMClient
from radlabel.pipeline import PipelineResult
from radlabel.results import write_result

FROZEN_FILE = Path("docs/m9b_handwritten_questions.md")
RECORDS = PRED_DIR / "ask_eval.jsonl"  # git-ignored: report text and answers
SPEND_CAP = 1.0  # USD of new spend for the whole evaluation (owner: stop if over $1)
TEMPLATE_LABELS = ["Cardiomegaly", "Pleural Effusion", "Support Devices", "Lung Opacity", "Atelectasis",
                   "Pneumothorax"]
NOUN = {"Cardiomegaly": "cardiomegaly", "Pleural Effusion": "a pleural effusion",
        "Support Devices": "a support device (tube, line or pacemaker)", "Lung Opacity": "a lung opacity",
        "Atelectasis": "atelectasis", "Pneumothorax": "a pneumothorax", "Fracture": "a fracture",
        "Edema": "pulmonary edema"}
FROZEN_SINGLE_REPORTS = 30  # dev reports that get the frozen questions of groups A, B, D
SIZES = (3, 10, 30, 50)
REPLICATES = 3  # batches per size: folds 0, 1, 2
POSITIVE_POOL = ["Cardiomegaly", "Pleural Effusion", "Support Devices", "Lung Opacity", "Atelectasis"]
NEGATIVE_POOL = ["Pneumothorax", "Fracture", "Edema"]
OUT_TOKENS = 85  # assumed completion tokens per answer (estimate only; the first real asks used 21-150)
CHARS_PER_TOKEN = 3.6  # conservative (English averages ~4)
PRICE_IN, PRICE_OUT = 0.40e-6, 1.60e-6  # gpt-4.1-mini, USD per token

BASELINE_SYSTEM = f"""You answer questions across several chest X-ray reports of one patient for a research demo (not
a medical device). You get ALL sentences of ALL the reports, each with its report number (reports are numbered in
upload order) and sentence ID (N = indication, C = comparison, F = findings, I = impression).
{ask_mod._RULES}"""


# ------------------------------------------------------------------ answer parsing (rules; pre-registered)
HEDGE_RE = re.compile(r"\b(possible|possibly|probable|probably|may|might|could|cannot be excluded|can't be excluded|"
                      r"uncertain|unclear|not definite|not definitive|suspected|suspicious|likely|questionable|"
                      r"equivocal)\b")
NO_RE = re.compile(r"^no\b|\bthere (?:is|are) no\b|\bno (?:evidence|sign|signs|mention|indication)\b|"
                   r"\bnot (?:described|mentioned|stated|seen|present|enlarged|identified|noted|reported)\b|"
                   r"\b(?:does|do|did) not\b|"
                   r"\b(?:doesn't|don't|isn't|aren't)\b|\bnone\b|\bnothing\b|\bwithout\b|\babsent\b|\bnegative\b|"
                   r"\bresolved\b|\bno longer\b|\bnormal\b|\bclear\b")
NONE_RE = re.compile(r"\b(none|no reports?|not any|zero|there (?:is|are) no|no such|do(?:es)? not|doesn't|don't)\b")
WORDS = {w: k for k, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
CERTAIN_RE = re.compile(r"\b(certain|certainly|definite|definitely|clearly|plainly|explicitly|stated)\b")
NO_OPACITY_RE = re.compile(r"no (?:lung )?opacity|not (?:mentioned|described|stated|reported)|no mention|"
                           r"does not (?:mention|describe|state)|doesn't (?:mention|describe|state)")


def first_sentence(answer: str) -> str:
    return re.split(r"(?<=[.!?])\s", answer.strip())[0].lower()


def parse_yn(answer: str | None, refusal: str | None) -> str:
    """notstated | refused | uncertain | yes | no. A refusal other than "The reports don't state this." is `refused`."""
    if answer is None:
        return "notstated" if refusal == ask_mod.NOT_STATED else "refused"
    first = first_sentence(answer)
    if HEDGE_RE.search(first):
        return "uncertain"
    if first.startswith("yes"):
        return "yes"
    if NO_RE.search(first):
        return "no"
    return "yes"  # an affirmative statement ("The heart is mildly enlarged.")


def parse_certainty(answer: str | None, refusal: str | None) -> str:
    """none | possible | certain | other (the frozen question 10)."""
    if answer is None:
        return "none" if refusal == ask_mod.NOT_STATED else "other"
    first = first_sentence(answer)
    if HEDGE_RE.search(first):
        return "possible"
    if NO_OPACITY_RE.search(first):
        return "none"
    return "certain" if CERTAIN_RE.search(first) or first.startswith("yes") else "other"


def report_numbers(text: str) -> set[int]:
    """Report numbers named in an answer ("reports 2, 5 and 7", "report 3", "reports 4-6")."""
    out: set[int] = set()
    for m in re.finditer(r"reports?\s+(\d+(?:(?:\s*(?:,|and|&|or|-|–|to))+\s*\d+)*)", text.lower()):
        chunk = m.group(1)
        for a, b in re.findall(r"(\d+)\s*(?:-|–|to)\s*(\d+)", chunk):
            out |= set(range(int(a), int(b) + 1))
        out |= {int(x) for x in re.findall(r"\d+", chunk)}
    return out


def parse_which(answer: str | None, refusal: str | None) -> set[int] | None:
    """The set of report numbers an answer names; empty for "none"; None if it cannot be read."""
    if answer is None:
        return set() if refusal == ask_mod.NOT_STATED else None
    nums = report_numbers(answer)
    if nums:
        return nums
    return set() if NONE_RE.search(answer.lower()) or parse_yn(answer, refusal) == "no" else None


def parse_count(answer: str | None, refusal: str | None) -> int | None:
    if answer is None:
        return 0 if refusal == ask_mod.NOT_STATED else None
    t = answer.lower()
    num = r"(\d+|" + "|".join(WORDS) + r")"
    m = re.search(num + r"\s+(?:of\s+(?:the\s+)?(?:\d+|" + "|".join(WORDS) + r")\s+)?reports?\b", t)
    if m:
        return int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
    m = re.search(r"\b(\d+)\b", t)
    if m:
        return int(m.group(1))
    return 0 if NONE_RE.search(t) else None


def parse_first(answer: str | None, refusal: str | None) -> int | str | None:
    """The report number named as first, "none", or None (unreadable)."""
    if answer is None:
        return "none" if refusal == ask_mod.NOT_STATED else None
    m = re.search(r"reports?\s+(\d+)", answer.lower())
    if m:
        return int(m.group(1))
    return "none" if NONE_RE.search(answer.lower()) or parse_yn(answer, refusal) == "no" else None


# ------------------------------------------------------------------ data
def frozen_questions() -> dict[int, tuple[str, str]]:
    """number -> (question, label for groups A-C / reason for D), read from the frozen file (never edited)."""
    rows = {}
    for ln in FROZEN_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", ln)
        if m:
            rows[int(m[1])] = (m[2], m[3])
    assert sorted(rows) == list(range(1, 21)), "the frozen question file changed"
    return rows


class Data:
    """Eval-side data: expert codes, eval-detector mentions, the v2 pipeline outputs (all unique reports)."""

    def __init__(self) -> None:
        self.it = Items()
        self.pos = {i: k for k, i in enumerate(self.it.ids)}
        full = (PRED_DIR / "verifier_agent_full.jsonl").open(encoding="utf-8")
        self.results = {int(r.report_id): r for r in map(PipelineResult.model_validate_json, full)}
        self.ments = {r["id"]: {lab: [tuple(x) for x in ms] for lab, ms in r["mentions"].items()}
                      for r in map(json.loads, (PROC / "eval_mentions.jsonl").open(encoding="utf-8"))}
        self.dev = [i for i, p in zip(self.it.ids, self.it.pilot, strict=True) if p]

    def coded(self, i: int, label: str) -> bool:
        return bool(self.it.gold["v1"][label][self.pos[i]])

    def hedged(self, i: int) -> bool:
        return bool(self.it.subset["hedged"][self.pos[i]])

    def v2(self, i: int, label: str) -> str:
        return next(f.status for f in self.results[i].final if f.label == label)


@cache
def sentence_mentions(text: str) -> dict[str, list[tuple[bool, bool]]]:
    from eval.subsets import mentions  # the eval-only detector (spaCy + negspacy)
    return mentions(text, "")


# ------------------------------------------------------------------ questions
def Q(**kw: Any) -> dict[str, Any]:
    return kw


def yn_expect(coded: bool) -> list[str]:
    return ["yes"] if coded else ["no", "notstated"]


def v2_expect(status: str) -> list[str]:
    return ["yes"] if status == "present" else ["uncertain"] if status == "uncertain" else ["no", "notstated"]


def single_questions(d: Data) -> list[dict[str, Any]]:
    """Part 1. Every question carries its expected answer from the codes and from the v2 labels."""
    fq = frozen_questions()
    rng = random.Random(f"{get_settings().seed}-m10b-single")
    sample = set(rng.sample(d.dev, FROZEN_SINGLE_REPORTS))
    out: list[dict[str, Any]] = []
    for i in d.dev:
        hed = d.hedged(i)
        for lab in TEMPLATE_LABELS:
            out.append(Q(qid=f"s{i}-is-{lab}", part="single", group="T1", rid=i, label=lab, kind="yn", hedged=hed,
                         question=f"Is there {NOUN[lab]}?", codes=yn_expect(d.coded(i, lab)),
                         v2=v2_expect(d.v2(i, lab)), should="answer" if d.coded(i, lab) else "either"))
        pos = [lab for lab in TEMPLATE_LABELS if d.coded(i, lab) or d.v2(i, lab) in ("present", "uncertain")]
        ctl = [lab for lab in TEMPLATE_LABELS if lab not in pos]
        random.Random(f"{get_settings().seed}-m10b-ctl-{i}").shuffle(ctl)
        for lab in pos + ctl[:1]:
            out.append(Q(qid=f"s{i}-supports-{lab}", part="single", group="T2", rid=i, label=lab, kind="support",
                         hedged=hed, question=f"What supports {lab}?", codes=["answered"] if d.coded(i, lab)
                         else ["notstated", "no"], v2=["answered"] if d.v2(i, lab) in ("present", "uncertain")
                         else ["notstated", "no"], should="answer" if d.coded(i, lab) else "either"))
        if i not in sample:
            continue
        for n in range(1, 11):
            text, lab = fq[n]
            m = d.ments[i].get(lab, [])
            clear = any(not neg and not hed_ for neg, hed_ in m)
            hedge_only = bool(m) and not clear and any(not neg for neg, _ in m)
            neg_only = bool(m) and all(neg for neg, _ in m)
            base = Q(qid=f"s{i}-f{n}", part="single", group="AB"[n > 6], rid=i, label=lab, frozen=n, hedged=hed,
                     question=text, should="either")
            if n in (1, 2, 3, 4, 5, 6):
                out.append({**base, "kind": "yn", "codes": yn_expect(d.coded(i, lab)),
                            "v2": v2_expect(d.v2(i, lab)), "should": "answer" if d.coded(i, lab) else "either"})
            elif n == 7:  # a negated-only edema mention must give "no"
                exp = ["yes"] if d.coded(i, lab) else ["no"] if neg_only else ["no", "notstated"]
                out.append({**base, "kind": "yn", "codes": exp, "v2": v2_expect(d.v2(i, lab))})
            elif n == 8:  # definite lung lesion: hedged-only must be "uncertain"
                exp = (["uncertain"] if hedge_only else ["yes"] if d.coded(i, lab) and clear
                       else None if d.coded(i, lab) else ["no", "notstated"])
                out.append({**base, "kind": "yn", "codes": exp, "v2": v2_expect(d.v2(i, lab))})
            elif n == 9:  # does the report state there is NO effusion
                exp = ["no"] if d.coded(i, lab) else ["yes"] if neg_only else ["no", "notstated"]
                st = d.v2(i, lab)
                out.append({**base, "kind": "yn", "codes": exp,
                            "v2": ["no"] if st == "present" else ["yes"] if neg_only else ["no", "notstated"]})
            else:  # 10: opacity certainty
                exp = ["certain"] if d.coded(i, lab) and clear else ["possible"] if hedge_only and d.coded(i, lab) \
                    else None if d.coded(i, lab) else ["none"]
                st = d.v2(i, lab)
                out.append({**base, "kind": "certainty", "codes": exp,
                            "v2": ["certain"] if st == "present" else ["possible"] if st == "uncertain" else ["none"]})
        for n in range(16, 21):
            out.append(Q(qid=f"s{i}-f{n}", part="single", group="D", rid=i, label=None, frozen=n, hedged=hed,
                         kind="refuse", question=fq[n][0], codes=["refused"], v2=["refused"], should="refuse"))
    return out


def batches(d: Data) -> list[dict[str, Any]]:
    """Part 2: 3 replicates (folds 0, 1, 2) of each size, drawn from that fold's non-dev, non-hedged reports."""
    out = []
    for n in SIZES:
        for r in range(REPLICATES):
            pool = [i for i, f in zip(d.it.ids, d.it.fold, strict=True)
                    if f == r and not d.it.pilot[d.pos[i]] and not d.hedged(i)]
            ids = random.Random(f"{get_settings().seed}-m10b-batch-{n}-{r}").sample(pool, n)
            out.append({"bid": f"b{n}-{r}", "n": n, "rep": r, "fold": r, "ids": ids})
    return out


def batch_questions(d: Data, b: dict[str, Any]) -> list[dict[str, Any]]:
    fq = frozen_questions()
    ids = b["ids"]
    nums = {lab: [k for k, i in enumerate(ids, 1) if d.coded(i, lab)] for lab in LABELS}
    v2n = {lab: [k for k, i in enumerate(ids, 1) if d.v2(i, lab) == "present"] for lab in LABELS}
    l1 = max(POSITIVE_POOL, key=lambda lab: (len(nums[lab]), -POSITIVE_POOL.index(lab)))
    l0 = next((lab for lab in NEGATIVE_POOL if not nums[lab]), NEGATIVE_POOL[-1])
    base = {"part": "rag", "bid": b["bid"], "n": b["n"], "rep": b["rep"], "should": "either", "hedged": False}
    out = []

    def add(qid: str, group: str, question: str, kind: str, label: str | None, codes: Any, v2: Any,
            frozen: int | None = None, should: str = "either") -> None:
        if kind != "refuse" and (bool(codes) if kind == "which" else codes > 0 if kind == "count" else codes != "none"):
            should = "answer"  # the codes expect a non-empty answer
        out.append({**base, "qid": f"{b['bid']}-{qid}", "group": group, "question": question, "kind": kind,
                    "label": label, "codes": codes, "v2": v2, "frozen": frozen, "should": should})
    for lab, tag in ((l1, "L1"), (l0, "L0")):
        add(f"which-{tag}", "TC", f"Which reports describe {NOUN[lab]}?", "which", lab, nums[lab], v2n[lab])
        add(f"count-{tag}", "TC", f"In how many reports is {NOUN[lab]} present?", "count", lab, len(nums[lab]),
            len(v2n[lab]))
    first = lambda xs: xs[0] if xs else "none"  # noqa: E731
    add("first-L1", "TC", f"In which report is {NOUN[l1]} first mentioned?", "first", l1, first(nums[l1]),
        first(v2n[l1]))
    normal = [k for k, i in enumerate(ids, 1) if d.coded(i, NO_FINDING)]
    normal2 = [k for k, i in enumerate(ids, 1) if d.v2(i, NO_FINDING) == "present"]
    for n in range(11, 16):
        text, lab = fq[n]
        c, v = {11: (nums["Cardiomegaly"], v2n["Cardiomegaly"]), 12: (len(nums["Pleural Effusion"]),
                                                                    len(v2n["Pleural Effusion"])),
                13: (first(nums["Support Devices"]), first(v2n["Support Devices"])), 14: (normal, normal2),
                15: (nums["Pneumothorax"], v2n["Pneumothorax"])}[n]
        kind = {11: "which", 12: "count", 13: "first", 14: "which", 15: "which"}[n]
        add(f"f{n}", "C", text, kind, lab if n != 14 else NO_FINDING, c, v, frozen=n)
    for n in range(16, 21):
        add(f"f{n}", "D", fq[n][0], "refuse", None, ["refused"], ["refused"], frozen=n, should="refuse")
    return out


# ------------------------------------------------------------------ running
class Meter:
    """Wraps the LLM client for one call: keeps every response (tokens, cost, raw text)."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm, self.responses = llm, []

    def complete(self, *a: Any, **k: Any) -> Any:
        r = self.llm.complete(*a, **k)
        self.responses.append(r)
        return r


def ask_full(llm: Any, session: Session, question: str) -> ask_mod.AskResult:
    """The baseline: every sentence of every report in the prompt (no retrieval)."""
    given = list(session.entries)
    user = "All report sentences:\n" + "\n".join(ask_mod._line(e) for e in given) + f"\n\nQuestion: {question}"
    a, r, c = ask_mod.check(ask_mod._complete(llm, BASELINE_SYSTEM, user, "full-eval"), given)
    return ask_mod.AskResult(answer=a, refusal=r, citations=c, retrieved_sentences=len(given),
                             retrieved_reports=len({e.report_no for e in given}))


def single_session(d: Data, i: int) -> Session:
    s = Session("eval")
    s.reports.append(to_report(1, f"report_{i}.txt", d.results[i]))
    return s


def batch_session(d: Data, b: dict[str, Any]) -> Session:
    """A session of the batch's reports in upload order, indexed with the fold model (out-of-fold embeddings)."""
    enc = load_encoder(f"models/eval/fold_{b['fold']}/model")
    session_mod.search_encode = lambda texts, batch_size=64: np.asarray(  # type: ignore[assignment]
        enc.encode(texts, normalize_embeddings=True, batch_size=batch_size))
    s = Session("eval")
    for k, i in enumerate(b["ids"], 1):
        s.add(to_report(k, f"report_{i}.txt", d.results[i]))
    return s


def call(q: dict[str, Any], method: str, llm: LLMClient, session: Session) -> dict[str, Any]:
    m = Meter(llm)
    t0 = time.perf_counter()
    retrieved: list[list[Any]] = []
    if method == "report":
        res = ask_mod.ask_report(m, session, 1, q["question"])  # type: ignore[arg-type]
    elif method == "rag":
        retrieved = [[e.report_no, e.sentence_id] for e in session.retrieve(q["question"], ask_mod.TOP_K)]
        res = ask_mod.ask_all(m, session, q["question"])  # type: ignore[arg-type]
    else:
        res = ask_full(m, session, q["question"])
    dt = time.perf_counter() - t0
    raw = [json.loads(r.text) if r.text.startswith("{") else {} for r in m.responses]
    return {"qid": q["qid"], "method": method, "answer": res.answer, "refusal": res.refusal,
            "citations": [c.model_dump() for c in res.citations], "retrieved": retrieved,
            "given": res.retrieved_sentences, "raw_citations": [c for x in raw for c in x.get("citations", [])],
            "input_tokens": sum(r.input_tokens for r in m.responses),
            "output_tokens": sum(r.output_tokens for r in m.responses),
            "cost_usd": sum(r.cost_usd for r in m.responses), "cached": all(r.cached for r in m.responses),
            "latency_s": dt}


def load_records() -> dict[tuple[str, str], dict[str, Any]]:
    if not RECORDS.exists():
        return {}
    rows = map(json.loads, RECORDS.open(encoding="utf-8"))
    return {(r["qid"], r["method"]): r for r in rows}


def run(parts: tuple[str, ...], llm: LLMClient) -> None:
    d = Data()
    done = load_records()
    spend0 = llm.spent
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    out = RECORDS.open("a", encoding="utf-8")

    def guarded(q: dict[str, Any], method: str, session: Session) -> dict[str, Any] | None:
        if (q["qid"], method) in done:
            return None
        if llm.spent - spend0 > SPEND_CAP:
            raise SystemExit(f"new spend passed ${SPEND_CAP}: stopped (finished calls are kept)")
        rec = {**call(q, method, llm, session), "part": q["part"]}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        return rec
    if "single" in parts:
        qs = single_questions(d)
        sessions = {i: single_session(d, i) for i in d.dev}
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda q: guarded(q, "report", sessions[q["rid"]]), qs))
    if "rag" in parts:  # sequential: latency is measured per request
        for b in batches(d):
            session = batch_session(d, b)
            for q in batch_questions(d, b):
                for method in ("rag", "full"):
                    guarded(q, method, session)
    print(json.dumps({"new_spend_usd": llm.spent - spend0}))


# ------------------------------------------------------------------ estimate (no LLM call)
class DryLLM:
    """Records the prompts instead of calling a model; answers a fixed refusal."""

    def __init__(self) -> None:
        self.prompts: list[tuple[str, int]] = []

    def complete(self, messages: list[dict[str, Any]], *a: Any, **k: Any) -> Any:
        from types import SimpleNamespace
        self.prompts.append((k.get("purpose", ""), sum(len(m["content"]) for m in messages)))
        return SimpleNamespace(text='{"answer": null, "refusal": "x", "citations": []}', input_tokens=0,
                               output_tokens=0, cost_usd=0.0, cached=False, filtered=False)


def estimate() -> dict[str, Any]:
    d = Data()
    dry = DryLLM()
    qs = single_questions(d)
    sessions = {i: single_session(d, i) for i in d.dev}
    for q in qs:
        ask_mod.ask_report(dry, sessions[q["rid"]], 1, q["question"])  # type: ignore[arg-type]
    single_n = len(dry.prompts)
    single_cost = sum(c / CHARS_PER_TOKEN * PRICE_IN + OUT_TOKENS * PRICE_OUT for _, c in dry.prompts)
    rows = {}
    rag = full = 0.0
    for b in batches(d):
        session = batch_session(d, b)
        dry.prompts.clear()
        bq = batch_questions(d, b)
        for q in bq:
            ask_mod.ask_all(dry, session, q["question"])  # type: ignore[arg-type]
        r_cost = sum(c / CHARS_PER_TOKEN * PRICE_IN + OUT_TOKENS * PRICE_OUT for _, c in dry.prompts)
        dry.prompts.clear()
        for q in bq:
            ask_full(dry, session, q["question"])  # type: ignore[arg-type]
        f_cost = sum(c / CHARS_PER_TOKEN * PRICE_IN + OUT_TOKENS * PRICE_OUT for _, c in dry.prompts)
        rows[b["bid"]] = {"questions": len(bq), "rag_usd": r_cost, "full_usd": f_cost}
        rag += r_cost
        full += f_cost
    total = single_cost + rag + full
    return {"single_calls": single_n, "single_usd": single_cost, "rag_usd": rag, "full_usd": full,
            "batch_questions": sum(r["questions"] for r in rows.values()), "total_usd": total, "by_batch": rows,
            "assumptions": {"chars_per_token": CHARS_PER_TOKEN, "output_tokens": OUT_TOKENS,
                            "price_per_1m_in_out": [PRICE_IN * 1e6, PRICE_OUT * 1e6]}}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "estimate"
    if mode == "estimate":
        print(json.dumps(estimate(), indent=1))
    elif mode == "run":
        run(tuple(sys.argv[2:]) or ("single", "rag"), LLMClient())
    else:
        raise SystemExit("usage: python -m eval.ask estimate | run [single|rag] | score")
    _ = (Counter, Callable, write_result)  # scoring is added below
