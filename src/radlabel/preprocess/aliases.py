"""Pipeline alias dictionary per label (README §6.1): hand-written from general clinical knowledge plus the
CheXpert labeler mention phrases. Fixed, never tuned on data, and written independently of the eval lexicon
(`eval/lexicon.yaml`), which must never be copied here.

- Held-out aliases (embedding evaluation, M10): per label, the first 30% of aliases in SHA-1 order of
  "label|alias", excluding the label's own name. A fixed hash rule, so the choice can't be cherry-picked.
- Anchor aliases: anatomy-only phrases ("cardiac silhouette") that point at a label without asserting it.
  They mark evidence and negation ("heart size is normal"), and assert the finding only with an
  enlargement word in the same clause (see `negation.py`).
- CheXpert phrases are prefix patterns: they match at a word start and may extend ("opaci" -> opacities);
  a trailing "_" means the word must end there. Hand-written aliases match whole words (+ optional s/es).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path

from radlabel.labels import LABELS, NO_FINDING, OTHER

CHEXPERT_PATH = Path(__file__).with_name("chexpert_mentions.json")  # MIT, pinned commit inside the file
CHEXPERT_FOR = {
    "Cardiomegaly": ["cardiomegaly"], "Lung Opacity": ["lung_opacity"], "Lung Lesion": ["lung_lesion"],
    "Atelectasis": ["atelectasis"], "Pleural Effusion": ["pleural_effusion"], "Fracture": ["fracture"],
    "Support Devices": ["support_devices"], "Edema": ["edema"], "Pleural Other": ["pleural_other"],
    "Consolidation": ["consolidation"], "Pneumothorax": ["pneumothorax"],
    # CheXpert's no_finding list = abnormal terms outside its labels; dropped labels fall into Other here
    OTHER: ["no_finding", "pneumonia", "enlarged_cardiomediastinum"],
}
ANCHORS = {"the heart", "heart size", "cardiac size", "cardiac shadow", "cardiac contour", "cardiac silhouette"}
HELDOUT_FRACTION = 0.3

HAND: dict[str, list[str]] = {
    NO_FINDING: ["no acute cardiopulmonary", "no acute disease", "no active disease", "no acute abnormality",
                 "no acute findings", "normal chest", "lungs are clear", "clear lungs", "unremarkable",
                 "within normal limits", "normal", "negative chest"],
    "Cardiomegaly": ["cardiomegaly", "enlarged heart", "cardiac enlargement", "enlarged cardiac silhouette",
                     "heart is enlarged", "heart size is enlarged", "enlargement of the cardiac silhouette",
                     "cardiac silhouette is enlarged"],
    "Lung Opacity": ["lung opacity", "opacity", "opacification", "airspace disease", "airspace opacity", "infiltrate",
                     "density", "densities", "haziness", "ground glass", "patchy opacity"],
    "Lung Lesion": ["lung lesion", "nodule", "pulmonary nodule", "lung nodule", "mass", "lung mass",
                    "cavitary lesion", "cavitation", "nodular opacity", "nodular density", "neoplasm", "tumor"],
    "Atelectasis": ["atelectasis", "atelectatic", "collapse", "subsegmental atelectasis", "plate-like atelectasis"],
    "Pleural Effusion": ["pleural effusion", "effusion", "pleural fluid", "hydrothorax", "layering fluid"],
    "Fracture": ["fracture", "fractured", "rib fracture", "compression fracture", "fx"],
    "Support Devices": ["support device", "catheter", "tube", "endotracheal tube", "nasogastric tube", "chest tube",
                        "central line", "central venous catheter", "picc", "port", "pacemaker", "pacer",
                        "defibrillator", "icd", "pacer leads", "sternotomy wires", "stent", "surgical clips",
                        "hardware", "prosthesis", "valve replacement", "device"],
    "Edema": ["edema", "pulmonary edema", "interstitial edema", "alveolar edema", "fluid overload"],
    "Pleural Other": ["pleural thickening", "pleural plaque", "pleural scarring", "pleural calcification",
                      "fibrothorax"],
    "Consolidation": ["consolidation", "consolidative", "airspace consolidation"],
    "Pneumothorax": ["pneumothorax", "pneumothoraces", "hydropneumothorax", "ptx"],
    OTHER: ["other abnormality", "scoliosis", "kyphosis", "granuloma", "calcified granuloma", "granulomatous",
            "hyperinflation", "hyperinflated", "hyperexpanded", "emphysema", "copd", "degenerative", "spondylosis",
            "osteophyte", "tortuous", "tortuosity", "ectatic", "atherosclerotic", "atherosclerosis", "calcification",
            "calcified", "hernia", "hiatal hernia", "scarring", "hypoinflation", "low lung volumes",
            "elevated hemidiaphragm", "bronchiectasis", "pneumonia", "widened mediastinum", "deformity",
            "osteopenia", "eventration", "bullae", "chronic changes"],
}


@dataclass(frozen=True)
class Alias:
    label: str
    text: str             # normalised, "_" kept for CheXpert end-of-word marks
    source: str           # "hand" | "chexpert"
    heldout: bool
    anchor: bool

    @cached_property
    def tokens(self) -> list[str]:
        return normalise(self.text.replace("_", " ")).split()


def normalise(text: str) -> str:
    """Lower-case; keep letters, digits, [redacted] and '?' / ';' as tokens; everything else -> space."""
    t = text.lower().replace("[redacted]", " [redacted] ")
    t = re.sub(r"([?;])", r" \1 ", t)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9?;\[\] ]", " ", t)).strip()


def _heldout_set(label: str, texts: list[str]) -> set[str]:
    own = normalise(label)
    pool = sorted((t for t in texts if normalise(t.replace("_", " ")) != own),
                  key=lambda t: hashlib.sha1(f"{label}|{t}".encode()).hexdigest())
    return set(pool[: round(HELDOUT_FRACTION * len(pool))])


@lru_cache
def aliases() -> dict[str, list[Alias]]:
    chex = json.loads(CHEXPERT_PATH.read_text(encoding="utf-8"))["mentions"]
    out: dict[str, list[Alias]] = {}
    taken: set[str] = set()
    for lab in LABELS:
        if lab == OTHER:
            continue
        for f in CHEXPERT_FOR.get(lab, []):
            taken.update(chex[f])
    for lab in LABELS:
        entries: list[tuple[str, str]] = [(normalise(t), "hand") for t in HAND[lab]]
        for f in CHEXPERT_FOR.get(lab, []):
            # an Other Abnormality phrase already owned by a CheXpert pathology label stays with that label
            entries += [(p.lower(), "chexpert") for p in chex[f] if not (lab == OTHER and p in taken)]
        seen: dict[str, str] = {}
        for t, src in entries:
            seen.setdefault(t, src)
        held = _heldout_set(lab, list(seen))
        out[lab] = [Alias(lab, t, src, t in held, t.replace("_", " ").strip() in ANCHORS) for t, src in seen.items()]
    return out
