"""Per-Brain live enablement. Default: nothing is authorised. There is no environment switch and no module-level flag."""
from __future__ import annotations

from dataclasses import dataclass

from .model import NotAuthorized


@dataclass(frozen=True)
class BrainAuthorization:
    brain_id: str
    approval_ref: str             # the recorded approval (id/path of Michael's cutover approval); must be non-empty
    schemas: tuple = ()           # () = every schema registered for the Brain; otherwise only these


class LiveAuthorization:
    """Immutable allow-list. `LiveAuthorization()` authorises nothing."""

    def __init__(self, *grants: BrainAuthorization):
        for g in grants:
            if not (isinstance(g.approval_ref, str) and g.approval_ref.strip()):
                raise NotAuthorized(f"authorization for {g.brain_id!r} needs a non-empty approval_ref")
        self._g = {g.brain_id: g for g in grants}

    def check(self, brain_id: str, schema: str | None = None) -> BrainAuthorization:
        g = self._g.get(brain_id)
        if g is None:
            raise NotAuthorized(f"{brain_id!r} has no live authorization")
        if schema is not None and g.schemas and schema not in g.schemas:
            raise NotAuthorized(f"{brain_id!r} is not authorised for schema {schema!r}")
        return g

    def brains(self) -> tuple:
        return tuple(sorted(self._g))
