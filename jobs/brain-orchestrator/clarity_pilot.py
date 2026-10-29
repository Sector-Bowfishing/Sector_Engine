#!/usr/bin/env python3
"""Water Clarity central-publication PILOT tool (owner-approved scope 2026-10-29; Water Clarity only).

One logical flow, each stage separate, each run under the identity the stage is meant to use (`--impersonate <service account>`; no key files):

  capture    read-only GETs of every Water Clarity path the Publisher may write + score/health/publication snapshots  -> baseline.json (private, outside the repository)
  build      Clarity's own builder turns the captured live state into ONE sealed artifact (state-neutral: values equal live); written create-only to the artifact bucket
  plan       Publisher baseline diff (GET only): artifact plan vs live; the report lists every difference
  acknowledge  records the deliberate first-live baseline (approval reference + diff hash)
  publish    ONE Publisher publication, readback of every written path, health mirror dry derivation; halts on any mismatch
  restore    rollback to the captured pre-pilot values for the paths the pilot wrote, ONLY where live still equals what the pilot wrote (never over newer data)
  rehearse   the same build/plan/acknowledge/publish/restore against an in-memory fake RTDB seeded from baseline.json (no cloud access)

Nothing here runs a Brain, starts a job, touches a schedule, writes /scores, /species, /health or any other Brain, or contains a credential.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
sys.path.insert(0, os.path.join(ROOT, "brains", "water-clarity", "runtime"))

BRAIN = "water-clarity"
SLOT = "waterClarity"
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
APPROVAL = os.environ.get("PILOT_APPROVAL_REF", "owner-approval-2026-10-29/water-clarity-pilot")


def _tokens(impersonate: str | None):
    """Token for RTDB. With --impersonate the token is minted for that service account (the stage runs AS that identity); never a key file."""
    from sector_brain_platform.rtdb import TokenProvider
    if impersonate:
        import subprocess
        out = subprocess.run(["gcloud", "auth", "print-access-token", f"--impersonate-service-account={impersonate}",
                              "--scopes=https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/devstorage.read_write"],
                             capture_output=True, text=True)
        if out.returncode:
            raise SystemExit(f"cannot mint a token for {impersonate}: {out.stderr.strip()[:300]}")
        os.environ["BRAIN_ACCESS_TOKEN"] = out.stdout.strip()
    return TokenProvider()


def _gcs_store(bucket: str, tokens):
    """The same stdlib REST store the Orchestrator image uses (no cloud client library, no application-default credentials): the stage's identity is the impersonated token."""
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    return GcsRestObjectStore(bucket, tokens)


def _rtdb(tokens):
    from sector_brain_platform.rtdb import BrainRtdb
    return BrainRtdb(RTDB_URL, tokens, brain_id=None)


