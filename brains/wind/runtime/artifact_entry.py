#!/usr/bin/env python3
"""Wind Brain artifact mode for a runner's lease cycle (Sector_Ops #51, Roadmap #23 section 2; DRAFT, off: no catalog job enables it, nothing deployed).

The same steps as the wind-hourly Cloud Run job, with the database writer replaced by a DryRunWriter:

  1. `run_hourly` ingests the latest NBM cycle, the last hour of RTMA-RU and METAR into a LOCAL store (public NOAA/IEM sources, no credential);
  2. the UNCHANGED `safe_publish` computes the Wind Brain's write set into a DryRunWriter (no RtdbWriter is ever built here, whatever the env says);
  3. `artifact.build_artifacts` seals it as ONE `wind-publication-v1` bundle (publish-artifact-v2) with the packaged knowledge release's lineage;
  4. it is stored create-only in a LOCAL artifact store (--artifact-dir) and, with --emit, written to a LOCAL hand-off file (never overwritten).

  python artifact_entry.py --store local:DIR --artifact-dir DIR [--emit FILE] [--skip-ingest] [--execution-id UUID]
env: SECTOR_ENGINE_COMMIT (code version recorded in the lineage)

NO database write, no bucket write, no gs:// store. The artifact reaches the central path only through the runner's own upload (`tools/runner/runner.py
upload`, lease-checked). The Publisher refuses it until Wind's knowledge release has an approval record (knowledge-release.json `approval`), Wind is
CENTRAL in publication-cutover.json and the execution control enables Wind: each an owner step.

Exit 0 = artifact stored (its reference is printed as JSON); 2 = refused (nothing stored); 3 = the run produced no publishable artifact (nothing stored).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

BRAIN_ID = "wind"
EVIDENCE = os.path.join(HERE, "sector_wind", "brain", "validation_evidence.json")


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def build(store, cfg, *, now: dt.datetime, run_summary: dict | None, execution_id: str, code_version: str, release: dict | None,
          directory: list | None = None):
    """(publishReport, BuildResult): Wind's own write set through a DryRunWriter, sealed with the release's lineage. Never touches a database."""
    import hashlib
    from sector_wind.brain import artifact as A
    from sector_wind.brain.publish import safe_publish
    from sector_wind.brain.writer import DryRunWriter
    from sector_brain_platform.knowledge_release import lineage_triple
    writer = DryRunWriter()
    kwargs = {"now": now, "run_summary": run_summary}
    if directory is not None:
        kwargs["directory"] = directory
    rep = safe_publish(store, cfg, writer, **kwargs)
    ev_sha = hashlib.sha256(open(EVIDENCE, "rb").read()).hexdigest() if os.path.exists(EVIDENCE) else "NONE"
    kr, mref, msha = lineage_triple(release)
    ctx = A.BuildContext(generated_at=_iso(now), execution_id=execution_id, code_version=code_version, evidence_sha256=ev_sha,
                         knowledge_release=kr, manifest_ref=mref, manifest_sha256=msha)
    return rep, A.build_artifacts(writer.patches, ctx)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True, help="the Wind archive: local:DIR only")
    ap.add_argument("--artifact-dir", required=True, help="a LOCAL artifact store (create-only)")
    ap.add_argument("--emit", default=None, help="also write the sealed artifact JSON to this LOCAL file (a runner's hand-off, e.g. Pulse's {out}/artifact.json)")
    ap.add_argument("--skip-ingest", action="store_true", help="seal what the store already holds (tests, a re-seal); no fetch")
    ap.add_argument("--execution-id", default=None, help="UUIDv4 of this run (default: a new one)")
    ap.add_argument("--now", default=None, help="with --skip-ingest only: the run time to seal at (tests, a re-seal), ISO-8601 UTC")
    a = ap.parse_args(argv)

    if not a.store.startswith("local:"):
        print("REFUSED (nothing stored): --store must be local:DIR (a runner never opens a bucket archive)", file=sys.stderr)
        return 2
    if not (a.artifact_dir or "").strip() or a.artifact_dir.startswith("gs://"):
        print("REFUSED (nothing stored): --artifact-dir is a local folder", file=sys.stderr)
        return 2
    if a.now and not a.skip_ingest:
        print("REFUSED (nothing stored): --now is for --skip-ingest only (a fetch always runs at the real time)", file=sys.stderr)
        return 2
    if (a.emit or "").strip() and (a.emit.startswith("gs://") or os.path.exists(a.emit)):
        print("REFUSED (nothing stored): --emit is a new local file (an earlier hand-off is never overwritten)", file=sys.stderr)
        return 2
    try:
        execution_id = str(uuid.UUID(a.execution_id, version=4)) if a.execution_id else str(uuid.uuid4())
    except ValueError:
        print("REFUSED (nothing stored): --execution-id is not a UUID", file=sys.stderr)
        return 2

    try:
        now = (dt.datetime.strptime(a.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if a.now
               else dt.datetime.now(dt.timezone.utc).replace(microsecond=0))
    except ValueError:
        print("REFUSED (nothing stored): --now is YYYY-MM-DDTHH:MM:SSZ", file=sys.stderr)
        return 2

    from sector_wind.ingest import DEFAULT_LEADS, load_config, verified_release
    from sector_wind.store import open_store
    try:
        release = verified_release()                         # BR-11: a missing or tampered packaged release stops the run; nothing falls back
        cfg = load_config()
    except Exception as e:                                   # noqa: BLE001
        print(f"REFUSED (nothing stored): knowledge release: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    store = open_store(a.store)
    res = None
    if not a.skip_ingest:
        from sector_wind.live import run_hourly
        try:
            res = run_hourly(store, cfg, now, DEFAULT_LEADS)
        finally:
            store.flush_ledger()                             # the ledger is written even when the run fails (as in main.py hourly)
        print(json.dumps({"ingest": res}, default=str)[:2000])
    rep, built = build(store, cfg, now=now, run_summary=res, execution_id=execution_id,
                       code_version=f"{BRAIN_ID}@{os.environ.get('SECTOR_ENGINE_COMMIT', 'unknown')}"[:40], release=release)
    print(json.dumps({"publishReport": {k: rep.get(k) for k in ("ok", "errors", "writes", "readinessCounts")}}, default=str)[:2000])
    if not rep.get("ok") or not built.artifact:
        print(f"FAILED (nothing stored): publish ok={rep.get('ok')}, artifact={'yes' if built.artifact else 'no'}, "
              f"errors={(rep.get('errors') or [])[:3]}", file=sys.stderr)
        return 3

    from sector_brain_platform.publisher.handoff import ArtifactWriter
    from sector_brain_platform.publisher.storage import LocalDirObjectStore
    ref = ArtifactWriter(LocalDirObjectStore(a.artifact_dir), BRAIN_ID).write(built.artifact)
    if (a.emit or "").strip():
        with open(a.emit, "x") as fh:                        # never overwrites an earlier hand-off
            json.dump(built.artifact, fh, sort_keys=True)
    print(json.dumps({"artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "executionId": ref.execution_id,
                      "artifactSchema": ref.expected_schema, "dropped": len(built.dropped), "unsupported": len(built.unsupported),
                      "deletes": len(built.deletes)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
