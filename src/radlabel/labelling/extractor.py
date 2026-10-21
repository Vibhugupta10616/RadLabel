"""Tier 1 LLM extractor (SPEC §6.2): zero-shot, synthetic in-prompt examples (hand-written, never IU text),
strict structured output with one required key per label. Calls go through `radlabel.llm` (cached, costed).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from radlabel.labelling.schema import LabelOut, ReportLabels, derive_no_finding
from radlabel.labels import LABELS
from radlabel.llm import LLMClient, LLMResponse
from radlabel.preprocess.sentences import Sentence

PROMPT_VERSION = "tier1-v1"  # FROZEN after the M4 pilot (owner): hash pinned in tests/test_extractor.py
TIER1_DEPLOYMENT = "gpt-4.1-mini"  # locked after the M4 pilot: "chosen on pilot, CIs overlap"
STATUSES = ["present", "absent", "uncertain", "not_mentioned"]

SYSTEM = """You label chest X-ray reports. The report is split into numbered sentences: Findings F1..Fn and
Impression I1..In. "[REDACTED]" marks words removed for privacy; never guess what they were.

For EVERY label give a status and the IDs of the sentences that support it:
- present: the report states the finding.
- absent: the report explicitly says the finding is not there (e.g. "no pleural effusion").
- uncertain: the report hedges about it ("possible", "may represent", "cannot exclude", "versus", "?").
- not_mentioned: the report doesn't talk about it; give no evidence.
For present, absent and uncertain, cite at least one sentence ID whose sentence mentions the finding.

Labels (each label is judged on its own; one label never implies another):
- No Finding: present only if the report describes no abnormality of any kind, including chronic or incidental
  findings (granulomas, scoliosis, degenerative spine, tortuous aorta, old surgery). Cite the normal statements.
  Otherwise not_mentioned. If No Finding is present, no other label may be present.
- Cardiomegaly: enlarged heart or cardiac silhouette, including mild or borderline-stated enlargement.
  Prominence of a single chamber alone is Other Abnormality.
- Lung Opacity: opacity, density, airspace disease or infiltrate in the lung. Nodules/masses, atelectasis,
  consolidation and edema have their own labels.
- Lung Lesion: nodule, mass or cavitation in the lung. Calcified granulomas, granulomatous disease and cysts are
  Other Abnormality; masses outside the lung (mediastinal, paratracheal, breast) are Other Abnormality.
- Atelectasis: atelectasis or collapse (including subsegmental or plate-like).
- Pleural Effusion: pleural effusion, including hydropneumothorax and hemothorax. Blunting of a costophrenic
  angle on its own is NOT an effusion (it is Other Abnormality).
- Fracture: any bone fracture, acute or healed.
- Support Devices: catheters, tubes, lines, pacemakers/ICDs and their leads, implanted devices (e.g. valve
  prostheses, stimulators), stents, surgical clips and other surgical instruments. Sutures and foreign bodies
  (e.g. piercings) are Other Abnormality.
- Edema: pulmonary edema only. Vascular congestion or heart failure without edema is Other Abnormality.
- Pleural Other: pleural thickening, plaques, pleural scarring or another pleural abnormality (not a blunted angle).
- Consolidation: consolidation.
- Pneumothorax: pneumothorax, including hydropneumothorax.
- Other Abnormality: any other abnormality (e.g. calcified granuloma, scoliosis, degenerative spine, tortuous or
  calcified aorta, hyperinflation/emphysema, low lung volumes, hernia, pneumonia, prominent mediastinum,
  scarring, sutures, blunted costophrenic angle, prior surgery).

Sections: the Impression overrides the Findings only when it explicitly contradicts the same finding. A general
statement such as "no acute cardiopulmonary disease" does not cancel specific findings.

Example 1 (synthetic)
F1: The cardiac silhouette is mildly enlarged.
F2: There is no pleural effusion or pneumothorax.
F3: Possible small opacity at the left base.
I1: Mild cardiomegaly.
I2: No acute pulmonary process.
-> Cardiomegaly present [F1, I1]; Pleural Effusion absent [F2]; Pneumothorax absent [F2];
   Lung Opacity uncertain [F3]; every other label not_mentioned [].

Example 2 (synthetic)
F1: Heart size is normal.
F2: The lungs are clear.
I1: No acute cardiopulmonary abnormality.
-> No Finding present [F2, I1]; Cardiomegaly absent [F1]; every other label not_mentioned []."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {lab: {"type": "object",
                         "properties": {"status": {"type": "string", "enum": STATUSES},
                                        "evidence": {"type": "array", "items": {"type": "string"}}},
                         "required": ["status", "evidence"], "additionalProperties": False}
                   for lab in LABELS},
    "required": LABELS,
    "additionalProperties": False,
}


def messages(sentences: list[Sentence]) -> list[dict[str, str]]:
    body = "\n".join(f"{s.id}: {s.text}" for s in sentences) or "(empty report)"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Report:\n" + body}]


def parse(report_id: str, text: str) -> ReportLabels | None:
    """None if the output is not valid JSON for the schema (counted as an invalid output)."""
    try:
        d = json.loads(text)
        out = ReportLabels(report_id=report_id, tier=1, labels=[
            LabelOut(label=lab, status=d[lab]["status"], evidence=list(d[lab]["evidence"])) for lab in LABELS])
        return derive_no_finding(out)  # the model's No Finding value is ignored (owner decision, M4)
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError):
        return None


def extract(llm: LLMClient, report_id: str, sentences: list[Sentence], *, deployment: str | None = None,
            max_tokens: int | None = None, temperature: float | None = 0.0,
            reasoning_effort: str | None = None) -> tuple[ReportLabels | None, LLMResponse]:
    r = llm.complete(messages(sentences), "tier1", deployment=deployment, json_schema=SCHEMA,
                     max_tokens=max_tokens or llm.s.tier1_max_tokens, temperature=temperature,
                     reasoning_effort=reasoning_effort, purpose=f"tier1:{PROMPT_VERSION}")
    return parse(report_id, r.text), r
