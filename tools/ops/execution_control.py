#!/usr/bin/env python3
"""OWNER CLI for the global Brain execution control at /control/executionControlV1 (Rehtac Cortex 2.7.0 PL-16; fam.control-execution-control,
registry writer @external-admin). Run by the owner with their own gcloud identity. No deployed component and no deploy script writes this node.

  python3 tools/ops/execution_control.py show
  python3 tools/ops/execution_control.py pause  --changed-by <name> --reason "<why>"                 # everything stops (default state)
  python3 tools/ops/execution_control.py enable --changed-by <name> --approval-ref <ref> --reason "<why>" \\
          --brains water-temp,water-clarity --confirm "RESUME RECURRING BRAIN EXECUTION"           # owner authorization only
  python3 tools/ops/execution_control.py brain  --changed-by <name> --brain wind --disable --reason "<why>"

`enable` leaves the Cloud Scheduler PAUSED: the central trigger is resumed separately by tools/ops/resume-orchestrator.sh, after its preflight.
`--dry-run` prints the document instead of writing it."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
from sector_brain_platform import execution_control as EC, orchestration as O  # noqa: E402

RTDB = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
CONFIRM = "RESUME RECURRING BRAIN EXECUTION"


def _token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()


def read() -> dict | None:
    req = urllib.request.Request(f"{RTDB}/{EC.NODE}.json", headers={"Authorization": f"Bearer {_token()}"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"null")


def write(doc: dict) -> None:
    req = urllib.request.Request(f"{RTDB}/{EC.NODE}.json", data=json.dumps(doc).encode(), method="PUT",
                                 headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("show", "pause", "enable", "brain"))
    ap.add_argument("--changed-by")
    ap.add_argument("--reason")
    ap.add_argument("--approval-ref")
    ap.add_argument("--brains", default="", help="enable: comma-separated Brain ids to enable (default: none)")
    ap.add_argument("--brain")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--enable-brain", dest="brain_on", action="store_const", const=True)
    g.add_argument("--disable", dest="brain_on", action="store_const", const=False)
    ap.add_argument("--max-starts-per-cycle", type=int, default=EC.DEFAULT_MAX_STARTS_PER_CYCLE)
    ap.add_argument("--confirm", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    ids = sorted(O.load_manifest()["brains"])
    cur_raw = None if a.dry_run and a.cmd != "show" else read()
    cur = EC.parse(cur_raw)
    if a.cmd == "show":
        print(json.dumps({"raw": cur_raw, "effective": EC.summary(cur)}, indent=1))
        return 0
    if not (a.changed_by and a.reason):
        print("--changed-by and --reason are required (audit)", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    brains = {b: {"enabled": (cur["brains"].get(b) or {}).get("enabled") is True, "limits": (cur["brains"].get(b) or {}).get("limits") or EC.DEFAULT_LIMITS} for b in ids}
    try:
        doc = _build(a, cur, brains, ids, now)
    except ValueError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    if doc is None:
        return 2
    if EC.parse(doc)["state"] != doc["state"]:
        print("refused: the document would not parse to the requested state", file=sys.stderr)
        return 2
    if a.dry_run:
        print(json.dumps(doc, indent=1))
        return 0
    write(doc)
    print(f"wrote {EC.NODE}: {doc['state']}; enabled Brains {[b for b, v in brains.items() if v['enabled']] or 'none'}")
    if doc["state"] == "ENABLED":
        print("the brain-orchestrator Cloud Scheduler is still PAUSED: resume it only with tools/ops/resume-orchestrator.sh")
    return 0


def _build(a, cur, brains, ids, now):
    if a.cmd == "pause":
        doc = EC.document("PAUSED", brains=brains, changed_by=a.changed_by, changed_at=now, approval_ref=a.approval_ref, reason=a.reason,
                          max_starts_per_cycle=a.max_starts_per_cycle)
    elif a.cmd == "enable":
        if a.confirm != CONFIRM:
            print(f'enable needs --confirm "{CONFIRM}" (owner authorization of recurring cloud spending)', file=sys.stderr)
            return None
        want = [b for b in a.brains.split(",") if b]
        unknown = sorted(set(want) - set(ids))
        if unknown:
            print(f"unknown Brain ids {unknown}", file=sys.stderr)
            return None
        for b in ids:
            brains[b]["enabled"] = b in want
        doc = EC.document("ENABLED", brains=brains, changed_by=a.changed_by, changed_at=now, approval_ref=a.approval_ref, reason=a.reason,
                          max_starts_per_cycle=a.max_starts_per_cycle)
    else:
        if a.brain not in ids or a.brain_on is None:
            print("brain needs --brain <id> and --enable-brain or --disable", file=sys.stderr)
            return None
        brains[a.brain]["enabled"] = a.brain_on
        doc = EC.document(cur["state"], brains=brains, changed_by=a.changed_by, changed_at=now, approval_ref=cur.get("approvalRef"),
                          reason=a.reason, max_starts_per_cycle=cur.get("maxStartsPerCycle", EC.DEFAULT_MAX_STARTS_PER_CYCLE))
    return doc


if __name__ == "__main__":
    sys.exit(main())
