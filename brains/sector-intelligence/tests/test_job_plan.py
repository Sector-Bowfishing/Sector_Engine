"""SI-P2 option (b) (Sector_Ops #50, owner-approved 2026-11-05): the job's own plan decides. FAKE clients only: no database, network, bucket or credential.

Pins that the job (`--artifact`) asks `orch.plan` with exactly the inputs `--plan` uses, and that `--emit-decision` hands its verdict to a runner."""
import json

import pytest

import run


LINEAGE = {"service": "sector-engine", "tag": "v1", "commit": "abc", "imageDigest": "sha256:d1"}
RUNNER_SVC = {"source": "runner", "trafficStatuses": [{"revision": "rev-1", "percent": 100}],
              "template": {"containers": [{"image": "runner-supplied@sha256:d1"}]}}
CLOUD_SVC = {"trafficStatuses": [{"revision": "rev-1", "percent": 100}], "template": {"containers": [{"image": "gcr.io/x@sha256:d1"}]}}


class FakeRtdb:
    def __init__(self, *a, **k):
        pass

    def get(self, path):
        return {"lastSuccessfulRun": "2026-11-05T10:00:00Z", "fingerprint": "old"} if path == f"brains/{run.sib.BRAIN_ID}" else None

    def consumed(self):
        return []


@pytest.fixture
def fake(monkeypatch):
    asked = []
    verdict = {"v": {"action": "SKIP", "reasons": ["no material change"]}}
    monkeypatch.setattr(run, "load_knowledge", lambda: ({"releaseId": "r1", "releaseDigest": "sha256:x"},
                                                        {"codeLineage": LINEAGE, "dependencies": {b: {} for b in run.sib.DEPENDENCY_ORDER}}, "catsha"))
    monkeypatch.setattr(run.bp, "TokenProvider", lambda *a, **k: object())
    monkeypatch.setattr(run.bp, "BrainRtdb", FakeRtdb)
    monkeypatch.setattr(run.bp, "ConsumptionRecorder", lambda *a, **k: None)
    monkeypatch.setattr(run, "read_upstream", lambda rtdb: {b: {"registry": {}, "health": {}, "validationStatus": {}} for b in run.sib.DEPENDENCY_ORDER})
    # the REAL engine_serving and fingerprint run; only the data sources are fake
    monkeypatch.setattr(run, "runner_service", lambda env=None: RUNNER_SVC)
    monkeypatch.setattr(run.sib, "dependency_status", lambda *a, **k: {"exists": True, "publishingStatus": "PUBLISHING", "health": "OK", "version": "1",
                                                                        "lifecycle": "ACTIVE", "connectionStatus": "CONNECTED"})
    monkeypatch.setattr(run, "http_json", lambda url, *a, **k: {"lakes": [{"id": "lake-a"}]})
    monkeypatch.setattr(run.sib, "build_updates", lambda **k: {f"/brains/{run.sib.BRAIN_ID}": {"dependencySummary": {}, "dependencies": {}}})
    monkeypatch.setattr(run.sib, "check_keys", lambda u: None)

    def plan(published, fp, version, **kw):
        asked.append((json.dumps(published, sort_keys=True), fp, version, json.dumps(kw, sort_keys=True)))
        return dict(verdict["v"])
    monkeypatch.setattr(run.orch, "plan", plan)
    return asked, verdict


def test_the_job_asks_the_plan_with_the_same_inputs_as_plan(fake, tmp_path, capsys):
    """Same process, same sources: --artifact asks orch.plan with the same published state, the same REAL fingerprint and version as --plan."""
    asked, _ = fake
    assert run.main(["--plan", "--no-pilot"]) == 0
    assert run.main(["--artifact", "--no-pilot", "--artifact-dir", str(tmp_path / "store")]) == 0
    assert len(asked) == 2 and asked[0][:3] == asked[1][:3]
    a0, a1 = json.loads(asked[0][3]), json.loads(asked[1][3])
    assert a0.keys() == a1.keys() and abs(a0["published_age_hours"] - a1["published_age_hours"]) < 0.01


def test_moving_the_plan_from_cloud_run_to_the_runner_changes_the_fingerprint_once(fake, monkeypatch, tmp_path, capsys):
    """Review of #132: why (b) and not (a). The Orchestrator's in-process plan reads Cloud Run (lineage verifiable); a runner-run job reads the runner's
    revision (never verified). The fingerprints differ, so under (a) the two plans could disagree every cycle. Under (b) only the job plans: the first
    cycle on the runner sees a changed fingerprint (one PUBLISH), and later runner cycles compare like with like."""
    asked, _ = fake
    assert run.main(["--plan", "--no-pilot"]) == 0                                       # runner-supplied (as in a Pulse job)
    monkeypatch.setattr(run, "runner_service", lambda env=None: None)
    monkeypatch.setattr(run, "cloud_run_service", lambda tokens, lineage: CLOUD_SVC)
    assert run.main(["--plan", "--no-pilot"]) == 0                                       # Cloud Run, as the Orchestrator reads it
    assert asked[0][1] != asked[1][1]


def test_a_skip_emits_the_decision_and_seals_nothing(fake, tmp_path, capsys):
    d = tmp_path / "decision.json"
    assert run.main(["--artifact", "--no-pilot", "--artifact-dir", str(tmp_path / "store"), "--emit-decision", str(d)]) == 0
    doc = json.loads(d.read_text())
    assert doc == {"schema": "sector-job-decision-v1", "brainId": run.sib.BRAIN_ID, "action": "SKIP", "reasons": ["no material change"],
                   "artifactId": None, "forced": False}
    assert not (tmp_path / "store").exists() or not list((tmp_path / "store").rglob("artifact.json"))


def test_emit_decision_is_refused_outside_artifact_mode_for_a_remote_or_existing_path(fake, tmp_path, capsys):
    store = ["--artifact-dir", str(tmp_path / "store")]
    assert run.main(["--plan", "--emit-decision", str(tmp_path / "d.json")]) == 2
    assert run.main(["--artifact", *store, "--emit-decision", "gs://bucket/d.json"]) == 2
    (tmp_path / "old.json").write_text("{}")
    assert run.main(["--artifact", *store, "--emit-decision", str(tmp_path / "old.json")]) == 2
    assert (tmp_path / "old.json").read_text() == "{}"
    assert "needs --artifact and a new LOCAL file" in capsys.readouterr().err


def test_a_publish_emits_the_decision_with_the_sealed_artifact(fake, tmp_path, monkeypatch, capsys):
    _, verdict = fake
    verdict["v"] = {"action": "PUBLISH", "reasons": ["inputs changed"]}
    monkeypatch.setattr(run, "seal_and_store", lambda updates, **k: {"artifactId": "art-1", "location": "artifacts/x", "sha256": "s", "executionId": "e"})
    d = tmp_path / "decision.json"
    assert run.main(["--artifact", "--no-pilot", "--artifact-dir", str(tmp_path / "store"), "--emit-decision", str(d)]) == 0
    doc = json.loads(d.read_text())
    assert doc["action"] == "PUBLISH" and doc["artifactId"] == "art-1" and doc["forced"] is False