def _sha(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _get(tree, path):
    node = tree
    for p in path.strip("/").split("/"):
        node = node.get(p) if isinstance(node, dict) else None
        if node is None:
            return None
    return node


def _strip(tree):
    """Drop empty containers so a tree with a removed leaf compares equal to one that never had it."""
    if isinstance(tree, dict):
        out = {k: _strip(v) for k, v in tree.items()}
        return {k: v for k, v in out.items() if v not in ({}, None)}
    return tree


def _nest(flat: dict) -> dict:
    tree = {}
    for k, v in flat.items():
        node = tree
        parts = k.strip("/").split("/")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
    return tree


# ----------------------------------------------------------------------------------------------------------------------------------------- capture
def capture(rtdb) -> dict:
    from sector_brain_platform.publisher.registry import CLARITY_REGISTRY_CHILDREN, _clarity_sources
    kids = [c for g in CLARITY_REGISTRY_CHILDREN.values() for c in g]
    keys = sorted((rtdb.get("lakeFleet", shallow=True) or {}).keys())
    paths = [f"brains/{BRAIN}/{c}" for c in kids] + [f"validation/{BRAIN}"] + [f"sources/{s}" for s in sorted(_clarity_sources())]
    for k in keys:
        paths += [f"lakes/{k}/states/{SLOT}", f"lakes/{k}/profiles/{SLOT}", f"lakeFleet/{k}/slots/{SLOT}", f"lakeFleet/{k}/readiness/{SLOT}", f"lakeFleet/{k}/modelVersions/{SLOT}",
                  f"snapshots/{k}/latest/{SLOT}", f"snapshots/{k}/latest/brainVersions/{BRAIN}"]
    def get(p):
        return p, rtdb.get(p)
    with cf.ThreadPoolExecutor(8) as ex:
        values = dict(ex.map(get, paths))
    other = {p: rtdb.get(p) for p in (f"scores/{BRAIN}", f"health/brains/{BRAIN}", f"brains/{BRAIN}/publication", f"brains/{BRAIN}/certification", "health/jobs/water-clarity-brain")}
    present = {p: v for p, v in values.items() if v is not None}
    return {"capturedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "lakeCount": len(keys), "paths": len(paths), "present": len(present),
            "values": present, "absent": sorted(p for p, v in values.items() if v is None), "context": other, "sha256": _sha(present)}


# ------------------------------------------------------------------------------------------------------------------------------------------ build
def build(baseline: dict, commit: str):
    import publish_artifact as PA
    updates = {"/" + p: v for p, v in baseline["values"].items()}
    ctx = PA.BuildContext(generated_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), execution_id=str(uuid.uuid4()), code_version=commit,
                          catalog_sha256=PA.catalog_digest(), **PA.release_lineage())
    r = PA.build_artifact(updates, ctx)
    if r.artifact is None or r.unsupported:
        raise SystemExit(f"artifact build failed closed: unsupported={r.unsupported[:5]}")
    return r


