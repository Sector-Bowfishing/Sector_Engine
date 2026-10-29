"""Orchestrator-owned operational health derived from PUBLISHED Brain intelligence (Cortex 3.1 FD-15; owner decision 2026-10-29).

The Publisher never writes /health/*. After a Brain's approved cutover its legacy domain-health facts (`/health/brains/{id}/{status,staleLakeCount}`) and per-source health
(`/health/sources/{id}`) keep being available to their readers (Sector Ops, Sector Intelligence), but they are written by the Orchestrator, derived ONLY from what the Publisher
actually published (`/brains/{id}/...` and `/sources/{id}`). Nothing here reads a Brain's process state, invents a value or writes a path the Orchestrator does not own.
"""
from __future__ import annotations

from . import data_ownership as DO

#: Brains whose legacy health paths are mirrored after cutover. Only Water Clarity (the approved pilot) is listed; a Brain is added with its own cutover plan.
def _clarity_source_ids():
    from .publisher.registry import _clarity_sources              # the Publisher registry's own list of the source records Clarity authors
    return tuple(_clarity_sources())


SPECS = {
    "water-clarity": {"registryChildren": ("status", "staleLakeCount"), "sources": _clarity_source_ids},
}


def derive(brain_id: str, registry: dict | None, sources: dict | None) -> dict:
    """-> {path: value} for the health paths this Brain's published data supports. Missing source data produces no path (unknown stays absent, never a default)."""
    spec = SPECS.get(brain_id)
    if not spec:
        return {}
    out = {}
    for c in spec["registryChildren"]:
        if isinstance(registry, dict) and registry.get(c) is not None:
            out[f"health/brains/{brain_id}/{c}"] = registry[c]
    if spec.get("sources"):
        for sid, rec in sorted((sources or {}).items()):
            if sid not in set(spec["sources"]()):
                continue
            if not isinstance(rec, dict) or rec.get("health") is None:
                continue
            row = {"status": rec["health"]}
            if rec.get("lastFetchAt") is not None:
                row["lastFetchAt"] = rec["lastFetchAt"]
            if rec.get("failures24h") is not None:
                row["failures24h"] = rec["failures24h"]
            out[f"health/sources/{sid}"] = row
    for k in out:
        assert DO.platform_path_role(k) == DO.ORCHESTRATOR, f"{k} is not Orchestrator-owned"
    return out


def stage(db, brain_ids, write: bool) -> dict:
    """Mirror for every named (central, published) Brain. Writes only paths whose value differs from what is there now. Returns what it did, for the cycle record."""
    done = {}
    for b in sorted(brain_ids):
        spec = SPECS.get(b)
        if not spec:
            continue
        registry = {c: db.get(f"brains/{b}/{c}") for c in spec["registryChildren"]}
        srcs = {}
        if spec.get("sources"):
            srcs = {k: v for k, v in (db.get("sources") or {}).items() if isinstance(v, dict) and k in set(spec["sources"]())}
        want = derive(b, registry, srcs)
        diff = {k: v for k, v in want.items() if db.get(k) != v}
        if diff and write:
            db.update(diff)
        done[b] = {"derived": len(want), "changed": len(diff), "written": bool(diff and write)}
    return done
