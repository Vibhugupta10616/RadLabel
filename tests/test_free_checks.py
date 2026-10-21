"""Free checks (README §6.2, M7): v2 escalation rules, recall scan, normal check. One test per rule."""

from test_repair_agent import tier1

from radlabel.labelling.free_checks import escalations, normal_check
from radlabel.labelling.schema import LabelOut, ReportLabels, derive_no_finding
from radlabel.labelling.verifier import verify
from radlabel.labels import LABELS
from radlabel.preprocess.sentences import report_sentences


def tagged(findings: str, impression: str, **over: tuple[str, list[str]]) -> tuple[ReportLabels, list]:
    sents = report_sentences(findings, impression)
    labs = {lab: LabelOut(label=lab, status="not_mentioned") for lab in LABELS}
    for k, (st, ev) in over.items():
        labs[k.replace("_", " ")] = LabelOut(label=k.replace("_", " "), status=st, evidence=ev)  # type: ignore
    return verify(derive_no_finding(ReportLabels(report_id="t", labels=list(labs.values()))), sents), sents


def reasons(findings: str, impression: str, **over: tuple[str, list[str]]) -> set[tuple[str, str]]:
    v, s = tagged(findings, impression, **over)
    return {(e.label, e.reason) for e in escalations(v, s)}


def test_fail_escalates() -> None:
    assert ("Cardiomegaly", "evidence_mentions_label") in {(e.label, e.reason) for e in escalations(
        tier1(Cardiomegaly=("present", ["F1"])), report_sentences("Heart is large. No pleural effusion.",
                                                                 "Cardiomegaly."))}


def test_escalating_flags_and_recorded_only_flags() -> None:
    assert ("Pleural Effusion", "negation_consistency") in reasons("No pleural effusion.", "",
                                                                   Pleural_Effusion=("present", ["F1"]))
    assert ("Pleural Effusion", "hedge_consistency") in reasons("Possible small left effusion.", "",
                                                                Pleural_Effusion=("present", ["F1"]))
    assert ("Cardiomegaly", "section_rule") in reasons("Mild cardiomegaly.", "No acute disease.",
                                                       Cardiomegaly=("absent", ["I1"]))
    assert ("Support Devices", "evidence_mentions_label") in reasons(
        "Midline sternotomy [REDACTED].", "", Support_Devices=("present", ["F1"]))  # [REDACTED] on present
    # recorded only: absent without evidence, absent with generic evidence, Other Abnormality flag
    r = reasons("Lungs are clear. Enlarged pulmonary arteries.", "",
                Support_Devices=("absent", []), Fracture=("absent", ["F1"]), Other_Abnormality=("present", ["F2"]))
    assert not {x for x in r if x[1] != "recall_scan" and x[0] != "No Finding"}


def test_generic_impression_keeps_findings_and_does_not_escalate() -> None:
    """README §6.2: Findings "mild cardiomegaly" + Impression "no acute disease" -> Cardiomegaly stays present."""
    v, s = tagged("Mild cardiomegaly.", "No acute disease.", Cardiomegaly=("present", ["F1"]))
    assert v.status("Cardiomegaly") == "present" and not escalations(v, s)


def test_recall_scan() -> None:
    assert ("Pleural Effusion", "recall_scan") in reasons("Small left pleural effusion.", "",
                                                          Pleural_Effusion=("not_mentioned", []))
    assert not reasons("Small left pleural effusion.", "", Pleural_Effusion=("present", ["F1"]))


def test_normal_check_needs_heart_and_lungs_and_nothing_abnormal() -> None:
    assert normal_check(report_sentences("Heart size is normal. The lungs are clear.", "Negative.")).ok
    nc = normal_check(report_sentences("", "No acute cardiopulmonary abnormality."))
    assert not nc.ok and nc.missing == ["heart", "lungs"]  # a general statement covers no region
    nc = normal_check(report_sentences("Normal heart size. Lungs clear. Calcified granuloma.", "No acute disease."))
    assert not nc.ok and "Other Abnormality" in nc.abnormal
    nc = normal_check(report_sentences("Heart size normal. Lungs are clear. No pneumothorax. No acute bony "
                                       "abnormality.", ""))
    assert nc.ok and {"pleura", "bones"} <= set(nc.covered)  # recorded, not required


def test_every_predicted_no_finding_is_checked() -> None:
    assert ("No Finding", "normal_check") in reasons("", "No acute cardiopulmonary abnormality.")
    assert not reasons("Heart size is normal. The lungs are clear.", "No acute disease.",
                       Cardiomegaly=("absent", ["F1"]))
