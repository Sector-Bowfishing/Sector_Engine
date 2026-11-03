#!/usr/bin/env python3
"""Water Temperature artifact mode (Sector_Ops #50 WT-P2 A2, cutover gate G1, decision WT-1 (a); DRAFT, not deployed).

Runs `WaterTempBrainJob --dry-run DIR` (with `--read-rtdb URL` for GET-only reads of the previous state, Engine #104), seals the write set
with `publish_artifact.py` (bundle `water-temp-publication-v1`) and stores ONE artifact create-only under `artifacts/water-temp/`. NO database
write. The shared implementation is sector_brain_platform.swift_artifact_entry (also used by Lake).

  python artifact_entry.py --job WaterTempBrainJob [--lake ID ...] [--limit N] [--read-rtdb URL] (--artifact-bucket B | --artifact-dir DIR)
  python artifact_entry.py --from-dir DIR (--artifact-bucket B | --artifact-dir DIR)        # seal an existing dry-run folder (tests, a runner)
env: SECTOR_ENGINE_COMMIT (code version recorded in the lineage); the Swift job reads SECTOR_BRAIN_ACCESS_TOKEN for --read-rtdb

Exit 0 = artifact stored (its reference is printed as JSON); 2 = refused (nothing stored); 3 = the job failed (nothing stored).
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import publish_artifact as pa                                                       # noqa: E402
from sector_brain_platform import swift_artifact_entry as SE               # noqa: E402

BRAIN_ID = "water-temp"
read_write_set = SE.read_write_set


def seal(updates: dict, *, now: dt.datetime, code_version: str) -> dict:
    return SE.seal(pa, updates, now=now, code_version=code_version)


def _job_args(ap):
    ap.add_argument("--lake", action="append", default=[])
    ap.add_argument("--limit", type=int, default=None)       # an int, so a typo is refused here (exit 2) instead of the Swift job running the whole fleet


def _job_command(a, td):
    cmd = [a.job, "--dry-run", td]
    for lake in a.lake:
        cmd += ["--lake", lake]
    if a.limit:
        cmd += ["--limit", str(a.limit)]
    return cmd + (["--read-rtdb", a.read_rtdb] if a.read_rtdb else [])


def main(argv=None) -> int:
    return SE.main(argv, brain_id=BRAIN_ID, builder=pa, bucket_env="WATER_TEMP_ARTIFACT_BUCKET", add_job_args=_job_args, job_command=_job_command)


if __name__ == "__main__":
    sys.exit(main())
