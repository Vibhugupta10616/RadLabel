"""Label set (SPEC §4.4). Shared by serving and evaluation; holds no expert data."""

NO_FINDING = "No Finding"
OTHER = "Other Abnormality"

HEADLINE = [
    NO_FINDING,
    "Cardiomegaly",
    "Lung Opacity",
    "Lung Lesion",
    "Atelectasis",
    "Pleural Effusion",
    "Fracture",
    "Support Devices",
    OTHER,
]
RARE = ["Edema", "Pleural Other", "Consolidation", "Pneumothorax"]
LABELS = HEADLINE + RARE
FINDING_LABELS = [lab for lab in LABELS if lab not in (NO_FINDING, OTHER)]

STATUSES = ("present", "absent", "uncertain", "not_mentioned")
