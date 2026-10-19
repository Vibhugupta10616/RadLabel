"""MeSH(major, manual codes) -> CheXpert-14 mapping v1 and report-level label statistics.

Usage: python -I map_and_stats.py iu.jsonl iu_mapped.jsonl
A rule matches a code if the code's head equals `head` and (if given) the first
sub-heading equals `sub`. Pneumonia and Enlarged Cardiomediastinum are still
mapped here so their counts are visible, but they are excluded from evaluation.
"""
import json
import re
import sys
import collections
import hashlib

RULES = {
    "Cardiomegaly": [("Cardiomegaly", None), ("Cardiac Shadow", "enlarged")],
    "Enlarged Cardiomediastinum": [("Mediastinum", "prominent"), ("Mediastinum", None)],
    "Lung Opacity": [("Opacity", "lung"), ("Density", "lung"), ("Airspace Disease", "lung"),
                     ("Infiltrate", "lung"), ("Opacity", "retrocardiac"), ("Density", "retrocardiac")],
    "Lung Lesion": [("Nodule", None), ("Mass", None), ("Cavitation", None), ("Cysts", None)],
    # v1: congestion / heart failure NOT mapped (reports say "congestion without edema")
    "Edema": [("Pulmonary Edema", None)],
    "Consolidation": [("Consolidation", None)],
    "Pneumonia": [("Pneumonia", None)],
    "Atelectasis": [("Pulmonary Atelectasis", None)],
    "Pneumothorax": [("Pneumothorax", None), ("Hydropneumothorax", None), ("Hemopneumothorax", None)],
    "Pleural Effusion": [("Pleural Effusion", None), ("Hydropneumothorax", None), ("Hemothorax", None)],
    "Pleural Other": [("Thickening", "pleura"), ("Pleura", None)],
    "Fracture": [("Fractures, Bone", None)],
    "Support Devices": [("Catheters, Indwelling", None), ("Implanted Medical Device", None),
                        ("Tube, Inserted", None), ("Medical Device", None), ("Stents", None),
                        ("Surgical Instruments", None), ("Sutures", None)],
}
LABELS = ["No Finding"] + list(RULES)
CHILD_TO_OPACITY = {"Edema", "Consolidation", "Pneumonia", "Atelectasis", "Lung Lesion"}


def parse(code):
    parts = [p.strip() for p in code.split("/")]
    return parts[0], (parts[1] if len(parts) > 1 else "")


def map_report(major):
    pos = set()
    unmapped = []
    for c in major:
        head, sub = parse(c)
        if head in ("normal", "No Indexing"):
            continue
        hit = False
        for lab, rules in RULES.items():
            for h, s in rules:
                if head == h and (s is None or sub == s):
                    pos.add(lab)
                    hit = True
        if not hit:
            unmapped.append(c)
    if major == ["normal"]:
        pos.add("No Finding")
    return pos, unmapped


def norm(t):
    t = t.lower().replace("xxxx", " ")
    t = re.sub(r"[^a-z ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


rows = [json.loads(l) for l in open(sys.argv[1])]
usable = [r for r in rows if r["major"] != ["No Indexing"] and (r["findings"] or r["impression"])]
print(f"all {len(rows)} | usable (coded, has text) {len(usable)}")

cnt = collections.Counter()
cnt_closed = collections.Counter()
unm_reports = 0
only_unmapped_abn = 0
unm_heads = collections.Counter()
for r in usable:
    pos, unm = map_report(r["major"])
    r["pos"] = sorted(pos)
    for l in pos:
        cnt[l] += 1
    closed = set(pos)
    if closed & CHILD_TO_OPACITY:
        closed.add("Lung Opacity")
    if "Cardiomegaly" in closed:
        closed.add("Enlarged Cardiomediastinum")
    for l in closed:
        cnt_closed[l] += 1
    if unm:
        unm_reports += 1
        for c in unm:
            unm_heads[parse(c)[0]] += 1
    if not pos and r["major"] != ["normal"]:
        only_unmapped_abn += 1

print(f"reports with >=1 unmapped code: {unm_reports} ({unm_reports/len(usable):.1%})")
print(f"abnormal reports with NO CheXpert label at all: {only_unmapped_abn} ({only_unmapped_abn/len(usable):.1%})")
print("top unmapped heads:", unm_heads.most_common(15))
print()
print(f"{'label':28s} {'pos':>5s} {'closed':>7s} {'~test(15%)':>10s}")
for l in LABELS:
    print(f"{l:28s} {cnt[l]:5d} {cnt_closed[l]:7d} {cnt[l]*0.15:10.0f}")

# exact duplicates after normalisation
h = collections.Counter(hashlib.md5(norm(r["findings"] + " " + r["impression"]).encode()).hexdigest() for r in usable)
dups = sum(v for v in h.values() if v > 1)
print()
print(f"distinct normalised texts: {len(h)} | reports sharing text with another: {dups} ({dups/len(usable):.1%})")
print("largest duplicate groups:", sorted(h.values(), reverse=True)[:8])

with open(sys.argv[2], "w") as f:
    for r in usable:
        f.write(json.dumps(r) + "\n")
