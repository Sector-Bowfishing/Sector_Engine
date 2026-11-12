"""deploy-job.sh switches for the GitHub Actions deployer (docs/architecture/conditions/DEPLOY_WORKFLOWS_V1.md §2): SKIP_IAM,
SKIP_SCHEDULER_DEFINITION, CARRY_ENV, IMAGE, CARRY_IMAGE. The whole script runs against a FAKE gcloud and docker on PATH that record every
call; nothing reaches Google Cloud. The default path (no switch) is checked to be unchanged."""
import json
import os
import stat
import subprocess
import textwrap

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "deploy-job.sh")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HEAD = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

LIVE_ENV = {"BRAIN_TOKEN_MODE": "metadata", "RUNNER_LEASES": "on", "PUBLICATION_COORDINATION": "on", "PUBLICATION_HANDOFF": "on",
            "CONDITIONS_SOURCES_PROJECTION": "0", "DEPLOYMENT_VERSION": "brain-orchestrator@" + HEAD[:12], "ORCHESTRATOR_SCOPE": "pilots"}
LIVE_IMAGE = "us-central1-docker.pkg.dev/p/cloud-run-source-deploy/brain-orchestrator@sha256:" + "c" * 64

FAKE_GCLOUD = r'''#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
case "$*" in
  *"--format=value(metadata.labels.commit)"*) echo "${FAKE_COMMIT}";;
  "run jobs describe"*"--format=json"*) cat "$FAKE_DESCRIBE";;
  "scheduler jobs describe"*"value(state)"*) echo "${FAKE_SCHED_STATE}";;
  "iam service-accounts describe"*) exit 0;;
  "run jobs deploy"*) for a in "$@"; do case "$a" in --env-vars-file) nxt=1;; *) [[ -n "${nxt:-}" ]] && cp "$a" "$FAKE_ENVFILE" && nxt=;; esac; done;;
esac
exit 0
'''
FAKE_DOCKER = r'''#!/usr/bin/env bash
echo "docker $*" >> "$FAKE_LOG"
if [[ "$1" == inspect ]]; then echo "${FAKE_IMAGE%:*}@sha256:$(printf 'd%.0s' {1..64})"; fi
exit 0
'''


def describe(env=LIVE_ENV):
    return {"metadata": {"labels": {"commit": HEAD[:12]}}, "spec": {"template": {"spec": {"template": {"spec": {
        "serviceAccountName": "brain-writer@x", "containers": [{"image": LIVE_IMAGE, "env": [{"name": k, "value": v} for k, v in env.items()]}]}}}}}}


