"""eval_v1.2 is PERMANENTLY frozen at the end of M1 (SPEC §4.8). Changing these files is a hard
stop: it needs owner approval, an entry in docs/eval_changelog.md, and a new hash here."""

import hashlib
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1] / "eval"
FROZEN = {
    "lexicon.yaml": "765b701b4de741aba9e1ee11dbf8d2666e52104b161cd62c75598f480a436038",
    "negex_termset.yaml": "afa56974b6e8f06559e60f2204f96e94f76323cbf02c86a42914c75713106a50",
}


def digest(name: str) -> str:
    return hashlib.sha256((EVAL / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_eval_v1_is_frozen() -> None:
    assert {n: digest(n) for n in FROZEN} == FROZEN
