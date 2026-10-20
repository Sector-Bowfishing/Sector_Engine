"""Field-level species identity-metadata patch for the Biological Brain's existing Brain RTDB writer.

Why it exists: `run.py --write` republishes every Fish path (whole `/species/{id}` nodes, the registry, validation, health, an activity event) and is a no-op
(SKIP) when the research release has not changed. Identity metadata added by the Species Registry (`waterDomains`, `waterDomainStatus`) can therefore not reach
`/species/{id}` without a full republish. This module computes the smallest safe change instead: it builds the species summaries exactly as a normal publish
would (same code), compares them with the live nodes, and emits ONLY the child paths of an explicit allow-list. If anything else about a species differs
(other than the two volatile timestamps), it REFUSES, so it can never carry knowledge, score or release changes. It writes through the same ownership-checked
`BrainRtdb.update` (one atomic multi-path update); it adds no writer, no path family and no ownership.
"""
from __future__ import annotations

PATCHABLE = ("waterDomains", "waterDomainStatus")       # the only species fields this patch may create, change or remove
VOLATILE = (("updatedAt",), ("responseBands", "generatedAt"))   # regenerated on every build; never a reason to write and never a reason to refuse


class PatchRefused(RuntimeError):
    pass


def _canon(node):
    """node without PATCHABLE and without the volatile leaves (deep copy)."""
    import copy
    d = copy.deepcopy({k: v for k, v in node.items() if k not in PATCHABLE})
    for path in VOLATILE:
        cur = d
        for p in path[:-1]:
            cur = cur.get(p) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, dict):
            cur.pop(path[-1], None)
    return d


def plan_patch(live_species: dict | None, desired_updates: dict) -> tuple[dict, dict]:
    """(patch, report). `desired_updates` is the multi-path update of a normal build (`/species/{id}` -> summary). Refuses on any non-allow-listed difference."""
    live = live_species or {}
    want = {k.split("/")[2]: v for k, v in desired_updates.items() if k.startswith("/species/") and k.count("/") == 2}
    if not want:
        raise PatchRefused("build produced no species summaries")
    missing = sorted(set(want) - set(live))
    extra = sorted(set(live) - set(want))
    if missing or extra:
        raise PatchRefused(f"species set differs from live (not in live: {missing[:5]}; not in build: {extra[:5]}); this patch never adds or removes species")
    patch, changes, offending = {}, [], []
    for sid in sorted(want):
        w, l = want[sid], live[sid]
        if w is None or not isinstance(l, dict):
            offending.append(f"{sid}: not a summary object")
            continue
        if _canon(w) != _canon(l):
            keys = sorted(k for k in set(_canon(w)) | set(_canon(l)) if _canon(w).get(k) != _canon(l).get(k))
            offending.append(f"{sid}: differs beyond {PATCHABLE}: {keys[:6]}")
            continue
        for f in PATCHABLE:
            if w.get(f) != l.get(f):
                patch[f"/species/{sid}/{f}"] = w.get(f)          # None (absent in the build) deletes the field
                changes.append({"speciesId": sid, "field": f, "from": l.get(f), "to": w.get(f)})
    if offending:
        raise PatchRefused("; ".join(offending[:5]) + (f" (+{len(offending) - 5} more)" if len(offending) > 5 else ""))
    return patch, {"speciesChecked": len(want), "paths": len(patch), "speciesChanged": len({c['speciesId'] for c in changes}), "changes": changes}


def verify_readback(live_species: dict, patch: dict) -> list[str]:
    """After a write: every patched path holds the intended value. Returns the problems."""
    bad = []
    for path, val in patch.items():
        _, _, sid, field = path.split("/")
        if (live_species.get(sid) or {}).get(field) != val:
            bad.append(path)
    return bad


def revert_patch(live_species: dict) -> dict:
    """Rollback: delete the allow-listed fields wherever they are present (restores the pre-patch node shape; nothing else is touched)."""
    return {f"/species/{sid}/{f}": None for sid, n in sorted((live_species or {}).items()) if isinstance(n, dict) for f in PATCHABLE if f in n}
