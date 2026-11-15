"""deploy-job.sh keeps the live job's CUSTOMER-lane switches (Sector_Ops #51, comment 6895061367). --set-env-vars replaces the whole env
list, so before this a Publisher redeploy for another reason silently turned an enabled lane off. The whole script runs against a FAKE
gcloud on PATH that records every call; nothing reaches Google Cloud."""
import json
import os
import re
import stat
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "deploy-job.sh")

FAKE_GCLOUD = r'''#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
case "$*" in
  "run jobs describe"*)
    case "$FAKE_DESCRIBE_MODE" in
      missing) echo "ERROR: (gcloud.run.jobs.describe) Cannot find job [brain-publisher]." >&2; exit 1;;
      error) echo "ERROR: (gcloud.run.jobs.describe) PERMISSION_DENIED" >&2; exit 1;;
      *) cat "$FAKE_DESCRIBE";;
    esac;;
  "iam service-accounts describe"*) exit 0;;
  "run jobs deploy"*) exit 0;;
esac
exit 0
'''


def run(tmp_path, live_env=None, mode="ok", **passed):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    g = bin_dir / "gcloud"
    g.write_text(FAKE_GCLOUD)
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    desc = tmp_path / "describe.json"
    env_list = [{"name": k, "value": v} for k, v in (live_env or {}).items()]
    desc.write_text(json.dumps({"metadata": {"labels": {"mode": "live"}},
                                "spec": {"template": {"spec": {"template": {"spec": {"containers": [{"env": env_list}]}}}}}}))
    log = tmp_path / "gcloud.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PUBLISHER_CUSTOMER_")}
    env.update(PATH=f"{bin_dir}:{os.environ['PATH']}", FAKE_LOG=str(log), FAKE_DESCRIBE=str(desc), FAKE_DESCRIBE_MODE=mode,
               MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY="yes", PUBLISHER_MODE="live", PUBLICATION_ARTIFACT_BUCKET="b", **passed)
    r = subprocess.run(["bash", SCRIPT], capture_output=True, text=True, env=env, timeout=300)
    calls = log.read_text().splitlines() if log.exists() else []
    deploy = [c for c in calls if c.startswith("gcloud run jobs deploy")]
    switches = {}
    if deploy:
        m = re.search(r"--set-env-vars (\S+)", deploy[0])
        switches = {k: v for k, v in (p.split("=", 1) for p in m.group(1).split(",")) if k.startswith("PUBLISHER_CUSTOMER_")}
    return r, deploy, switches


def test_a_live_switch_not_passed_here_is_kept(tmp_path):
    r, deploy, sw = run(tmp_path, {"PUBLISHER_CUSTOMER_CLARITY": "1", "PUBLISHER_CUSTOMER_LAKE_LEVEL": "0"})
    assert r.returncode == 0, r.stderr
    assert sw == {"PUBLISHER_CUSTOMER_CLARITY": "1", "PUBLISHER_CUSTOMER_LAKE_LEVEL": "0"}
    assert "carried from the live job" in r.stdout


def test_a_switch_passed_here_wins_over_the_live_value(tmp_path):
    r, deploy, sw = run(tmp_path, {"PUBLISHER_CUSTOMER_CLARITY": "1"}, PUBLISHER_CUSTOMER_CLARITY="0", PUBLISHER_CUSTOMER_WATER_TEMP="1")
    assert r.returncode == 0, r.stderr
    assert sw == {"PUBLISHER_CUSTOMER_CLARITY": "0", "PUBLISHER_CUSTOMER_WATER_TEMP": "1"}


def test_no_live_switch_means_none_is_added(tmp_path):
    r, deploy, sw = run(tmp_path, {"BRAIN_TOKEN_MODE": "metadata"})
    assert r.returncode == 0, r.stderr
    assert len(deploy) == 1 and sw == {}


def test_a_missing_job_carries_nothing_and_still_deploys(tmp_path):
    r, deploy, sw = run(tmp_path, mode="missing")
    assert r.returncode == 0, r.stderr
    assert len(deploy) == 1 and sw == {}


def test_any_other_describe_error_refuses_the_deploy(tmp_path):
    r, deploy, sw = run(tmp_path, mode="error")
    assert r.returncode == 2 and deploy == []
    assert "refusing to deploy" in r.stderr


def test_a_live_value_other_than_0_or_1_refuses_the_deploy(tmp_path):
    r, deploy, sw = run(tmp_path, {"PUBLISHER_CUSTOMER_CLARITY": "yes"})
    assert r.returncode == 2 and deploy == []
