"""Runner leases: which runner (the cloud jobs or Sector Pulse on the owner's Mac mini) runs a Brain's next cycle (Sector_Ops #46, #47, #50). DRAFT, nothing wired by default.

One lease object per Brain in the private artifact store, written by compare-and-swap (generation match, the same mechanism as the Publisher's apply lock):

    exports/runners/leases/{brainId}.json        sector-runner-lease-v1 {brainId, holder, cycleId, grantedAt, grantedBy, heartbeatAt, leaseUntil}
    exports/runners/{holder}/executions/{brainId}/{executionId}.json      sector-runner-execution-v1, create-only: a run that did not happen in Cloud Run

Who may do what (tested):
  * grant / take over   only the Orchestrator (`grant`). It is the single scheduling authority (Cortex PL-15), wherever it runs.
  * renew               only the current holder, only while the lease is unexpired (`renew`). An expired lease cannot be renewed: it must be granted again.
  * run                 a runner runs a cycle only while it holds an unexpired lease for that Brain (`may_run`).
  * failover            an expired lease moves to a different holder only when the reviewed policy enables failover. **OFF by default** (`runner-policy.json`):
                        with failover off, a dead primary means the Brain does not run, never that the other runner silently takes over (no surprise cloud cost).
  * publication         an artifact is requested for publication only when its runner held the lease for its cycle (`held_for_cycle`); the Publisher's apply lock and
                        artifactId idempotency stay the last line.

Nothing here talks to a database or starts anything. It needs a store with get / put(if_generation_match) / generation / list (publisher.storage contract).
"""
from __future__ import annotations

import datetime as dt
import json
import os

from .publisher.canonical import canonical_bytes
from .publisher.storage import PreconditionFailed, ScopedObjectStore

SCHEMA = "sector-runner-lease-v1"
EXEC_SCHEMA = "sector-runner-execution-v1"
PREFIX = "exports/runners/"            # under the store's existing exports/ root (publisher.storage PREFIXES); no new bucket root
HOLDERS = ("cloud", "pulse")
POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner-policy.json")
DEFAULT_TTL_MINUTES = 20                 # a heartbeat every ~5 min keeps it; two missed heartbeats plus margin and it expires


class LeaseBusy(RuntimeError):
    pass


class LeaseLost(RuntimeError):
    pass


def lease_key(brain_id: str) -> str:
    return f"{PREFIX}leases/{brain_id}.json"


def execution_key(holder: str, brain_id: str, execution_id: str) -> str:
    return f"{PREFIX}{holder}/executions/{brain_id}/{execution_id}.json"


def orchestrator_view(store) -> ScopedObjectStore:
    """The Orchestrator: read every lease and runner execution, grant leases. It cannot write a runner's execution records."""
    return ScopedObjectStore(store, read=(PREFIX,), create=(f"{PREFIX}leases/",), overwrite=(f"{PREFIX}leases/",))


def runner_view(store, holder: str) -> ScopedObjectStore:
    """A runner: read leases, renew its own (the CAS check refuses another holder's), create its own execution records once."""
    if holder not in HOLDERS:
        raise ValueError(f"unknown runner {holder!r}")
    return ScopedObjectStore(store, read=(PREFIX,), create=(f"{PREFIX}{holder}/executions/",), overwrite=(f"{PREFIX}leases/",))


def load_policy(path: str = POLICY_FILE) -> dict:
    p = json.load(open(path, encoding="utf-8"))
    if p.get("schema") != "sector-runner-policy-v1":
        raise ValueError("not a sector-runner-policy-v1 document")
    return p


def primary(policy: dict, brain_id: str) -> str:
    return (policy.get("primary") or {}).get(brain_id, policy.get("defaultPrimary", "cloud"))


