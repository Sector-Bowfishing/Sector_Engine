"""Wind's previous state derived from the LIVE Brain database (W-H2, Sector_Ops #51 decision D2). GET only.

In artifact mode Wind's own bookkeeping (brain/wind/last_publish.json) advances when the artifact is SEALED, even if the central path later refuses the
hand-off. Reading the previous state from what is live instead means "previous" is, by construction, what the Publisher accepted: nothing has to be
committed later, and the local file stays a cache only.

It reads, through a GET-only view (the Pulse read token; never a writer):
  * brains/wind                                  -> version, lastSuccessfulRun, lastError (as the one-item `errors` list)
  * lakeFleet/{k}/readiness/wind                 -> readiness, for each live Wind lake (the exact field publish() writes; the state object at
                                                    lakes/{k}/states/wind has no top-level readiness, so reading it found nothing and readiness
                                                    events were never emitted in read-live mode; fixed 2026-11-23)
  * lakes/{k}/profiles/wind/geometry/tableSha256 -> profileShas, for each nationally profiled lake
A missing node is "never published" (the field is left out). Any read error raises: the run then seals nothing rather than guess.
"""
from __future__ import annotations

from . import contract as C
from .lakes import WIND_LAKE_IDS


class ReadOnlyView:
    """Exposes get() only, so no code path can write through it whatever the token could do."""

    def __init__(self, inner):
        self._inner = inner

    def get(self, path: str, shallow: bool = False):
        return self._inner.get(path, shallow=shallow)


def live_previous(reader):
    """A previous(keys, national) callable for publish(previous=...). `reader` needs get(path); it is wrapped GET-only."""
    view = ReadOnlyView(reader)

    def load(keys: dict, national: dict) -> dict:
        reg = view.get(f"brains/{C.BRAIN_ID}") or {}
        if not isinstance(reg, dict):
            raise ValueError(f"brains/{C.BRAIN_ID} is not an object")
        readiness = {}
        for lid in WIND_LAKE_IDS.values():
            r = view.get(f"lakeFleet/{keys[lid]}/readiness/{C.SLOT}")
            if r is not None:
                readiness[lid] = r
        shas = {}
        for lid in national:
            s = view.get(f"lakes/{keys[lid]}/profiles/{C.SLOT}/geometry/tableSha256")
            if s is not None:
                shas[lid] = s
        err = (reg.get("lastError") or {}).get("message") if isinstance(reg.get("lastError"), dict) else None
        out = {"readiness": readiness, "profileShas": shas, "errors": [err] if err else []}
        for f in ("version", "lastSuccessfulRun"):
            if reg.get(f) is not None:
                out[f] = reg[f]
        return out

    return load
