"""Shared support for the Depth certification tests: one REAL publisher run (unchanged `publish()`) on the pilot lakes of the packaged release, with
synthetic Lake Brain states, and the pinned artifact build context. Offline; the release is exercised locally, never published from."""
import datetime as dt
import os
import uuid

import depth_brain  # noqa: F401
from depth_brain import knowledge as K, publish_artifact as pa
from depth_brain.publish import publish
from depth_brain.writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_K = {}


def knowledge():
    if "k" not in _K:
        _K["k"] = K.load()
    return _K["k"]


def manifest():
    if "m" not in _K:
        _K["m"] = knowledge().json("candidates.json")
    return _K["m"]


def pilot_states(elev_offset=-1.4):
    out = {}
    for c in manifest()["candidates"]:
        if c["rollout"] == "PILOT_VERIFIED":
            out[c["lakeId"]] = {"kind": "OBSERVED", "sourceCapability": c["levelSource"]["capability"] or "DIRECT_OPERATOR_POOL",
                                "currentElevationFt": c["reference"]["poolFt"] + elev_offset, "unit": "ft", "observationTime": "2026-10-14T18:00:00Z",
                                "freshness": {"stale": False}, "provenance": {"brainVersion": "1.0.0"}}
    return out


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(generated_at="2026-10-14T19:00:00Z", elev_offset=-1.4) -> dict:
    now = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    w = DryRunWriter()
    rep = publish(manifest(), pilot_states(elev_offset), w, now, release=knowledge().summary())
    assert rep["ok"], rep["errors"]
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def build(updates, *, n=1, generated_at="2026-10-14T19:00:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, knowledge=knowledge(), consumed=consumed)
