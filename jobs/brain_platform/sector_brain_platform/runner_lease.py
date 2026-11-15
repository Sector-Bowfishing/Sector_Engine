"""Runner leases: which runner (the cloud jobs, or a registered runner outside Cloud Run) runs a Brain's next cycle (Sector_Ops #46, #47, #50). DRAFT, nothing wired by default.

One lease object per Brain in the private artifact store, written by compare-and-swap (generation match, the same mechanism as the Publisher's apply lock):

    exports/runners/leases/{brainId}.json        sector-runner-lease-v1 {brainId, holder, cycleId, grantedAt, grantedBy, heartbeatAt, leaseUntil}
    exports/runners/{holder}/executions/{brainId}/{executionId}.json      sector-runner-execution-v1, create-only: a run that did not happen in Cloud Run
    exports/runners/grants/{brainId}/{cycleId}.json                      the grant ledger (#51 C2): create-only copy of every grant the Orchestrator made

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
import re

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


def grant_key(brain_id: str, cycle_id: str) -> str:
    return f"{PREFIX}grants/{brain_id}/{cycle_id}.json"


def lease_key(brain_id: str) -> str:
    return f"{PREFIX}leases/{brain_id}.json"


def execution_key(holder: str, brain_id: str, execution_id: str) -> str:
    return f"{PREFIX}{holder}/executions/{brain_id}/{execution_id}.json"


def orchestrator_view(store) -> ScopedObjectStore:
    """The Orchestrator: read every lease and runner execution, grant leases. It cannot write a runner's execution records."""
    return ScopedObjectStore(store, read=(PREFIX,), create=(f"{PREFIX}leases/", f"{PREFIX}grants/"), overwrite=(f"{PREFIX}leases/",))


def runner_view(store, holder: str) -> ScopedObjectStore:
    """A runner: read leases, renew its own (`renew` refuses another holder's lease), create its own execution records once. The path scope alone does not stop
    a runner rewriting a lease document: that must also be enforced by the runner's credential (IAM), never by this view only."""
    if holder not in HOLDERS:
        raise ValueError(f"unknown runner {holder!r}")
    return ScopedObjectStore(store, read=(PREFIX,), create=(f"{PREFIX}{holder}/executions/", f"{PREFIX}{holder}/faults/"),
                             overwrite=(f"{PREFIX}leases/",))


FAULT_SCHEMA = "sector-runner-fault-v1"


def fault_key(holder: str, brain_id: str, at: dt.datetime, kind: str) -> str:
    return f"{PREFIX}{holder}/faults/{brain_id}/{at.astimezone(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{kind}.json"


