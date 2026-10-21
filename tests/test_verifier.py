"""One test (at least) per verifier rule, README §6.2."""

from radlabel.labelling.schema import LabelOut, ReportLabels
from radlabel.labelling.verifier import passed, verify
from radlabel.preprocess.sentences import report_sentences


def run(findings: str, impression: str, *labels: tuple[str, str, list[str]]) -> ReportLabels:
    out = ReportLabels(report_id="t", labels=[LabelOut(label=lab, status=st, evidence=ev)  # type: ignore[arg-type]
                                              for lab, st, ev in labels])
    return verify(out, report_sentences(findings, impression))


def checks(r: ReportLabels) -> set[tuple[str, str]]:
    return {(m.check, m.level) for m in r.verifier_messages}


def test_evidence_exists() -> None:
    r = run("Small left effusion.", "", ("Pleural Effusion", "present", []))
    assert ("evidence_exists", "fail") in checks(r)
    r = run("Small left effusion.", "", ("Pleural Effusion", "present", ["F7"]))
    assert ("evidence_exists", "fail") in checks(r)
    assert passed(run("Small left effusion.", "", ("Pleural Effusion", "present", ["F1"])))


def test_evidence_mentions_label_fail_and_redaction_flag() -> None:
    r = run("Heart size is normal. Small left effusion.", "", ("Pleural Effusion", "present", ["F1"]))
    assert ("evidence_mentions_label", "fail") in checks(r)
    r = run("Mild [REDACTED] atelectasis at the left base.", "", ("Pleural Effusion", "present", ["F1"]))
    assert ("evidence_mentions_label", "flag") in checks(r) and ("evidence_mentions_label", "fail") not in checks(r)


def test_negation_consistency() -> None:
    r = run("No pleural effusion.", "", ("Pleural Effusion", "present", ["F1"]))
    assert ("negation_consistency", "flag") in checks(r) and passed(r)  # flag, not fail (owner rule, M4)
    assert ("negation_consistency", "flag") not in checks(run("No pneumothorax but small effusion.", "",
                                                               ("Pleural Effusion", "present", ["F1"])))


def test_hedge_consistency_converts_to_uncertain() -> None:
    r = run("Possible small left effusion.", "", ("Pleural Effusion", "present", ["F1"]))
    assert r.status("Pleural Effusion") == "uncertain"
    assert ("hedge_consistency", "flag") in checks(r)


def test_no_finding_exclusivity() -> None:
    r = run("Mild cardiomegaly.", "No acute disease.",
            ("No Finding", "present", ["I1"]), ("Cardiomegaly", "present", ["F1"]))
    assert ("no_finding_exclusivity", "fail") in checks(r)


def test_section_rule_generic_impression_does_not_cancel_findings() -> None:
    """README §6.2: Findings "mild cardiomegaly" + Impression "no acute disease" -> Cardiomegaly stays present."""
    r = run("Mild cardiomegaly.", "No acute disease.", ("Cardiomegaly", "present", ["F1"]))
    assert r.status("Cardiomegaly") == "present" and passed(r)
    r = run("Mild cardiomegaly.", "No acute disease.", ("Cardiomegaly", "absent", ["I1"]))
    assert ("section_rule", "flag") in checks(r)  # generic Impression can't cancel a specific finding -> review


def test_section_rule_explicit_contradiction_wins() -> None:
    r = run("Questionable small effusion. Effusion at the left base.", "No pleural effusion.",
            ("Pleural Effusion", "present", ["F2"]))
    assert ("section_rule", "flag") in checks(r)
    assert passed(run("Effusion at the left base.", "No pleural effusion.", ("Pleural Effusion", "absent", ["I1"])))


def test_absent_evidence_normal_phrase_passes_else_flags() -> None:
    r = run("The lungs are clear.", "", ("Consolidation", "absent", ["F1"]))
    assert not r.verifier_messages                                 # label-scoped normal phrase
    r = run("No acute osseous abnormality.", "", ("Fracture", "absent", ["F1"]))
    assert not r.verifier_messages
    r = run("The heart is normal in size.", "", ("Fracture", "absent", ["F1"]))
    assert ("evidence_mentions_label", "flag") in checks(r) and passed(r)   # absent -> flag, never fail
    r = run("The lungs are clear.", "", ("Consolidation", "present", ["F1"]))
    assert ("evidence_mentions_label", "fail") in checks(r)       # present still needs the label


def test_no_finding_is_derived_not_checked() -> None:
    from radlabel.labelling.schema import derive_no_finding

    out = ReportLabels(report_id="t", labels=[LabelOut(label="No Finding", status="absent", evidence=["F9"]),
                                              LabelOut(label="Edema", status="uncertain", evidence=["F1"])])
    assert derive_no_finding(out).status("No Finding") == "not_mentioned"
    out = ReportLabels(report_id="t", labels=[LabelOut(label="Edema", status="absent", evidence=["F1"])])
    d = derive_no_finding(out)
    assert d.status("No Finding") == "present"
    assert not [m for m in verify(d, report_sentences("No edema.", "")).verifier_messages if m.label == "No Finding"]


def test_rule_a_absent_without_evidence_flags() -> None:
    r = run("Lungs are clear.", "", ("Support Devices", "absent", []))
    assert ("evidence_exists", "flag") in checks(r) and passed(r)
    assert ("evidence_exists", "fail") in checks(run("Lungs are clear.", "", ("Support Devices", "present", [])))


def test_rule_b_other_abnormality_evidence_flags() -> None:
    r = run("Enlarged pulmonary arteries.", "", ("Other Abnormality", "present", ["F1"]))
    assert ("evidence_mentions_label", "flag") in checks(r) and passed(r)


def test_rule_d_redacted_evidence_flags() -> None:
    r = run("Midline sternotomy [REDACTED].", "", ("Support Devices", "present", ["F1"]))
    assert ("evidence_mentions_label", "flag") in checks(r) and passed(r)
    r = run("Midline sternotomy changes.", "", ("Support Devices", "present", ["F1"]))
    assert ("evidence_mentions_label", "fail") in checks(r)


def test_hedge_consistency_definition_wording_is_not_a_hedge() -> None:
    """M6 fix: the Cardiomegaly definition counts mild/borderline enlargement as present, so it is not a hedge."""
    for f in ("Borderline cardiomegaly.", "Heart size is borderline.", "Borderline enlarged cardiac silhouette."):
        r = run(f, "", ("Cardiomegaly", "present", ["F1"]))
        assert r.status("Cardiomegaly") == "present" and ("hedge_consistency", "flag") not in checks(r), f
    r = run("Possible borderline cardiomegaly.", "", ("Cardiomegaly", "present", ["F1"]))  # a real hedge remains
    assert r.status("Cardiomegaly") == "uncertain" and ("hedge_consistency", "flag") in checks(r)
    r = run("Borderline small left effusion.", "", ("Pleural Effusion", "present", ["F1"]))  # label-scoped
    assert r.status("Pleural Effusion") == "uncertain"
