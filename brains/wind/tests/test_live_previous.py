"""W-H2 (Sector_Ops #51 decision D2): Wind's previous state is read from what is LIVE (GET only), so a hand-off the central path refused can never
advance it. Local only: a dict stands in for the Brain database; no network, no writer."""
import json
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
                 f"lakeFleet/{KEYS[lid]}/readiness/{C.SLOT}": "CALIBRATION",
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


# ── end to end through artifact_entry.main (2026-11-23): a hand-off is "accepted" only when its writes are live ─────────────────────────────

class TreeDb:
    """GET-only Brain database stand-in with tree semantics: SET mutations of sealed artifacts are applied as the Publisher would apply them."""

    def __init__(self):
        self.tree = {}

    def apply(self, artifact: dict) -> None:
        for sec in artifact["sections"]:
            for m in sec["mutations"]:
                parts = [p for p in m["path"].strip("/").split("/") if p]
                node = self.tree
                for p in parts[:-1]:
                    node = node.setdefault(p, {})
                if m["op"] == "SET":
                    node[parts[-1]] = m["value"]
                else:
                    node.pop(parts[-1], None)

    def get(self, path, shallow=False):
        node = self.tree
        for p in [p for p in path.strip("/").split("/") if p]:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return node


@pytest.fixture
def live(monkeypatch):
    import sector_brain_platform as BP
    db = TreeDb()
    monkeypatch.setattr(P, "fetch_directory", lambda *a, **k: DIRECTORY)
    monkeypatch.setattr(BP, "BrainRtdb", lambda url, tokens: db)
    monkeypatch.setattr(BP, "TokenProvider", lambda: None)
    monkeypatch.setenv(E.TEST_CLOCK_ENV, "1")
    return db


def _run(tmp_path, n, *extra):
    emit = tmp_path / f"hand-off-{n}.json"
    rc = E.main(["--store", f"local:{tmp_path / 'archive'}", "--artifact-dir", str(tmp_path / f"store-{n}"), "--emit", str(emit),
                 "--skip-ingest", "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), *extra])
    return rc, (json.loads(emit.read_text()) if emit.exists() else None)


def _activity(artifact) -> list:
    return [m["value"]["kind"] for s in artifact["sections"] for m in s["mutations"]
            if m["path"].startswith("/activity/") and isinstance(m.get("value"), dict)]


def test_a_hand_off_without_read_rtdb_is_refused_and_changes_nothing(tmp_path, live):
    st = make_store(tmp_path / "archive")
    rc, art = _run(tmp_path, 1)
    assert rc == 2 and art is None
    assert not (tmp_path / "store-1").exists()
    assert st.get_json(E.BOOKKEEPING) is None


def test_a_read_live_seal_never_advances_the_local_bookkeeping(tmp_path, live):
    st = make_store(tmp_path / "archive")
    rc, art = _run(tmp_path, 1, "--read-rtdb")
    assert rc == 0 and art is not None
    assert st.get_json(E.BOOKKEEPING) is None                    # publish() wrote it; the read-live run put it back
    seeded = {"at": "2026-10-01T00:00:00Z", "version": "seeded"}
    st.put_json(E.BOOKKEEPING, seeded)
    assert _run(tmp_path, 2, "--read-rtdb")[0] == 0
    assert st.get_json(E.BOOKKEEPING) == seeded                  # a seeded cache is left exactly as it was


def test_refused_hand_off_is_re_sent_and_accepted_one_is_not(tmp_path, live):
    """Commit-after-acceptance, by construction (D2): run 1 is sealed and handed off. Refused (never applied live): run 2 re-registers and
    re-sends. Accepted (its writes applied live): run 3 sees it as previous and sends no registration event."""
    make_store(tmp_path / "archive")
    rc, first = _run(tmp_path, 1, "--read-rtdb")
    assert rc == 0 and "brain.registered" in _activity(first)
    rc, refused = _run(tmp_path, 2, "--read-rtdb")              # nothing reached the database
    assert rc == 0 and "brain.registered" in _activity(refused)
    live.apply(refused)                                          # the Publisher accepted this one
    rc, after = _run(tmp_path, 3, "--read-rtdb")
    assert rc == 0 and not {"brain.registered", "brain.version"} & set(_activity(after))


def test_live_previous_reads_back_what_publish_writes(tmp_path, live):
    """The paths live_previous reads are the paths publish() writes: an accepted artifact yields the same readiness, version and
    lastSuccessfulRun as Wind's own bookkeeping for that run (the 2026-11-23 readiness-path fix)."""
    st = make_store(tmp_path / "archive")
    rep, built = E.build(st, CFG, now=NOW, run_summary=None, execution_id=str(uuid.uuid4()), code_version="wind@test",
                         release=verified_release(), directory=DIRECTORY)
    assert rep["ok"], rep.get("errors")
    book = st.get_json(E.BOOKKEEPING)
    live.apply(built.artifact)
    keys = {l["id"]: C.lake_key(l["id"]) for l in DIRECTORY}
    prev = live_previous(live)(keys, {})
    assert prev["readiness"] == book["readiness"] and set(prev["readiness"]) == set(WIND_LAKE_IDS.values())
    assert (prev["version"], prev["lastSuccessfulRun"]) == (book["version"], book["lastSuccessfulRun"])


def test_a_readiness_change_after_an_accepted_publish_emits_its_event(tmp_path, live):
    lid = next(iter(WIND_LAKE_IDS.values()))
    make_store(tmp_path / "archive")
    rc, first = _run(tmp_path, 1, "--read-rtdb")
    live.apply(first)
    live.tree["lakeFleet"][C.lake_key(lid)]["readiness"][C.SLOT] = "DEGRADED"     # what was live differs from this run's readiness
    rc, nxt = _run(tmp_path, 2, "--read-rtdb")
    assert rc == 0 and {"readiness.promoted", "readiness.changed"} & set(_activity(nxt))
