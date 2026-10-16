#!/usr/bin/env python3
"""Pre-production schedule audit (docs/brains/platform/cost-freeze/schedule-policy.json).

Fails (exit 1) when a Brain-related Cloud Scheduler job is ENABLED but not on the policy allowlist with gate, cost bound and stop condition.
Read-only: one `gcloud scheduler jobs list`, or --input <file.json> for tests.

  python3 check_preproduction_schedules.py            # live
  python3 check_preproduction_schedules.py --input jobs.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY = os.path.join(HERE, "..", "..", "docs", "brains", "platform", "cost-freeze", "schedule-policy.json")
REQUIRED = ("gate", "maxMonthlyUsd", "stop", "approvedAt")


def audit(jobs: list[dict], policy: dict) -> tuple[list[str], list[str]]:
    """-> (violations, enabled_ok)."""
    brain = set(policy["brainSchedulers"])
    allow = policy.get("allowEnabled", {})
    bad, ok = [], []
    for name, entry in allow.items():
        missing = [k for k in REQUIRED if not entry.get(k)]
        if missing:
            bad.append(f"allowlist entry {name} lacks {missing}")
    for j in jobs:
        name = (j.get("name") or "").rsplit("/", 1)[-1]
        if name not in brain or j.get("state") != "ENABLED":
            continue
        if name in allow:
            ok.append(name)
        else:
            bad.append(f"{name} is ENABLED ({j.get('schedule')}) but has no recorded readiness gate: pause it or add a gated allowlist entry")
    return bad, ok


def drift(jobs: list[dict], manifest: dict) -> list[str]:
    """Compare live Cloud Scheduler with the orchestrator's execution manifest (the single schedule model). Reports: a job the manifest says is
    PAUSED/MANUAL but is ENABLED; a VALIDATION_EXCEPTION that is not ENABLED (evidence capture silently off); a live scheduler the manifest does not know."""
    live = {(j.get("name") or "").rsplit("/", 1)[-1]: j for j in jobs}
    known = {mj.get("scheduler"): (jid, mj) for jid, mj in manifest["jobs"].items() if mj.get("scheduler")}
    out = []
    for sch, (jid, mj) in sorted(known.items()):
        st = (live.get(sch) or {}).get("state")
        if st is None:
            if mj["classification"] in ("VALIDATION_EXCEPTION", "ORCHESTRATOR_OWNED"):
                out.append(f"DRIFT {sch}: manifest says {mj['classification']} but no such scheduler exists")
        elif st == "ENABLED" and mj["classification"] in ("PAUSED", "MANUAL", "INPUT_DRIVEN"):
            out.append(f"DRIFT {sch}: ENABLED but the manifest classifies it {mj['classification']}")
        elif st != "ENABLED" and mj["classification"] == "VALIDATION_EXCEPTION":
            out.append(f"DRIFT {sch}: validation exception is {st}: prospective evidence capture is not running")
    for name in sorted(set(live) - set(known) - {"unrelated"}):
        out.append(f"UNMANAGED {name}: live scheduler not in the execution manifest (hidden cron) - classify it or confirm it is not Brain-related")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    a = ap.parse_args()
    if a.input:
        jobs = json.load(open(a.input))
    else:
        r = subprocess.run(["gcloud", "scheduler", "jobs", "list", "--location", os.environ.get("REGION", "us-central1"), "--format=json"], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr, file=sys.stderr); return 2
        jobs = json.loads(r.stdout)
    bad, ok = audit(jobs, json.load(open(POLICY)))
    sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
    from sector_brain_platform import orchestration as O
    notes = drift(jobs, O.load_manifest())
    print("enabled Brain schedulers with a gate:", ", ".join(ok) or "none")
    for n in notes:
        print(n, file=sys.stderr)
    bad += [n for n in notes if n.startswith(("DRIFT", "UNMANAGED"))]
    for b in bad:
        print("VIOLATION:", b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
