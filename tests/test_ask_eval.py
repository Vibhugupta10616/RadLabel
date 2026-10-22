"""M10b answer parsing (pre-registered rules, eval/ask.py): the scoring is only as exact as these."""

from eval import ask as ev
from radlabel.api.ask import NOT_STATED


def test_yes_no_classes() -> None:
    p = ev.parse_yn
    assert p("Yes, there is a small left pleural effusion.", None) == "yes"
    assert p("There is a small left pleural effusion.", None) == "yes"  # an affirmative statement
    assert p("No, there is no pneumothorax.", None) == "no"
    assert p("The lungs are clear and there is no effusion.", None) == "no"
    assert p("The report does not mention a fracture.", None) == "no"
    assert p("Possible atelectasis at the left base.", None) == "uncertain"
    assert p("Yes, a possible nodule is described.", None) == "uncertain"  # a hedge wins over "yes"
    assert p(None, NOT_STATED) == "notstated"
    assert p(None, "I cannot provide advice on treatment or medication.") == "refused"


def test_certainty() -> None:
    c = ev.parse_certainty
    assert c("The opacity is stated plainly in the findings.", None) == "certain"
    assert c("The opacity is described as possible.", None) == "possible"
    assert c("No lung opacity is mentioned.", None) == "none"
    assert c(None, NOT_STATED) == "none"


def test_report_sets() -> None:
    w = ev.parse_which
    assert w("Reports 2, 5 and 7 describe an enlarged heart.", None) == {2, 5, 7}
    assert w("An enlarged heart is described in report 3.", None) == {3}
    assert w("Reports 4-6 describe it.", None) == {4, 5, 6}
    assert w("No reports describe an enlarged heart.", None) == set()
    assert w(None, NOT_STATED) == set()
    assert w("Several reports do.", None) is None  # unreadable counts as wrong
    assert w("Yes, reports 1 and 12.", None) == {1, 12}


def test_counts_and_first_mention() -> None:
    assert ev.parse_count("A pleural effusion is present in 3 reports.", None) == 3
    assert ev.parse_count("It is present in two of the 10 reports.", None) == 2
    assert ev.parse_count("None of the reports describe it.", None) == 0
    assert ev.parse_count("Not sure.", None) is None
    assert ev.parse_first("The pacemaker was first described in report 3 as new.", None) == 3
    assert ev.parse_first("No report mentions a device.", None) == "none"
    assert ev.parse_first(None, NOT_STATED) == "none"


def test_post_hoc_lenient_refusal() -> None:
    from eval.ask_score import lenient_refusal as ok
    assert ok({"answer": None})
    assert ok({"answer": "The reports do not state the exact age of the patient, only that it is a [REDACTED]-year-old."})
    assert ok({"answer": "The reports do not provide details about the findings of the CT scan."})
    assert not ok({"answer": "The patient is a [REDACTED]-year-old male."})  # no "not stated"
    assert not ok({"answer": "The report does not state it, but the patient is 45 years old."})  # an invented number
    assert not ok({"answer": "It does not say; this could be cancer."})
