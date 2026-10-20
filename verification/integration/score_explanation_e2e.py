#!/usr/bin/env python3
"""Brain Score Explanation V1 — NONPRODUCTION end-to-end driver (Firebase RTDB emulator only).

Drives the REAL authoritative path against a local RTDB emulator so Sector Ops can be shown to follow it with no refresh:

    LivePublisher (test authorization)  ->  /brains/<id>/publication COMPLETE  ->  S1 trigger (publication_trigger.seen_token)
        ->  score_brains.main(["--write", "--if-changed"])  (unmodified)  ->  /scores/<id> {..., explanation}  ->  Ops onValue

  snapshot --out F       READ-ONLY: record every GET the scorer's dry run makes against PRODUCTION into a tree (writes are refused in-process)
  seed --snapshot F      write that tree into the emulator (+ /access/opsUsers/<uid> for the Ops test user)
  cycle --outcome O [--force]  one Orchestrator-like cycle: O = validated (publish a validated Fish improvement) | failed (same publication, the live
                         write fails) | none (no publication); then trigger -> score exactly as orchestrate.py step 4 does
  read --path P          print an emulator node

The emulator is addressed only through EMULATOR (default 127.0.0.1:9000) and NAMESPACE; the scorer's production URL is never used for writes.
Every write goes to the emulator. Nothing here is imported by any runtime.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain-scores"))

from sector_brain_platform import publication_trigger as PT  # noqa: E402
from sector_brain_platform.rtdb import BrainRtdb  # noqa: E402

FISH = "biological-state"
FAKE_URL = "https://sector-brain-e2e.emulator.invalid"           # passes the client's sector-brain guard; rewritten to the emulator below


def emulator_base(host: str, ns: str) -> tuple[str, str]:
    if not (host.startswith("127.0.0.1:") or host.startswith("localhost:")):
        raise SystemExit(f"refusing non-local emulator host {host!r}")
    return f"http://{host}", ns


def emulator_transport(host: str, ns: str, fail_next_patch: list | None = None):
    base, ns = emulator_base(host, ns)

    def transport(method, url, body):
        assert url.startswith(FAKE_URL), url                          # nothing but the in-process fake URL is ever rewritten
        u = base + url[len(FAKE_URL):] + "&" + urllib.parse.urlencode({"ns": ns})
        if method == "PATCH" and fail_next_patch:
            fail_next_patch.pop()
            return 401, '{"error": "e2e: injected definite write failure"}'
        req = urllib.request.Request(u, data=body, method=method, headers={"Content-Type": "application/json", "Authorization": "Bearer owner"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")
    return transport


class _Owner:
    def token(self):
        return "owner"


def emulator_db(host, ns, **kw):
    return BrainRtdb(FAKE_URL, tokens=_Owner(), transport=emulator_transport(host, ns, kw.pop("fail_next_patch", None)), **kw)


# ---------------------------------------------------------------- snapshot (production, read-only)
def snapshot(out: str) -> None:
    import score_brains
    tree: dict = {}

    def put(path, value):
        parts = [p for p in path.strip("/").split("/") if p]
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
            if not isinstance(node, dict):
                return
        if parts:
            node[parts[-1]] = value

    class Recording(BrainRtdb):
        def get(self, path, shallow=False):
            v = super().get(path, shallow)
            if not shallow and v is not None:
                put(path, copy.deepcopy(v))
            return v

        def update(self, updates):                                    # the snapshot can never write production
            raise PermissionError("snapshot is read-only")

    score_brains.BrainRtdb = Recording
    score_brains.main.__globals__["BrainRtdb"] = Recording
    sys.argv = ["score_brains.py"]                                    # dry run: reads only
    score_brains.main()
    tree.pop("activity", None)                                        # activity is not a scoring input
    json.dump({"_source": f"read-only scorer dry-run GETs against production, {dt.datetime.now(dt.timezone.utc).isoformat()}", "tree": tree},
              open(out, "w"))
    print(f"snapshot: {len(json.dumps(tree))} bytes, roots {sorted(tree)}")


# ---------------------------------------------------------------- seed / read (emulator)
def seed(path: str, host: str, ns: str, ops_user: str) -> None:
    tree = json.load(open(path))["tree"]
    tree.setdefault("access", {}).setdefault("opsUsers", {})[ops_user] = True
    tree.setdefault("control", {})["orchestrator"] = {"lastSeen": {b: PT.seen_token(n) for b, n in (tree.get("brains") or {}).items() if PT.seen_token(n)}}
    base, ns = emulator_base(host, ns)
    req = urllib.request.Request(f"{base}/.json?ns={ns}", data=json.dumps(tree).encode(), method="PUT",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer owner"})
    urllib.request.urlopen(req, timeout=60).read()
    print(f"seeded {ns} on {host}: roots {sorted(tree)}")


def read(host, ns, path):
    print(json.dumps(emulator_db(host, ns).get(path), indent=1))


# ---------------------------------------------------------------- one cycle
def _fish_artifact(responsibilities: dict, n: int, at: str):
    from sector_brain_platform.publisher import default_registry, seal_bundle
    return seal_bundle(brain_id=FISH, bundle_id="fish-publication-v1",
                       sections=[{"artifactSchema": "fish-registry-v1",
                                  "mutations": [{"op": "SET", "path": f"/brains/{FISH}/responsibilities", "value": responsibilities}]}],
                       lifecycle="PROFILED", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=at,
                       execution_id=f"00000000-0000-4000-8000-{n:012d}", code_version="e2e-nonproduction@1",
                       input_fingerprint="sha256:" + f"{n:02x}" * 32, knowledge_release="2026-10-17.1",
                       manifest_ref="local:e2e/manifest.json", manifest_sha256="sha256:" + "cd" * 32, registry=default_registry())


def publish(host, ns, outcome: str, now: dt.datetime) -> dict:
    """The REAL LivePublisher (publisher_live) with the test authorization, its production RTDB adapter ARMED against the emulator only."""
    from sector_brain_platform.publisher_live.rig import Rig
    from sector_brain_platform.publisher_live.rtdb_client import RtdbRestPublisherClient
    fail = ["x"] if outcome == "failed" else []
    client = RtdbRestPublisherClient(FAKE_URL, brain_id=FISH, tokens=_Owner(), transport=emulator_transport(host, ns, fail), armed=True)
    r = Rig(brains=(FISH,), clock=now)
    r.rtdb = client
    r.live = r._build(None, 4 * 1024 * 1024, r.signals.append)
    live = client.get(f"brains/{FISH}/responsibilities")
    base = _fish_artifact(live, 1, (now - dt.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    r.reconcile(r.ref(base))                                          # deliberate baseline = what is live now (history store is per-process)
    improved = copy.deepcopy(live)
    improved["biologicalState"]["validation"] = "VALIDATED"          # the "validated candidate improvement" under test (emulator data only)
    res = r.live.publish(r.ref(_fish_artifact(improved, 2, now.strftime("%Y-%m-%dT%H:%M:%SZ"))))
    return {"result": res.result.value, "signals": len(r.signals)}


def cycle(host, ns, outcome: str, force: bool = False) -> dict:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    db = emulator_db(host, ns)
    out = {"outcome": outcome}
    if outcome in ("validated", "failed"):
        out["publication"] = publish(host, ns, outcome, now)
    # orchestrate.py step 4, verbatim semantics: tokens -> changed Brains -> scorer only when something changed
    brains = db.get("brains") or {}
    state = db.get("control/orchestrator") or {}
    seen = {b: PT.seen_token(brains.get(b)) for b in brains}
    changed = sorted(b for b in seen if seen[b] != (state.get("lastSeen") or {}).get(b))
    out["changedBrains"] = changed
    if changed or force:                                              # force = orchestrate.py --force-scores
        import score_brains
        patched = lambda url=None, **kw: emulator_db(host, ns, **kw)     # noqa: E731  the scorer's own code, writing to the emulator
        score_brains.main.__globals__["BrainRtdb"] = patched
        sys.argv = ["score_brains.py", "--write", "--if-changed", "--db", FAKE_URL]
        score_brains.main()
        out["scored"] = True
    else:
        out["scored"] = False
    db.update({"control/orchestrator/lastSeen": {**(state.get("lastSeen") or {}), **{b: v for b, v in seen.items() if v}}})
    s = db.get(f"scores/{FISH}") or {}
    ex = s.get("explanation") or {}
    out["fish"] = {"value": s.get("value"), "uncapped": s.get("uncapped"), "scoreUpdatedAt": s.get("scoreUpdatedAt"),
                   "evaluationId": ex.get("evaluationId"), "gap": (ex.get("target") or {}).get("gap"), "change": (ex.get("change") or {}).get("direction")}
    print(json.dumps(out))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "seed", "cycle", "read"])
    ap.add_argument("--out"); ap.add_argument("--snapshot"); ap.add_argument("--path", default="scores")
    ap.add_argument("--outcome", choices=["validated", "failed", "none"], default="none")
    ap.add_argument("--emulator", default=os.environ.get("E2E_RTDB_EMULATOR", "127.0.0.1:9000"))
    ap.add_argument("--ns", default=os.environ.get("E2E_RTDB_NAMESPACE", "sector-brain-e2e"))
    ap.add_argument("--ops-user", default="e2e-ops-user")
    ap.add_argument("--force", action="store_true", help="run the scorer even when no Brain changed (orchestrate.py --force-scores)")
    a = ap.parse_args(argv)
    if a.cmd == "snapshot":
        snapshot(a.out)
    elif a.cmd == "seed":
        seed(a.snapshot, a.emulator, a.ns, a.ops_user)
    elif a.cmd == "read":
        read(a.emulator, a.ns, a.path)
    else:
        cycle(a.emulator, a.ns, a.outcome, a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
