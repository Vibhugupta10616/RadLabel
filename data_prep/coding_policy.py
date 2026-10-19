"""Probe the IU coders' policy on hedged and negated findings, and rough label noise."""
import json
import re
import sys
import random

rows = [json.loads(l) for l in open(sys.argv[1])]
random.seed(0)

TERMS = {
    "Pleural Effusion": r"effusion",
    "Pneumonia": r"pneumonia",
    "Atelectasis": r"atelectasis",
    "Cardiomegaly": r"cardiomegaly|heart (size )?(is )?enlarged|enlarged (cardiac|heart)",
    "Pneumothorax": r"pneumothorax",
    "Edema": r"edema",
    "Consolidation": r"consolidation",
}
HEDGE = r"(\?|\b(question(able)?|suspicion|suspect(ed)?|differential|consider|could|might|cannot rule out|not ruled out|possibl[ey]|may represent|cannot be excluded|can not be excluded|cannot exclude|not excluded|questionable|suspicious for|suggestive of|likely|probable|concerning for|versus|vs\.?)\b)"
NEG = r"\b(no|not|without|negative for|free of|clear of|resolved|resolution of|no evidence of|removed)\b"

def sentences(r):
    text = (r["findings"] + " " + r["impression"]).replace("XXXX", "")
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if s.strip()]

def classify(r, pat):
    """Return 'pos' if some sentence mentions the term without negation/hedge,
    'hedged' if only hedged mentions, 'neg' if only negated, None if absent."""
    kinds = set()
    for s in sentences(r):
        sl = s.lower()
        m = re.search(pat, sl)
        if not m:
            continue
        before = sl[: m.start()]
        if re.search(NEG, before):
            kinds.add("neg")
        elif re.search(HEDGE, sl):
            kinds.add("hedged")
        else:
            kinds.add("pos")
    if not kinds:
        return None
    if "pos" in kinds:
        return "pos"
    if "hedged" in kinds:
        return "hedged"
    return "neg"

print(f"{'label':18s} {'text':>8s} {'n':>5s} {'coded':>6s} {'rate':>6s}")
examples = {}
for lab, pat in TERMS.items():
    for kind in ("pos", "hedged", "neg"):
        sel = [r for r in rows if classify(r, pat) == kind]
        coded = [r for r in sel if lab in r["pos"]]
        rate = len(coded) / len(sel) if sel else float("nan")
        print(f"{lab:18s} {kind:>8s} {len(sel):5d} {len(coded):6d} {rate:6.0%}")
        if kind == "hedged":
            examples[lab] = [(r["id"], r["pos"], [s for s in sentences(r) if re.search(pat, s.lower())]) for r in sel[:3]]
        if kind == "pos" and lab in ("Pleural Effusion", "Cardiomegaly"):
            miss = [r for r in sel if lab not in r["pos"]]
            examples[lab + " | text-positive but NOT coded"] = [
                (r["id"], r["major"], [s for s in sentences(r) if re.search(pat, s.lower())]) for r in random.sample(miss, min(4, len(miss)))]

print()
for k, v in examples.items():
    print("==", k)
    for e in v:
        print("  ", e)
