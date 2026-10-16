import os, subprocess, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import preflight_lineage as L


def g(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(cwd, rel, text):
    p = os.path.join(cwd, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(text)


@pytest.fixture
def repo(tmp_path):
    d = str(tmp_path)
    g(d, "init", "-q", "-b", "main"); g(d, "config", "user.email", "t@t"); g(d, "config", "user.name", "t")
    write(d, "jobs/brain-scores/score_brains.py", "def rtdb_safe(): pass\ndef _content(): pass\n# score.changed\nguard_scores = 1\n")
    write(d, "jobs/brain-scores/check_score_artifacts.py", "def compare(): pass\n")
    write(d, "jobs/brain-orchestrator/deploy-job.sh", "python3 check_score_artifacts.py\n")
    write(d, "jobs/brain-orchestrator/orchestrate.py", '"--if-changed"\n')
    g(d, "add", "."); g(d, "commit", "-qm", "deployed")
    return d


def test_descendant_of_deployed_passes(repo):
    dep = g(repo, "rev-parse", "HEAD")
    write(repo, "jobs/brain_platform/x.py", "1\n"); g(repo, "add", "."); g(repo, "commit", "-qm", "new")
    fails, notes = L.check(dep, "HEAD", repo)
    assert fails == [] and any("shared-path diff" in n for n in notes)


def test_branch_cut_before_the_deployed_commit_is_refused(repo):
    old = g(repo, "rev-parse", "HEAD")
    g(repo, "checkout", "-q", "-b", "specialist")
    g(repo, "checkout", "-q", "main"); write(repo, "jobs/brain_platform/y.py", "1\n"); g(repo, "add", "."); g(repo, "commit", "-qm", "deployed work")
    deployed = g(repo, "rev-parse", "HEAD")
    fails, _ = L.check(deployed, "specialist", repo)       # specialist branch lacks the deployed work
    assert fails and "NOT an ancestor" in fails[0]
    assert old != deployed


def test_removed_protection_is_refused(repo):
    dep = g(repo, "rev-parse", "HEAD")
    write(repo, "jobs/brain-scores/score_brains.py", "def _content(): pass\n# score.changed\n"); g(repo, "add", "."); g(repo, "commit", "-qm", "oops")
    fails, _ = L.check(dep, "HEAD", repo)
    assert any("rtdb_safe" in f for f in fails) and any("guard_scores" in f for f in fails)


def test_unknown_or_missing_deployed_commit_is_unverifiable_not_passed(repo):
    assert L.check(None, "HEAD", repo)[0]
    assert "not in this repository" in L.check("deadbeef" * 5, "HEAD", repo)[0][0]
