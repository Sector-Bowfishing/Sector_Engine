#!/usr/bin/env python3
"""Lake Brain artifact mode (Sector_Ops #48 step A2, decision WT-1 (a); DRAFT, not deployed).

Runs the Swift job in DRY-RUN form (`LakeBrainJob --dry-run DIR`, optionally `--read-rtdb URL` for GET-only reads of the previous profiles),
reads the write set it produced, seals it with the existing Python builder (`publish_artifact.py`, bundle `lake-publication-v1`) and stores ONE
artifact create-only under `artifacts/lake-brain/` with the Brain's ArtifactWriter. It performs NO database write: the central Publisher is the
only writer once Lake is CENTRAL. One implementation of the envelope and sealing (the Python builder) serves both Swift Brains.

  python artifact_entry.py --job LakeBrainJob [--scope pilots] [--read-rtdb URL] [--archive gs://B|DIR] (--artifact-bucket B | --artifact-dir DIR)
  python artifact_entry.py --from-dir DIR (--artifact-bucket B | --artifact-dir DIR)        # seal an existing dry-run folder (tests, a runner)
env: SECTOR_ENGINE_COMMIT (code version recorded in the lineage)

Exit 0 = artifact stored (its reference is printed as JSON); 2 = refused (nothing stored); 3 = the job failed (nothing stored).
Known limit: the Swift dry-run folder represents a delete (null) by removing the file, so a run that deletes a path cannot be sealed faithfully
from the folder. The recorded write set has no deletes today; a run with a `null` is refused here until the Swift side records deletes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import publish_artifact as pa                                                       # noqa: E402

BRAIN_ID = "lake-brain"


def read_write_set(directory: str) -> dict:
    """{path: value} from a LocalDirectoryStore folder (each path written as `<path>.json`). Underscore folders (the job's local archive) are not paths."""
    out = {}
    for dp, ds, fs in os.walk(directory):
        ds[:] = sorted(d for d in ds if not d.startswith("_") and not d.startswith("."))
        for f in sorted(fs):
            if not f.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), directory)[:-5]
            out[rel.replace(os.sep, "/")] = json.load(open(os.path.join(dp, f), encoding="utf-8"))
    return out


def seal(updates: dict, *, now: dt.datetime, code_version: str) -> dict:
    if any(v is None for v in updates.values()):
        raise ValueError("the write set contains a delete (null): refused until the Swift dry run records deletes")
    built = pa.build_artifact(updates, pa.BuildContext(now.strftime("%Y-%m-%dT%H:%M:%SZ"), str(uuid.uuid4()), code_version), consumed=None)
    if not built.artifact:
        raise ValueError("the builder produced no artifact")
    return built.artifact


def store_for(a):
    if a.artifact_dir:
        from sector_brain_platform.publisher.storage import LocalDirObjectStore
        return LocalDirObjectStore(a.artifact_dir)
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    from sector_brain_platform.rtdb import TokenProvider
    return GcsRestObjectStore(a.artifact_bucket, TokenProvider())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default=None, help="path to the LakeBrainJob executable")
    ap.add_argument("--from-dir", default=None, help="an existing dry-run folder to seal instead of running the job")
    ap.add_argument("--scope", default="pilots")
    ap.add_argument("--read-rtdb", default=None)
    ap.add_argument("--archive", default=None)
    ap.add_argument("--artifact-bucket", default=os.environ.get("LAKE_ARTIFACT_BUCKET"))
    ap.add_argument("--artifact-dir", default=None)
    a = ap.parse_args(argv)
    if not (a.artifact_bucket or a.artifact_dir) or bool(a.job) == bool(a.from_dir):
        print("REFUSED (nothing stored): give --job or --from-dir, and --artifact-bucket or --artifact-dir", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.timezone.utc)
    with tempfile.TemporaryDirectory(prefix="lake-dry-run-") as td:
        src = a.from_dir
        if a.job:
            src = td
            cmd = [a.job, "--dry-run", td, "--scope", a.scope] + (["--read-rtdb", a.read_rtdb] if a.read_rtdb else []) + (["--archive", a.archive] if a.archive else [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            sys.stdout.write(r.stdout[-2000:])
            if r.returncode != 0:
                print(f"FAILED (nothing stored): LakeBrainJob exit {r.returncode}: {r.stderr[-500:]}", file=sys.stderr)
                return 3
        try:
            art = seal(read_write_set(src), now=now, code_version=f"lake-brain@{os.environ.get('SECTOR_ENGINE_COMMIT', 'unknown')}")
        except ValueError as e:
            print(f"REFUSED (nothing stored): {e}", file=sys.stderr)
            return 2
    from sector_brain_platform.publisher.handoff import ArtifactWriter
    ref = ArtifactWriter(store_for(a), BRAIN_ID).write(art)
    print(json.dumps({"artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "executionId": ref.execution_id,
                      "artifactSchema": ref.expected_schema}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
