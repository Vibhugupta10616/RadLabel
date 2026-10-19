"""Redaction token and text normalisation."""

import re

REDACTED = "[REDACTED]"
_XXXX = re.compile(r"X{4,}")


def redact(text: str) -> str:
    """Replace the IU de-identification token `XXXX` with `[REDACTED]`."""
    return _XXXX.sub(REDACTED, text)


def norm_text(text: str) -> str:
    """Normalisation used for exact-duplicate detection (README §3.3)."""
    t = text.lower().replace("xxxx", " ")
    t = re.sub(r"[^a-z ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()
