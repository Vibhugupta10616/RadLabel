"""The pipeline alias list is frozen at M3 (owner decision D5). A change needs owner approval and may only
be based on training-fold error analysis, never on out-of-fold or test results; then update this hash."""

import hashlib
import json

from radlabel.preprocess.aliases import aliases

FROZEN = "4b1c69665867cf069de709691cd88a564584a8c24c3e14ba4fa9d1704754caa1"


def test_alias_set_is_frozen() -> None:
    d = [[a.label, a.text, a.source, a.heldout, a.anchor] for v in aliases().values() for a in v]
    assert hashlib.sha256(json.dumps(d).encode()).hexdigest() == FROZEN
