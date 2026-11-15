"""deploy.sh IMAGE= mode (docs/architecture/conditions/DEPLOY_WORKFLOWS_V1.md §1): `--image` instead of `--source`, everything else the same
flow. deploy.sh runs from a throwaway git repository against a FAKE gcloud that records every call (SKIP_SMOKE=1: no HTTP). Nothing reaches
Google Cloud."""
import os
import shutil
import stat
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

FAKE_GCLOUD = r'''#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
state="$(cat "$FAKE_STATE" 2>/dev/null || echo before)"
case "$*" in
  "run deploy"*) echo after > "$FAKE_STATE";;
  "run services describe"*"--format=json"*)
    if [[ "$state" == after ]]; then
      echo '{"status":{"latestCreatedRevisionName":"sector-engine-00002-new","url":"https://svc","traffic":[{"revisionName":"sector-engine-00001-old","percent":100},{"revisionName":"sector-engine-00002-new","percent":0,"tag":"candidate","url":"https://candidate---svc"}]}}'
    else
      echo '{"status":{"latestCreatedRevisionName":"sector-engine-00001-old","url":"https://svc","traffic":[{"revisionName":"sector-engine-00001-old","percent":100}]}}'
    fi;;
  "run revisions describe"*"serviceAccountName"*) echo "${FAKE_RUNS_AS:-}";;
  "run revisions describe"*) echo "$FAKE_SHA";;
  "run services describe"*"value(status.url)"*) echo "https://svc";;
esac
exit 0
'''


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "ops").mkdir(parents=True)
    (r / "scripts").mkdir()
    shutil.copy(os.path.join(ROOT, "deploy.sh"), r / "deploy.sh")
    for stub in ("ops/check_warm_tags.sh", "scripts/linux-smoke.sh"):
        (r / stub).write_text('#!/usr/bin/env bash\necho "stub $0 IMAGE=${IMAGE:-} SKIP_BUILD=${SMOKE_SKIP_BUILD:-}" >> "$FAKE_LOG"\nexit 0\n')
        (r / stub).chmod(0o755)
    (r / ".gitignore").write_text("gha-creds-*.json\n")
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True, text=True).stdout.strip()   # noqa: E731
    g("init", "-q", "-b", "main")
    g("-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x")
    g("update-ref", "refs/remotes/origin/main", "HEAD")
    sha = g("rev-parse", "HEAD")
    g("checkout", "-q", "--detach", sha)                        # what actions/checkout of an exact sha produces
    (r / "gha-creds-abc.json").write_text("{}")                 # google-github-actions/auth's credentials file: ignored, not "dirty"
    b = tmp_path / "bin"
    b.mkdir()
    (b / "gcloud").write_text(FAKE_GCLOUD)
    (b / "gcloud").chmod((b / "gcloud").stat().st_mode | stat.S_IEXEC)
    return r, sha, tmp_path


def run(repo, **env):
    r, sha, tmp = repo
    base = {k: v for k, v in os.environ.items() if k not in ("ALLOW_BRANCH_DEPLOY", "IMAGE", "SKIP_LINUX_SMOKE", "RUNTIME_SA")}
    full = {**base, "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(tmp / "calls.log"), "FAKE_STATE": str(tmp / "state"),
            "FAKE_SHA": sha[:12], "SKIP_SMOKE": "1", **env}
    p = subprocess.run(["bash", str(r / "deploy.sh")], cwd=r, env=full, capture_output=True, text=True, timeout=120)
    calls = (tmp / "calls.log").read_text().splitlines() if (tmp / "calls.log").exists() else []
    return p, calls


DIGEST = "us-central1-docker.pkg.dev/p/sector-engine/sector-engine@sha256:" + "a" * 64


