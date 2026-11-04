"""Orchestrator-owned operational health derived from PUBLISHED Brain intelligence (Cortex 3.1 FD-15; owner decision 2026-10-29).

The Publisher never writes /health/*. After a Brain's approved cutover its legacy domain-health facts (`/health/brains/{id}/{status,staleLakeCount}`) and per-source health
(`/health/sources/{id}`) keep being available to their readers (Sector Ops, Sector Intelligence), but they are written by the Orchestrator, derived ONLY from what the Publisher
actually published (`/brains/{id}/...` and `/sources/{id}`). Nothing here reads a Brain's process state, invents a value or writes a path the Orchestrator does not own.
"""
from __future__ import annotations

from . import data_ownership as DO

#: Brains whose legacy health paths are mirrored after cutover. Water Clarity (the approved pilot) and Lake (#48 A3, ahead of its cutover) are listed.
def _clarity_source_ids():
    from .publisher.registry import _clarity_sources              # the Publisher registry's own list of the source records Clarity authors
    return tuple(_clarity_sources())


def _water_temp_source_ids():
    from .publisher.registry import WATER_TEMP, _owned_sources     # the Publisher registry's own list of the source records Water Temp authors
    return tuple(sorted(_owned_sources(WATER_TEMP)))


def _lake_source_ids():
    from .publisher.registry import LAKE, _owned_sources           # the Publisher registry's own list of the source records Lake authors
    return tuple(sorted(_owned_sources(LAKE)))


# `registryMap` = {health child: the PUBLISHED registry field it is derived from}. A Brain registry's `status` is its lifecycle (CALIBRATION, BETA, ...),
# and its run health is `health`: copying `status` would publish the lifecycle as health (2026-11-04 review). Without a map, a child is copied from the
# registry field of the same name. `retireChildren` are legacy children that nothing published supports: they are removed (written null) so a stale
# value never sits beside fresh ones; unknown stays absent.
SPECS = {
    "water-clarity": {"registryChildren": ("status", "staleLakeCount"), "registryMap": {"status": "health", "staleLakeCount": "staleLakeCount"},
                      "sources": _clarity_source_ids},
    # Sector_Ops #48 A3: mirrored only once Lake is CENTRAL (the stage derives health for CENTRAL Brains that published); until then Lake's own writer writes them.
    # `reasons` is not in Lake's published registry, so it stays absent until Lake publishes it.
    # Lake's job also writes lastRun/lastSuccess/durationMs/errorCount (and latestError on failure): lastSuccess is published (lastSuccessfulRun), the rest retire.
    "lake-brain": {"registryChildren": ("status", "staleLakeCount", "reasons", "lastSuccess"),
                   "registryMap": {"status": "health", "staleLakeCount": "staleLakeCount", "reasons": "healthReasons", "lastSuccess": "lastSuccessfulRun"},
                   "retireChildren": ("lastRun", "errorCount", "durationMs", "latestError"), "sources": _lake_source_ids},
    # Sector_Ops #50 WT-P2 A3: mirrored only once Water Temp is CENTRAL; until then its own writer writes them. Its job writes lastRun/lastSuccess/errorCount/durationMs
    # today (latestError on the failure path): lastSuccess is published (lastSuccessfulRun); the others are execution facts nothing published carries,
    # so they are retired at cutover.
    "water-temp": {"registryChildren": ("status", "staleLakeCount", "lastSuccess"),
                   "registryMap": {"status": "health", "staleLakeCount": "staleLakeCount", "lastSuccess": "lastSuccessfulRun"},
                   "retireChildren": ("lastRun", "errorCount", "durationMs", "latestError"), "sources": _water_temp_source_ids},
}

#: Source health fields carried from the published `/sources/{id}` record when present (Water Temp publishes failuresLastRun, Clarity failures24h).
SOURCE_FIELDS = ("lastFetchAt", "failures24h", "failuresLastRun")


def registry_map(spec: dict) -> dict:
    return spec.get("registryMap") or {c: c for c in spec["registryChildren"]}


def derive(brain_id: str, registry: dict | None, sources: dict | None) -> dict:
    """-> {path: value} for the health paths this Brain's published data supports. Missing source data produces no path (unknown stays absent, never a default);
    a retired child maps to None (removed)."""
    spec = SPECS.get(brain_id)
    if not spec:
        return {}
    out = {}
    for c, field in registry_map(spec).items():
        if isinstance(registry, dict) and registry.get(field) is not None:
            out[f"health/brains/{brain_id}/{c}"] = registry[field]
    for c in spec.get("retireChildren") or ():
        out[f"health/brains/{brain_id}/{c}"] = None                 # removed: no published fact supports it
    if spec.get("sources"):
        for sid, rec in sorted((sources or {}).items()):
            if sid not in set(spec["sources"]()):
                continue
            if not isinstance(rec, dict) or rec.get("health") is None:
                continue
            row = {"status": rec["health"]}
            for f in SOURCE_FIELDS:
                if rec.get(f) is not None:
                    row[f] = rec[f]
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
        registry = {f: db.get(f"brains/{b}/{f}") for f in registry_map(spec).values()}
        srcs = {}
        if spec.get("sources"):
            srcs = {k: v for k, v in (db.get("sources") or {}).items() if isinstance(v, dict) and k in set(spec["sources"]())}
        want = derive(b, registry, srcs)
        diff = {k: v for k, v in want.items() if db.get(k) != v}
        if diff and write:
            db.update(diff)
        done[b] = {"derived": len(want), "changed": len(diff), "written": bool(diff and write)}
    return done
