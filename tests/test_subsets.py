import data_prep.subset_stats as ref
from eval import subsets
from eval.subsets import mentions, negation_only_labels


def test_reference_definitions_are_used_unchanged() -> None:
    assert subsets.is_hedged is ref.is_hedged
    assert subsets.is_redaction_adjacent is ref.is_redaction_adjacent
    assert subsets.HEDGE is ref.HEDGE


def test_negation_only_pairs() -> None:
    m = mentions("No pneumothorax. Small left effusion.", "")
    assert negation_only_labels(m, {"Pleural Effusion"}) == ["Pneumothorax"]
    # expert code present -> not a pair
    assert negation_only_labels(m, {"Pleural Effusion", "Pneumothorax"}) == []
    # any mention in a hedged sentence excludes the pair
    m = mentions("No pneumothorax. Possible small pneumothorax at the apex.", "")
    assert negation_only_labels(m, set()) == []
    # mixed negated + clear mention -> not a pair
    m = mentions("No effusion on the left. Small right effusion.", "")
    assert negation_only_labels(m, set()) == []


def test_lemma_matching_overlaps_and_resolution() -> None:
    assert mentions("Bilateral Effusions.", "") == {"Pleural Effusion": [(False, False)]}
    m = mentions("Moderate right pleural effusion with air fluid level.", "")
    assert "Pneumothorax" in m and "Pleural Effusion" in m           # shared alias counts for both labels
    assert all(neg for neg, _ in mentions("The effusion has resolved.", "")["Pleural Effusion"])
