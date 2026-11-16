"""SI-A2 deploy switch (Sector_Ops #51, owner approval 2026-11-15 "go faster", item 4): deploy-job.sh passes SI_ARTIFACT_JOB to the job only when it is
deployed with SI_ARTIFACT_JOB=on. Default off: the variable is not set at all, so an off deploy keeps exactly today's environment key set and
orchestrate.py keeps the in-process Sector Intelligence. The switch block and the env line are run in bash on their own (no gcloud, no deploy)."""
import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = open(os.path.join(HERE, "..", "deploy-job.sh"), encoding="utf-8").read()
START = DEPLOY.index('PUBLICATION_COORDINATION="${PUBLICATION_COORDINATION:-off}"')
END = DEPLOY.index('RTDB_URL="${RTDB_URL:-')
BLOCK = DEPLOY[START:END]
ENV_START = DEPLOY.index("ENV_FLAGS=(--set-env-vars")
ENV_BLOCK = "\n".join(DEPLOY[ENV_START:].split("\n", 2)[:2]) + "\n"
FILL = ("RTDB_URL=r ENGINE_URL=e LAKE_BRAIN_ARCHIVE=l BIOLOGY_BUCKET=b COMMIT=c WIND_MEASUREMENTS=off CONDITIONS_SOURCES_PROJECTION=0\n")
PROBE = 'printf "SI=%s\\nENV=%s\\n" "$SI_ARTIFACT_JOB" "${ENV_FLAGS[1]}"\n'
SWITCHES = ("PUBLICATION_COORDINATION", "PUBLICATION_HANDOFF", "RUNNER_LEASES", "ORCH_ARGS", "SI_ARTIFACT_JOB")


def run(env):
    clean = {k: v for k, v in os.environ.items() if k not in SWITCHES}
    script = "set -euo pipefail\n" + BLOCK + FILL + ENV_BLOCK + PROBE
    r = subprocess.run(["bash", "-c", script], env={**clean, **env}, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


def keys(out):
    env = out.split("ENV=", 1)[1].strip()
    return [kv.split("=", 1)[0] for kv in env.split(",")]


def test_default_is_off_and_leaves_the_environment_key_set_unchanged():
    code, out = run({})
    assert code == 0 and "SI=off" in out
    assert "SI_ARTIFACT_JOB" not in keys(out)


def test_on_needs_runner_leases():
    assert run({"SI_ARTIFACT_JOB": "on"})[0] != 0


def test_on_with_runner_leases_reaches_the_job_as_1():
    code, out = run({"SI_ARTIFACT_JOB": "on", "RUNNER_LEASES": "on"})
    assert code == 0
    k = keys(out)
    assert k.count("SI_ARTIFACT_JOB") == 1 and "SI_ARTIFACT_JOB=1" in out
    off = keys(run({"RUNNER_LEASES": "on"})[1])
    assert k == off + ["SI_ARTIFACT_JOB"]          # nothing else in the key set moves


@pytest.mark.parametrize("value", ["1", "ON", "true", "yes"])
def test_only_on_or_off_is_accepted(value):
    assert run({"SI_ARTIFACT_JOB": value, "RUNNER_LEASES": "on"})[0] != 0


def test_carry_env_refuses_an_explicit_si_switch():
    line = next(l for l in DEPLOY.splitlines() if l.startswith("for _v in WIND_MEASUREMENTS"))
    assert " SI_ARTIFACT_JOB " in line


def test_orchestrator_reads_exactly_1():
    src = open(os.path.join(HERE, "..", "orchestrate.py"), encoding="utf-8").read()
    assert 'env.get("SI_ARTIFACT_JOB") == "1"' in src