def test_image_mode_deploys_the_digest_with_the_same_flow(repo):
    p, calls = run(repo, IMAGE=DIGEST)
    assert p.returncode == 0, p.stdout + p.stderr
    dep = next(c for c in calls if c.startswith("gcloud run deploy"))
    assert f"--image {DIGEST}" in dep and "--source" not in dep and "--allow-unauthenticated" not in dep
    for flag in ("--no-traffic", "--tag candidate", f"--labels commit={repo[1][:12]}", "--memory 1Gi", "--cpu 2", "--concurrency 1",
                 "--min-instances 0", "--max-instances 30", "--update-secrets USGS_API_KEY=usgs-api-key:latest", "--startup-probe", "--liveness-probe"):
        assert flag in dep, flag
    assert "--set-env-vars" not in dep and "--clear-env-vars" not in dep
    assert any("update-traffic" in c and "--to-revisions sector-engine-00002-new=100" in c for c in calls)
    assert any(f"linux-smoke.sh IMAGE={DIGEST} SKIP_BUILD=1" in c for c in calls)       # the smoke test runs on the prebuilt image
    assert "Rollback: ./deploy.sh --rollback sector-engine-00001-old" in p.stdout


def test_default_source_path_is_unchanged(repo):
    p, calls = run(repo, ALLOW_BRANCH_DEPLOY="1")             # detached HEAD without IMAGE needs the existing override
    assert p.returncode == 0, p.stdout + p.stderr
    dep = next(c for c in calls if c.startswith("gcloud run deploy"))
    assert "--source ." in dep and "--allow-unauthenticated" in dep and "--image" not in dep
    assert any("linux-smoke.sh IMAGE= SKIP_BUILD=" in c for c in calls)


def test_image_must_be_a_digest(repo):
    p, calls = run(repo, IMAGE="us-central1-docker.pkg.dev/p/sector-engine/sector-engine:abc")
    assert p.returncode != 0 and not calls


def test_image_mode_refuses_a_commit_not_on_main(repo):
    r, _, _ = repo
    subprocess.run(["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "off main"], check=True)
    p, calls = run(repo, IMAGE=DIGEST, SKIP_LINUX_SMOKE="1")
    assert p.returncode != 0 and "not main" in p.stdout
    assert not [c for c in calls if c.startswith("gcloud run deploy")]


def test_rollback_path_is_unchanged(repo):
    r, _, tmp = repo
    full = {**os.environ, "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}", "FAKE_LOG": str(tmp / "rb.log"), "FAKE_STATE": str(tmp / "state"),
            "SKIP_LINUX_SMOKE": "1"}
    q = subprocess.run(["bash", str(r / "deploy.sh"), "--rollback", "sector-engine-00001-old"], cwd=r, env=full, capture_output=True, text=True)
    assert q.returncode == 0
    assert any("update-traffic sector-engine" in c and "--to-revisions sector-engine-00001-old=100" in c for c in (tmp / "rb.log").read_text().splitlines())


RUNTIME = "sector-engine-runtime@example-project.iam.gserviceaccount.com"


def test_runtime_sa_is_passed_checked_and_never_printed(repo):
    p, calls = run(repo, IMAGE=DIGEST, RUNTIME_SA=RUNTIME, FAKE_RUNS_AS=RUNTIME)
    assert p.returncode == 0, p.stdout + p.stderr
    assert f"--service-account {RUNTIME}" in next(c for c in calls if c.startswith("gcloud run deploy"))
    assert "candidate runs as RUNTIME_SA" in p.stdout
    assert "iam.gserviceaccount.com" not in p.stdout + p.stderr


def test_candidate_with_another_identity_is_not_promoted(repo):
    p, calls = run(repo, IMAGE=DIGEST, RUNTIME_SA=RUNTIME, FAKE_RUNS_AS="old-runtime@example-project.iam.gserviceaccount.com")
    assert p.returncode != 0 and "does not run as RUNTIME_SA" in p.stdout
    assert not [c for c in calls if "update-traffic" in c and "--to-revisions" in c]
    assert "iam.gserviceaccount.com" not in p.stdout + p.stderr


@pytest.mark.parametrize("env", [{"RUNTIME_SA": RUNTIME},                                  # --source path: refused
                                 {"IMAGE": DIGEST, "RUNTIME_SA": "not-an-email"}])
def test_runtime_sa_refusals(repo, env):
    p, calls = run(repo, ALLOW_BRANCH_DEPLOY="1", **env)
    assert p.returncode == 2 and not [c for c in calls if c.startswith("gcloud run deploy")]


def test_without_runtime_sa_the_identity_flag_is_not_passed(repo):
    p, calls = run(repo, IMAGE=DIGEST)
    assert p.returncode == 0 and "--service-account" not in next(c for c in calls if c.startswith("gcloud run deploy"))