def failover_enabled(policy: dict, brain_id: str) -> bool:
    f = policy.get("failover") or {}
    return bool(f.get("enabled")) and brain_id in (f.get("brains") or [])


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _t(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def read(store, brain_id: str) -> tuple[dict | None, int]:
    raw = store.get(lease_key(brain_id))
    return (json.loads(raw) if raw else None), store.generation(lease_key(brain_id))


def fresh(lease: dict | None, now: dt.datetime) -> bool:
    until = _t((lease or {}).get("leaseUntil"))
    return bool(until and now <= until)


def grant(store, policy: dict, brain_id: str, holder: str, cycle_id: str, now: dt.datetime, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> dict:
    """The Orchestrator grants the next cycle. Rules: a fresh lease of another holder is never taken (LeaseBusy); the policy's primary gets the lease when
    there is none or it has expired; another holder gets an expired lease only when failover is enabled for this Brain. Same holder: re-granted for the new cycle."""
    if holder not in HOLDERS:
        raise ValueError(f"unknown runner {holder!r}")
    cur, gen = read(store, brain_id)
    if cur and cur.get("holder") != holder:
        if fresh(cur, now):
            raise LeaseBusy(f"{brain_id} is held by {cur['holder']} until {cur['leaseUntil']}")
        if holder != primary(policy, brain_id) and not failover_enabled(policy, brain_id):
            raise LeaseBusy(f"{brain_id}: the lease of {cur['holder']} expired, and failover to {holder} is OFF in the runner policy")
    if not cur and holder != primary(policy, brain_id) and not failover_enabled(policy, brain_id):
        raise LeaseBusy(f"{brain_id}: {holder} is not the policy primary ({primary(policy, brain_id)}) and failover is OFF")
    doc = {"schema": SCHEMA, "brainId": brain_id, "holder": holder, "cycleId": cycle_id, "grantedAt": _iso(now), "grantedBy": "orchestrator",
           "heartbeatAt": _iso(now), "leaseUntil": _iso(now + dt.timedelta(minutes=ttl_minutes))}
    try:
        store.put(lease_key(brain_id), canonical_bytes(doc), if_generation_match=gen)
    except PreconditionFailed:
        raise LeaseBusy(f"{brain_id}: the lease changed concurrently") from None
    return doc


def renew(store, brain_id: str, holder: str, now: dt.datetime, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> dict:
    """The holder's heartbeat. Refused when another runner holds it, when it already expired (LeaseLost: stop before sealing), or on a concurrent change."""
    cur, gen = read(store, brain_id)
    if not cur or cur.get("holder") != holder:
        raise LeaseLost(f"{brain_id}: {holder} does not hold the lease")
    if not fresh(cur, now):
        raise LeaseLost(f"{brain_id}: the lease of {holder} expired at {cur['leaseUntil']}; only the Orchestrator can grant it again")
    doc = {**cur, "heartbeatAt": _iso(now), "leaseUntil": _iso(now + dt.timedelta(minutes=ttl_minutes))}
    try:
        store.put(lease_key(brain_id), canonical_bytes(doc), if_generation_match=gen)
    except PreconditionFailed:
        raise LeaseLost(f"{brain_id}: the lease changed concurrently") from None
    return doc


def may_run(store, brain_id: str, holder: str, now: dt.datetime) -> tuple[bool, str]:
    cur, _ = read(store, brain_id)
    if not cur:
        return False, "NO_LEASE"
    if cur.get("holder") != holder:
        return False, f"HELD_BY_{str(cur.get('holder')).upper()}"
    if not fresh(cur, now):
        return False, "LEASE_EXPIRED"
    return True, "LEASE_HELD"


def cloud_may_start(store, policy: dict, brain_id: str, now: dt.datetime) -> tuple[bool, str]:
    """The Orchestrator's gate before it starts a Brain's Cloud Run job. A Brain whose primary is not the cloud never starts in the cloud unless failover is on AND
    the primary's lease has expired. A Brain whose primary is the cloud starts unless another runner holds a fresh lease."""
    cur, _ = read(store, brain_id)
    if primary(policy, brain_id) != "cloud":
        if not failover_enabled(policy, brain_id):
            return False, f"PRIMARY_{primary(policy, brain_id).upper()}_FAILOVER_OFF"
        if fresh(cur, now) and cur.get("holder") != "cloud":
            return False, f"HELD_BY_{cur['holder'].upper()}"
        return True, "FAILOVER_PRIMARY_EXPIRED"
    if cur and cur.get("holder") != "cloud" and fresh(cur, now):
        return False, f"HELD_BY_{cur['holder'].upper()}"
    return True, "CLOUD_PRIMARY"


def record_execution(store, holder: str, brain_id: str, execution_id: str, *, status: str, started_at: str, ended_at: str, artifact: dict | None,
                     cycle_id: str | None, engine_commit: str | None) -> str:
    """Create-only run record for a run outside Cloud Run, in the shape the Orchestrator reconciles (orchestration.execution_record fields used by the
    publication stage). An identical record re-written is a no-op; a different one under the same key is an error."""
    if status not in ("SUCCEEDED", "FAILED"):
        raise ValueError("status must be SUCCEEDED or FAILED")
    doc = {"schema": EXEC_SCHEMA, "executionId": execution_id, "brainId": brain_id, "runner": holder, "status": status, "startedAt": started_at,
           "endedAt": ended_at, "cycleId": cycle_id, "engineCommit": engine_commit, "artifact": artifact}
    key = execution_key(holder, brain_id, execution_id)
    data = canonical_bytes(doc)
    try:
        store.put(key, data, if_generation_match=0)
    except PreconditionFailed:
        if store.get(key) != data:
            raise ValueError(f"{key} already holds a different record") from None
    return key


def runner_executions(store, brain_ids, since: str | None = None) -> list[dict]:
    """Every recorded runner execution (any holder) for these Brains, oldest first, as execution records the publication stage reconciles."""
    out = []
    for k in sorted(store.list(PREFIX)):
        parts = k.split("/")
        if len(parts) != 6 or parts[3] != "executions" or parts[4] not in brain_ids or not k.endswith(".json"):
            continue
        try:
            r = json.loads(store.get(k))
        except (TypeError, ValueError):
            continue
        if r.get("schema") == EXEC_SCHEMA and (since is None or (r.get("endedAt") or "") >= since):
            out.append({"executionId": r["executionId"], "brainId": r["brainId"], "status": r["status"], "startedAt": r["startedAt"], "endedAt": r["endedAt"],
                        "runner": r["runner"], "cycleId": r.get("cycleId")})
    return sorted(out, key=lambda e: e["endedAt"] or "")


def held_for_cycle(lease_history: list[dict], holder: str, cycle_id: str) -> bool:
    """Was `holder` the granted holder of `cycle_id`? The Orchestrator keeps the grants it made (its ledger); a runner's artifact for a cycle it did not hold
    is never requested for publication."""
    return any(g.get("holder") == holder and g.get("cycleId") == cycle_id for g in lease_history)
