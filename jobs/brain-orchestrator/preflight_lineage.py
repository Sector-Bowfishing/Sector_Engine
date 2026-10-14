#!/usr/bin/env python3
"""Shared-infrastructure lineage preflight: NO SPECIALIST BRANCH MAY ROLL THE SHARED ORCHESTRATOR BACKWARD.

Run by deploy-job.sh before anything is staged or deployed. Fails (exit 1) when:
  1. the currently deployed commit (Cloud Run job label `commit`) is NOT an ancestor of HEAD   -> HEAD would roll shared code backward / sideways;
  2. a protection that exists at the deployed commit is missing at HEAD                       -> a durability safeguard was removed;
  3. the deployed commit cannot be determined or is not in the local repo                     -> unverifiable (fetch, or pass --deployed-sha).
Override only with a recorded decision: ALLOW_BACKWARD_LINEAGE=1.

  python3 preflight_lineage.py [--job brain-orchestrator] [--deployed-sha <sha>] [--head HEAD]
Local git + one read-only `gcloud run jobs describe`. No network writes."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SHARED_PATHS = ("jobs/brain-orchestrator", "jobs/brain-scores", "jobs/brain_platform", "docs/brains/scoring", "docs/brains/conformance")
# (path, substring that must still be present at HEAD if it was present at the deployed commit). Each is a durability safeguard.
PROTECTIONS = (
    ("jobs/brain-scores/score_brains.py", "def rtdb_safe"),                 # RTDB-illegal key sanitising (Wind 'Freshness/reliability' incident)
    ("jobs/brain-scores/score_brains.py", "def _content"),                  # content-aware publication (no perpetual rewrites)
    ("jobs/brain-scores/score_brains.py", "score.changed"),                 # change events
    ("jobs/brain-scores/check_score_artifacts.py", "def compare"),          # stale-artifact deploy guard
    ("jobs/brain-scores/score_brains.py", "guard_scores"),                  # runtime stale-score guard (Model v1)
    ("jobs/brain-orchestrator/deploy-job.sh", "check_score_artifacts.py"),  # guard wired into the deploy
    ("jobs/brain-orchestrator/orchestrate.py", "--if-changed"),             # score publish only after a state change
    ("jobs/brain-orchestrator/orchestrate.py", "control_plane"),            # PRE_PRODUCTION decision model gates execution
    ("jobs/brain_platform/sector_brain_platform/orchestration.py", "schedule_policy"),   # recurring-compute policy is code, not only docs
)


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def show(ref, path, cwd=ROOT):
    r = git("show", f"{ref}:{path}", cwd=cwd)
    return r.stdout if r.returncode == 0 else None


def deployed_sha(job: str) -> str | None:
    r = subprocess.run(["gcloud", "run", "jobs", "describe", job, "--region", os.environ.get("REGION", "us-central1"),
                        "--project", os.environ.get("PROJECT_ID", "sector-9393c"), "--format=value(metadata.labels.commit)"], capture_output=True, text=True)
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def check(deployed: str | None, head: str = "HEAD", cwd: str = ROOT) -> tuple[list[str], list[str]]:
    """-> (failures, notes)."""
    fails, notes = [], []
    if not deployed:
        return ["cannot determine the deployed commit (no `commit` label / gcloud unavailable): pass --deployed-sha"], notes
    if git("cat-file", "-e", f"{deployed}^{{commit}}", cwd=cwd).returncode != 0:
        return [f"deployed commit {deployed} is not in this repository: `git fetch --all` (or the deploy came from another clone)"], notes
    if git("merge-base", "--is-ancestor", deployed, head, cwd=cwd).returncode != 0:
        base = git("merge-base", deployed, head, cwd=cwd).stdout.strip()[:12]
        fails.append(f"deployed commit {deployed} is NOT an ancestor of {head} (merge-base {base or 'none'}): deploying would roll shared infrastructure backward or drop deployed work")
    for path, needle in PROTECTIONS:
        then, now = show(deployed, path, cwd), show(head, path, cwd)
        if then is not None and needle in then and (now is None or needle not in now):
            fails.append(f"protection removed: {path} no longer contains {needle!r}")
        elif then is None:
            notes.append(f"(protection {path}::{needle} did not exist at the deployed commit)")
    diff = git("diff", "--stat", f"{deployed}..{head}", "--", *SHARED_PATHS, cwd=cwd).stdout.strip().splitlines()
    notes.append(f"shared-path diff {deployed[:8]}..{head}: " + (diff[-1].strip() if diff else "no shared-path changes"))
    return fails, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default="brain-orchestrator")
    ap.add_argument("--deployed-sha", default=None)
    ap.add_argument("--head", default="HEAD")
    a = ap.parse_args()
    sha = a.deployed_sha or deployed_sha(a.job)
    fails, notes = check(sha, a.head)
    for n in notes:
        print("  ", n)
    for f in fails:
        print("  FAIL:", f, file=sys.stderr)
    if fails and os.environ.get("ALLOW_BACKWARD_LINEAGE") == "1":
        print("  !! ALLOW_BACKWARD_LINEAGE=1: proceeding past lineage failures (record the decision)")
        return 0
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
