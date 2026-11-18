"""Identity split (Sector_Ops #19, owner approval 2026-11-18): the Water Temp and Lake job deploy scripts deploy each job as its OWN service
account, let brain-orchestrator start it, and FAIL CLOSED when an account is missing: never a fallback to the shared brain-writer account.
The deploy-orchestrator workflow refuses to deploy a job that does not already run as brain-orchestrator and restores the service account
on rollback. Each script runs against a FAKE gcloud that records every call; nothing reaches Google Cloud."""
import os
import stat
import subprocess

import pytest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FAKE_GCLOUD = r'''#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
case "$*" in
  "iam service-accounts describe"*) [[ -n "${FAKE_SA_MISSING:-}" && "$*" == *"${FAKE_SA_MISSING}"* ]] && exit 1; exit 0;;
  "scheduler jobs describe"*) exit 1;;
esac
exit 0
'''
JOBS = {
    "water-temp": ("brains/water-temperature/deploy/deploy-job.sh", "water-temp-brain", "brain-job-water-temp"),
    "lake": ("brains/lake/deploy/deploy-job.sh", "lake-brain", "brain-job-lake-brain"),
}
P = "@sector-9393c.iam.gserviceaccount.com"


@pytest.fixture()
def fake(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    g = b / "gcloud"
    g.write_text(FAKE_GCLOUD)
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    return tmp_path


def run(fake, script, **env):
    clean = {k: v for k, v in os.environ.items() if k not in ("SA_NAME", "INVOKER_SA_NAME", "DRY_RUN", "IMAGE", "FAKE_SA_MISSING")}
    full = {**clean, "PATH": f"{fake / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(fake / "calls.log"),
            "IMAGE": "us-central1-docker.pkg.dev/p/r/brain-jobs:abc123", **env}
    r = subprocess.run(["bash", os.path.join(ROOT, script)], env=full, capture_output=True, text=True, timeout=120)
    calls = (fake / "calls.log").read_text().splitlines() if (fake / "calls.log").exists() else []
    return r, calls


@pytest.mark.parametrize("brain", sorted(JOBS))
def test_deploys_as_its_own_account_and_orchestrator_invokes_it(fake, brain):
    script, job, acct = JOBS[brain]
    r, calls = run(fake, script)
    assert r.returncode == 0, r.stdout + r.stderr
    dep = next(c for c in calls if c.startswith(f"gcloud run jobs deploy {job} "))
    assert f"--service-account {acct}{P}" in dep
    assert not [c for c in calls if "brain-writer" in c], calls
    inv = [c for c in calls if c.startswith(f"gcloud run jobs add-iam-policy-binding {job} ")]
    assert inv and all(f"--member serviceAccount:brain-orchestrator{P} --role roles/run.invoker" in c for c in inv), inv
    assert not [c for c in calls if c.startswith("gcloud projects add-iam-policy-binding")], calls
    assert not [c for c in calls if c.startswith("gcloud iam service-accounts create")], calls


@pytest.mark.parametrize("brain", sorted(JOBS))
@pytest.mark.parametrize("missing", ["own", "invoker"])
def test_missing_account_fails_closed_and_never_falls_back(fake, brain, missing):
    script, job, acct = JOBS[brain]
    r, calls = run(fake, script, FAKE_SA_MISSING=(acct if missing == "own" else "brain-orchestrator") + "@")
    assert r.returncode != 0
    assert "does not exist" in r.stdout
    assert not [c for c in calls if c.startswith("gcloud run jobs deploy")], calls
    assert not [c for c in calls if "add-iam-policy-binding" in c], calls
    assert not [c for c in calls if "brain-writer" in c], calls


@pytest.mark.parametrize("brain", sorted(JOBS))
def test_sa_name_stays_overridable(fake, brain):
    script, job, _ = JOBS[brain]
    r, calls = run(fake, script, SA_NAME="some-other-account")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"--service-account some-other-account{P}" in next(c for c in calls if c.startswith(f"gcloud run jobs deploy {job} "))


def test_lake_bucket_grants_are_no_broader_than_the_identity_split_script():
    s = open(os.path.join(ROOT, JOBS["lake"][0])).read()
    grants = [l for l in s.splitlines() if "add-iam-policy-binding" in l and "storage buckets" in l]
    assert len(grants) == 2
    assert any('gs://$ARCHIVE_BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectAdmin' in l for l in grants)
    assert any('gs://$TVA_BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectViewer' in l for l in grants)


def test_orchestrator_workflow_refuses_another_identity_and_restores_the_account_on_rollback():
    wf = yaml.safe_load(open(os.path.join(ROOT, ".github/workflows/deploy-orchestrator.yml")))
    steps = {s.get("id"): s for s in wf["jobs"]["deploy"]["steps"] if s.get("id")}
    pre = steps["preflight"]["run"]
    assert '"${cur_sa%%@*}" != "brain-orchestrator"' in pre and "exit 1" in pre
    rb = steps["rollback"]["run"]
    assert 'prev_sa="$(python3' in rb and '${prev_sa:+--service-account "$prev_sa"}' in rb
    assert '["serviceAccount"] != sys.argv[2]' in rb
    assert 'a["serviceAccount"] == b["serviceAccount"]' in steps["verify"]["run"]