def record_fault(view, holder: str, brain_id: str, kind: str, detail: str, now: dt.datetime) -> str:
    """Sector_Ops #51: a runner reports a fault it stopped itself for (create-only). The Orchestrator's cycle watchdog reads every fault and
    latches a halt (cycle_watchdog RUNNER_FAULT), which alerts the owner."""
    if holder not in HOLDERS:
        raise ValueError(f"unknown runner {holder!r}")
    if not re.fullmatch(r"[A-Z_]{3,40}", kind or ""):
        raise ValueError(f"fault kind {kind!r} must match [A-Z_]{{3,40}}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", brain_id or ""):
        raise ValueError(f"brain id {brain_id!r} is not a valid id")
    key = fault_key(holder, brain_id, now, kind)
    doc = {"schema": FAULT_SCHEMA, "brainId": brain_id, "holder": holder, "kind": kind, "detail": (detail or "")[:300],
           "at": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    view.put(key, json.dumps(doc, sort_keys=True).encode(), if_generation_match=0)
    return key


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
    try:                                                         # the ledger first (create-only): a lease never exists without its grant record
        store.put(grant_key(brain_id, cycle_id), canonical_bytes(doc), if_generation_match=0)
    except PreconditionFailed:
        pass                                                     # the same cycle granted again to its holder (an identical cycleId): the first grant stands
    try:                                                         # then the lease. If this loses the race, the orphan grant record is harmless: may_run needs the lease
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
                     cycle_id: str | None, engine_commit: str | None, decision: dict | None = None) -> str:
    """Create-only run record for a run outside Cloud Run, in the shape the Orchestrator reconciles (orchestration.execution_record fields used by the
    publication stage). An identical record re-written is a no-op; a different one under the same key is an error.

    SKIPPED (SI-P2, Sector_Ops #50): the Brain's own plan, run inside the job, said SKIP. Such a record carries no artifact and the decision instead
    ({"action": "SKIP", "reasons": [...]}); the publication stage counts it as a normal cycle outcome, never as a missing artifact or a failed run.
    SUCCEEDED and FAILED records keep their exact shape (no `decision` key), so records written before this are byte-identical."""
    if status not in ("SUCCEEDED", "FAILED", "SKIPPED"):
        raise ValueError("status must be SUCCEEDED, FAILED or SKIPPED")
    if status == "SKIPPED":
        if artifact is not None:
            raise ValueError("a SKIPPED run hands off no artifact")
        if not isinstance(decision, dict) or decision.get("action") != "SKIP":
            raise ValueError('a SKIPPED run needs its decision: {"action": "SKIP", "reasons": [...]}')
        if not cycle_id:
            raise ValueError("a SKIPPED run must name the cycle it was granted")
    elif decision is not None:
        raise ValueError("only a SKIPPED run carries a decision")
    doc = {"schema": EXEC_SCHEMA, "executionId": execution_id, "brainId": brain_id, "runner": holder, "status": status, "startedAt": started_at,
           "endedAt": ended_at, "cycleId": cycle_id, "engineCommit": engine_commit, "artifact": artifact}
    if decision is not None:
        doc["decision"] = {"action": "SKIP", "reasons": [str(r) for r in (decision.get("reasons") or [])][:20]}
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
        if r.get("runner") != parts[2]:                       # a record claims the runner whose folder holds it, or it is ignored
            continue
        if r.get("schema") == EXEC_SCHEMA and (since is None or (r.get("endedAt") or "") >= since):
            e = {"executionId": r["executionId"], "brainId": r["brainId"], "status": r["status"], "startedAt": r["startedAt"], "endedAt": r["endedAt"],
                 "runner": r["runner"], "cycleId": r.get("cycleId")}
            if r["status"] == "SKIPPED":
                e["decision"] = r.get("decision")
            out.append(e)
    return sorted(out, key=lambda e: e["endedAt"] or "")


def ledger_grant(store, brain_id: str, cycle_id: str | None) -> dict | None:
    """The Orchestrator's grant record for this cycle (the grant ledger, #51 C2), or None. The ledger is the ONLY lease history that counts: a runner's
    credential may rewrite the live lease object (renew), so a lease object alone never proves a grant."""
    if not cycle_id or "/" in str(cycle_id):
        return None
    try:
        g = json.loads(store.get(grant_key(brain_id, cycle_id)) or "null")
    except (TypeError, ValueError):
        return None
    return g if isinstance(g, dict) and g.get("schema") == SCHEMA and g.get("brainId") == brain_id and g.get("cycleId") == cycle_id else None


def grants_since(store, brain_id: str, since: str) -> list[dict]:
    """Grants made for one Brain at or after `since` (ISO), oldest first: the daily-cap and re-grant cooldown input."""
    out = []
    for k in store.list(f"{PREFIX}grants/{brain_id}/"):
        try:
            g = json.loads(store.get(k))
        except (TypeError, ValueError):
            continue
        if g.get("schema") == SCHEMA and (g.get("grantedAt") or "") >= since:
            out.append(g)
    return sorted(out, key=lambda g: g["grantedAt"])


def held_for_cycle(lease_history: list[dict], holder: str, cycle_id: str) -> bool:
    """Was `holder` the granted holder of `cycle_id`? The Orchestrator keeps the grants it made (its ledger); a runner's artifact for a cycle it did not hold
    is never requested for publication."""
    return any(g.get("holder") == holder and g.get("cycleId") == cycle_id for g in lease_history)


def reconcilable_executions(store, brain_ids, since: str | None = None, exclude=()) -> tuple[list[dict], list[dict]]:
    """Runner executions the publication stage may reconcile: only those whose runner held the granted lease for their cycle. Returns (kept, skipped)."""
    kept, skipped = [], []
    for e in runner_executions(store, brain_ids, since=since):
        if e["executionId"] in exclude:
            continue
        g = ledger_grant(store, e["brainId"], e["cycleId"])
        (kept if g and held_for_cycle([g], e["runner"], e["cycleId"]) else skipped).append(e)
    return kept, skipped
