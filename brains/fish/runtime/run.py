"""Biological Brain run: private canonical species knowledge -> Brain RTDB (sector-brain) summaries.

Reads the PRIVATE canonical bundle (gs://sector-biology-private/biology/v1, or a local copy) and writes only the
Biological Brain's Brain RTDB paths: /species/{speciesId}, /brains/biological-state, /validation/biological-state,
/health/brains/biological-state and one /activity event on a version change. It touches no production path:
Engine /conditions, the app databases and every other brain are unaffected by anything here.

usage:
  python run.py --plan                                  # orchestrator question: is a publish warranted?
  python run.py --dry-run --out out/                    # verify + build everything against the live RTDB (GET only), write JSON files, no writes
  python run.py --write                                 # LEGACY direct publish (one atomic multi-path update). Target: the Publisher is the only production write door
                                                        # (fish-publication-v1, publish_artifact.py); this path retires at the Publisher cutover (not started).
  python run.py --bundle /path/to/biology/v1 ...        # read a local bundle copy instead of the bucket
env:
  BIOLOGY_BUCKET (sector-biology-private), BIOLOGY_PREFIX (biology/v1), BRAIN_RTDB_URL (sector-brain),
  BRAIN_TOKEN_MODE metadata|gcloud, DEPLOYMENT_VERSION (else brain/biological@<git sha> when available)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biological_brain as bb      # noqa: E402
import brain_platform as bp        # noqa: E402
import orchestration as orch       # noqa: E402
import publish_artifact as pa      # noqa: E402

BUCKET = os.environ.get("BIOLOGY_BUCKET", "sector-biology-private")
PREFIX = os.environ.get("BIOLOGY_PREFIX", "biology/v1")
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", bp.BRAIN_RTDB_URL)


def gcs_reader(tokens: bp.TokenProvider):
    """Authenticated read from the private bucket (never public URLs)."""
    def read(path: str) -> bytes:
        obj = urllib.parse.quote(f"{PREFIX}/{path}", safe="")
        url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{obj}?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tokens.token()}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise bb.BundleError(f"gs://{BUCKET}/{PREFIX}/{path}: HTTP {e.code}") from e
    return read


def local_reader(root: str):
    def read(path: str) -> bytes:
        with open(os.path.join(root, path), "rb") as fh:
            return fh.read()
    return read


def deployment_version() -> str:
    if os.environ.get("DEPLOYMENT_VERSION"):
        return os.environ["DEPLOYMENT_VERSION"]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)),
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return f"brain/biological@{sha}" if sha else "brain/biological@unknown"
    except Exception:
        return "brain/biological@unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--bundle", help="local bundle root (contains latest.json); default: the private bucket")
    ap.add_argument("--out", default="out")
    ap.add_argument("--force", action="store_true", help="publish even when --plan says SKIP")
    ap.add_argument("--offline", action="store_true", help="do not read the Brain RTDB (dry-run/plan without credentials)")
    a = ap.parse_args(argv)

    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc)
    tokens = bp.TokenProvider()
    read = local_reader(a.bundle) if a.bundle else gcs_reader(tokens)
    uri_root = f"gs://{BUCKET}/{PREFIX}" if not a.bundle else "local:" + os.path.abspath(a.bundle)
    deployment = deployment_version()

    rtdb = None if a.offline else bp.BrainRtdb(RTDB_URL, tokens, brain_id=bb.BRAIN_ID, recorder=bp.ConsumptionRecorder(bb.BRAIN_ID))   # ownership-checked; --plan/--dry-run only GET; reads recorded as ACTUAL consumption
    published = rtdb.get(f"brains/{bb.BRAIN_ID}") if rtdb else None
    pointer = json.loads(read("latest.json"))
    decision = orch.plan(published, pointer, bb.BRAIN_VERSION)
    if a.plan:
        print(json.dumps(decision, indent=1))
        return 0

    bundle = bb.load_bundle(read)                                   # verifies hashes + structure + arithmetic; raises on any problem
    existing = set((rtdb.get("species", shallow=True) or {}).keys()) if rtdb else set()
    updates = bb.build_updates(bundle, now=now, uri_root=uri_root, deployment=deployment, descriptor=orch.DESCRIPTOR,
                               duration_ms=int((time.time() - t0) * 1000), published=published, existing_species=existing,
                               event_id=bp.event_id(now, bb.BRAIN_ID, 0))
    bb.check_keys(updates)
    body = json.dumps({k.lstrip("/"): v for k, v in updates.items()}, separators=(",", ":"), allow_nan=False)
    summary = dict(decision=decision, researchVersion=bundle.research_version, species=len(bundle.profiles),
                   paths=len(updates), bytes=len(body), speciesPayloadMaxBytes=max(len(json.dumps(v)) for k, v in updates.items() if k.startswith("/species/") and v))
    if rtdb is not None:
        summary["consumed"] = rtdb.consumed()                     # consumption-lineage-v1: what this run actually read from the Brain RTDB (own nodes excluded)

    if a.write and rtdb is None:
        raise SystemExit("--write needs the Brain RTDB; drop --offline")
    if a.dry_run:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "updates.json"), "w") as fh:
            json.dump(updates, fh, indent=1, ensure_ascii=False)
        # The Publisher-bound view of the SAME update: one sealed fish-publication-v1 artifact, evaluated by the SHADOW Publisher in memory.
        # Nothing is sent anywhere; no production path is touched.
        built = pa.build_artifact(updates, bundle, pa.BuildContext(str(uuid.uuid4()), now.strftime("%Y-%m-%dT%H:%M:%SZ"), deployment),
                                  published=published, consumed=summary.get("consumed"))
        with open(os.path.join(a.out, "artifact.json"), "w") as fh:
            json.dump(built.artifact, fh, indent=1, ensure_ascii=False, sort_keys=True)
        from sector_brain_platform.publisher import local_shadow_stack
        stack = local_shadow_stack()                                    # in-memory: the Brain may only create its own artifact; the Publisher only reads it
        ev = stack.publisher.evaluate_reference(stack.writer(bb.BRAIN_ID).write(built.artifact))
        summary["publisher"] = dict(mode=ev.mode.value, result=ev.result.value, codes=ev.codes, live=False, artifactSchema=pa.FISH_BUNDLE,
                                    outputFingerprint=built.artifact["lineage"]["outputFingerprint"], mutations=built.counts, droppedLegacyPaths=len(built.dropped))
        print(json.dumps(summary, indent=1))
        return 0

    if decision["action"] == "SKIP" and not a.force:
        print(json.dumps(summary | {"published": False}, indent=1))
        return 0
    bp.check_schema(rtdb)
    rtdb.update(updates)
    print(json.dumps(summary | {"published": True, "rtdbWrites": rtdb.writes, "rtdbBytes": rtdb.bytes_written}, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except bb.BundleError as e:
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
