"""Product language (closed set). The Brain never says "grass is here", names a species, or claims submerged vegetation.

headline() is the ONLY place the Brain turns evidence into words. A statement of "observed" strength needs a validation
state of PARTIAL or better; below that the strongest wording is "Likely surface vegetation"."""
from __future__ import annotations

from . import contract as C

_STRONG = ("PARTIAL", "VALIDATED")


def headline(presence: str, validation_state: str, *, stale: bool, potential_only: bool = False) -> str:
    if potential_only:
        return C.LANGUAGE["POTENTIAL"]
    if stale or presence == "UNKNOWN":
        return C.LANGUAGE["NONE"]
    if presence == "NOT_OBSERVED":
        return C.LANGUAGE["NOT_OBSERVED"]
    if presence == "PRESENT":
        return C.LANGUAGE["OBSERVED"] if validation_state in _STRONG else C.LANGUAGE["LIKELY"]
    return C.LANGUAGE["NONE"]


def assert_clean(text: str) -> str:
    low = text.lower()
    for bad in C.FORBIDDEN_PHRASES:
        if bad in low:
            raise ValueError(f"forbidden product phrase {bad!r} in {text!r}")
    return text
