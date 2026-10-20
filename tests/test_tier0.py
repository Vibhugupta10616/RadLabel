from radlabel.labelling.tier0 import key, label, learn


def test_learn_needs_three_normal_training_copies() -> None:
    a, b = key("Lungs are clear.", "No acute disease."), key("Heart normal.", "Normal chest.")
    assert learn([a, a, a, b, b]) == {a}


def test_label_matches_exact_normalised_text_only() -> None:
    pats = learn([key("Lungs are clear.", "No acute disease.")] * 3)
    hit = label("7", "LUNGS ARE CLEAR", "no acute disease!", pats)  # case/punctuation-insensitive
    assert hit is not None and hit.tier == 0 and hit.status("No Finding") == "present"
    assert all(x.status == "not_mentioned" for x in hit.labels if x.label != "No Finding")
    assert label("8", "Lungs are clear.", "Mild cardiomegaly.", pats) is None