@pytest.fixture()
def fake(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    for name, body in (("gcloud", FAKE_GCLOUD), ("docker", FAKE_DOCKER)):
        p = b / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    d = tmp_path / "describe.json"
    d.write_text(json.dumps(describe()))
    return tmp_path


def run(fake, **env):
    clean = {k: v for k, v in os.environ.items() if k not in (
        "WIND_MEASUREMENTS", "PUBLICATION_COORDINATION", "PUBLICATION_HANDOFF", "RUNNER_LEASES", "ORCH_ARGS", "CONDITIONS_SOURCES_PROJECTION",
        "IMAGE", "CARRY_ENV", "CARRY_IMAGE", "SKIP_IAM", "SKIP_SCHEDULER_DEFINITION", "DRY_RUN")}
    full = {**clean, "PATH": f"{fake / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(fake / "calls.log"), "FAKE_DESCRIBE": str(fake / "describe.json"),
            "FAKE_COMMIT": HEAD[:12], "FAKE_SCHED_STATE": "PAUSED", "FAKE_ENVFILE": str(fake / "deployed-env.yaml"),
            "FAKE_IMAGE": env.get("IMAGE", ""), **env}
    r = subprocess.run(["bash", SCRIPT], env=full, capture_output=True, text=True, timeout=300)
    calls = (fake / "calls.log").read_text().splitlines() if (fake / "calls.log").exists() else []
    return r, calls


def deploy_call(calls):
    return next(c for c in calls if c.startswith("gcloud run jobs deploy"))


WIF = {"SKIP_IAM": "1", "SKIP_SCHEDULER_DEFINITION": "1", "CARRY_ENV": "1", "CONDITIONS_SOURCES_PROJECTION": "1"}


def test_wif_path_builds_on_the_runner_carries_env_and_touches_no_iam_or_scheduler(fake):
    img = "us-central1-docker.pkg.dev/p/sector-engine/brain-orchestrator:" + HEAD
    r, calls = run(fake, **WIF, IMAGE=img)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not [c for c in calls if "iam" in c.split(" --")[0] or "add-iam-policy-binding" in c], calls
    assert not [c for c in calls if c.startswith("gcloud scheduler jobs") and " describe " not in f" {c} "], calls
    assert f"docker build -t {img} ." in calls and f"docker push {img}" in calls
    dep = deploy_call(calls)
    assert "--source" not in dep and f"--image {img.rsplit(':', 1)[0]}@sha256:" in dep
    assert "--set-env-vars" not in dep and "--env-vars-file" in dep and "--args" not in dep
    deployed = dict(l.split(": ", 1) for l in (fake / "deployed-env.yaml").read_text().splitlines())
    deployed = {json.loads(k): json.loads(v) for k, v in deployed.items()}
    assert deployed == {**LIVE_ENV, "CONDITIONS_SOURCES_PROJECTION": "1", "DEPLOYMENT_VERSION": "brain-orchestrator@" + HEAD[:12]}


def test_carry_image_is_an_env_only_change(fake):
    r, calls = run(fake, **WIF, CARRY_IMAGE="1")
    assert r.returncode == 0, r.stdout + r.stderr
    dep = deploy_call(calls)
    assert f"--image {LIVE_IMAGE}" in dep and f"commit={HEAD[:12]}" in dep
    assert not [c for c in calls if c.startswith("docker")]


def test_scheduler_not_paused_fails_and_is_never_paused_or_resumed(fake):
    r, calls = run(fake, **WIF, CARRY_IMAGE="1", FAKE_SCHED_STATE="ENABLED")
    assert r.returncode != 0 and "refusing to report success" in r.stdout
    assert not [c for c in calls if c.startswith("gcloud scheduler jobs pause") or c.startswith("gcloud scheduler jobs resume")]


@pytest.mark.parametrize("extra", [{"RUNNER_LEASES": "off"}, {"WIND_MEASUREMENTS": "off"}, {"CONDITIONS_SOURCES_PROJECTION": None},
                                   {"CARRY_ENV": "0", "CARRY_IMAGE": "1"}, {"CARRY_IMAGE": "1", "IMAGE": "x/y:z"}, {"SKIP_IAM": "yes"}])
def test_refusals(fake, extra):
    env = {**WIF, **{k: v for k, v in extra.items() if v is not None}}
    for k, v in extra.items():
        if v is None:
            env.pop(k)
    r, calls = run(fake, **env)
    assert r.returncode != 0
    assert not [c for c in calls if c.startswith("gcloud run jobs deploy")]


def test_secret_env_is_refused(fake):
    d = describe()
    d["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"].append({"name": "K", "valueFrom": {"secretKeyRef": {"name": "s"}}})
    (fake / "describe.json").write_text(json.dumps(d))
    r, calls = run(fake, **WIF, CARRY_IMAGE="1")
    assert r.returncode != 0 and not [c for c in calls if c.startswith("gcloud run jobs deploy")]


def test_default_path_is_unchanged(fake):
    r, calls = run(fake, DRY_RUN="1")
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "+ gcloud run jobs deploy brain-orchestrator --source ." in out and "--set-env-vars BRAIN_TOKEN_MODE=metadata," in out
    assert "+ gcloud projects add-iam-policy-binding" in out and "+ gcloud run jobs add-iam-policy-binding brain-orchestrator" in out
    assert "+ gcloud scheduler jobs update http brain-orchestrator" in out     # the pause's DRY_RUN echo goes to /dev/null, as before
    assert '|| run gcloud scheduler jobs pause "$JOB"' in open(SCRIPT).read()
    assert not [c for c in calls if c.startswith("docker")]


def test_prebuilt_digest_is_deployed_as_is_without_docker(fake):
    img = "us-central1-docker.pkg.dev/p/brain-orchestrator/brain-orchestrator@sha256:" + "e" * 64
    r, calls = run(fake, **WIF, IMAGE=img)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"--image {img}" in deploy_call(calls)
    assert not [c for c in calls if c.startswith("docker")]
    assert "us-central1-docker.pkg.dev" not in r.stdout          # the registry path is not echoed (public Actions logs)
    assert "iam.gserviceaccount.com" not in r.stdout + r.stderr  # nor a service-account email
