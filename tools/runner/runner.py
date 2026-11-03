#!/usr/bin/env python3
"""Runner tools for a runner outside Cloud Run (Sector Pulse on the owner's Mac mini; Sector_Ops #50). DRAFT. Pulse calls these through its Engine bridge, from a
commit-pinned Engine snapshot, with a credential that can only do what is listed here. Nothing here writes a database or starts a job.

  runner.py show   --brain B (--bucket NAME | --store-dir DIR)
  runner.py renew  --brain B --holder pulse (--bucket NAME | --store-dir DIR)                     # heartbeat; refused if the lease is not this runner's or expired
  runner.py grant  --brain B --holder pulse --cycle C (--bucket | --store-dir)                     # ORCHESTRATOR ONLY (it is the single scheduling authority)
  runner.py upload --artifact artifact.json --holder pulse --started-at T --ended-at T [--cycle C] [--engine-commit SHA] (--bucket | --store-dir)
      verifies the locally sealed artifact (lineage present, canonical form), requires this runner to hold a fresh lease for the Brain, stores it create-only
      under artifacts/{brainId}/ with the Brain's ArtifactWriter (the same call Cloud Run jobs make), reads it back by digest, then creates the runner
      execution record the Orchestrator reconciles. Exit 0 = stored and verified; 3 = no lease; 4 = refused artifact; 5 = readback mismatch.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "brain_platform"))

from sector_brain_platform import runner_lease as RL                                  # noqa: E402
from sector_brain_platform.publisher.canonical import canonical_bytes, sha256_ref      # noqa: E402
from sector_brain_platform.publisher.handoff import ArtifactWriter                      # noqa: E402

REQUIRED_LINEAGE = ("brainId", "executionId", "artifactSchema", "generatedAt")


def _store(a):
    if a.store_dir:
        from sector_brain_platform.publisher.storage import LocalDirObjectStore
        return LocalDirObjectStore(a.store_dir)
    if a.bucket:
        from sector_brain_platform.object_bucket import GcsRestObjectStore
        from sector_brain_platform.rtdb import TokenProvider
        return GcsRestObjectStore(a.bucket, TokenProvider())
    raise SystemExit("REFUSED: give --bucket or --store-dir")


def _now():
    return dt.datetime.now(dt.timezone.utc)


def upload(a, store) -> int:
    try:
        art = json.load(open(a.artifact, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"REFUSED: unreadable artifact ({type(e).__name__})", file=sys.stderr)
        return 4
    lin = art.get("lineage") or {}
    missing = [k for k in REQUIRED_LINEAGE if not lin.get(k)]
    if missing:
        print(f"REFUSED: lineage lacks {missing}", file=sys.stderr)
        return 4
    brain = lin["brainId"]
    ok, why = RL.may_run(RL.runner_view(store, a.holder), brain, a.holder, _now())
    if not ok:
        print(f"REFUSED: {a.holder} may not hand off {brain} now ({why})", file=sys.stderr)
        return 3
    ref = ArtifactWriter(store, brain).write(art)                     # create-only; an identical re-upload is idempotent, a different one is an error
    back = store.get(ref.location)
    if back is None or sha256_ref(back) != ref.sha256 or canonical_bytes(json.loads(back)) != back:
        print("FAILED: readback does not match what was stored", file=sys.stderr)
        return 5
    rec = {"artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "schema": ref.expected_schema}
    key = RL.record_execution(RL.runner_view(store, a.holder), a.holder, brain, ref.execution_id, status="SUCCEEDED", started_at=a.started_at,
                              ended_at=a.ended_at, artifact=rec, cycle_id=a.cycle, engine_commit=a.engine_commit)
    print(json.dumps({"stored": rec, "executionRecord": key, "executionId": ref.execution_id}, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("show", "renew", "grant", "upload"))
    ap.add_argument("--bucket", default=None)
    ap.add_argument("--store-dir", default=None)
    ap.add_argument("--brain", default=None)
    ap.add_argument("--holder", choices=RL.HOLDERS, default=None)
    ap.add_argument("--cycle", default=None)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--started-at", default=None)
    ap.add_argument("--ended-at", default=None)
    ap.add_argument("--engine-commit", default=None)
    a = ap.parse_args(argv)
    store = _store(a)
    if a.cmd == "show":
        cur, _ = RL.read(RL.orchestrator_view(store), a.brain)
        print(json.dumps({"lease": cur, "fresh": RL.fresh(cur, _now())}, sort_keys=True))
        return 0
    if a.cmd == "renew":
        try:
            print(json.dumps(RL.renew(RL.runner_view(store, a.holder), a.brain, a.holder, _now()), sort_keys=True))
            return 0
        except RL.LeaseLost as e:
            print(f"LEASE LOST: {e}", file=sys.stderr)
            return 3
    if a.cmd == "grant":
        try:
            print(json.dumps(RL.grant(RL.orchestrator_view(store), RL.load_policy(), a.brain, a.holder, a.cycle, _now()), sort_keys=True))
            return 0
        except RL.LeaseBusy as e:
            print(f"NOT GRANTED: {e}", file=sys.stderr)
            return 3
    if not (a.artifact and a.holder and a.started_at and a.ended_at):
        print("REFUSED: upload needs --artifact, --holder, --started-at and --ended-at", file=sys.stderr)
        return 2
    return upload(a, store)


if __name__ == "__main__":
    sys.exit(main())
