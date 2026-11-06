"""runner.py upload / renew / show against a local store (Sector_Ops #50). No network, no credential."""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform", "tests"))
import runner as R                                                         # noqa: E402
from publisher_fixtures import wind_artifact                               # noqa: E402
from sector_brain_platform import runner_lease as RL                       # noqa: E402
from sector_brain_platform.publisher.storage import LocalDirObjectStore    # noqa: E402

POLICY = {"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {"wind": "pulse"}, "failover": {"enabled": False, "brains": []}}
TIMES = ["--started-at", "2026-11-02T12:00:00Z", "--ended-at", "2026-11-02T12:03:00Z"]


def setup(tmp_path, lease=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    d = str(tmp_path / "store")
    art = wind_artifact(n=1)
    p = tmp_path / "artifact.json"
    p.write_text(json.dumps(art, indent=2))                                # a local run writes pretty JSON; the uploader stores the canonical form
    if lease:
        RL.grant(RL.orchestrator_view(LocalDirObjectStore(d)), POLICY, "wind", "pulse", "c1", dt.datetime.now(dt.timezone.utc))
    return d, str(p), art


def test_upload_stores_create_only_verifies_and_records_the_run(tmp_path, capsys):
    d, p, art = setup(tmp_path)
    assert R.main(["upload", "--store-dir", d, "--artifact", p, "--holder", "pulse", "--cycle", "c1", "--engine-commit", "abc"] + TIMES) == 0
    out = json.loads(capsys.readouterr().out)
    s = LocalDirObjectStore(d)
    assert s.get(out["stored"]["location"]) is not None and out["executionId"] == art["lineage"]["executionId"]
    ex = RL.runner_executions(RL.orchestrator_view(s), {"wind"})
    assert len(ex) == 1 and ex[0]["runner"] == "pulse" and ex[0]["cycleId"] == "c1"
    assert R.main(["upload", "--store-dir", d, "--artifact", p, "--holder", "pulse", "--cycle", "c1", "--engine-commit", "abc"] + TIMES) == 0   # idempotent


def test_upload_without_the_lease_is_refused_and_stores_nothing(tmp_path):
    d, p, art = setup(tmp_path, lease=False)
    assert R.main(["upload", "--store-dir", d, "--artifact", p, "--holder", "pulse"] + TIMES) == 3
    assert LocalDirObjectStore(d).get(f"artifacts/wind/{art['lineage']['artifactId']}/artifact.json") is None
    d2, p2, _ = setup(tmp_path / "b")
    assert R.main(["upload", "--store-dir", d2, "--artifact", p2, "--holder", "cloud"] + TIMES) == 3       # the lease is pulse's


def test_a_bad_artifact_is_refused(tmp_path):
    d, p, art = setup(tmp_path)
    bad = dict(art, lineage={k: v for k, v in art["lineage"].items() if k != "executionId"})
    open(p, "w").write(json.dumps(bad))
    assert R.main(["upload", "--store-dir", d, "--artifact", p, "--holder", "pulse"] + TIMES) == 4
    open(p, "w").write("not json")
    assert R.main(["upload", "--store-dir", d, "--artifact", p, "--holder", "pulse"] + TIMES) == 4


def test_renew_and_show(tmp_path, capsys):
    d, _, _ = setup(tmp_path)
    assert R.main(["renew", "--store-dir", d, "--brain", "wind", "--holder", "pulse"]) == 0
    assert R.main(["renew", "--store-dir", d, "--brain", "wind", "--holder", "cloud"]) == 3
    capsys.readouterr()
    assert R.main(["show", "--store-dir", d, "--brain", "wind"]) == 0
    assert json.loads(capsys.readouterr().out)["lease"]["holder"] == "pulse"


# -- skip (SI-P2): the job's own plan said SKIP, so there is no artifact ------------------------------------------------------------------------------
def test_skip_records_a_skipped_run_for_the_held_cycle(tmp_path, capsys):
    d, _, _ = setup(tmp_path)
    args = ["skip", "--store-dir", d, "--brain", "wind", "--holder", "pulse", "--cycle", "c1", "--reason", "inputs unchanged", "--engine-commit", "abc"] + TIMES
    assert R.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"executionId": "c1-skip", "executionRecord": "exports/runners/pulse/executions/wind/c1-skip.json", "status": "SKIPPED"}
    s = LocalDirObjectStore(d)
    ex = RL.runner_executions(RL.orchestrator_view(s), {"wind"})
    assert len(ex) == 1 and ex[0]["status"] == "SKIPPED" and ex[0]["cycleId"] == "c1"
    assert ex[0]["decision"] == {"action": "SKIP", "reasons": ["inputs unchanged"]}
    assert not [k for k in s.list("artifacts/")]                           # nothing handed off
    assert R.main(args) == 0                                               # idempotent
    kept, skipped = RL.reconcilable_executions(RL.orchestrator_view(s), {"wind"})
    assert [e["executionId"] for e in kept] == ["c1-skip"] and skipped == []


def test_skip_is_refused_without_the_lease_or_for_another_cycle(tmp_path):
    d, _, _ = setup(tmp_path, lease=False)
    assert R.main(["skip", "--store-dir", d, "--brain", "wind", "--holder", "pulse", "--cycle", "c1"] + TIMES) == 3
    d2, _, _ = setup(tmp_path / "b")
    assert R.main(["skip", "--store-dir", d2, "--brain", "wind", "--holder", "pulse", "--cycle", "c0"] + TIMES) == 3
    assert R.main(["skip", "--store-dir", d2, "--brain", "wind", "--holder", "cloud", "--cycle", "c1"] + TIMES) == 3
    assert R.main(["skip", "--store-dir", d2, "--brain", "wind", "--holder", "pulse"] + TIMES) == 2
    assert R.main(["skip", "--store-dir", d2, "--brain", "wind", "--holder", "pulse", "--cycle", "a/b"] + TIMES) == 2
    assert RL.runner_executions(RL.orchestrator_view(LocalDirObjectStore(d2)), {"wind"}) == []


def test_a_re_run_in_the_same_cycle_reports_the_skip_already_recorded(tmp_path, capsys):
    d, _, _ = setup(tmp_path)
    base = ["skip", "--store-dir", d, "--brain", "wind", "--holder", "pulse", "--cycle", "c1", "--started-at", "2026-11-02T12:00:00Z"]
    assert R.main(base + ["--ended-at", "2026-11-02T12:01:00Z"]) == 0
    capsys.readouterr()
    assert R.main(base + ["--ended-at", "2026-11-02T12:09:00Z", "--reason=-starts with a dash"]) == 0
    assert json.loads(capsys.readouterr().out)["alreadyRecorded"] is True
    assert len(RL.runner_executions(RL.orchestrator_view(LocalDirObjectStore(d)), {"wind"})) == 1
