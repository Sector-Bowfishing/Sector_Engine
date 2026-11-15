"""The cycle watchdog (Sector_Ops #51, O6.3 in the system): every brain-orchestrator cycle checks the reviewed halt conditions itself, so the
watch never depends on a laptop. A trip LATCHES a halt in the private bucket; while it is latched the cycle starts nothing, grants nothing and
starts no Publisher (the same gate as a PAUSED execution control), and it also tries to pause its own Cloud Scheduler trigger.

  exports/orchestrator/watchdog/halt.json   sector-cycle-watchdog-halt-v1 {state: HALTED|CLEARED, at, trips[], cycle, schedulerPause, clearedBy?, ...}

Only the owner clears it (tools/ops/watchdog.py clear). The policy is reviewed in git (watchdog-policy.json, next to runner-policy.json).

The checks (each a Trip(kind, detail)); everything created before the policy's `since` is history and ignored:
  EXECUTION_OUTSIDE_POLICY   a Cloud Run execution of a job outside `allowedJobs` (e.g. a cloud water-clarity-brain start)
  LEASE_OUTSIDE_POLICY       a runner lease for a Brain the policy doesn't name, or held by anyone but that Brain's holder
  GRANT_OUTSIDE_POLICY       a grant-ledger record for a Brain the policy doesn't name
  MORE_ARTIFACTS_THAN_GRANTS a Brain sealed more artifacts than it was granted cycles (two artifacts in one cycle)
  ARTIFACT_OUTSIDE_POLICY    an artifact for a Brain the policy doesn't name
  PUBLISH_OUTSIDE_POLICY     a publication record for a Brain the policy doesn't name
  PUBLISH_NOT_COMPLETE       a LIVE record that isn't PUBLISHED + COMPLETE + live (a readback mismatch, a failed apply)
  PUBLISH_OUTSIDE_LAKES      a publication that wrote a lake outside the Brain's allowed lakes
  QUARANTINED                the Publisher quarantined the Brain
  LOCK_STUCK                 the Publisher's apply lock HELD longer than `lockHeldMaxMinutes`
  CONTROL_OUTSIDE_POLICY     the execution control enables a Brain the policy doesn't name
  RUNNER_FAULT               a runner (Pulse) reported a fault (exports/runners/{holder}/faults/)
  CHECK_FAILED               the store could not be read: never a silent pass (the cycle holds; the latch is NOT written for this alone)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(HERE, "watchdog-policy.json")
POLICY_SCHEMA = "sector-cycle-watchdog-policy-v1"
LATCH_KEY = "exports/orchestrator/watchdog/halt.json"
LATCH_SCHEMA = "sector-cycle-watchdog-halt-v1"
LAKE_PATH = re.compile(r"^/?(?:lakes|lakeFleet|snapshots)/([^/]+)/")


# The Publisher's apply lock and quarantine marker (its locks module; a platform module never imports the live Publisher, so the paths are
# restated here and pinned equal by jobs/brain-orchestrator/tests/test_cycle_watchdog.py).
def lock_key(brain_id: str) -> str:
    return f"publishes/{brain_id}/_locks/apply.json"


def quarantine_key(brain_id: str) -> str:
    return f"publishes/{brain_id}/_locks/quarantine.json"


@dataclass(frozen=True)
class Trip:
    kind: str
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail[:300]}


@dataclass
class Result:
    trips: list = field(default_factory=list)
    checked: list = field(default_factory=list)

    @property
    def tripped(self) -> bool:
        return any(t.kind != "CHECK_FAILED" for t in self.trips)

    @property
    def unreadable(self) -> bool:
        return any(t.kind == "CHECK_FAILED" for t in self.trips)


def load_policy(path: str | None = None) -> dict:
    with open(path or POLICY_PATH, encoding="utf-8") as fh:
        pol = json.load(fh)
    if pol.get("schema") != POLICY_SCHEMA:
        raise ValueError(f"watchdog policy schema {pol.get('schema')!r} != {POLICY_SCHEMA}")
    if not isinstance(pol.get("brains"), dict) or not isinstance(pol.get("allowedJobs"), list) or not pol.get("since"):
        raise ValueError("watchdog policy needs brains{}, allowedJobs[] and since")
    return pol


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s) -> str:
    """A comparable UTC 'YYYY-MM-DDTHH:MM:SS' prefix of an ISO time, or '' when absent."""
    return (s or "")[:19] if isinstance(s, str) else ""


def _json(store, key):
    raw = store.get(key)
    return json.loads(raw) if raw else None


# ------------------------------------------------------------------------------------------------------------------------------ the checks
CLEAN_RESULTS = {"PUBLISHED", "ROLLED_BACK"}      # with status COMPLETE and live
UNCHANGED_RESULTS = {"SKIP"}                       # unchanged against the head: nothing written (review of #141: never a halt)
PAIRING_SLACK = dt.timedelta(hours=1)              # a grant just before the boundary still pairs with its artifact just after it


def boundary(policy: dict, latch: dict | None) -> str:
    """Events before this are history: the policy's `since`, or the time the owner last CLEARED a halt (review of #141: a cleared halt must
    not re-trip on the same immutable records)."""
    since = _ts(policy["since"])
    if latch and latch.get("state") == "CLEARED":
        since = max(since, _ts(latch.get("at")))
    return since


def _keys(store, prefix: str, after: str) -> list[str]:
    """Keys under `prefix`, skipping objects created before `after` when the store reports creation times (the GCS store does), so every cycle
    reads only recent objects and old, malformed history never fails a check."""
    lister = getattr(store, "list_created", None)
    if lister is None:
        return store.list(prefix)
    return [k for k, created in lister(prefix) if _ts(created) >= after]


def _shift(ts: str, delta: dt.timedelta) -> str:
    return _ts(_iso(dt.datetime.fromisoformat(ts + "+00:00") - delta)) if ts else ts


def evaluate(policy: dict, *, store, executions: dict, control: dict | None, now: dt.datetime, latch: dict | None = None) -> Result:
    """All checks. `store` is the raw artifact store (read-only use here), `executions` {job: [Cloud Run execution]} as the cycle already
    lists them, `control` the parsed execution control (execution_control.parse), `latch` the current latch (a CLEARED one moves the
    boundary). Never raises: an unreadable input is a CHECK_FAILED trip."""
    res = Result()
    since = boundary(policy, latch)
    pair_since = _shift(since, PAIRING_SLACK)
    brains = policy["brains"]
    allowed_jobs = set(policy["allowedJobs"])

    def check(name, fn):
        try:
            fn()
            res.checked.append(name)
        except Exception as e:                                       # noqa: BLE001 - a check that can't read is never a silent pass
            res.trips.append(Trip("CHECK_FAILED", f"{name}: {type(e).__name__}"))

    def executions_check():
        for job, items in sorted((executions or {}).items()):
            for e in items or []:
                created = _ts((e.get("metadata") or {}).get("creationTimestamp"))
                if created >= since and job not in allowed_jobs:
                    res.trips.append(Trip("EXECUTION_OUTSIDE_POLICY", f"job {job} execution {(e.get('metadata') or {}).get('name')} at {created}Z"))

    def leases_check():
        for k in store.list("exports/runners/leases/"):                  # current state, not history: always every lease
            brain = k.rsplit("/", 1)[-1].removesuffix(".json")
            doc = _json(store, k) or {}
            want = (brains.get(brain) or {}).get("holder")
            if want is None:
                res.trips.append(Trip("LEASE_OUTSIDE_POLICY", f"lease for {brain} (holder {doc.get('holder')}), not in the policy"))
            elif doc.get("holder") != want:
                res.trips.append(Trip("LEASE_OUTSIDE_POLICY", f"lease for {brain} held by {doc.get('holder')}, expected {want}"))

    grants_since: dict[str, int] = {}

    def grants_check():
        for k in _keys(store, "exports/runners/grants/", pair_since):
            brain = k.split("/")[3] if len(k.split("/")) > 4 else "?"
            doc = _json(store, k) or {}
            granted = _ts(doc.get("grantedAt"))
            if granted < pair_since:
                continue
            if granted >= since and brain not in brains:
                res.trips.append(Trip("GRANT_OUTSIDE_POLICY", f"grant {k.rsplit('/', 1)[-1]} for {brain}"))
            grants_since[brain] = grants_since.get(brain, 0) + 1          # pairs with artifacts since the boundary (an hour of slack)

    def artifacts_check():
        counts: dict[str, int] = {}
        for k in _keys(store, "artifacts/", since):
            if not k.endswith("/artifact.json"):
                continue
            brain = k.split("/")[1]
            lineage = ((_json(store, k) or {}).get("lineage") or {})
            if _ts(lineage.get("generatedAt")) < since:
                continue
            counts[brain] = counts.get(brain, 0) + 1
            if brain not in brains:
                res.trips.append(Trip("ARTIFACT_OUTSIDE_POLICY", f"artifact {k} for {brain}"))
        for brain, n in sorted(counts.items()):
            if brain in brains and n > grants_since.get(brain, 0):
                res.trips.append(Trip("MORE_ARTIFACTS_THAN_GRANTS", f"{brain}: {n} artifacts since {since}Z for {grants_since.get(brain, 0)} granted cycles"))

    def publishes_check():
        seen_brains = set()
        for k in _keys(store, "publishes/", since):
            parts = k.split("/")
            if len(parts) < 3:
                continue
            brain = parts[1]
            seen_brains.add(brain)
            if not k.endswith("/record.json") or parts[2].startswith("_"):
                continue
            rec = _json(store, k) or {}
            when = max(_ts(rec.get("publishedAt")), _ts(rec.get("evaluatedAt")))
            if when < since:
                continue
            if brain not in brains:
                res.trips.append(Trip("PUBLISH_OUTSIDE_POLICY", f"publication {parts[2]} for {brain}"))
                continue
            result = rec.get("result")
            clean = (result in CLEAN_RESULTS and rec.get("status") == "COMPLETE" and rec.get("live")) or result in UNCHANGED_RESULTS
            if rec.get("mode") == "LIVE" and not clean:                  # REJECTED, FAILED_VALIDATION, PRECONDITION_FAILED, APPLY_FAILED, READBACK_MISMATCH, unknown
                res.trips.append(Trip("PUBLISH_NOT_COMPLETE", f"{brain} publication {parts[2]}: {result} {rec.get('status')}"))
            lakes = set((brains.get(brain) or {}).get("lakes") or [])
            if lakes:
                outside = sorted({m.group(1) for p in (rec.get("pathSha256") or {}) for m in [LAKE_PATH.match(p)] if m} - lakes)
                if outside:
                    res.trips.append(Trip("PUBLISH_OUTSIDE_LAKES", f"{brain} publication {parts[2]} wrote {outside[:5]}"))
        max_held = int(policy.get("lockHeldMaxMinutes", 30))
        for brain in sorted(seen_brains | set(brains)):
            if (_json(store, quarantine_key(brain)) or {}).get("state") == "QUARANTINED":
                res.trips.append(Trip("QUARANTINED", f"{brain} is quarantined by the Publisher"))
            lock = _json(store, lock_key(brain)) or {}
            if lock.get("state") == "HELD":
                at = lock.get("since") or lock.get("at") or ""             # the Publisher writes {state, publishId, since}
                try:
                    age = (now - dt.datetime.fromisoformat(at.replace("Z", "+00:00"))).total_seconds() / 60
                except ValueError:
                    age = 1e9
                if age > max_held:
                    res.trips.append(Trip("LOCK_STUCK", f"{brain} apply lock HELD since {at} ({int(age)} min)"))

    def control_check():
        enabled = sorted(b for b, v in ((control or {}).get("brains") or {}).items() if (v or {}).get("enabled"))
        if (control or {}).get("state") == "ENABLED":
            outside = [b for b in enabled if b not in brains]
            if outside:
                res.trips.append(Trip("CONTROL_OUTSIDE_POLICY", f"execution control enables {outside}"))

    def faults_check():
        for k in _keys(store, "exports/runners/", since):
            parts = k.split("/")
            if len(parts) >= 5 and parts[3] == "faults" and k.endswith(".json"):
                doc = _json(store, k) or {}
                if _ts(doc.get("at")) >= since:
                    res.trips.append(Trip("RUNNER_FAULT", f"{parts[2]} reported {doc.get('kind')} for {doc.get('brainId')}: {str(doc.get('detail'))[:160]}"))

    for name, fn in (("executions", executions_check), ("leases", leases_check), ("grants", grants_check), ("artifacts", artifacts_check),
                     ("publishes", publishes_check), ("control", control_check), ("faults", faults_check)):
        check(name, fn)
    return res


# ------------------------------------------------------------------------------------------------------------------------------ the latch
def read_latch(store) -> dict | None:
    """The latch document, or None. Raises when the store can't be read (the caller fails closed)."""
    return _json(store, LATCH_KEY)


