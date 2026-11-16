#!/usr/bin/env python3
"""Non-production rehearsal of exit-gate checks X09 (atomic write) and X13 (rollback) against a REAL Brain database (Sector_Engine #198).

Owner approval B5 (Sector_Ops #51, `owner-approval-2026-11-16/sector-ops-51-b1-b5`): build the tool. Running it is Michael's, once, with his own login,
against the non-production Brain database named by the read-only instance check (Sector_Ops #51 comment 6890459402, item 1).

WHAT IT REFUSES
  * Any database URL that is not listed in DEV_BRAIN_DATABASES below. The list is hard-coded and EMPTY in this change, so today the tool refuses every
    database. A reviewed PR adds the one non-production instance once the check names it. There is no override flag.
  * The production Brain database and both app databases, even if someone lists them (checked at import and again at run time).
  * Any bucket not listed in DEV_BUCKETS (also empty). Without --bucket the Publisher's control objects (_heads, _baseline, records, locks) live in memory
    for the run; the exit gate scopes X09/X13 to Publisher-owned RTDB paths, so the RTDB half is what this rehearses.

WHAT IT DOES (Brain `wind`, SYNTHETIC artifacts only: lake keys `rehearsal_lake_*`, invented values, fresh ids per run)
  seed  publish A through the real LivePublisher (baseline acknowledged first), so there is a previous release.
  X13   publish B (adds `rehearsal_lake_extra`), roll B back through LivePublisher.rollback, read back every key A and B touch and assert it equals the
        state captured after A (byte for byte, canonical JSON); the extra lake is gone; the publication marker and the wind lake-state head point at A again.
  X09   publish C (40 lakes) with a small update limit so it applies in chunks, MANIFEST-LAST; the client fails the 2nd data chunk BEFORE sending it (the
        same fault point as the repo's fake-client proof). Assert: the publication marker is the previous release (only `pending` added), the head did not
        move, every key outside the one chunk that landed is unchanged, a different artifact cannot jump the interrupted one, and resuming C completes it.
  Writes an evidence JSON (inputs, per-step results, readback digests; no values, no credentials) to docs/cortex/evidence/.

It never deletes anything except the paths B added (that is the rollback under test). Moving the exit-gate rows from NOT_RUN stays Michael's call.

  python tools/ops/dev_rehearsal.py --database-url URL --approval-ref REF [--bucket NAME] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PLATFORM = os.path.join(ROOT, "jobs", "brain_platform")
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

from sector_brain_platform import rtdb as RT                                                     # noqa: E402
from sector_brain_platform.publisher import ArtifactWriter, MemoryObjectStore, PublishHistory, default_registry, publisher_view, seal_bundle   # noqa: E402
from sector_brain_platform.publisher.canonical import canonical_bytes                            # noqa: E402
from sector_brain_platform.publisher_live import apply as AP                                     # noqa: E402
from sector_brain_platform.publisher_live import baseline as BL                                  # noqa: E402
from sector_brain_platform.publisher_live.authorization import BrainAuthorization, LiveAuthorization   # noqa: E402
from sector_brain_platform.publisher_live.model import LiveResult, RtdbDefiniteFailure           # noqa: E402
from sector_brain_platform.publisher_live.publisher import LivePublisher                         # noqa: E402

STANDARD = "dev-rehearsal-v1"
BRAIN = "wind"
PUB = f"brains/{BRAIN}/publication"
LAKE_SCHEMA, LAKE_SCOPE = "wind-lake-state-v1", "lake-live"
CHUNK_LIMIT = 2500                     # bytes: forces C into several chunks (same limit as the fake-client proof)
FAIL_ON_UPDATE = 3                     # update call 1 = pending marker, 2 = data chunk 1, 3 = data chunk 2 -> fails before it is sent
EVIDENCE_DIR = os.path.join(ROOT, "docs", "cortex", "evidence")

#: The ONLY databases this tool will touch. Empty until the read-only instance check names the non-production Brain database; a reviewed PR adds it.
DEV_BRAIN_DATABASES: frozenset = frozenset()
#: The ONLY buckets it may use for the Publisher's control objects. Empty: control objects stay in memory unless a reviewed PR adds a dev bucket.
DEV_BUCKETS: frozenset = frozenset()

PRODUCTION_BRAIN_DATABASES = frozenset({RT.BRAIN_RTDB_URL.rstrip("/")})


class Refused(RuntimeError):
    pass


def _norm_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _never_production(url: str) -> None:
    u = _norm_url(url)
    if u in PRODUCTION_BRAIN_DATABASES or any(db in u for db in RT.APP_DATABASES):
        raise Refused(f"refused: {u!r} is a production Brain or app database")


for _u in DEV_BRAIN_DATABASES:          # a production URL can never be listed: fail at import, before any run
    _never_production(_u)


def guard_database(url: str, allowed=None) -> str:
    """-> the normalised URL, or Refused. `allowed` defaults to the hard-coded list (tests pass their own fake URL)."""
    u = _norm_url(url)
    _never_production(u)
    allowed = DEV_BRAIN_DATABASES if allowed is None else frozenset(_norm_url(a) for a in allowed)
    for a in allowed:
        _never_production(a)
    if u not in allowed:
        raise Refused(f"refused: {u!r} is not a listed non-production Brain database (listed: {sorted(allowed) or 'none'})")
    return u


def guard_bucket(name: str, allowed=None) -> str:
    allowed = DEV_BUCKETS if allowed is None else frozenset(allowed)
    if name not in allowed:
        raise Refused(f"refused: bucket {name!r} is not a listed non-production bucket (listed: {sorted(allowed) or 'none'})")
    return name


class FaultOnUpdate:
    """Wraps a Publisher RTDB client. The n-th update() raises a DEFINITE failure WITHOUT reaching the database; every other call passes through."""

    def __init__(self, inner, fail_on: int):
        self.inner, self.fail_on, self.calls = inner, fail_on, 0

    def get(self, path):
        return self.inner.get(path)

    def update(self, updates):
        self.calls += 1
        if self.calls == self.fail_on:
            raise RtdbDefiniteFailure(f"rehearsal: forced failure on update call {self.calls} (not sent)")
        return self.inner.update(updates)


# -- synthetic artifacts ---------------------------------------------------------------------------------------------------------------------
def _lakes(n):
    return tuple(f"rehearsal_lake_{i:03d}" for i in range(n))


def _sections(speed, lakes, stamp):
    muts = []
    for k in lakes:
        muts += [{"op": "SET", "path": f"/lakes/{k}/states/wind", "value": {"kind": "modeled", "windMS": speed, "inputAgeHours": 1.5, "generatedAt": stamp}},
                 {"op": "SET", "path": f"/lakeFleet/{k}/slots/wind", "value": {"readiness": "CALIBRATION", "stale": False}}]
    lake = {"artifactSchema": LAKE_SCHEMA, "scope": LAKE_SCOPE, "freshness": {"freshnessStatus": "FRESH"}, "mutations": muts}
    registry = {"artifactSchema": "wind-registry-v1", "mutations": [
        {"op": "SET", "path": f"/brains/{BRAIN}/version", "value": "dev-rehearsal"},
        {"op": "SET", "path": f"/brains/{BRAIN}/status", "value": "CALIBRATION"},
        {"op": "SET", "path": f"/brains/{BRAIN}/updatedAt", "value": stamp},
        {"op": "SET", "path": f"/brains/{BRAIN}/lastSuccessfulRun", "value": stamp},
        {"op": "SET", "path": f"/health/brains/{BRAIN}/status", "value": "HEALTHY"},
        {"op": "SET", "path": f"/health/brains/{BRAIN}/staleLakeCount", "value": 0},
        {"op": "SET", "path": f"/validation/{BRAIN}", "value": {"status": "NOT_VALIDATED"}}]}
    source = {"artifactSchema": "wind-source-registry-v1", "mutations": [
        {"op": "SET", "path": "/sources/noaa-nbm-v5", "value": {"provider": "synthetic-rehearsal", "latestObservationAt": stamp}},
        {"op": "SET", "path": "/health/sources/noaa-nbm-v5", "value": {"status": "HEALTHY", "lastFetchAt": stamp, "latencyMs": 120, "failures24h": 0}}]}
    return [lake, registry, source]


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def synthetic_artifact(*, speed, lakes, generated_at, new_id):
    stamp = _iso(generated_at)
    return seal_bundle(brain_id=BRAIN, bundle_id="wind-publication-v1", sections=_sections(speed, lakes, stamp), lifecycle="CALIBRATION",
                       review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=stamp, execution_id=new_id(),
                       code_version="dev-rehearsal", input_fingerprint="sha256:" + "00" * 32, artifact_id=new_id())


# -- readback helpers ------------------------------------------------------------------------------------------------------------------------
def snapshot(rtdb, keys) -> dict:
    return {k: rtdb.get(k) for k in sorted(set(keys))}


def digest(snap: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(AP._norm(snap))).hexdigest()


def differing(before: dict, after: dict, keys) -> list:
    return sorted(k for k in keys if not AP.canonical_equal(before.get(k), after.get(k)))


def _data_keys(updates):
    return sorted(k for k in (updates or {}) if k != PUB)


# -- the rehearsal ---------------------------------------------------------------------------------------------------------------------------
def rehearse(rtdb, store, *, approval_ref: str, clock, new_id) -> dict:
    """Run seed -> X13 -> X09 against `rtdb` (a Publisher RTDB client) and `store` (an ObjectStore for the control objects). Returns the evidence."""
    history = PublishHistory(publisher_view(store))
    auth = LiveAuthorization(BrainAuthorization(BRAIN, approval_ref))

    def publisher(client, limit=None):
        kw = {} if limit is None else {"max_update_bytes": limit}
        return LivePublisher(default_registry(), history, client, auth, clock=clock, id_factory=new_id, **kw)

    live = publisher(rtdb)
    writer = ArtifactWriter(store, BRAIN)
    t0 = clock()
    ev = {"checks": {}, "steps": []}

    def step(name, result, **extra):
        ev["steps"].append({"step": name, "result": getattr(result, "value", result), **extra})

    # seed: previous release A
    ref_a = writer.write(synthetic_artifact(speed=4.2, lakes=_lakes(2), generated_at=t0 - dt.timedelta(minutes=40), new_id=new_id))
    prior = rtdb.get(PUB)
    ev["priorPublicationArtifactId"] = prior.get("artifactId") if isinstance(prior, dict) else None
    live.acknowledge_baseline(ref_a, approval_ref=approval_ref)
    out_a = live.publish(ref_a)
    step("seed.publishA", out_a.result, artifactId=ref_a.artifact_id)
    if out_a.result is not LiveResult.PUBLISHED:
        ev["checks"] = {c: {"status": "NOT_RUN", "reason": f"seed publish returned {out_a.result.value}: {out_a.detail}"} for c in ("X09", "X13")}
        return ev

    # X13: rollback restores the pre-cutover state
    ref_b = writer.write(synthetic_artifact(speed=8.0, lakes=_lakes(2) + ("rehearsal_lake_extra",), generated_at=t0 - dt.timedelta(minutes=30), new_id=new_id))
    plan_b = live.dry_run(ref_b).updates or {}
    keys13 = sorted(set(_data_keys(out_a.updates)) | set(_data_keys(plan_b)))
    pre13 = snapshot(rtdb, keys13)
    out_b = live.publish(ref_b)
    step("X13.publishB", out_b.result, artifactId=ref_b.artifact_id)
    extra_landed = rtdb.get("lakes/rehearsal_lake_extra/states/wind") is not None
    rb = live.rollback(BRAIN, out_b.publish_id, approval_ref=approval_ref, reason="dev rehearsal X13") if out_b.result is LiveResult.PUBLISHED else None
    step("X13.rollbackB", rb.result if rb else "NOT_RUN")
    post13 = snapshot(rtdb, keys13)
    pub13 = rtdb.get(PUB) or {}
    head13 = history.head(BRAIN, LAKE_SCHEMA, LAKE_SCOPE) or {}
    diff13 = differing(pre13, post13, keys13)
    x13 = {"PUBLISHED_B": out_b.result is LiveResult.PUBLISHED, "B_extra_lake_landed": extra_landed,
           "ROLLED_BACK": bool(rb) and rb.result is LiveResult.ROLLED_BACK, "readback_equals_pre_cutover": not diff13,
           "extra_lake_removed": rtdb.get("lakes/rehearsal_lake_extra") is None,
           "marker_restored": pub13.get("artifactId") == ref_a.artifact_id and pub13.get("status") == "COMPLETE"
           and (pub13.get("rollback") or {}).get("fromPublishId") == out_b.publish_id,
           "head_restored": head13.get("artifactId") == ref_a.artifact_id,
           "baseline_acknowledged": BL.acknowledgement(store, BRAIN, LAKE_SCHEMA, LAKE_SCOPE) is not None}
    ev["checks"]["X13"] = {"status": "PASS" if all(x13.values()) else "FAIL", "assertions": x13, "keysCompared": len(keys13),
                           "preCutoverDigest": digest(pre13), "afterRollbackDigest": digest(post13), "differingKeys": diff13[:50]}

    # X09: forced mid-write failure leaves the prior state intact (manifest-last)
    ref_c = writer.write(synthetic_artifact(speed=6.0, lakes=_lakes(40), generated_at=t0 - dt.timedelta(minutes=20), new_id=new_id))
    small = publisher(rtdb, CHUNK_LIMIT)
    plan_c = small.dry_run(ref_c).updates or {}
    chunks = AP.chunk_updates(plan_c, PUB, CHUNK_LIMIT) if plan_c else []
    landed = sorted(chunks[0]) if chunks else []
    keys09 = sorted(set(_data_keys(plan_c)) | set(keys13))
    pre09, pub_pre = snapshot(rtdb, keys09), rtdb.get(PUB) or {}
    head_pre = history.head(BRAIN, LAKE_SCHEMA, LAKE_SCOPE)
    faulty = FaultOnUpdate(rtdb, FAIL_ON_UPDATE)
    out_c = publisher(faulty, CHUNK_LIMIT).publish(ref_c)
    step("X09.publishC.faulted", out_c.result, artifactId=ref_c.artifact_id, updateCalls=faulty.calls, chunks=len(chunks))
    post09, pub_post = snapshot(rtdb, keys09), rtdb.get(PUB) or {}
    head_post = history.head(BRAIN, LAKE_SCHEMA, LAKE_SCOPE)
    untouched = [k for k in keys09 if k not in landed]
    diff09 = differing(pre09, post09, untouched)
    pub_rest_same = AP.canonical_equal({k: v for k, v in pub_post.items() if k != "pending"}, {k: v for k, v in pub_pre.items() if k != "pending"})
    jump = small.publish(writer.write(synthetic_artifact(speed=5.0, lakes=_lakes(3), generated_at=t0 - dt.timedelta(minutes=15), new_id=new_id)))
    step("X09.otherArtifactWhileInterrupted", jump.result)
    resumed = small.publish(ref_c)
    step("X09.resumeC", resumed.result, mode=resumed.mode, calls=resumed.calls)
    pub_done = rtdb.get(PUB) or {}
    x09 = {"chunked_plan": len(chunks) >= 3, "APPLY_FAILED": out_c.result is LiveResult.APPLY_FAILED,
           "marker_still_previous": pub_post.get("artifactId") == pub_pre.get("artifactId") and pub_post.get("status") == "COMPLETE",
           "only_pending_added": pub_rest_same and (pub_post.get("pending") or {}).get("artifactId") == ref_c.artifact_id,
           "head_unchanged": head_post == head_pre,
           "untouched_keys_identical": not diff09,
           "different_artifact_refused": jump.result is LiveResult.PRECONDITION_FAILED,
           "resume_completes": resumed.result is LiveResult.PUBLISHED and resumed.mode == "CHUNKED"
           and pub_done.get("artifactId") == ref_c.artifact_id and "pending" not in pub_done}
    ev["checks"]["X09"] = {"status": "PASS" if all(x09.values()) else "FAIL", "assertions": x09, "keysCompared": len(untouched),
                           "nonAuthoritativeKeysLanded": len(landed), "beforeDigest": digest({k: pre09[k] for k in untouched}),
                           "afterFailureDigest": digest({k: post09[k] for k in untouched}), "differingKeys": diff09[:50]}
    return ev


# -- CLI -------------------------------------------------------------------------------------------------------------------------------------
def _git_commit():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:                                                                            # noqa: BLE001
        return None


def build_clients(url, bucket):                                                                 # pragma: no cover - real network; Michael's run only
    from sector_brain_platform.publisher_live.rtdb_client import RtdbRestPublisherClient
    tokens = RT.TokenProvider()
    rtdb = RtdbRestPublisherClient(url, brain_id=BRAIN, tokens=tokens, armed=True)
    if bucket is None:
        return rtdb, MemoryObjectStore()
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    store = GcsRestObjectStore(bucket, tokens)
    if store.list(f"publishes/{BRAIN}/"):
        raise Refused(f"refused: bucket {bucket!r} already holds {BRAIN} publication records; use a fresh non-production bucket")
    return rtdb, store


def main(argv=None, *, allowed_databases=None, allowed_buckets=None, make_clients=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--database-url", required=True, help="the non-production Brain database (must be listed in DEV_BRAIN_DATABASES)")
    ap.add_argument("--approval-ref", required=True, help="the owner approval this run is made under")
    ap.add_argument("--bucket", default=None, help="optional non-production bucket for the control objects (must be listed in DEV_BUCKETS)")
    ap.add_argument("--out-dir", default=EVIDENCE_DIR)
    a = ap.parse_args(argv)
    try:
        url = guard_database(a.database_url, allowed_databases)
        bucket = guard_bucket(a.bucket, allowed_buckets) if a.bucket else None
        if not a.approval_ref.strip():
            raise Refused("refused: --approval-ref is empty")
        rtdb, store = (make_clients or build_clients)(url, bucket)
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 2
    started = dt.datetime.now(dt.timezone.utc)
    ev = rehearse(rtdb, store, approval_ref=a.approval_ref, clock=lambda: dt.datetime.now(dt.timezone.utc), new_id=lambda: str(uuid.uuid4()))
    ev = {"standard": STANDARD, "brainId": BRAIN, "database": url, "objectStore": f"gs://{bucket}" if bucket else "memory", "approvalRef": a.approval_ref,
          "gitCommit": _git_commit(), "startedAt": _iso(started), "finishedAt": _iso(dt.datetime.now(dt.timezone.utc)), **ev}
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, f"dev-rehearsal-{BRAIN}-{started.strftime('%Y%m%dT%H%M%SZ')}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({c: v["status"] for c, v in ev["checks"].items()}, sort_keys=True))
    print(f"evidence: {os.path.relpath(path, ROOT)}")
    return 0 if all(v["status"] == "PASS" for v in ev["checks"].values()) and ev["checks"] else 1


if __name__ == "__main__":
    sys.exit(main())
