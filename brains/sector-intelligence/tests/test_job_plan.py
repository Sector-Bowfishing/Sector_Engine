"""SI-P2 option (b) (Sector_Ops #50, owner-approved 2026-11-05): the job's own plan decides. FAKE clients only: no database, network, bucket or credential.

Pins that the job (`--artifact`) asks `orch.plan` with exactly the inputs `--plan` uses, and that `--emit-decision` hands its verdict to a runner."""
import json

import pytest

import run


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
                                                        {"codeLineage": {}, "dependencies": {b: {} for b in run.sib.DEPENDENCY_ORDER}}, "catsha"))
    monkeypatch.setattr(run.bp, "TokenProvider", lambda *a, **k: object())
    monkeypatch.setattr(run.bp, "BrainRtdb", FakeRtdb)
    monkeypatch.setattr(run.bp, "ConsumptionRecorder", lambda *a, **k: None)
    monkeypatch.setattr(run, "read_upstream", lambda rtdb: {b: {"registry": {}, "health": {}, "validationStatus": {}} for b in run.sib.DEPENDENCY_ORDER})
    monkeypatch.setattr(run, "runner_service", lambda env=None: {"revision": "rev-1"})
    monkeypatch.setattr(run.sib, "engine_serving", lambda svc, lineage, now: {"revision": "rev-1"})
    monkeypatch.setattr(run.sib, "dependency_status", lambda *a, **k: {"connectionStatus": "CONNECTED"})
    monkeypatch.setattr(run.sib, "fingerprint", lambda *a: "fp-1")
    monkeypatch.setattr(run, "http_json", lambda url, *a, **k: {"lakes": [{"id": "lake-a"}]})
    monkeypatch.setattr(run.sib, "build_updates", lambda **k: {f"/brains/{run.sib.BRAIN_ID}": {"dependencySummary": {}, "dependencies": {}}})
    monkeypatch.setattr(run.sib, "check_keys", lambda u: None)

    def plan(published, fp, version, **kw):
        asked.append((json.dumps(published, sort_keys=True), fp, version, json.dumps(kw, sort_keys=True)))
        return dict(verdict["v"])
    monkeypatch.setattr(run.orch, "plan", plan)
    return asked, verdict


def test_the_job_asks_the_plan_with_the_same_inputs_as_plan(fake, tmp_path, capsys):
    asked, _ = fake
    assert run.main(["--plan", "--no-pilot"]) == 0
    assert run.main(["--artifact", "--no-pilot", "--artifact-dir", str(tmp_path / "store")]) == 0
    assert len(asked) == 2 and asked[0][:3] == asked[1][:3]
    assert json.loads(asked[0][3]).keys() == json.loads(asked[1][3]).keys()


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
