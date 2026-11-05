#!/usr/bin/env python3
"""Lake Brain artifact mode (Sector_Ops #48 step A2, decision WT-1 (a); DRAFT, not deployed).

Runs `LakeBrainJob --dry-run DIR` (optionally `--read-rtdb URL`, GET-only reads of the previous profiles), seals the write set with
`publish_artifact.py` (bundle `lake-publication-v1`) and stores ONE artifact create-only under `artifacts/lake-brain/`. NO database write.
The shared implementation is sector_brain_platform.swift_artifact_entry (also used by Water Temperature).

  python artifact_entry.py --job LakeBrainJob [--scope pilots] [--read-rtdb URL] [--archive gs://B|DIR] (--artifact-bucket B | --artifact-dir DIR)
  python artifact_entry.py --from-dir DIR (--artifact-bucket B | --artifact-dir DIR)        # seal an existing dry-run folder (tests, a runner)
env: SECTOR_ENGINE_COMMIT (code version recorded in the lineage)

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

BRAIN_ID = "lake-brain"
read_write_set = SE.read_write_set


def seal(updates: dict, *, now: dt.datetime, code_version: str) -> dict:
    return SE.seal(pa, updates, now=now, code_version=code_version)


def _job_args(ap):
    ap.add_argument("--scope", default="pilots")
    ap.add_argument("--archive", default=None)
    ap.add_argument("--seed-archive", default=None, help="read-only fallback history archive (gs:// allowed: read only)")
    ap.add_argument("--presence", default=None, help="where the private presence release lives")
    ap.add_argument("--fault", action="append", default=[], help="REHEARSAL ONLY, with --artifact-dir: e.g. cwms-unreachable (Sector_Ops #48 B4b)")


def _job_command(a, td):
    return ([a.job, "--dry-run", td, "--scope", a.scope] + (["--read-rtdb", a.read_rtdb] if a.read_rtdb else []) + (["--archive", a.archive] if a.archive else [])
            + (["--seed-archive", a.seed_archive] if a.seed_archive else []) + (["--presence", a.presence] if a.presence else [])
            + [x for f in a.fault for x in ("--fault", f)])


def _validate(a) -> str | None:
    """On the PARSED arguments (so `--fa`, `--fault=x` and an empty `--artifact-dir ""` are all seen): a fault-injected artifact must never reach a bucket."""
    if a.fault and not (a.artifact_dir or "").strip():
        return "--fault is a rehearsal and needs --artifact-dir (a local folder), never a bucket"
    if a.fault and a.from_dir:
        return "--fault applies to a --job run; --from-dir seals an existing folder"
    return None


def main(argv=None) -> int:
    return SE.main(argv, brain_id=BRAIN_ID, builder=pa, bucket_env="LAKE_ARTIFACT_BUCKET", add_job_args=_job_args, job_command=_job_command, validate=_validate)


if __name__ == "__main__":
    sys.exit(main())
