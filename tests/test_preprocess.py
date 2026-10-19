from radlabel.preprocess.dedup import cluster
from radlabel.preprocess.sentences import report_sentences, split_sentences
from radlabel.preprocess.text import norm_text, redact


def test_redact_and_norm() -> None:
    assert redact("Sternotomy XXXX XXXX noted.") == "Sternotomy [REDACTED] [REDACTED] noted."
    assert norm_text("No XXXX effusion; 2.5 cm.") == "no effusion cm"


def test_sentence_ids_and_split_rules() -> None:
    s = report_sentences("Mild cardiomegaly. No effusion.", "1. No acute disease. 2. Stable 2.5 cm nodule.")
    assert [x.id for x in s] == ["F1", "F2", "I1", "I2"]
    assert s[2].text == "1. No acute disease."
    assert s[3].section == "impression" and "2.5 cm" in s[3].text
    assert split_sentences("Heart XXXX. Lungs clear.".replace("XXXX", "[REDACTED]")) == [
        "Heart [REDACTED].", "Lungs clear."]


def test_clusters_exact_and_near_duplicates() -> None:
    base = ("the heart is normal in size the mediastinum is unremarkable the lungs are clear there is no pleural "
            "effusion or pneumothorax the osseous structures are intact no acute cardiopulmonary abnormality "
            "the trachea is midline the costophrenic angles are sharp")
    c = cluster({
        "a": base, "b": base.upper() + " XXXX",           # exact after normalisation
        "c": base + " stable",                             # near-duplicate (Jaccard 0.97)
        "d": "large right pleural effusion with adjacent atelectasis",
    })
    assert c["a"] == c["b"] == c["c"]
    assert c["d"] != c["a"]
