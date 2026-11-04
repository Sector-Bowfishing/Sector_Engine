"""Lake artifact mode (Sector_Ops #48 A2): the recorded Swift write set, laid out as the dry-run folder, seals into the same artifact the shadow
builder makes, is stored create-only, and nothing writes a database. No Swift build, no network."""
import datetime as dt
import json
import os

import pytest

import artifact_entry as E
import publish_artifact as pa
from sector_brain_platform.publisher.storage import LocalDirObjectStore

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = json.load(open(os.path.join(HERE, "golden", "lake_run_updates.json")))


def lay_out(updates, d):
    for path, v in updates.items():
        f = os.path.join(d, path + ".json")
        os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump(v, open(f, "w"))
    os.makedirs(os.path.join(d, "_archive", "x"), exist_ok=True)                    # the job's local archive is not a path
    json.dump({"not": "a path"}, open(os.path.join(d, "_archive", "x", "a.json"), "w"))


def test_the_folder_round_trips_to_the_recorded_write_set(tmp_path):
    lay_out(GOLDEN, str(tmp_path))
    assert E.read_write_set(str(tmp_path)) == GOLDEN


def test_sealed_like_the_shadow_builder_and_stored_create_only(tmp_path, capsys):
    run, store = tmp_path / "run", tmp_path / "store"
    lay_out(GOLDEN, str(run))
    assert E.main(["--from-dir", str(run), "--artifact-dir", str(store)]) == 0
    ref = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    stored = json.loads(LocalDirObjectStore(str(store)).get(ref["location"]))
    expect = pa.build_artifact(GOLDEN, pa.BuildContext(stored["lineage"]["generatedAt"], stored["lineage"]["executionId"], stored["lineage"]["codeVersion"])).artifact
    assert stored["sections"] == expect["sections"] and stored["lineage"]["artifactSchema"] == expect["lineage"]["artifactSchema"]
    assert ref["location"].startswith("artifacts/lake-brain/") and stored["lineage"]["brainId"] == "lake-brain"
    assert not os.path.exists(os.path.join(str(store), "publishes"))                   # nothing published, only the artifact


def test_refusals_store_nothing(tmp_path):
    run, store = tmp_path / "run", tmp_path / "store"
    lay_out(GOLDEN, str(run))
    assert E.main(["--from-dir", str(run)]) == 2                                       # no target
    assert E.main(["--artifact-dir", str(store)]) == 2                                 # no source
    with pytest.raises(ValueError, match="delete"):
        E.seal({**GOLDEN, "lakes/Wilson_AL/states/lake": None}, now=dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc), code_version="t")
    assert not os.path.exists(str(store))


def test_a_failing_job_stores_nothing(tmp_path):
    job = tmp_path / "LakeBrainJob"
    job.write_text("#!/bin/sh\necho boom >&2\nexit 7\n"); job.chmod(0o755)
    assert E.main(["--job", str(job), "--artifact-dir", str(tmp_path / "store")]) == 3
    assert not os.path.exists(str(tmp_path / "store"))


def test_the_entry_has_no_database_writer():
    src = open(E.__file__).read()
    assert "BrainRtdb" not in src and "RtdbRestPublisherClient" not in src and ".update(" not in src


@pytest.mark.parametrize("args", [["--fault", "cwms-unreachable", "--artifact-bucket", "b"], ["--fault=cwms-unreachable"]])
def test_a_rehearsal_fault_is_refused_unless_the_artifact_stays_local(args, capsys):
    """Sector_Ops #48 B4b: a fault-injected artifact must never reach a bucket the Publisher reads."""
    assert E.main(["--job", "/nonexistent/LakeBrainJob"] + args) == 2
    assert "needs --artifact-dir" in capsys.readouterr().err


def test_a_rehearsal_fault_is_passed_to_the_job():
    import argparse
    ap = argparse.ArgumentParser()
    E._job_args(ap)
    a = ap.parse_args(["--fault", "cwms-unreachable"])
    a.job, a.read_rtdb = "LakeBrainJob", None
    assert E._job_command(a, "D")[-2:] == ["--fault", "cwms-unreachable"]
def test_seed_archive_and_presence_are_forwarded_to_the_job():
    import argparse
    ap = argparse.ArgumentParser()
    E._job_args(ap)
    a = ap.parse_args(["--seed-archive", "gs://seed", "--presence", "DIR"])
    a.job, a.read_rtdb = "LakeBrainJob", None
    cmd = E._job_command(a, "D")
    assert cmd[cmd.index("--seed-archive") + 1] == "gs://seed" and cmd[cmd.index("--presence") + 1] == "DIR"
