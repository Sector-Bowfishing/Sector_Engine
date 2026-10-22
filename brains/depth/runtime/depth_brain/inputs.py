"""Depth's live inputs: published Lake Brain state only (Brain RTDB GET). Depth never reads raw level feeds or Lake's implementation."""
from __future__ import annotations

import json


def load_lake_states(spec: str, manifest: dict) -> dict:
    """spec: "rtdb:<url>" (live GET reads) or "file:<path>" (a saved {lakeId: states/lake} map, for local dry runs)."""
    kind, _, val = spec.partition(":")
    if kind == "file":
        with open(val, encoding="utf-8") as fh:
            return json.load(fh)
    if kind == "rtdb":
        from sector_brain_platform import BrainRtdb, lake_key
        db = BrainRtdb(val, brain_id="depth")
        fleet = db.get("lakeFleet") or {}                                   # one read: which lakes have a published Lake Brain slot
        has_lake = {k for k, v in fleet.items() if isinstance(v, dict) and (v.get("readiness") or {}).get("lake")}
        out = {}
        for c in manifest["candidates"]:
            k = lake_key(c["lakeId"])
            if not c.get("shiftPossible") or (has_lake and k not in has_lake):
                continue
            s = db.get(f"lakes/{k}/states/lake")
            if s:
                out[c["lakeId"]] = s
        return out
    raise ValueError(f"unknown lake-states spec {spec!r}")