def _publisher(store, tokens, armed_rtdb: bool, resolver_dir: str, require_approved: bool = True):
    from sector_brain_platform.publisher import PublishHistory, default_registry, publisher_view
    from sector_brain_platform.publisher_live.authorization import BrainAuthorization, LiveAuthorization
    from sector_brain_platform.publisher_live.publisher import LivePublisher
    from sector_brain_platform.publisher_live.release_resolver import PackagedReleaseResolver
    from sector_brain_platform.publisher_live.rtdb_client import RtdbRestPublisherClient

    rt = RtdbRestPublisherClient(RTDB_URL, brain_id=BRAIN, tokens=tokens, armed=armed_rtdb)
    return LivePublisher(default_registry(), PublishHistory(publisher_view(store)), rt, LiveAuthorization(BrainAuthorization(BRAIN, APPROVAL)), release_resolver=PackagedReleaseResolver(resolver_dir, BRAIN, require_approved=require_approved))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("capture", "build", "plan", "acknowledge", "publish", "release-lock", "verify", "restore", "rehearse"))
    ap.add_argument("--out", required=True, help="private evidence directory (outside the repository)")
    ap.add_argument("--bucket")
    ap.add_argument("--impersonate", help="service account this stage runs as")
    ap.add_argument("--commit", default=os.environ.get("DEPLOYMENT_VERSION", "unknown"))
    ap.add_argument("--release-approval-not-recorded-ok", action="store_true",
                    help="CALIBRATION lane only: accept a packaged release whose approval is NOT_RECORDED. The release must still verify file-by-file and match the artifact lineage. Used ONLY for the "
                         "state-neutral pilot republish of data already live from this same release; without it an unapproved release is rejected")
    ap.add_argument("--yes-live", action="store_true", help="required for acknowledge/publish/restore (live writes)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    j = lambda name: os.path.join(a.out, name)       # noqa: E731
    load = lambda name: json.load(open(j(name), encoding="utf-8"))     # noqa: E731
    dump = lambda name, d: json.dump(d, open(j(name), "w", encoding="utf-8"), indent=1, sort_keys=True)     # noqa: E731
    resolver_dir = os.path.join(ROOT, "brains", "water-clarity", "runtime")

    if a.stage == "capture":
        b = capture(_rtdb(_tokens(a.impersonate)))
        dump("baseline.json", b)
        print(json.dumps({k: b[k] for k in ("capturedAt", "lakeCount", "paths", "present", "sha256")}), "absent:", len(b["absent"]))
        return 0
    if a.stage == "build":
        b = load("baseline.json")
        r = build(b, a.commit)
        from sector_brain_platform.publisher.handoff import ArtifactWriter
        store = _gcs_store(a.bucket, _tokens(a.impersonate))
        ref = ArtifactWriter(store, BRAIN).write(r.artifact)
        dump("ref.json", {"brain_id": ref.brain_id, "artifact_id": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "execution_id": ref.execution_id, "expected_schema": ref.expected_schema})
        dump("build-report.json", {"dropped": r.dropped, "omittedUnknown": r.omitted_unknown, "deletes": r.deletes, "artifactSha256": ref.sha256, "bundleSchema": r.artifact["lineage"]["artifactSchema"]})
        print("artifact", ref.location, ref.sha256, "dropped", len(r.dropped), "deletes", len(r.deletes))
        return 0
    if a.stage == "rehearse":
        return _rehearse(load("baseline.json"), a.commit, resolver_dir, dump)

    from sector_brain_platform.publisher.refs import ArtifactRef
    tokens = _tokens(a.impersonate)
    store = _gcs_store(a.bucket, tokens)
    live = _publisher(store, tokens, True, resolver_dir, require_approved=not a.release_approval_not_recorded_ok)
    ref = ArtifactRef(**load("ref.json"))
    if a.stage == "plan":
        diff = live.baseline_diff(ref)
        dump("plan-diff.json", diff)
        print({k: (len(v) if isinstance(v, list) else v) for k, v in diff.items()})
        return 0 if not diff["differing"] and not diff["missingLive"] else 3
    if not a.yes_live:
        raise SystemExit("this stage writes: pass --yes-live (only inside the approved pilot sequence)")
    if a.stage == "acknowledge":
        diff = live.acknowledge_baseline(ref, approval_ref=APPROVAL)
        dump("ack-diff.json", diff)
        print("baseline acknowledged", diff["diffSha256"])
        return 0
    if a.stage == "publish":
        baseline = load("baseline.json")
        res = live.publish(ref)
        dump("publish-result.json", {"result": res.result.value, "codes": res.codes, "detail": res.detail, "publishId": res.publish_id, "record": res.record})
        print(res.result.value, res.codes, res.detail)
        if res.result.value != "PUBLISHED":
            return 4
        written = sorted((res.record.get("pathSha256") or {}).keys())
        rb = _rtdb(tokens)
        bad = [p for p in written if p not in baseline["values"] and p.strip("/") not in baseline["values"] and not p.startswith(f"brains/{BRAIN}/publication") and not p.strip("/").startswith(f"brains/{BRAIN}/publication")]
        mism = [p for p in written if baseline["values"].get(p.strip("/")) is not None and rb.get(p) != baseline["values"][p.strip("/")]]
        dump("readback.json", {"written": written, "changedVsBaseline": mism, "notInBaseline": bad})
        print("readback: written", len(written), "mismatch vs pre-pilot values", len(mism), "paths not in baseline", len(bad))
        return 0 if not mism else 5
    if a.stage == "release-lock":
        from sector_brain_platform.publisher_live import locks as LK
        pid = _latest_publish_id(store)
        cur = json.loads(store.get(f"publishes/{BRAIN}/_locks/apply.json") or b"{}")
        if cur.get("state") == "HELD" and cur.get("publishId") == pid:           # only the lock of the COMPLETE publication it belongs to
            LK.release(store, BRAIN, pid, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        after = json.loads(store.get(f"publishes/{BRAIN}/_locks/apply.json") or b"{}")
        dump("lock-after.json", {"before": cur, "after": after})
        print("lock:", cur.get("state"), "->", after.get("state"))
        return 0 if after.get("state") == "RELEASED" else 7
    if a.stage == "verify":
        baseline = load("baseline.json")
        pid = _latest_publish_id(store)
        rec = json.loads(store.get(f"publishes/{BRAIN}/{pid}/record.json"))
        rb = _rtdb(tokens)
        from sector_brain_platform.publisher.canonical import canonical_bytes, sha256_ref
        written = rec.get("pathSha256") or {}

        def chk(p):
            return p, sha256_ref(canonical_bytes(rb.get(p)))
        with cf.ThreadPoolExecutor(8) as ex:
            live_sha = dict(ex.map(chk, sorted(written)))
        bad_sha = sorted(p for p, h in live_sha.items() if h != written[p])
        pub = rb.get(f"brains/{BRAIN}/publication") or {}
        from sector_brain_platform.publisher_live.apply import canonical_equal
        changed = sorted(p for p in written if baseline["values"].get(p.strip("/")) is not None and not canonical_equal(rb.get(p), baseline["values"][p.strip("/")]))
        ctx = {p: rb.get(p) for p in (f"scores/{BRAIN}", f"health/brains/{BRAIN}")}
        out = {"publishId": pid, "record": {k: rec.get(k) for k in ("result", "status", "live", "publishedAt", "artifactId", "lifecycle", "knowledgeRelease")},
               "pathsChecked": len(written), "liveHashMismatch": bad_sha[:20], "liveHashMismatchCount": len(bad_sha),
               "valuesChangedVsPrePilot": changed[:20], "valuesChangedVsPrePilotCount": len(changed),
               "publicationNodeMatchesRecord": pub.get("publishId") == pid and pub.get("status") == "COMPLETE",
               "scoreNow": {k: (ctx[f"scores/{BRAIN}"] or {}).get(k) for k in ("value", "basis")}, "scoreBefore": {k: ((baseline["context"].get(f"scores/{BRAIN}")) or {}).get(k) for k in ("value", "basis")},
               "healthNodeUnchanged": _sha(ctx[f"health/brains/{BRAIN}"]) == _sha(baseline["context"].get(f"health/brains/{BRAIN}"))}
        dump("verify.json", out)
        print(json.dumps(out, indent=1)[:1500])
        return 0 if not bad_sha and not changed and out["publicationNodeMatchesRecord"] and out["scoreNow"] == out["scoreBefore"] and out["healthNodeUnchanged"] else 8
    if a.stage == "restore":
        baseline, pr = load("baseline.json"), load("publish-result.json")
        out = restore(_rtdb(tokens), baseline, pr["record"].get("pathSha256") or {}, pr.get("publishId"))
        dump("restore-result.json", out)
        print("removed", len(out["removed"]), "already equal", out["alreadyEqualToPrePilot"], "skipped (newer)", len(out["skipped"]))
        return 0
    return 2


def _latest_publish_id(store) -> str:
    ids = sorted({k.split("/")[2] for k in store.list(f"publishes/{BRAIN}/") if k.endswith("/record.json")})
    if len(ids) != 1:
        raise SystemExit(f"expected exactly one publication record for {BRAIN}, found {ids}")
    return ids[0]


def restore(rb, baseline: dict, written_sha: dict, publish_id: str | None = None) -> dict:
    """Undo the pilot, path by path, without ever overwriting newer data. The pilot is state-neutral (every Water Clarity value it wrote equals the captured pre-pilot value), so:
      * a value path whose live value still equals the captured pre-pilot value needs no change (already restored);
      * a value path whose live value differs is NEWER intelligence (a later run or publication): left alone and reported;
      * a path the pilot added that did not exist before (the Publisher's own publication record) is removed only while live still equals what the pilot wrote.
    A real (non state-neutral) publication is rolled back with LivePublisher.rollback, which re-applies the previous immutable artifact through the same validators."""
    from sector_brain_platform.publisher_live.apply import canonical_equal
    from sector_brain_platform.publisher.canonical import canonical_bytes, sha256_ref
    remove, unchanged, newer = {}, [], []
    for p, sha in sorted(written_sha.items()):
        before = baseline["values"].get(p.strip("/"))
        now = rb.get(p)
        if before is None:
            if now is not None and sha256_ref(canonical_bytes(now)) == sha:
                remove[p] = None
            elif now is not None:
                newer.append({"path": p, "why": "added by the pilot but changed since: left alone"})
        elif canonical_equal(now, before):
            unchanged.append(p)
        else:
            newer.append({"path": p, "why": "live differs from the pre-pilot value (newer data): left alone"})
    pub = rb.get(f"brains/{BRAIN}/publication")                                       # the Publisher's own record of THIS publication (not in pathSha256)
    if isinstance(pub, dict) and publish_id and pub.get("publishId") == publish_id and baseline["values"].get(f"brains/{BRAIN}/publication") is None:
        remove[f"brains/{BRAIN}/publication"] = None
    elif isinstance(pub, dict) and publish_id and pub.get("publishId") != publish_id:
        newer.append({"path": f"brains/{BRAIN}/publication", "why": "a later publication replaced the pilot's record: left alone"})
    if remove:
        rb.update(remove)
    return {"removed": sorted(remove), "alreadyEqualToPrePilot": len(unchanged), "skipped": newer}


def _rehearse(baseline: dict, commit: str, resolver_dir: str, dump) -> int:
    """No cloud access: the identical publisher code against a fake RTDB holding the captured live values and an in-memory store."""
    sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform", "tests"))
    from sector_brain_platform.publisher import MemoryObjectStore
    from sector_brain_platform.publisher.handoff import ArtifactWriter
    from sector_brain_platform.publisher_live.rig import Rig
    r = build(baseline, commit)
    rig = Rig(brains=(BRAIN,), tree=_nest(baseline["values"]), clock=dt.datetime.now(dt.timezone.utc))
    ref = ArtifactWriter(rig.store, BRAIN).write(r.artifact)
    diff = rig.live.baseline_diff(ref)
    rig.live.acknowledge_baseline(ref, approval_ref=APPROVAL)
    pre = json.loads(json.dumps(rig.rtdb.tree))
    res = rig.live.publish(ref)
    out = {"diff": {k: (len(v) if isinstance(v, list) else v) for k, v in diff.items()}, "result": res.result.value, "codes": res.codes, "writes": len(rig.rtdb.updates)}
    again = rig.live.publish(ref)
    out["secondPublish"] = again.result.value
    post = json.loads(json.dumps(rig.rtdb.tree))
    changed = sorted(p for p in baseline["values"] if _get(post, p) != _get(pre, p))
    out["valuesChangedByPublication"] = len(changed)                                    # state-neutral: no Water Clarity value may differ
    added = sorted(k for k in res.record["pathSha256"] if _get(pre, k) is None)
    out["pathsAddedByPublication"] = added
    rec = res.record
    rb = restore(rig.rtdb, baseline, rec["pathSha256"], res.publish_id)
    after = json.loads(json.dumps(rig.rtdb.tree))
    out["restore"] = {"removed": rb["removed"], "alreadyEqual": rb["alreadyEqualToPrePilot"], "skipped": len(rb["skipped"]), "treeEqualsPrePilot": _strip(after) == _strip(pre)}
    dump("rehearsal.json", out)
    print(json.dumps(out))
    ok = res.result.value == "PUBLISHED" and again.result.value == "SKIP" and not changed and out["restore"]["treeEqualsPrePilot"]
    return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())
