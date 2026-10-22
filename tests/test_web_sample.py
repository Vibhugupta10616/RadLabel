"""The frontend shows the sample patient's texts from its own copy (web/src/sample/); it must equal data/sample/."""

from pathlib import Path

from radlabel.api import sample

WEB = Path(__file__).resolve().parents[1] / "web" / "src" / "sample"


def test_frontend_sample_texts_match_the_backend_sample() -> None:
    for name, text in zip(sample.FILES, sample.texts(), strict=True):
        assert (WEB / name).read_text(encoding="utf-8").replace("\r\n", "\n") == text, name
