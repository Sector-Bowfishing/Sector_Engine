"""Artifact mode for the Swift Brains (Lake, Water Temperature): one implementation of "run the Swift job as a dry run, seal its write set
with the Brain's Python builder, store ONE artifact create-only" (cutover decision WT-1 (a); Sector_Ops #48 A2, #50 WT-P2).

The Swift job runs in DRY-RUN form (`<Job> --dry-run DIR`, optionally `--read-rtdb URL` for GET-only reads of the previous state). This module
reads the folder it wrote, seals it with the Brain's `publish_artifact.build_artifact`, and stores the artifact under `artifacts/<brainId>/`
with the Brain's ArtifactWriter. It performs NO database write: the central Publisher is the only writer once the Brain is CENTRAL.

Exit 0 = artifact stored (its reference is printed as JSON); 2 = refused (nothing stored); 3 = the job failed (nothing stored).
Known limit: the Swift dry-run folder represents a delete (null) by removing the file, so a run that deletes a path cannot be sealed faithfully
from the folder. The recorded write sets have no deletes today; a `null` value is refused until the Swift side records deletes.
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
from typing import Callable


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


def seal(builder, updates: dict, *, now: dt.datetime, code_version: str) -> dict:
    if any(v is None for v in updates.values()):
        raise ValueError("the write set contains a delete (null): refused until the Swift dry run records deletes")
    built = builder.build_artifact(updates, builder.BuildContext(now.strftime("%Y-%m-%dT%H:%M:%SZ"), str(uuid.uuid4()), code_version), consumed=None)
    if not built.artifact:
        raise ValueError("the builder produced no artifact")
    return built.artifact


def store_for(artifact_dir: str | None, artifact_bucket: str | None):
    if artifact_dir:
        from .publisher.storage import LocalDirObjectStore
        return LocalDirObjectStore(artifact_dir)
    from .object_bucket import GcsRestObjectStore
    from .rtdb import TokenProvider
    return GcsRestObjectStore(artifact_bucket, TokenProvider())


def main(argv, *, brain_id: str, builder, bucket_env: str, add_job_args: Callable[[argparse.ArgumentParser], None],
         job_command: Callable[[argparse.Namespace, str], list[str]], validate: Callable[[argparse.Namespace], str | None] | None = None) -> int:
    """The CLI both Brains share. `add_job_args` declares the Brain's own job flags; `job_command(a, dir)` builds the dry-run command line; `validate(a)` (optional)
    returns a refusal reason for the PARSED arguments, so a check holds whatever spelling argparse accepted (abbreviations, `=` forms)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default=None, help="path to the Swift job executable")
    ap.add_argument("--from-dir", default=None, help="an existing dry-run folder to seal instead of running the job")
    ap.add_argument("--read-rtdb", default=None, help="with --job: the live Brain RTDB the dry run reads (GET only) for the previous state")
    add_job_args(ap)
    ap.add_argument("--artifact-bucket", default=os.environ.get(bucket_env))
    ap.add_argument("--artifact-dir", default=None)
    ap.add_argument("--emit", default=None, help="also write the sealed artifact JSON to this LOCAL file (a runner's hand-off, e.g. Pulse's {out}/artifact.json)")
    a = ap.parse_args(argv)
    why = validate(a) if validate else None
    if why:
        print(f"REFUSED (nothing stored): {why}", file=sys.stderr)
        return 2
    if not (a.artifact_bucket or a.artifact_dir) or bool(a.job) == bool(a.from_dir):
        print("REFUSED (nothing stored): give --job or --from-dir, and --artifact-bucket or --artifact-dir", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.timezone.utc)
    with tempfile.TemporaryDirectory(prefix=f"{brain_id}-dry-run-") as td:
        src = a.from_dir
        if a.job:
            src = td
            r = subprocess.run(job_command(a, td), capture_output=True, text=True)
            sys.stdout.write(r.stdout[-2000:])
            if r.returncode != 0:
                print(f"FAILED (nothing stored): {os.path.basename(a.job)} exit {r.returncode}: {r.stderr[-500:]}", file=sys.stderr)
                return 3
        try:
            art = seal(builder, read_write_set(src), now=now, code_version=f"{brain_id}@{os.environ.get('SECTOR_ENGINE_COMMIT', 'unknown')}")
        except ValueError as e:
            print(f"REFUSED (nothing stored): {e}", file=sys.stderr)
            return 2
    from .publisher.handoff import ArtifactWriter
    ref = ArtifactWriter(store_for(a.artifact_dir, a.artifact_bucket), brain_id).write(art)
    if (a.emit or "").strip():
        if a.emit.startswith("gs://"):
            print("REFUSED: --emit is a local file", file=sys.stderr)
            return 2
        with open(a.emit, "x") as fh:                                                   # never overwrites an earlier hand-off
            json.dump(art, fh, sort_keys=True)
    print(json.dumps({"artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "executionId": ref.execution_id,
                      "artifactSchema": ref.expected_schema}, sort_keys=True))
    return 0
