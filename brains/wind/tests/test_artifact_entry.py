"""Wind artifact mode for a runner's lease cycle (artifact_entry.py; Sector_Ops #51, Roadmap #23 section 2). Local only: tmp stores, no network,
no database. The write set is the UNCHANGED publish() against a DryRunWriter, sealed as one wind-publication-v1 bundle with the release lineage."""
import json
import uuid

import pytest

import artifact_entry as E
from sector_wind.brain import publish as P
from sector_wind.ingest import verified_release
from sector_brain_platform.knowledge_release import lineage_triple
from sector_brain_platform.publisher.storage import LocalDirObjectStore
from test_brain import CFG, DIRECTORY, NOW, make_store

NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def no_directory_fetch(monkeypatch):
    monkeypatch.setattr(P, "fetch_directory", lambda *a, **k: DIRECTORY)


def test_build_seals_one_bundle_with_the_release_lineage(tmp_path):
    st = make_store(tmp_path / "archive")
    rep, built = E.build(st, CFG, now=NOW, run_summary={"runAt": NOW_ISO, "errors": [], "seconds": 1}, execution_id=str(uuid.uuid4()),
                         code_version="wind@test", release=verified_release(), directory=DIRECTORY)
    assert rep["ok"], rep.get("errors")
    lin = built.artifact["lineage"]
    kr, mref, msha = lineage_triple(verified_release())
    assert lin["brainId"] == "wind"
    assert (lin["knowledgeRelease"], lin["manifestRef"], lin["manifestSha256"]) == (kr, mref, msha)
    assert lin["artifactSchema"] == "wind-publication-v1"


def test_main_stores_create_only_and_emits_the_hand_off(tmp_path, no_directory_fetch):
    make_store(tmp_path / "archive")
    out, emit = tmp_path / "store", tmp_path / "artifact.json"
    args = ["--store", f"local:{tmp_path / 'archive'}", "--artifact-dir", str(out), "--emit", str(emit), "--skip-ingest", "--now", NOW_ISO]
    assert E.main(args) == 0
    art = json.loads(emit.read_text())
    assert art["lineage"]["brainId"] == "wind"
    keys = [k for k in LocalDirObjectStore(str(out)).list("artifacts/wind/")]
    assert len(keys) == 1
    assert E.main(args) == 2                                  # the hand-off file exists: never overwritten


@pytest.mark.parametrize("bad", [
    ["--store", "gs://sector-wind-candidate/wind/v1", "--artifact-dir", "X"],
    ["--store", "local:/x", "--artifact-dir", "gs://bucket"],
    ["--store", "local:/x", "--artifact-dir", "X", "--now", "2026-10-12T06:20:00Z"],       # --now without --skip-ingest
    ["--store", "local:/x", "--artifact-dir", "X", "--skip-ingest", "--now", "yesterday"],
    ["--store", "local:/x", "--artifact-dir", "X", "--execution-id", "not-a-uuid"],
    ["--store", "local:/x", "--artifact-dir", "X", "--emit", "gs://b/artifact.json"],
])
def test_refusals_store_nothing(bad, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert E.main(bad) == 2
    assert not (tmp_path / "X").exists()


def test_no_database_writer_even_with_the_legacy_env(tmp_path, no_directory_fetch, monkeypatch):
    monkeypatch.setenv("SECTOR_WIND_BRAIN_RTDB_URL", "https://example.invalid")
    import sector_wind.brain.writer as W

    def boom(*a, **k):
        raise AssertionError("artifact mode must never build an RtdbWriter")
    monkeypatch.setattr(W, "RtdbWriter", boom)
    make_store(tmp_path / "archive")
    assert E.main(["--store", f"local:{tmp_path / 'archive'}", "--artifact-dir", str(tmp_path / "s"), "--skip-ingest", "--now", NOW_ISO]) == 0


def test_a_failed_publish_stores_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "fetch_directory", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("engine down")))
    make_store(tmp_path / "archive")
    assert E.main(["--store", f"local:{tmp_path / 'archive'}", "--artifact-dir", str(tmp_path / "s"), "--skip-ingest", "--now", NOW_ISO]) == 3
    assert not (tmp_path / "s").exists() or not list(LocalDirObjectStore(str(tmp_path / "s")).list("artifacts/wind/"))
