"""job_env: snapshot, carry-forward (only the projection changes), restore, compare. Offline."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import job_env as J  # noqa: E402

LIVE_ENV = {
    "BRAIN_TOKEN_MODE": "metadata", "RUNNER_LEASES": "on", "PUBLICATION_COORDINATION": "on", "PUBLICATION_HANDOFF": "on",
    "WIND_MEASUREMENTS": "off", "CONDITIONS_SOURCES_PROJECTION": "0", "DEPLOYMENT_VERSION": "brain-orchestrator@aaaaaaaaaaaa",
    "PUBLICATION_CUTOVER": "/job/jobs/brain-orchestrator/publication-cutover.json", "WEIRD": 'a,b="c"\\d',
}


def describe(env=LIVE_ENV, extra=None, image="us-central1-docker.pkg.dev/p/r/brain-orchestrator@sha256:" + "a" * 64):
    entries = [{"name": k, "value": v} for k, v in env.items()] + (extra or [])
    return {"metadata": {"labels": {"commit": "aaaaaaaaaaaa"}},
            "spec": {"template": {"spec": {"template": {"spec": {"serviceAccountName": "sa", "containers": [
                {"image": image, "env": entries, "args": ["--publish-health"]}]}}}}}}


def test_snapshot():
    s = J.snapshot(describe())
    assert s["env"] == LIVE_ENV and s["commit"] == "aaaaaaaaaaaa" and s["args"] == ["--publish-health"] and s["image"].endswith("a" * 64)


def test_carry_changes_only_the_projection_and_deployment_version():
    s = J.snapshot(describe())
    env = J.carried(s, "1")
    assert J.diff(s["env"], env) == ["CONDITIONS_SOURCES_PROJECTION: '0' -> '1'"]
    env2 = J.carried(s, "1", "brain-orchestrator@bbbbbbbbbbbb")
    assert sorted(J.diff(s["env"], env2)) == ["CONDITIONS_SOURCES_PROJECTION: '0' -> '1'",
                                              "DEPLOYMENT_VERSION: 'brain-orchestrator@aaaaaaaaaaaa' -> 'brain-orchestrator@bbbbbbbbbbbb'"]
    assert env["RUNNER_LEASES"] == "on" and env["PUBLICATION_HANDOFF"] == "on"     # the live hybrid switches survive
    with pytest.raises(J.Refused):
        J.carried(s, "2")


def test_env_file_round_trips_awkward_values():
    env = {**LIVE_ENV, "NL": "x\ny", "UNI": "é"}
    assert J.read_env_yaml(J.env_yaml(env)) == env


def test_secret_reference_is_refused():
    with pytest.raises(J.Refused):
        J.snapshot(describe(extra=[{"name": "K", "valueFrom": {"secretKeyRef": {"name": "s", "key": "latest"}}}]))


def test_cli_carry_restore_compare(tmp_path):
    d = tmp_path / "d.json"
    d.write_text(json.dumps(describe()))
    snap, env, back = tmp_path / "s.json", tmp_path / "e.yaml", tmp_path / "r.yaml"
    assert J.main(["snapshot", "--describe", str(d), "--out", str(snap)]) == 0
    assert J.main(["carry", "--snapshot", str(snap), "--projection", "1", "--out", str(env)]) == 0
    assert J.main(["restore", "--snapshot", str(snap), "--out", str(back)]) == 0
    assert J.main(["compare", "--snapshot", str(snap), "--env", str(back)]) == 0
    assert J.main(["compare", "--snapshot", str(snap), "--env", str(env)]) == 1           # the job still has projection 0
    assert J.main(["compare", "--snapshot", str(snap), "--env", str(back), "--image", "other"]) == 1
