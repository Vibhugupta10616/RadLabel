from radlabel.preprocess.aliases import HELDOUT_FRACTION, aliases, normalise
from radlabel.preprocess.negation import mentions, redaction_adjacent


def find(text: str, label: str) -> list[tuple[bool, bool, bool]]:
    return [(m.negated, m.hedged, m.asserted) for m in mentions(text) if m.label == label]


def test_negation_list_scope() -> None:
    t = "No focal airspace consolidation, pleural effusion, or pneumothorax."
    assert find(t, "Consolidation") == [(True, False, True)]
    assert find(t, "Pleural Effusion") == [(True, False, True)]
    assert find(t, "Pneumothorax") == [(True, False, True)]


def test_clause_boundary_stops_negation() -> None:
    t = "No pneumothorax but there is a small left effusion."
    assert find(t, "Pneumothorax")[0][0] is True
    assert all(not neg for neg, _, _ in find(t, "Pleural Effusion"))


def test_following_and_weak_negation() -> None:
    assert find("The effusion has resolved.", "Pleural Effusion")[0][0] is True
    assert all(neg for neg, _, _ in find("Heart size is normal.", "Cardiomegaly"))
    assert all(neg for neg, _, _ in find("Normal heart size.", "Cardiomegaly"))


def test_pseudo_negation() -> None:
    assert find("No change in the small right pleural effusion.", "Pleural Effusion")[0][0] is False


def test_hedge() -> None:
    assert find("Possible small left effusion.", "Pleural Effusion")[0] == (False, True, True)
    assert find("Atelectasis versus pneumonia.", "Atelectasis")[0][1] is True


def test_anchor_needs_enlargement_word() -> None:
    assert find("Stable cardiac silhouette.", "Cardiomegaly") == [(False, False, False)]
    assert any(a for _, _, a in find("The cardiac silhouette is enlarged.", "Cardiomegaly"))


def test_longer_span_of_other_label_wins() -> None:
    labs = {m.label for m in mentions("Mild right pleural thickening.")}
    assert "Pleural Other" in labs and "Other Abnormality" not in labs


def test_redaction_adjacent() -> None:
    assert redaction_adjacent("Small [REDACTED] effusion.")
    assert not redaction_adjacent("[REDACTED] views of the chest were obtained today for comparison.")


def test_aliases_heldout_rule_and_independence() -> None:
    for lab, als in aliases().items():
        pool = [a for a in als if a.tokens != normalise(lab).split()]
        assert sum(a.heldout for a in als) == round(HELDOUT_FRACTION * len(pool))
        assert not any(a.heldout and a.tokens == normalise(lab).split() for a in als)  # label name never held out
    assert any(a.source == "chexpert" for a in aliases()["Lung Opacity"])
