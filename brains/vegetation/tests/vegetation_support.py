"""Shared support for the Vegetation certification tests: one REAL dry-run publish (unchanged `publish()`) of the packaged release (fleet manifest +
agency records) into an in-memory store, and the pinned artifact build context. Offline; the release is exercised locally, never published from."""
import datetime as dt
import os
import uuid

import vegetation_brain  # noqa: F401
from vegetation_brain import knowledge as K, publish_artifact as pa
from vegetation_brain.publish import publish
from vegetation_brain.writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NOW = dt.datetime(2026, 10, 14, 19, 0, tzinfo=dt.timezone.utc)
_K = {}


def knowledge():
    if "k" not in _K:
        _K["k"] = K.load()
    return _K["k"]


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(drop_agency_lake=None) -> dict:
    k = knowledge()
    agency = k.json("agency_fwc_pacpvi.json")["records"]
    if drop_agency_lake:
        agency = {lid: r for lid, r in agency.items() if lid != drop_agency_lake}
    w = DryRunWriter()
    rep = publish(k.json("fleet.json"), w, now=NOW, agency=agency, littoral=k.json("agency_sfwmd_okeechobee.json")["records"], release=k.summary())
    assert rep["ok"], rep["errors"]
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def build(updates, *, n=1, generated_at="2026-10-14T19:00:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, knowledge=knowledge(), consumed=consumed)
