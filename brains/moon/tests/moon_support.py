"""Shared support for the Moon tests: one REAL dry-run publish (unchanged `publish()`) over a fixed slice of the packaged lake directory into an
in-memory store, and the pinned artifact build context. Offline; nothing is published."""
import datetime as dt
import os
import uuid

import moon_brain  # noqa: F401
from moon_brain import lakes as L, publish_artifact as pa
from moon_brain.publish import publish
from moon_brain.writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NOW = dt.datetime(2026, 11, 22, 19, 0, tzinfo=dt.timezone.utc)
NIGHT = dt.date(2026, 11, 22)
SLICE = ("Guntersville|AL", "Lake Martin|AL", "Iliamna|AK", "Teshekpuk|AK")
_D = {}


def directory(only=SLICE) -> dict:
    if "d" not in _D:
        _D["d"] = L.load()
    d = _D["d"]
    return {**d, "lakes": [r for r in d["lakes"] if only is None or r["lakeId"] in only]}


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(date=NIGHT, weather=None, only=SLICE) -> dict:
    w = DryRunWriter()
    rep = publish(directory(only), w, date, weather, now=NOW)
    assert rep["ok"], rep["errors"]
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def build(updates, *, n=1, generated_at="2026-11-22T19:00:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, release_lineage=L.lineage(), consumed=consumed)
