"""SI_ARTIFACT_JOB deploy guard (Sector_Ops #51, owner approval 2026-11-16 18:09Z): while sector-intelligence is CENTRAL in the deployed commit's
publication-cutover.json, a brain-orchestrator deploy without SI_ARTIFACT_JOB=1 is refused. Local only: tmp files, no gcloud."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))

import si_artifact_guard as G                                                  # noqa: E402

CENTRAL = {"schema": "sector-publication-cutover-v1", "brains": {"water-temp": {"state": "CENTRAL"},
                                                                 "sector-intelligence": {"state": "CENTRAL", "approvalRef": "x"}}}
DIRECT = {"schema": "sector-publication-cutover-v1", "brains": {"water-temp": {"state": "CENTRAL"}}}


def env_yaml(**env):
    return "".join(f"{json.dumps(k)}: {json.dumps(v)}\n" for k, v in sorted(env.items()))


def test_si_central_refuses_an_off_deploy_and_allows_an_on_deploy():
    assert G.check(CENTRAL, switch="off").startswith("REFUSED")
    assert G.check(CENTRAL, switch="on") is None


def test_si_not_central_allows_either_switch():
    assert G.check(DIRECT, switch="off") is None
    assert G.check(DIRECT, switch="on") is None


def test_carried_env_must_hold_si_artifact_job_1_while_central():
    assert G.check(CENTRAL, env_yaml=env_yaml(RUNNER_LEASES="on", SI_ARTIFACT_JOB="1")) is None
    assert G.check(CENTRAL, env_yaml=env_yaml(RUNNER_LEASES="on")).startswith("REFUSED")
    assert G.check(CENTRAL, env_yaml=env_yaml(SI_ARTIFACT_JOB="0")).startswith("REFUSED")
    assert G.check(DIRECT, env_yaml=env_yaml(RUNNER_LEASES="on")) is None


def test_bad_inputs_fail_closed(tmp_path):
    with pytest.raises(ValueError):
        G.check({"nobrains": 1}, switch="on")
    with pytest.raises(ValueError):
        G.check(CENTRAL)
    c = tmp_path / "c.json"
    c.write_text("not json")
    assert G.main(["--cutover", str(c), "--switch", "on"]) == 2
    assert G.main(["--cutover", str(tmp_path / "missing.json"), "--switch", "on"]) == 2


def test_cli_exit_codes(tmp_path):
    c, e = tmp_path / "c.json", tmp_path / "env.yaml"
    c.write_text(json.dumps(CENTRAL))
    e.write_text(env_yaml(SI_ARTIFACT_JOB="1"))
    assert G.main(["--cutover", str(c), "--switch", "off"]) == 1
    assert G.main(["--cutover", str(c), "--switch", "on"]) == 0
    assert G.main(["--cutover", str(c), "--env-yaml", str(e)]) == 0


def test_the_committed_cutover_is_readable_by_the_guard():
    with open(os.path.join(ROOT, "jobs", "brain-orchestrator", "publication-cutover.json")) as fh:
        cut = json.load(fh)
    G.si_is_central(cut)                                                     # must not raise on the real document


def test_deploy_job_sh_calls_the_guard_on_both_paths():
    with open(os.path.join(ROOT, "jobs", "brain-orchestrator", "deploy-job.sh")) as fh:
        sh = fh.read()
    assert 'si_artifact_guard.py" --cutover publication-cutover.json --switch "$SI_ARTIFACT_JOB" || exit 1' in sh
    assert 'si_artifact_guard.py" --cutover publication-cutover.json --env-yaml "$CARRY_DIR/env.yaml" || exit 1' in sh
    # the explicit-env check runs before anything is built or deployed
    assert sh.index("--switch \"$SI_ARTIFACT_JOB\"") < sh.index("run gcloud run jobs deploy")
    assert sh.index("--env-yaml \"$CARRY_DIR/env.yaml\"") < sh.index("run gcloud run jobs deploy")
