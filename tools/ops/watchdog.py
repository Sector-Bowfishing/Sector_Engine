#!/usr/bin/env python3
"""OWNER CLI for the brain-orchestrator cycle watchdog (Sector_Ops #51, O6.3 in the system). Runs with the owner's own gcloud identity.

  python3 tools/ops/watchdog.py show                         the latch (HALTED / CLEARED / none)
  python3 tools/ops/watchdog.py check                        run every check now, read-only (no latch, no pause), and print the trips
  python3 tools/ops/watchdog.py clear --changed-by <name> --approval-ref <ref> --reason "<why>"
                                                             clear a HALTED latch (the halt is kept inside the CLEARED document)

Clearing does NOT resume anything: if the watchdog paused the scheduler, resume it with tools/ops/resume-orchestrator.sh after fixing the cause."""
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
from sector_brain_platform import cycle_watchdog as WD, execution_control as EC, gcp  # noqa: E402
from sector_brain_platform.object_bucket import GcsRestObjectStore  # noqa: E402

BUCKET = os.environ.get("PUBLICATION_ARTIFACT_BUCKET", "sector-9393c-brain-artifacts")
RTDB = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")


class OwnerTokens:
    def __init__(self):
        self._t = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()

    def token(self, *a, **k):
        return self._t

    __call__ = get = token


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("show", "check", "clear"))
    ap.add_argument("--changed-by")
    ap.add_argument("--approval-ref")
    ap.add_argument("--reason")
    a = ap.parse_args(argv)
    tokens = OwnerTokens()
    store = GcsRestObjectStore(BUCKET, tokens)
    now = dt.datetime.now(dt.timezone.utc)
    if a.cmd == "show":
        print(json.dumps(WD.read_latch(store), indent=1, sort_keys=True))
        return 0
    if a.cmd == "check":
        req = urllib.request.Request(f"{RTDB}/{EC.NODE}.json", headers={"Authorization": f"Bearer {tokens.token()}"})
        ctl = EC.parse(json.loads(urllib.request.urlopen(req, timeout=20).read() or b"null"))
        execs = {(j.get("metadata") or {}).get("name"): gcp.list_executions(tokens, (j.get("metadata") or {}).get("name"), limit=20)
                 for j in gcp.list_run_jobs(tokens)}
        res = WD.evaluate(WD.load_policy(), store=store, executions=execs, control=ctl, now=now)
        print(WD.log_line(res))
        for t in res.trips:
            print(f"  {t.kind}: {t.detail}")
        return 1 if (res.tripped or res.unreadable) else 0
    if not (a.changed_by and a.approval_ref and a.reason):
        print("clear needs --changed-by, --approval-ref and --reason", file=sys.stderr)
        return 2
    doc = WD.clear(store, changed_by=a.changed_by, approval_ref=a.approval_ref, reason=a.reason, now=now)
    print(f"latch CLEARED at {doc['at']}. The scheduler is NOT resumed: tools/ops/resume-orchestrator.sh, after fixing the cause.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
