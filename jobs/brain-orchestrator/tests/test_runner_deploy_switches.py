"""Sector_Ops #51 O5.1: the hybrid runner switches in deploy-job.sh. RUNNER_LEASES and PUBLICATION_HANDOFF default OFF; ORCH_ARGS unset leaves the
job's arguments untouched; only allowlisted arguments pass. The switch block is run on its own in bash (no gcloud, no deploy)."""
import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = open(os.path.join(HERE, "..", "deploy-job.sh"), encoding="utf-8").read()
START = DEPLOY.index('PUBLICATION_COORDINATION="${PUBLICATION_COORDINATION:-off}"')
END = DEPLOY.index('RTDB_URL="${RTDB_URL:-')
BLOCK = DEPLOY[START:END]
ENV_LINE = DEPLOY.split("--set-env-vars", 1)[1].split("\n", 1)[0]
PROBE = 'printf "HANDOFF=%s\\nLEASES=%s\\n" "$PUBLICATION_HANDOFF" "$RUNNER_LEASES"; printf "ARG=%s\\n" ${ARGS_FLAG[@]+"${ARGS_FLAG[@]}"}\n'


def run(env):
    clean = {k: v for k, v in os.environ.items() if k not in ("PUBLICATION_COORDINATION", "PUBLICATION_HANDOFF", "RUNNER_LEASES", "ORCH_ARGS")}
    r = subprocess.run(["bash", "-c", "set -euo pipefail\n" + BLOCK + PROBE], env={**clean, **env}, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


def test_defaults_are_off_and_leave_the_job_arguments_alone():
    code, out = run({})
    assert code == 0
    assert "HANDOFF=off" in out and "LEASES=off" in out
    assert "ARG=\n" in out and "--args" not in out


def test_both_switches_reach_the_job_environment():
    assert "PUBLICATION_HANDOFF=$PUBLICATION_HANDOFF" in ENV_LINE and "RUNNER_LEASES=$RUNNER_LEASES" in ENV_LINE
    assert 'ARGS_FLAG[@]+"${ARGS_FLAG[@]}"' in DEPLOY.split("gcloud run jobs deploy", 1)[1].split("--set-env-vars", 1)[0]


@pytest.mark.parametrize("name,value", [("RUNNER_LEASES", "ON"), ("RUNNER_LEASES", "1"), ("PUBLICATION_HANDOFF", "true")])
def test_only_on_or_off_is_accepted(name, value):
    env = {"PUBLICATION_COORDINATION": "on", name: value}
    assert run(env)[0] != 0


def test_handoff_needs_coordination():
    assert run({"PUBLICATION_HANDOFF": "on"})[0] != 0
    code, out = run({"PUBLICATION_HANDOFF": "on", "PUBLICATION_COORDINATION": "on", "RUNNER_LEASES": "on"})
    assert code == 0 and "HANDOFF=on" in out and "LEASES=on" in out


def test_hybrid_args_drop_the_shadow_lane():
    code, out = run({"ORCH_ARGS": "--publish-engineering-status;--publish-health"})
    assert code == 0 and "ARG=--args=^;^--publish-engineering-status;--publish-health" in out and "shadow" not in out


def test_empty_orch_args_clears_them():
    code, out = run({"ORCH_ARGS": ""})
    assert code == 0 and "ARG=--args=\n" in out


@pytest.mark.parametrize("bad", ["--dry-run;--publish-health", "--publish-health;--runner-mode", "--run-now", "--publish-health,--x", "x;--force-shadow-lane"])
def test_arguments_outside_the_allowlist_are_refused(bad):
    assert run({"ORCH_ARGS": bad})[0] != 0
