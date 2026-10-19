"""Per-Brain apply lock and quarantine marker, kept in the versioned history store (generation-match = compare-and-swap).

RTDB has no multi-location compare-and-set, so serialisation of live publishes for one Brain is done HERE: the lock is acquired with a generation-matched put
and is never auto-expired (fail closed: a crashed run leaves the lock held until an operator breaks it with a recorded reason, after reading live state).
"""
from __future__ import annotations

import json

from ..publisher.canonical import canonical_bytes
from ..publisher.storage import PreconditionFailed, _seg


def lock_key(brain_id: str) -> str:
    return f"publishes/{_seg(brain_id, 'brainId')}/_locks/apply.json"


def quarantine_key(brain_id: str) -> str:
    return f"publishes/{_seg(brain_id, 'brainId')}/_locks/quarantine.json"


class LockBusy(RuntimeError):
    pass


def _state(store, key):
    b = store.get(key)
    return json.loads(b) if b else None


def acquire(store, brain_id: str, publish_id: str, now: str) -> int:
    key = lock_key(brain_id)
    cur = _state(store, key)
    if cur and cur.get("state") == "HELD":
        raise LockBusy(f"apply lock for {brain_id} is held by {cur.get('publishId')} since {cur.get('since')}")
    gen = store.generation(key)
    try:
        return store.put(key, canonical_bytes({"state": "HELD", "publishId": publish_id, "since": now}), if_generation_match=gen)
    except PreconditionFailed:
        raise LockBusy(f"apply lock for {brain_id} was taken concurrently") from None


def release(store, brain_id: str, publish_id: str, now: str) -> None:
    key = lock_key(brain_id)
    cur = _state(store, key)
    if not cur or cur.get("publishId") != publish_id:
        return                                             # not ours: never release another run's lock
    store.put(key, canonical_bytes({"state": "RELEASED", "publishId": publish_id, "at": now}), if_generation_match=store.generation(key))


def break_lock(store, brain_id: str, reason: str, now: str) -> None:
    if not (isinstance(reason, str) and reason.strip()):
        raise ValueError("breaking a lock requires a recorded reason")
    key = lock_key(brain_id)
    store.put(key, canonical_bytes({"state": "RELEASED", "brokenReason": reason, "at": now}), if_generation_match=store.generation(key))


def quarantined(store, brain_id: str):
    q = _state(store, quarantine_key(brain_id))
    return q if q and q.get("state") == "QUARANTINED" else None


def quarantine(store, brain_id: str, publish_id: str, reason: str, now: str) -> None:
    key = quarantine_key(brain_id)
    store.put(key, canonical_bytes({"state": "QUARANTINED", "publishId": publish_id, "reason": reason, "at": now}), if_generation_match=store.generation(key))


def clear_quarantine(store, brain_id: str, publish_id: str, now: str) -> None:
    key = quarantine_key(brain_id)
    store.put(key, canonical_bytes({"state": "CLEARED", "byPublishId": publish_id, "at": now}), if_generation_match=store.generation(key))