def is_halted(latch: dict | None) -> bool:
    return bool(latch) and latch.get("state") == "HALTED"


def write_halt(store, trips: list, *, cycle: str, now: dt.datetime, scheduler_pause: str) -> dict:
    """Latch HALTED (compare-and-swap on the current generation). An existing HALTED latch is kept as it is: the first trip is the evidence."""
    cur_gen = store.generation(LATCH_KEY)
    cur = _json(store, LATCH_KEY)
    if is_halted(cur):
        return cur
    doc = {"schema": LATCH_SCHEMA, "state": "HALTED", "at": _iso(now), "cycle": cycle, "trips": [t.as_dict() for t in trips][:20],
           "schedulerPause": scheduler_pause,
           "clear": "owner only: python3 tools/ops/watchdog.py clear --changed-by <name> --approval-ref <ref> --reason <why>"}
    store.put(LATCH_KEY, json.dumps(doc, sort_keys=True).encode(), if_generation_match=cur_gen)
    return doc


def clear(store, *, changed_by: str, approval_ref: str, reason: str, now: dt.datetime) -> dict:
    """Owner action: CLEARED, keeping the halt it clears as evidence."""
    if not (changed_by.strip() and approval_ref.strip() and reason.strip()):
        raise ValueError("clear needs changed_by, approval_ref and reason")
    cur_gen = store.generation(LATCH_KEY)
    cur = _json(store, LATCH_KEY)
    doc = {"schema": LATCH_SCHEMA, "state": "CLEARED", "at": _iso(now), "clearedBy": changed_by, "approvalRef": approval_ref,
           "reason": reason[:300], "previous": cur}
    store.put(LATCH_KEY, json.dumps(doc, sort_keys=True).encode(), if_generation_match=cur_gen)
    return doc


def log_line(res: Result) -> str:
    """One line per cycle. The owner's alert matches `[watchdog] HALT ` (with the space: a new trip, not the hourly `HALTED since` reminder)
    and `[watchdog] UNREADABLE`."""
    if res.tripped:
        return "[watchdog] HALT " + "; ".join(f"{t.kind}: {t.detail}" for t in res.trips)[:900]
    if res.unreadable:
        return "[watchdog] UNREADABLE (holding this cycle, no latch) " + "; ".join(t.detail for t in res.trips)[:400]
    return f"[watchdog] OK {len(res.checked)} checks"
