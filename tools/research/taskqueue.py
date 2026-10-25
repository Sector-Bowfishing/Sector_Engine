#!/usr/bin/env python3
"""Persistent research task queue of the campaign coordinator (owner directive 2026-10-26: a generated task is executable work, never the end of an investigation).

One queue for the whole research home: <home>/shared/queue/queue.json (atomic writes, checkpointed after every transition). A task moves
QUEUED -> CLAIMED -> DONE | FAILED(requeued up to maxAttempts) | BLOCKED(exact reason, next source). It is deduplicated by a stable key (brain|gap|kind|topic) so the same
question is never asked twice, ordered by bowfishing priority, and resumable: a CLAIMED task whose executor died is returned to the queue by `recover`.

Task kinds:
  agent-research     find legitimate downloadable evidence for a gap anywhere (open web); result = sector-agent-result-v1
  implement-experiment  turn a verified dataset into a reviewed offline experiment (code + pre-declared thresholds) that the validator can re-run
Who executes: `campaign.py loop --executor claude-cli` (headless Claude Code, bounded by turns and dollars), `--executor session` (the coordinating Claude session
dispatches subagents and records results with `task-done`), or any command template (tests use a fake one). The queue never executes anything itself.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading

_lock = threading.Lock()
KINDS = ("agent-research", "implement-experiment")
STATUSES = ("QUEUED", "CLAIMED", "DONE", "FAILED", "BLOCKED")
BRAIN_PRIORITY = {"biological-state": 10, "water-temp": 20, "wind": 30, "lake-brain": 40, "water-clarity": 50, "depth": 60, "vegetation": 70, "sector-intelligence": 80}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path(home: str) -> str:
    return os.path.join(home, "shared", "queue", "queue.json")


def load(home: str) -> dict:
    p = path(home)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"schema": "sector-research-queue-v1", "tasks": []}


def _save(home: str, q: dict) -> None:
    p = path(home)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    q["updatedAt"] = now_iso()
    tmp = p + ".tmp"
    json.dump(q, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, p)


def key_of(brain: str, gap: str, kind: str, topic: str = "") -> str:
    return hashlib.sha256(f"{brain}|{gap}|{kind}|{topic}".encode()).hexdigest()[:12]


def enqueue(home: str, brain: str, gap: str, kind: str, title: str, brief_path: str, created_by: str, topic: str = "", priority: int | None = None, max_attempts: int = 2,
            payload: dict | None = None) -> dict:
    """Idempotent: an identical question (brain|gap|kind|topic) already queued, running or done is returned, not duplicated. A FAILED one with attempts left is requeued."""
    if kind not in KINDS:
        raise ValueError(f"unknown task kind {kind!r}")
    k = key_of(brain, gap, kind, topic)
    with _lock:
        q = load(home)
        for t in q["tasks"]:
            if t["key"] == k:
                if t["status"] == "FAILED" and t["attempts"] < t["maxAttempts"]:
                    t["status"] = "QUEUED"
                    t["history"].append({"at": now_iso(), "event": "requeued after failure"})
                    _save(home, q)
                return t
        t = {"id": f"T{len(q['tasks']) + 1:04d}-{k[:6]}", "key": k, "brain": brain, "gap": gap, "kind": kind, "title": title, "brief": brief_path, "createdBy": created_by,
             "priority": BRAIN_PRIORITY.get(brain, 90) if priority is None else priority, "status": "QUEUED", "attempts": 0, "maxAttempts": max_attempts, "payload": payload or {},
             "createdAt": now_iso(), "history": [{"at": now_iso(), "event": "queued"}]}
        q["tasks"].append(t)
        _save(home, q)
        return t


def next_task(home: str, kinds: tuple | None = None) -> dict | None:
    q = load(home)
    cand = [t for t in q["tasks"] if t["status"] == "QUEUED" and (not kinds or t["kind"] in kinds)]
    return sorted(cand, key=lambda t: (t["priority"] + 5 * t["attempts"], t["id"]))[0] if cand else None


def _set(home: str, tid: str, **fields) -> dict:
    with _lock:
        q = load(home)
        for t in q["tasks"]:
            if t["id"] == tid:
                ev = fields.pop("event", None)
                t.update(fields)
                if ev:
                    t["history"].append({"at": now_iso(), "event": ev})
                _save(home, q)
                return t
    raise KeyError(tid)


def claim(home: str, tid: str, executor: str) -> dict:
    t = next(x for x in load(home)["tasks"] if x["id"] == tid)
    return _set(home, tid, status="CLAIMED", attempts=t["attempts"] + 1, executor=executor, event=f"claimed by {executor}")


def complete(home: str, tid: str, summary: str, result: str | None = None) -> dict:
    return _set(home, tid, status="DONE", result=result, summary=summary[:400], event="done: " + summary[:120])


def fail(home: str, tid: str, error: str) -> dict:
    t = next(x for x in load(home)["tasks"] if x["id"] == tid)
    st = "QUEUED" if t["attempts"] < t["maxAttempts"] else "FAILED"
    return _set(home, tid, status=st, error=error[:400], event=f"failed ({t['attempts']}/{t['maxAttempts']}): " + error[:100])


def block(home: str, tid: str, reason: str, next_source: str) -> dict:
    return _set(home, tid, status="BLOCKED", error=reason[:400], nextSource=next_source[:400], event="blocked: " + reason[:100])


def recover(home: str) -> int:
    """Tasks left CLAIMED by an executor that died (killed session, context limit) go back to the queue; nothing is lost and finished work is not repeated."""
    n = 0
    with _lock:
        q = load(home)
        for t in q["tasks"]:
            if t["status"] == "CLAIMED":
                t["status"] = "QUEUED"
                t["history"].append({"at": now_iso(), "event": "recovered after an interrupted executor"})
                n += 1
        if n:
            _save(home, q)
    return n


def counts(home: str) -> dict:
    out = dict.fromkeys(STATUSES, 0)
    for t in load(home)["tasks"]:
        out[t["status"]] += 1
    return out
