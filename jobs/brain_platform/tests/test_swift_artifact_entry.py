"""The shared Swift-Brain artifact entry (Lake, Water Temperature): folder round trip, delete refusal, the job's command line, and no database writer."""
import datetime as dt
import json
import os
import types

import pytest

from sector_brain_platform import swift_artifact_entry as SE


def test_underscore_folders_are_not_paths(tmp_path):
    (tmp_path / "brains" / "x").mkdir(parents=True)
    (tmp_path / "brains" / "x" / "status.json").write_text('"OK"')
    (tmp_path / "_archive").mkdir()
    (tmp_path / "_archive" / "a.json").write_text("{}")
    assert SE.read_write_set(str(tmp_path)) == {"brains/x/status": "OK"}


def test_a_delete_is_refused_before_the_builder_runs():
    builder = types.SimpleNamespace(build_artifact=lambda *a, **k: pytest.fail("builder called"), BuildContext=lambda *a: None)
    with pytest.raises(ValueError, match="delete"):
        SE.seal(builder, {"brains/x/status": None}, now=dt.datetime(2026, 11, 3, tzinfo=dt.timezone.utc), code_version="t")


def test_the_brain_decides_its_job_command(tmp_path):
    seen = []
    job = tmp_path / "Job"
    job.write_text("#!/bin/sh\necho \"$@\" > \"$3/args.txt\"; exit 9\n"); job.chmod(0o755)

    def cmd(a, td):
        seen.append(td)
        return [a.job, "--dry-run", td, "--read-rtdb", a.read_rtdb]
    assert SE.main(["--job", str(job), "--read-rtdb", "https://x", "--artifact-dir", str(tmp_path / "s")], brain_id="b", builder=None,
                   bucket_env="NONE", add_job_args=lambda ap: None, job_command=cmd) == 3
    assert seen and not os.path.exists(tmp_path / "s")


def test_no_database_writer_in_the_shared_entry():
    src = open(SE.__file__).read()
    assert "BrainRtdb" not in src and "RtdbRestPublisherClient" not in src and ".update(" not in src
