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
    assert ("negation_consistency", "fail") in checks(r)
    assert ("negation_consistency", "fail") not in checks(run("No pneumothorax but small effusion.", "",
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
    assert ("section_rule", "fail") in checks(r)  # generic Impression can't cancel a specific finding


def test_section_rule_explicit_contradiction_wins() -> None:
    r = run("Questionable small effusion. Effusion at the left base.", "No pleural effusion.",
            ("Pleural Effusion", "present", ["F2"]))
    assert ("section_rule", "fail") in checks(r)
    assert passed(run("Effusion at the left base.", "No pleural effusion.", ("Pleural Effusion", "absent", ["I1"])))
