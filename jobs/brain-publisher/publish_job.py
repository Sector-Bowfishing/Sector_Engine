#!/usr/bin/env python3
"""brain-publisher: the recurring central Publisher job (Cortex 3.1 PL-19, FD-15). PREPARED, NOT DEPLOYED, NOT ARMED.

One execution = one bounded pass, started by brain-orchestrator (no schedule of its own, PL-15):

  1. execution control   /control/executionControlV1 must be ENABLED for automatic work (fail closed); an admin run names its approval with --admin-ref (PL-15)
  2. cutover document    the reviewed publication-cutover.json staged into the image; only Brains marked CENTRAL with an approvalRef are considered
  3. requests            exports/orchestrator/publication-requests/{brain}/ (written by the Orchestrator, read-only here), oldest first, at most --max-artifacts per pass
  4. publish             the existing LivePublisher, one instance per Brain (its own LiveAuthorization, release resolver and key guard); without --live it runs dry_run():
                         the identical preparation, nothing written anywhere
  5. outcome             the Publisher's immutable history (publishes/), which the Orchestrator imports; a JSON report on stdout (and --out)
  6. customer copies     only with --live and only for a Brain whose PUBLISHER_CUSTOMER_* switch is set (absent = nothing, the default): after a verified
                         publication, that Brain's CUSTOMER-lane copy (customer/lakes/{k}/level | clarity | waterTemp) in one separate, key-guarded update
                         (publisher_live/customer_lane.py). A copy failure is reported and never undoes the publication.

The job writes only publishes/ in the artifact store, the producing Brain's validated paths in the Brain database, and (step 6, switch set) that Brain's own customer copy. It never writes /scores, /control, /health, /jobs,
never builds an artifact, never runs a Brain and never changes a schedule. Release approval is required (PackagedReleaseResolver require_approved=True); there is no exception flag.

usage:
  python publish_job.py --artifact-bucket B [--live] [--max-artifacts 4] [--admin-ref REF] [--out report.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "brain_platform"), os.path.join(HERE, "sector_brain_platform", "..")):   # repo layout, then the staged image layout
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

from sector_brain_platform import execution_control as EC                     # noqa: E402
from sector_brain_platform import publication_requests as PR                  # noqa: E402
from sector_brain_platform import publication_stage as PS                     # noqa: E402

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
CUTOVER = os.environ.get("PUBLICATION_CUTOVER") or next(
    (p for p in (os.path.join(HERE, "publication-cutover.json"), os.path.join(HERE, "..", "brain-orchestrator", "publication-cutover.json")) if os.path.exists(p)), None)
DEFAULT_MAX = 4


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pass(*, store, control: dict, cutover_path: str | None, make_publisher, live: bool, max_artifacts: int = DEFAULT_MAX, admin_ref: str | None = None,
             clock=lambda: dt.datetime.now(dt.timezone.utc), customer_lane=None) -> dict:
    """The whole pass with every client injected. `store` is the raw artifact store (wrapped here in the Publisher job's view); `make_publisher(brain_id)` returns a LivePublisher
    whose history uses the same view. `customer_lane(brain_id, result)` (optional) runs after a live PUBLISHED/RECOVERED result and returns a small
    report or None (lane not configured for that Brain: nothing is added). Returns the report; raises nothing for a single bad request (it becomes a problem entry)."""
    view = PR.publisher_job_view(store)
    report = {"schema": "sector-publisher-pass-v1", "startedAt": _iso(clock()), "mode": "LIVE" if live else "DRY_RUN", "adminRef": admin_ref,
              "executionControl": {"state": control.get("state"), "reason": control.get("reason")}, "brains": {}, "problems": [], "published": 0}
    allowed, why = EC.automatic_allowed(control)
    if not allowed and not (isinstance(admin_ref, str) and admin_ref.strip()):
        report["status"] = "HELD"
        report["reason"] = why
        return report
    cut, problems = PS.load_cutover(cutover_path)
    report["problems"] += [{"kind": p["kind"], "brainId": p.get("brainId"), "why": p.get("why")} for p in problems]
    central = sorted(b for b, e in cut.items() if e["state"] == "CENTRAL")
    budget = max(0, int(max_artifacts))
    for brain in central:
        if allowed and not EC.brain_enabled(control, brain) and not admin_ref:
            report["brains"][brain] = {"status": "HELD", "reason": "Brain disabled in the execution control"}
            continue
        todo, probs = PR.pending(view, brain, cut)
        report["problems"] += probs
        out = report["brains"][brain] = {"status": "DONE", "pending": len(todo), "results": []}
        if not todo:
            continue
        publisher = make_publisher(brain)
        for _at, ref in todo:
            if budget == 0:
                out["status"] = "BUDGET_EXHAUSTED"
                break
            budget -= 1
            try:
                res = publisher.publish(ref) if live else publisher.dry_run(ref)
            except Exception as e:                                             # noqa: BLE001 - unknown outcome: recorded, never counted as published
                out["results"].append({"artifactId": ref.artifact_id, "result": "ERROR", "detail": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            entry = {"artifactId": ref.artifact_id, "result": res.result.value, "codes": list(res.codes or []), "publishId": res.publish_id,
                     "updatePaths": len(res.updates or {}), "applied": bool(live and res.result.value in ("PUBLISHED", "RECOVERED"))}
            if customer_lane is not None and entry["applied"]:
                try:
                    lane = customer_lane(brain, res)
                except Exception as e:                                         # noqa: BLE001 - a copy failure never undoes a verified publication
                    lane = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
                    report["problems"].append({"kind": "CUSTOMER_COPY_FAILED", "brainId": brain, "why": lane["error"]})
                if lane is not None:
                    entry["customerCopies"] = lane
            out["results"].append(entry)
            report["published"] += 1 if live and res.result.value in ("PUBLISHED", "RECOVERED") else 0
    report["status"] = report.get("status") or "DONE"
    report["finishedAt"] = _iso(clock())
    return report


class _ReadOnlyRtdb:
    """Dry run: the Publisher may read (baseline, preconditions); any write is refused before it reaches a transport."""
    def __init__(self, db):
        self._db = db

    def get(self, path):
        return self._db.get(path)

    def update(self, updates):
        raise PermissionError("brain-publisher dry run: no database write")


def customer_env(environ=os.environ) -> dict:
    """The CUSTOMER-lane switches that are SET in the job's environment (absent stays absent: the lane is not configured for that Brain)."""
    from sector_brain_platform.publisher_live import customer_lane as CL
    names = sorted({e[1] for e in CL.LANE.values()})
    return {k: environ[k] for k in names if k in environ}


class _CustomerLaneDb:
    """Reads through the job's reader; writes only the Brain's own customer copy keys (customer_lane.key_allowed), never anything else."""
    def __init__(self, db, brain_id):
        self._db, self.brain_id = db, brain_id

    def get(self, path):
        return self._db.get(path)

    def update(self, updates):
        from sector_brain_platform.publisher_live import customer_lane as CL
        CL.assert_keys(self.brain_id, updates)
        return self._db.update(updates)


def make_customer_lane(env: dict, db_for, *, runner_for, clock=lambda: dt.datetime.now(dt.timezone.utc)):
    """-> customer_lane(brain_id, result) for run_pass, or None when no switch is set at all (the default: byte-identical to before)."""
    from sector_brain_platform.publisher_live import customer_lane as CL
    if not env:
        return None

    def lane(brain_id, res):
        if not CL.configured(brain_id, env):
            return None
        return CL.write_pass(brain_id, res.updates or {}, res.record or {}, rtdb=_CustomerLaneDb(db_for(brain_id), brain_id), env=env,
                             runner=runner_for(brain_id), now=clock())
    return lane


def _release_dir(brain_id: str) -> str:
    """The Brain's packaged knowledge release staged into this image (deploy-job.sh copies brains/<dir>/runtime/knowledge-release.json + its files to releases/<brainId>/)."""
    return os.path.join(HERE, "releases", brain_id)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-bucket", default=os.environ.get("PUBLICATION_ARTIFACT_BUCKET"), required=False)
    ap.add_argument("--live", action="store_true", help="apply publications (needs the approved deploy that passes it); default: dry run, nothing written")
    ap.add_argument("--max-artifacts", type=int, default=DEFAULT_MAX)
    ap.add_argument("--admin-ref", default=None, help="explicit, authorized admin run (PL-15): the approval reference; required while the execution control is PAUSED")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if not a.artifact_bucket:
        print("REFUSED: no artifact bucket (--artifact-bucket / PUBLICATION_ARTIFACT_BUCKET)", file=sys.stderr)
        return 2
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    from sector_brain_platform.publisher import PublishHistory, default_registry
    from sector_brain_platform.publisher_live.authorization import BrainAuthorization, LiveAuthorization
    from sector_brain_platform.publisher_live.publisher import LivePublisher
    from sector_brain_platform.publisher_live.release_resolver import PackagedReleaseResolver
    from sector_brain_platform.publisher_live.rtdb_client import RtdbRestPublisherClient
    from sector_brain_platform.rtdb import BrainRtdb, TokenProvider

    tokens = TokenProvider()
    store = GcsRestObjectStore(a.artifact_bucket, tokens)
    reader = BrainRtdb(RTDB_URL, tokens, brain_id=None)
    try:
        control = EC.parse(reader.get(EC.NODE))
    except Exception as e:                                                     # noqa: BLE001 - unreadable control = PAUSED (fail closed)
        control = EC.parse(None)
        control["reason"] = f"execution control unreadable ({type(e).__name__}): fail closed (PAUSED)"
    cut, _ = PS.load_cutover(CUTOVER)
    view = PR.publisher_job_view(store)

    def make_publisher(brain_id):
        db = RtdbRestPublisherClient(RTDB_URL, brain_id=brain_id, tokens=tokens, armed=True) if a.live else _ReadOnlyRtdb(reader)
        return LivePublisher(default_registry(), PublishHistory(view), db, LiveAuthorization(BrainAuthorization(brain_id, cut[brain_id]["approvalRef"])),
                             release_resolver=PackagedReleaseResolver(_release_dir(brain_id), brain_id, require_approved=True))
    lane = None
    if a.live:
        from sector_brain_platform import runner_lease as RL
        from sector_brain_platform.rtdb import BrainRtdb as _Raw
        policy = RL.load_policy()
        raw = _Raw(RTDB_URL, tokens, brain_id=None)
        lane = make_customer_lane(customer_env(), lambda _b: raw, runner_for=lambda b: RL.primary(policy, b))
    report = run_pass(store=store, control=control, cutover_path=CUTOVER, make_publisher=make_publisher, live=a.live, max_artifacts=a.max_artifacts, admin_ref=a.admin_ref,
                      customer_lane=lane)
    report["deploymentVersion"] = os.environ.get("DEPLOYMENT_VERSION")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
    print(json.dumps(report, indent=1, sort_keys=True))
    failed = any(r["result"] in ("ERROR", "APPLY_FAILED", "READBACK_MISMATCH", "QUARANTINED") for b in report["brains"].values() for r in b.get("results", []))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
