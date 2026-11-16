#!/usr/bin/env python3
"""Read-only before/after evidence for production exit checks X08, X11 and X12 around ONE live publish (Lake B6, Sector_Ops #51 2026-11-15).

GET only. The token comes from $BRAIN_ACCESS_TOKEN (Michael's own gcloud token, or a read-only identity's) and is never printed or stored.
Captures hold live data, so they are written OUTSIDE any git checkout (this repository is public), owner-readable only, and never committed.

  capture   --brain lake-brain --out DIR                          every root fingerprinted (per lake at slot level) + health + score + publication  -> DIR/fingerprints.json
  wait      --brain lake-brain --since-publish-id ID [--timeout-min N]   poll /brains/{id}/publication until its publishId changes (prints the new id)
  evaluate  --brain lake-brain --before DIR --after DIR --record record.json --out FILE   X08 / X11 / X12 verdicts (exit 0 only if all PASS)

What each check means here (docs/architecture/production/PRODUCTION_EXIT_GATE_V1.md):
  X08  every fingerprint that changed between the captures is inside the publish record's write set (pathSha256), or is owned by ANOTHER writer
       (another Brain's slot / registry / source, the Orchestrator's health, the Publisher's reserved node of another Brain). A change on a path this
       Brain owns but the record did not write is FAIL; a change nobody owns is REVIEW. Other writers keep running between captures, so their
       changes are listed, not failed.
  X11  /health/brains/{id} after the publish is not blanked, and is not HEALTHY while it reports stale lakes or reasons.
  X11  (cont.) HEALTHY with staleLakeCount > 0 is legitimate under Lake's own rule (reviewed lakes only), so it is reported, not failed.
  X12  /scores/{id} is unchanged in value, scoreVersion, uncapped and basis, and the record wrote nothing under /scores. No score to compare = INCONCLUSIVE.
The verdict is INCONCLUSIVE unless: the record is this Brain's, LIVE, PUBLISHED and COMPLETE; exactly this publish happened between the captures (before = the record's
previousPublishId, or no publication at all when it has none; after = its publishId); and each capture saw the same COMPLETE, non-pending publication node at its start
and end. Scope: every root is fingerprinted, except that per-lake snapshots cover snapshots/{k}/latest only (listed in the output).
Nothing here writes, pauses, resumes, deploys or grants anything.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "brain_platform"))

from sector_brain_platform.keys import BRAINS                       # noqa: E402
from sector_brain_platform.ownership import LAKE_BRAIN_ONLY_FLEET, PLATFORM_ONLY, PLATFORM_WRITER, SCORER_CHILDREN   # noqa: E402

RTDB_URL = "https://sector-brain.firebaseio.com"
SCHEMA = "sector-exit-watch-v1"
FLEET_ROOTS = ("lakes", "lakeFleet", "snapshots")                    # per-lake nodes; snapshots/{k}/latest only
PER_CHILD_ROOTS = {"brains": 1, "validation": 0, "sources": 0, "activity": 0, "health": 2, "jobs": 1}   # root -> depth below each child (one GET per child)
ROOT_DEPTH: dict[str, int] = {}                                      # every other root: one GET, depth 2
#: External-admin paths no cycle or publish may change: a change there is REVIEW, never an "other writer". The rest of /control is the Orchestrator's projection.
WATCHED = ("access", "control/executionControlV1")
SLOT_PARENTS = {"states", "profiles", "slots", "readiness", "modelVersions"}   # lakes/{k}/<parent>/<slot>, lakeFleet/{k}/<parent>/<slot>
#: Fleet children owned by one Brain outside the slot pattern (ownership.LAKE_BRAIN_ONLY_FLEET), and Lake's lake-state-v1 children of /lakes/{k}.
FLEET_ONLY = {f: "lake-brain" for f in LAKE_BRAIN_ONLY_FLEET}
LAKE_NODE_ONLY = {"brain": "lake-brain", "speciesPresence": "lake-brain"}


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def inside_git(path: str) -> bool:
    d = os.path.abspath(path)
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return r.returncode == 0 or "dubious ownership" in (r.stderr or "")      # a refused repository is still a repository


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):          # never re-send the token to another host
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def get(url: str, path: str, token: str, shallow: bool = False, timeout: int = 60):
    q = "?shallow=true" if shallow else ""
    req = urllib.request.Request(f"{url.rstrip('/')}/{urllib.parse.quote(path)}.json{q}", headers={"Authorization": f"Bearer {token}"}, method="GET")
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fingerprint(node, prefix: str, depth: int) -> dict[str, str]:
    """{path: sha256} of every subtree `depth` levels below `prefix` (shallower leaves are hashed where they end)."""
    if depth == 0 or not isinstance(node, dict):
        return {} if node is None else {prefix: _sha(node)}
    out: dict[str, str] = {}
    for k, v in node.items():
        out.update(fingerprint(v, f"{prefix}/{k}", depth - 1))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------- ownership
def _slot_owners() -> dict[str, str]:
    out = {}
    for brain, (slot, snap_field, _name) in BRAINS.items():
        out[slot] = brain
        out[snap_field] = brain
    return out


def _source_owners() -> dict[str, str]:
    from sector_brain_platform.publisher.registry import SOURCE_OWNERS
    return dict(SOURCE_OWNERS)


def owner(path: str, slots=None, sources=None) -> str | None:
    """The writer that owns a fingerprint path, or None when nothing declares it."""
    slots = _slot_owners() if slots is None else slots
    sources = _source_owners() if sources is None else sources
    p = path.strip("/").split("/")
    if p[0] in ("lakes", "lakeFleet") and len(p) >= 3:
        if p[2] in SLOT_PARENTS and len(p) >= 4:
            return slots.get(p[3])
        return (FLEET_ONLY if p[0] == "lakeFleet" else LAKE_NODE_ONLY).get(p[2])
    if p[0] == "snapshots" and len(p) >= 4 and p[2] == "latest":
        if p[3] == "brainVersions" and len(p) >= 5:
            return p[4] if p[4] in BRAINS else None
        return slots.get(p[3])
    if p[0] == "brains" and len(p) >= 2:
        if len(p) >= 3 and p[2] in ("publication", "certification"):
            return "publisher:" + p[1]
        if len(p) >= 3 and p[2] in SCORER_CHILDREN:
            return "scorer"
        return p[1]
    if p[0] == "validation" and len(p) >= 2:
        return p[1]
    if p[0] == "sources" and len(p) >= 2:
        return sources.get(p[1])
    if p[0] == "health":
        return "orchestrator"
    if p[0] == "scores":
        return "scorer"
    if any("/".join(p) == w or "/".join(p).startswith(w + "/") or w.startswith("/".join(p) + "/") for w in WATCHED):
        return None
    if p[0] == "control":
        return "orchestrator"
    if p[0] == "activity" and len(p) >= 2:
        for b in BRAINS:                              # event ids name their writer: ...-{brainId}-...
            if f"-{b}-" in p[1]:
                return b
        return "scorer" if f"-{PLATFORM_WRITER}-" in p[1] else None
    if p[0] in PLATFORM_ONLY:
        return "platform:" + p[0]
    return None


# ------------------------------------------------------------------------------------------------------------------------------------ capture
def capture(brain: str, fetch, workers: int = 8) -> dict:
    pub_start = fetch(f"brains/{brain}/publication")
    roots = sorted((fetch("", shallow=True) or {}).keys())
    keys = set()
    for r in FLEET_ROOTS:
        keys |= set((fetch(r, shallow=True) or {}).keys()) if r in roots else set()
    keys = sorted(keys)
    jobs = []
    for r in roots:
        if r == "lakes" or r == "lakeFleet":
            jobs += [(f"{r}/{k}", 2) for k in keys]
        elif r == "snapshots":
            jobs += [(f"snapshots/{k}/latest", 2) for k in keys]
        elif r in PER_CHILD_ROOTS:
            jobs += [(f"{r}/{c}", PER_CHILD_ROOTS[r]) for c in sorted((fetch(r, shallow=True) or {}).keys())]
        else:
            jobs.append((r, ROOT_DEPTH.get(r, 2)))

    def one(job):
        path, depth = job
        return fingerprint(fetch(path), path, depth)
    prints: dict[str, str] = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for part in ex.map(one, jobs):
            prints.update(part)
    out = {"schema": SCHEMA, "brain": brain, "capturedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "lakeCount": len(keys),
           "roots": roots, "scope": "every root; per-lake snapshots/{k}/latest only", "fingerprints": prints,
           "health": fetch(f"health/brains/{brain}"), "score": fetch(f"scores/{brain}"), "publicationAtStart": pub_start}
    out["publication"] = fetch(f"brains/{brain}/publication")
    return out


# ----------------------------------------------------------------------------------------------------------------------------------- evaluate
def _covered(path: str, written) -> bool:
    p = path.strip("/")
    for w in written:
        w = w.strip("/")
        if w == p or w.startswith(p + "/") or p.startswith(w + "/"):
            return True
    return False


SCORE_KEYS = ("value", "scoreVersion", "basis")          # the gate's criterion; `uncapped` may move under an unchanged value and is only reported


def _settled(c: dict) -> bool:
    """The capture saw one COMPLETE, non-pending publication node at its start and its end (or none at all)."""
    a, b = c.get("publicationAtStart"), c.get("publication")
    if a != b:
        return False
    return b is None or (isinstance(b, dict) and b.get("status") == "COMPLETE" and not b.get("pending"))


def evaluate(brain: str, before: dict, after: dict, record: dict) -> dict:
    written = sorted((record.get("pathSha256") or {}).keys())
    pid, prev = record.get("publishId"), record.get("previousPublishId")
    pub_before, pub_after = (before.get("publication") or {}).get("publishId"), (after.get("publication") or {}).get("publishId")
    window = {"publishId": pid, "previousPublishId": prev, "publicationBefore": pub_before, "publicationAfter": pub_after,
              "beforeAt": before.get("capturedAt"), "afterAt": after.get("capturedAt")}
    problems = []
    if record.get("brainId") != brain:
        problems.append(f"record brainId {record.get('brainId')!r} is not {brain!r}")
    if not (record.get("live") is True and record.get("result") == "PUBLISHED" and record.get("status") == "COMPLETE"):
        problems.append(f"record is not LIVE PUBLISHED COMPLETE (live={record.get('live')}, result={record.get('result')}, status={record.get('status')})")
    if not (pid and pub_after == pid and pub_before != pid and pub_before == prev):
        problems.append("the captures do not bracket exactly this publish (before must be the record's previousPublishId, after its publishId)")
    if not (_settled(before) and _settled(after)):
        problems.append("a capture overlapped a publish (publication node changed, pending or not COMPLETE during the capture)")
    exact = not problems
    window["exactlyThisPublish"] = exact
    window["problems"] = problems

    fb, fa = before["fingerprints"], after["fingerprints"]
    changed = sorted(p for p in set(fb) | set(fa) if fb.get(p) != fa.get(p))
    slots, sources = _slot_owners(), _source_owners()
    own, unowned, others = [], [], {}
    for p in changed:
        if _covered(p, written):
            continue
        o = owner(p, slots, sources)
        if o == brain:
            own.append(p)
        elif o is None:
            unowned.append(p)
        else:
            others.setdefault(o, []).append(p)
    x08 = "FAIL" if own else "REVIEW" if unowned else "PASS"

    h = after.get("health") if isinstance(after.get("health"), dict) else {}
    wrongly_healthy = h.get("status") == "HEALTHY" and bool(h.get("reasons"))
    x11 = "FAIL" if (not h or not h.get("status") or wrongly_healthy) else "PASS"

    sb = before.get("score") if isinstance(before.get("score"), dict) else {}
    sa = after.get("score") if isinstance(after.get("score"), dict) else {}
    score_written = [w for w in written if w.strip("/").split("/")[0] == "scores"
                     or (w.strip("/").split("/")[0] == "brains" and len(w.strip("/").split("/")) >= 3 and w.strip("/").split("/")[2] in SCORER_CHILDREN)]
    score_same = {k: sb.get(k) for k in SCORE_KEYS} == {k: sa.get(k) for k in SCORE_KEYS}
    if score_written or (sb and not score_same):
        x12 = "FAIL"
    elif sb.get("value") is None or sb.get("scoreVersion") is None:
        x12 = "INCONCLUSIVE"                          # nothing to compare: never a PASS
    else:
        x12 = "PASS"

    checks = {"X08": x08, "X11": x11, "X12": x12}
    if not exact:
        checks = {k: "INCONCLUSIVE" for k in checks}
    return {"schema": SCHEMA, "brain": brain, "window": window, "checks": checks, "scope": {"before": before.get("roots"), "after": after.get("roots")},
            "X08": {"changed": len(changed), "inWriteSet": len(changed) - len(own) - len(unowned) - sum(len(v) for v in others.values()),
                    "ownOutsideWriteSet": own[:50], "ownOutsideWriteSetCount": len(own), "unowned": unowned[:50], "unownedCount": len(unowned),
                    "otherWriters": {o: {"count": len(v), "sample": v[:5]} for o, v in sorted(others.items())}},
            "X11": {"before": {k: (before.get("health") or {}).get(k) for k in ("status", "staleLakeCount", "reasons")},
                    "after": {k: h.get(k) for k in ("status", "staleLakeCount", "reasons")}, "blanked": not h, "wronglyHealthy": wrongly_healthy,
                    "refreshed": before.get("health") != after.get("health")},
            "X12": {"before": {k: sb.get(k) for k in SCORE_KEYS + ("uncapped",)}, "after": {k: sa.get(k) for k in SCORE_KEYS + ("uncapped",)},
                    "recordWroteScores": score_written}}


# --------------------------------------------------------------------------------------------------------------------------------------- main
def _private_dump(path: str, obj) -> None:
    old = os.umask(0o077)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, sort_keys=True, ensure_ascii=False)
    finally:
        os.umask(old)


def main(argv=None, fetch_raw=get, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=("capture", "wait", "evaluate"))
    ap.add_argument("--brain", required=True, choices=sorted(BRAINS))
    ap.add_argument("--out")
    ap.add_argument("--rtdb", default=RTDB_URL)
    ap.add_argument("--since-publish-id")
    ap.add_argument("--timeout-min", type=float, default=180)
    ap.add_argument("--before")
    ap.add_argument("--after")
    ap.add_argument("--record")
    a = ap.parse_args(argv)

    if a.stage == "evaluate":
        if not (a.before and a.after and a.record and a.out):
            print("REFUSED: evaluate needs --before, --after, --record and --out", file=sys.stderr)
            return 2
        if inside_git(a.out):
            print(f"REFUSED: {a.out} is inside a git checkout; evidence stays private", file=sys.stderr)
            return 2
        if os.path.exists(a.out):
            print(f"REFUSED: {a.out} exists (evidence is never overwritten)", file=sys.stderr)
            return 2
        load = lambda d: json.load(open(os.path.join(d, "fingerprints.json"), encoding="utf-8"))   # noqa: E731
        res = evaluate(a.brain, load(a.before), load(a.after), json.load(open(a.record, encoding="utf-8")))
        _private_dump(a.out, res)
        print(json.dumps({"checks": res["checks"], "window": res["window"],
                          "X08": {k: res["X08"][k] for k in ("changed", "inWriteSet", "ownOutsideWriteSetCount", "unownedCount")}}, indent=1))
        return 0 if all(v == "PASS" for v in res["checks"].values()) else 1

    token = os.environ.get("BRAIN_ACCESS_TOKEN")
    if not token:
        print("REFUSED: set BRAIN_ACCESS_TOKEN", file=sys.stderr)
        return 2
    u = urllib.parse.urlparse(a.rtdb)
    if u.scheme != "https" or not (u.hostname or "").endswith(".firebaseio.com"):
        print("REFUSED: --rtdb must be an https://*.firebaseio.com database (the token is sent to it)", file=sys.stderr)
        return 2
    fetch = lambda path, shallow=False: fetch_raw(a.rtdb, path, token, shallow)   # noqa: E731

    if a.stage == "wait":
        if not a.since_publish_id:
            print("REFUSED: wait needs --since-publish-id", file=sys.stderr)
            return 2
        deadline = time.monotonic() + a.timeout_min * 60
        while True:
            try:
                cur = (fetch(f"brains/{a.brain}/publication") or {}).get("publishId")
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    print(f"REFUSED: the database answered {e.code}; the token has expired or lacks access. Mint a new one and re-run wait", file=sys.stderr)
                    return 4
                print(f"retrying after a read error: HTTP {e.code}", file=sys.stderr)
                cur = None
            except OSError as e:                       # URLError/timeouts: one transient error must not end a long wait
                print(f"retrying after a read error: {type(e).__name__}", file=sys.stderr)
                cur = None
            if cur and cur != a.since_publish_id:
                print(cur)
                return 0
            if time.monotonic() >= deadline:
                print(f"TIMEOUT: publication is still {cur}", file=sys.stderr)
                return 3
            sleep(60)

    if not a.out:
        print("REFUSED: capture needs --out", file=sys.stderr)
        return 2
    if inside_git(a.out):
        print(f"REFUSED: {a.out} is inside a git checkout; a capture holds live data and must stay private", file=sys.stderr)
        return 2
    if os.path.exists(os.path.join(a.out, "fingerprints.json")):
        print(f"REFUSED: {a.out} already holds a capture (captures are never overwritten)", file=sys.stderr)
        return 2
    cap = capture(a.brain, fetch)
    os.makedirs(a.out, mode=0o700, exist_ok=True)
    _private_dump(os.path.join(a.out, "fingerprints.json"), cap)
    print(json.dumps({"capturedAt": cap["capturedAt"], "lakeCount": cap["lakeCount"], "fingerprints": len(cap["fingerprints"]),
                      "publishId": (cap["publication"] or {}).get("publishId"), "sha256": _sha(cap["fingerprints"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
