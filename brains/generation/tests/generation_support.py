"""Shared support for the Generation tests: one REAL publisher run (unchanged `publish()`) over the packaged release's catalog, answered from the
labelled hand-built fixtures (no network), and the pinned artifact build context. The release is exercised locally, never published from."""
import datetime as dt
import os
import uuid

import generation_brain  # noqa: F401
from generation_brain import knowledge as K, publish_artifact as pa
from generation_brain.fixtures import fixture_transport
from generation_brain.http import Fetcher
from generation_brain.publish import publish
from generation_brain.writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FIXTURES = os.path.join(HERE, "fixtures", "hand-built")
NOW = dt.datetime(2026, 11, 22, 20, 0, tzinfo=dt.timezone.utc)          # 2 PM CST at Guntersville
LAKES = ("Guntersville|AL", "Wheeler|AL", "Bull Shoals Lake|AR", "Lake Murray (SC)|SC")
_K = {}


def knowledge():
    if "k" not in _K:
        _K["k"] = K.load()
    return _K["k"]


def catalog(lakes=LAKES):
    cat = knowledge().catalog()
    return {**cat, "dams": [d for d in cat["dams"] if d["lakeId"] in lakes]}


def fetcher(access=None, transport=None):
    return Fetcher(access if access is not None else knowledge().access(), transport=transport or fixture_transport(FIXTURES), sleep=lambda s: None)


def run(now=NOW, lakes=LAKES, writer=None, scope="bound", transport=None):
    w = writer or DryRunWriter()
    f = fetcher(transport=transport)
    rep = publish(catalog(lakes), knowledge().access(), f, w, now, scope=scope, release=knowledge().summary())
    return rep, w, f


def run_updates(now=NOW, transport=None) -> dict:
    rep, w, _ = run(now=now, transport=transport)
    assert rep["ok"], rep["errors"]
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def build(updates, *, n=1, generated_at="2026-11-22T20:00:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, knowledge=knowledge(), consumed=consumed)
