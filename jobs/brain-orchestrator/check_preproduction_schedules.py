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


def audit(jobs: list[dict], policy: dict, control: dict | None = None) -> tuple[list[str], list[str]]:
    """-> (violations, enabled_ok). control = the PARSED /control/executionControlV1 (execution_control.parse); None = not checked.
    Central scheduling (Cortex 2.7.0 PL-15/PL-16): a deprecated per-Brain scheduler must never be ENABLED, and the single authority may be
    ENABLED only while the execution control is ENABLED."""
    brain = set(policy["brainSchedulers"])
    allow = policy.get("allowEnabled", {})
    deprecated = policy.get("deprecatedSchedulers", {})
    bad, ok = [], []
    for j in jobs:
        name = (j.get("name") or "").rsplit("/", 1)[-1]
        if name in deprecated and j.get("state") == "ENABLED":
            bad.append(f"{name} is ENABLED but DEPRECATED (deprecated {deprecated[name].get('deprecatedAt')}): the orchestrator is the only scheduling authority (PL-15); pause it")
        need = (allow.get(name) or {}).get("requiresExecutionControl")
        if need and j.get("state") == "ENABLED" and (control is None or control.get("state") != need):
            bad.append(f"{name} is ENABLED while the execution control is {(control or {}).get('state', 'NOT CHECKED')}: it may run only with the control {need} (PL-16)")
    for name, entry in allow.items():
        missing = [k for k in REQUIRED if not entry.get(k)]
        if missing:
            bad.append(f"allowlist entry {name} lacks {missing}")
    for j in jobs:
        name = (j.get("name") or "").rsplit("/", 1)[-1]
        if name not in brain or j.get("state") != "ENABLED" or name in deprecated:
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
    for jid, mj in manifest["jobs"].items():                    # deprecated per-Brain schedulers: known, and must stay PAUSED (PL-15)
        dep = mj.get("deprecatedScheduler")
        if dep:
            known.setdefault(dep, (jid, {**mj, "classification": "PAUSED"}))
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
    ap.add_argument("--control-file", default=None, help="a /control/executionControlV1 document (tests); live mode reads the RTDB node")
    a = ap.parse_args()
    if a.input:
        jobs = json.load(open(a.input))
    else:
        r = subprocess.run(["gcloud", "scheduler", "jobs", "list", "--location", os.environ.get("REGION", "us-central1"), "--format=json"], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr, file=sys.stderr); return 2
        jobs = json.loads(r.stdout)
    sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
    from sector_brain_platform import orchestration as O, execution_control as EC
    control = None
    if a.control_file:
        control = EC.parse(json.load(open(a.control_file)))
    elif not a.input:
        r = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
        try:
            import urllib.request
            req = urllib.request.Request(f"{os.environ.get('BRAIN_RTDB_URL', 'https://sector-brain.firebaseio.com')}/{EC.NODE}.json",
                                         headers={"Authorization": f"Bearer {r.stdout.strip()}"})
            control = EC.parse(json.loads(urllib.request.urlopen(req, timeout=20).read() or b"null"))
        except Exception as e:                                    # unreadable = PAUSED (fail closed)
            control = EC.parse(None)
            print(f"execution control unreadable ({type(e).__name__}): treated as PAUSED", file=sys.stderr)
    if control is not None:
        print(f"execution control: {control['state']} ({control['reason']})")
    bad, ok = audit(jobs, json.load(open(POLICY)), control)
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
