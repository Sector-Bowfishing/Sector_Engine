"""W-H2 (Sector_Ops #51 decision D2): Wind's previous state is read from what is LIVE (GET only), so a hand-off the central path refused can never
advance it. Local only: a dict stands in for the Brain database; no network, no writer."""
import uuid

import pytest

import artifact_entry as E
from sector_wind.brain import contract as C
from sector_wind.brain import publish as P
from sector_wind.brain.lakes import WIND_LAKE_IDS
from sector_wind.brain.live_previous import ReadOnlyView, live_previous
from sector_wind.brain.writer import DryRunWriter
from sector_wind.ingest import verified_release
from test_brain import CFG, DIRECTORY, NOW, make_store

KEYS = {lid: C.lake_key(lid) for lid in WIND_LAKE_IDS.values()}


class FakeDb:
    """GET-only stand-in for the Brain RTDB: path -> value. Records every path read."""

    def __init__(self, tree: dict | None = None, fail: str | None = None):
        self.tree, self.fail, self.reads = tree or {}, fail, []

    def get(self, path, shallow=False):
        self.reads.append(path)
        if self.fail and path.startswith(self.fail):
            raise RuntimeError("read failed")
        return self.tree.get(path)


def _kinds(writer):
    out = []
    for p in writer.patches:
        for k, v in p.items():
            if k.startswith("activity/") and isinstance(v, dict):
                out.append(v.get("kind"))
    return out


def test_maps_the_live_nodes_and_leaves_missing_ones_out():
    lid = next(iter(WIND_LAKE_IDS.values()))
    db = FakeDb({f"brains/{C.BRAIN_ID}": {"version": "v9", "lastSuccessfulRun": "2026-11-14T10:00:00Z", "lastError": {"message": "boom"}},
                 f"lakes/{KEYS[lid]}/states/{C.SLOT}/readiness": "CALIBRATION",
                 "lakes/Other_TN/profiles/wind/geometry/tableSha256": "abc"})
    prev = live_previous(db)(KEYS | {"Other|TN": "Other_TN", "Gone|TN": "Gone_TN"}, {"Other|TN": {}, "Gone|TN": {}})
    assert prev == {"version": "v9", "lastSuccessfulRun": "2026-11-14T10:00:00Z", "errors": ["boom"],
                    "readiness": {lid: "CALIBRATION"}, "profileShas": {"Other|TN": "abc"}}


def test_nothing_live_is_an_empty_previous():
    assert live_previous(FakeDb())(KEYS, {}) == {"readiness": {}, "profileShas": {}, "errors": []}


def test_the_view_is_get_only():
    v = ReadOnlyView(FakeDb())
    assert not any(hasattr(v, m) for m in ("patch", "put", "update", "set", "delete"))


def test_a_refused_hand_off_does_not_advance_previous(tmp_path):
    """Run 1 is sealed (local bookkeeping advances) but the central path refuses it: nothing reaches the database. Run 2 reading LIVE previous state
    still sees 'never registered' and re-sends; run 2 reading the local file would wrongly believe it was published."""
    st = make_store(tmp_path / "archive")
    P.publish(st, CFG, DryRunWriter(), now=NOW, directory=DIRECTORY)                     # run 1: sealed; local bookkeeping now says "registered"
    w_local, w_live = DryRunWriter(), DryRunWriter()
    P.publish(st, CFG, w_local, now=NOW, directory=DIRECTORY)
    P.publish(st, CFG, w_live, now=NOW, directory=DIRECTORY, previous=live_previous(FakeDb()))
    assert "brain.registered" not in _kinds(w_local)
    assert "brain.registered" in _kinds(w_live)


def test_an_accepted_hand_off_is_not_re_sent(tmp_path):
    st = make_store(tmp_path / "archive")
    w = DryRunWriter()
    P.publish(st, CFG, w, now=NOW, directory=DIRECTORY, previous=live_previous(FakeDb({f"brains/{C.BRAIN_ID}": {"version": C.BRAIN_VERSION}})))
    assert not {"brain.registered", "brain.version"} & set(_kinds(w))


def test_a_read_failure_seals_nothing(tmp_path):
    st = make_store(tmp_path / "archive")
    rep, built = E.build(st, CFG, now=NOW, run_summary=None, execution_id=str(uuid.uuid4()), code_version="wind@test",
                         release=verified_release(), directory=DIRECTORY, previous=live_previous(FakeDb(fail="brains/")))
    assert not rep["ok"] and not built.artifact


def test_rtdb_url_without_read_rtdb_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(E.TEST_CLOCK_ENV, "1")
    make_store(tmp_path / "archive")
    assert E.main(["--store", f"local:{tmp_path / 'archive'}", "--artifact-dir", str(tmp_path / "s"), "--skip-ingest",
                   "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "--rtdb-url", "https://example.invalid"]) == 2
    assert not (tmp_path / "s").exists()
