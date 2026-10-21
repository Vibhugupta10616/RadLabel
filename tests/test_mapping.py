import pytest

from data_prep.mapping import expert_labels, load_mapping

V1, STRICT = load_mapping("v1"), load_mapping("strict")


@pytest.mark.parametrize("codes, expected", [
    (["normal"], {"No Finding"}),
    (["Technical Quality of Image Unsatisfactory"], set()),
    (["normal", "Cardiomegaly/mild"], {"Cardiomegaly"}),
    (["Hydropneumothorax/right"], {"Pleural Effusion", "Pneumothorax"}),
    (["Fractures, Bone/ribs"], {"Fracture"}),
    (["Catheters, Indwelling"], {"Support Devices"}),
    (["Calcified Granuloma/lung/upper lobe/right"], {"Other Abnormality"}),
    (["Pulmonary Congestion"], {"Other Abnormality"}),       # not Edema (SPEC §4.4)
    (["Pneumonia/lower lobe"], {"Other Abnormality"}),       # dropped label
    (["Mediastinum/prominent"], {"Other Abnormality"}),      # dropped label
    (["Opacity/hilum"], {"Other Abnormality"}),              # non-lung site
    (["Opacity/lung/base"], {"Lung Opacity"}),
    # Lung Opacity broadened to any lung site; site check on all sub-headings (owner, 2026-10-20)
    (["Opacity/left/base"], {"Lung Opacity"}),
    (["Density/costophrenic angle/left"], {"Lung Opacity"}),
    (["Opacity/sulcus/posterior"], {"Lung Opacity"}),
    (["Airspace Disease/retrocardiac"], {"Lung Opacity"}),
    (["Opacity/lung/hilum/right"], {"Lung Opacity"}),         # first sub `lung` wins over later hilum
    (["Nodule/lung/hilum"], {"Lung Lesion"}),
    (["Opacity/right/hilum"], {"Other Abnormality"}),         # first sub not lung, later non-lung site
    (["Mass/right/paratracheal"], {"Other Abnormality"}),
    (["Density/heart"], {"Other Abnormality"}),
    (["Opacity/supracardiac"], {"Other Abnormality"}),
    (["Nodule/pleura"], {"Pleural Other"}),                   # pleural site -> Pleural Other
    (["Opacity/pleural sinus"], {"Pleural Other"}),
    (["Contrast Media/abdomen/left"], set()),                 # ignored like Technical Quality
    # Lung Lesion needs a lung site (SPEC §4.4)
    (["Nodule/lung/upper lobe/right"], {"Lung Lesion"}),
    (["Nodule"], {"Lung Lesion"}),
    (["Nodule/scattered"], {"Lung Lesion"}),
    (["Cysts/humerus/right/large"], {"Other Abnormality"}),
    (["Cysts/lung/upper lobe/left"], {"Other Abnormality"}),  # Cysts removed from Lung Lesion
    (["Sutures/lung/apex/right"], {"Other Abnormality"}),     # not a CheXpert support-devices mention
    (["Mass/breast/left"], {"Other Abnormality"}),
    (["Nodule/thorax"], {"Other Abnormality"}),
    # Pleura with a "blunted" sub-heading anywhere is not Pleural Other
    (["Pleura/blunted/mild"], {"Other Abnormality"}),
    (["Pleura/right/blunted"], {"Other Abnormality"}),
    (["Pleura/base/bilateral/abnormal/chronic"], {"Pleural Other"}),
])
def test_v1(codes: list[str], expected: set[str]) -> None:
    assert V1.map_codes(codes) == expected


def test_strict_keeps_no_finding_and_other_and_excludes_v1_only() -> None:
    e = expert_labels(["Density/lung", "Scoliosis", "Stents"], V1, STRICT)
    assert e["v1"] == ["Lung Opacity", "Other Abnormality", "Support Devices"]
    assert e["strict"] == ["Other Abnormality"]
    assert e["strict_excluded"] == ["Lung Opacity", "Support Devices"]
    assert expert_labels(["Implanted Medical Device/left"], V1, STRICT)["strict"] == ["Support Devices"]
    assert expert_labels(["normal"], V1, STRICT)["strict"] == ["No Finding"]


def test_strict_lung_site_rule() -> None:
    assert STRICT.map_codes(["Mass/mediastinum"]) == {"Other Abnormality"}
    assert expert_labels(["Mass/mediastinum"], V1, STRICT)["strict"] == ["Other Abnormality"]
    assert expert_labels(["Cavitation/lung"], V1, STRICT)["strict_excluded"] == ["Lung Lesion"]
