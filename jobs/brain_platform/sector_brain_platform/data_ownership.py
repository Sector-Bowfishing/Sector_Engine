"""Cortex 3.1 data ownership and the nine target Brains, as the Engine enforces them.

Cortex (read only here) is the authority: `firebase-data.md` FD-15 (Brains produce, the Publisher writes canonical Brain intelligence; the Orchestrator owns operational
health, execution records and job controls; the shared scorer owns authoritative scores) and `brain-architecture.md` BA-01..BA-10 (nine target Brains; the combined
deployed `biological-state` package is a frozen LEGACY_COMBINED identity until its approved migration). The Engine keeps a MIRROR of the columns it needs
(`data_ownership.json`); tests compare the mirror with Cortex whenever Cortex is present, so drift is a test failure, not a surprise.

This module changes no production behaviour. `ownership.path_allowed` stays the runtime gate of the existing direct writers; this module
  * names the platform ROLES (orchestrator, scorer, Publisher) instead of one conflated "brain-platform" writer,
  * resolves any path to its registered family, current writer and target writer,
  * audits the Engine's ownership table against that registry (`audit`), and
  * recognizes the nine target Brains and maps them to what is deployed (`recognize`, `execution_order`).
"""
from __future__ import annotations

import json
import os
import re

from .keys import BRAINS
from .ownership import PLATFORM_WRITER, path_allowed

HERE = os.path.dirname(os.path.abspath(__file__))
ORCHESTRATOR, SCORER, PUBLISHER = "platform.orchestrator", "platform.scorer", "platform.publisher-live"
PLATFORM_ROLES = (ORCHESTRATOR, SCORER, PUBLISHER)


def mirror() -> dict:
    return json.load(open(os.path.join(HERE, "data_ownership.json"), encoding="utf-8"))


_FAMS = None


def _families() -> list:
    global _FAMS
    if _FAMS is None:
        out = []
        for f in mirror()["families"]:
            rx = "^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(f["pattern"])) + "(/.*)?$"
            out.append({**f, "rx": re.compile(rx), "depth": f["pattern"].count("/") + 0.001 * len(f["pattern"])})
        _FAMS = sorted(out, key=lambda x: -x["depth"])           # most specific family first (fam.lakefleet-last-updated before fam.lakefleet)
    return _FAMS


def family_for(path: str) -> dict | None:
    p = "/" + path.strip("/")
    for f in _families():
        if f["rx"].match(p):
            return f
    return None


def _brain_key(f: dict, path: str) -> str | None:
    """The Brain id embedded in a per-Brain family path (/brains/{brainId}, /health/brains/{brainId}, /validation/{brainId})."""
    s = [x for x in path.strip("/").split("/") if x]
    pat = [x for x in f["pattern"].strip("/").split("/") if x]
    for i, seg in enumerate(pat):
        if seg == "{brainId}" and i < len(s):
            return s[i]
    return None


def registered_writer(path: str) -> dict:
    """{family, current, target}: `current` is today's writer role (a platform role, 'brain:<id>', '@slot-brain', 'external', 'none'), `target` the Cortex target writer."""
    f = family_for(path)
    if not f:
        return {"family": None, "current": "UNREGISTERED", "target": None}
    w = f["writer"] or "NOT_VERIFIED"
    if w == "@owning-brain":
        key = _brain_key(f, path)
        cur = f"brain:{key}" if key else "@owning-brain"
    elif w.startswith("brain."):
        cur = "brain:" + w[len("brain."):]
    elif w in ("@external-admin",) or w.startswith("external."):
        cur = "external"
    elif w == "@none":
        cur = "none"
    else:
        cur = w
    return {"family": f["id"], "current": cur, "target": f.get("targetWriter"), "status": f["status"], "domain": f["domain"]}


def platform_role_allowed(role: str, path: str) -> bool:
    """May a platform ROLE write `path` today? Orchestrator: control, jobs and (target) health families. Scorer: authoritative scores and the legacy engine/score alias.
    Publisher: the families whose registered target writer is the Publisher (reached through the live Publisher package; its own key guard still applies)."""
    r = registered_writer(path)
    if role == PUBLISHER:
        return r["target"] == PUBLISHER
    if role == ORCHESTRATOR:
        return r["current"] == ORCHESTRATOR or r["target"] == ORCHESTRATOR
    if role == SCORER:
        return r["current"] == SCORER
    return False


#: Platform roots the registry does not list (a Cortex gap, recorded in docs/cortex/CORTEX_GAPS.md): the role the Engine assigns them so no path stays ambiguous.
UNREGISTERED_PLATFORM_ROLES = {("health", "engine"): ORCHESTRATOR, ("health", "rtdb"): ORCHESTRATOR, ("engine",): SCORER, ("activity",): ORCHESTRATOR}


def platform_path_role(path: str) -> str | None:
    """The ONE platform role that owns a platform path (Orchestrator: control, jobs, health, platform activity; Scorer: scores and the engine score alias). None for paths no
    platform role may write (Brain families, external-admin access lists, schemaVersion)."""
    s = [x for x in path.strip("/").split("/") if x]
    if not s:
        return None
    r = registered_writer(path)
    if r["current"] in (ORCHESTRATOR, SCORER):
        return r["current"]
    if r["family"] and r["target"] == ORCHESTRATOR:
        return ORCHESTRATOR
    for k, role in UNREGISTERED_PLATFORM_ROLES.items():
        if tuple(s[:len(k)]) == k and r["current"] in ("UNREGISTERED", "none"):
            return role
    return None


def role_of_platform_writer(path: str) -> str | None:
    """The single platform role that owns `path` among the families the conflated PLATFORM_WRITER ('brain-platform') may write today."""
    for role in (SCORER, ORCHESTRATOR):
        if platform_role_allowed(role, path):
            return role
    return None


# ------------------------------------------------------------------------------------------------------------------------------- audit
_SUB = {"{brainId}": "wind", "{eventId}": "wind-probe-1", "{jobId}": "probe-job", "{sourceId}": "probe-source", "{speciesId}": "probe_species", "{lakeKey}": "Probe_Lake_XX", "{uid}": "uid1"}
CHILD_PROBES = ("publication", "score", "scores")


def sample(pattern: str, brain: str = "wind") -> str:
    p = pattern
    for k, v in _SUB.items():
        p = p.replace(k, brain if k == "{brainId}" else v)
    return p.lstrip("/")


def audit(allowed=path_allowed) -> list:
    """Compare the Engine's runtime ownership table with the Cortex-mirrored registry. Every finding names the path, the writer and the rule broken.
    A direct Brain write that the registry still lists as the CURRENT writer (pre-cutover) is NOT a finding; it is reported by `pre_cutover_direct_writes`."""
    out = []
    brains = list(BRAINS)
    for f in mirror()["families"]:
        for b in brains:
            probe = sample(f["pattern"], "wind")
            other = sample(f["pattern"], b)
            # 1. a Brain writing a family whose registered writer is not a Brain (platform, external, none)
            w = f["writer"] or "NOT_VERIFIED"
            non_brain = w.startswith("platform.") or w in ("@external-admin", "@none") or w.startswith("external.")
            if non_brain and allowed(b, probe):
                out.append({"rule": "FD-15/SC-04", "code": "BRAIN_WRITES_NON_BRAIN_FAMILY", "brain": b, "path": "/" + probe, "family": f["id"], "writer": w})
            # 2. a Brain writing another Brain's per-Brain family (/brains/{brainId}, /validation/{brainId}, /health/brains/{brainId})
            if w == "@owning-brain" and "{brainId}" in f["pattern"] and b != "wind" and allowed(b, probe):
                out.append({"rule": "FD-03/BA-05", "code": "BRAIN_WRITES_OTHER_BRAIN_KEY", "brain": b, "path": "/" + probe, "family": f["id"], "writer": w})
            if w.startswith("brain.") and w != f"brain.{b}" and allowed(b, other) and "{brainId}" not in f["pattern"]:
                out.append({"rule": "FD-03", "code": "BRAIN_WRITES_OTHER_BRAIN_FAMILY", "brain": b, "path": "/" + other, "family": f["id"], "writer": w})
        # 3. the conflated platform writer must not write a Brain-owned canonical family
        probe = sample(f["pattern"], "wind")
        if (f["writer"] or "").startswith(("brain.", "@owning-brain", "@slot-brain")) and f["status"] == "CANONICAL" and allowed(PLATFORM_WRITER, probe):
            out.append({"rule": "FD-15", "code": "PLATFORM_WRITES_BRAIN_FAMILY", "brain": PLATFORM_WRITER, "path": "/" + probe, "family": f["id"], "writer": f["writer"]})
    # 3b. the platform writer must not write @external-admin families (access lists, the owner's execution-control document)
    for f in mirror()["families"]:
        if (f["writer"] or "") == "@external-admin" and allowed(PLATFORM_WRITER, sample(f["pattern"])):
            out.append({"rule": "FD-03/PL-15", "code": "PLATFORM_WRITES_EXTERNAL_ADMIN_FAMILY", "brain": PLATFORM_WRITER, "path": "/" + sample(f["pattern"]), "family": f["id"], "writer": f["writer"]})
    # 4. whole-node writes of a collection root (replaces every child written by others)
    for root in ("species", "brains", "validation", "lakeFleet", "lakes", "snapshots", "health", "sources", "activity"):
        for b in brains:
            if allowed(b, root):
                out.append({"rule": "FD-03", "code": "WHOLE_ROOT_WRITE", "brain": b, "path": "/" + root, "family": None, "writer": "brain"})
    # 5. a Brain writing the scorer's or the Publisher's child of its own node
    for b in brains:
        for child in ("score", "scores"):
            p = f"brains/{b}/{child}"
            if allowed(b, p) and not (b == "wind" and child == "scores"):                # /brains/wind/scores is the registered LEGACY wind family
                out.append({"rule": "SC-04", "code": "BRAIN_WRITES_SCORER_FIELD", "brain": b, "path": "/" + p, "family": "fam.brains", "writer": "platform.scorer"})
    return out


def pre_cutover_direct_writes() -> list:
    """The Brain-written canonical families that still have a direct writer today and a Publisher target (FD-15): information, never a failure, until each Brain's approved cutover."""
    return [{"family": f["id"], "pattern": f["pattern"], "currentWriter": f["writer"], "targetWriter": f["targetWriter"]} for f in mirror()["families"]
            if f["targetWriter"] == PUBLISHER and (f["writer"] or "").startswith(("brain.", "@owning-brain", "@slot-brain"))]


def role_conflicts() -> list:
    """Platform paths whose role is ambiguous in the Engine (one conflated writer for orchestrator, scorer and Publisher)."""
    out = []
    for f in mirror()["families"]:
        p = sample(f["pattern"])
        if allowed_by_platform(p) and role_of_platform_writer(p) is None and (f["writer"] or "").startswith("platform."):
            out.append({"path": "/" + p, "family": f["id"], "registeredWriter": f["writer"]})
    return out


def allowed_by_platform(path: str) -> bool:
    return path_allowed(PLATFORM_WRITER, path)


# ------------------------------------------------------------------------------------------------------------------------------- nine target Brains
def target_brains() -> list:
    return mirror()["targetBrains"]


def target_ids() -> list:
    return [b["id"] for b in target_brains()]


def recognize(brain_id: str) -> dict:
    """Classify an identity: TARGET (a Cortex target Brain), DEPLOYED (a deployed package that maps to one or more targets) or UNREGISTERED. The combined `biological-state` stays
    LEGACY_COMBINED and maps to BOTH fish-knowledge and fish-behavior; it is never reassigned to one of them (BA-04)."""
    tb = {b["id"]: b for b in target_brains()}
    mapped = [t["id"] for t in target_brains() if t["deployedAs"] == brain_id]
    legacy = {x["id"]: x for x in mirror().get("legacyIdentities") or []}
    if brain_id in legacy:
        x = legacy[brain_id]
        if x.get("status") == "LEGACY_ALIAS":          # fish / biological-brain / biological: names, never Brain identities (FD-02): not writable keys, not dispatch targets
            return {"id": brain_id, "kind": "ALIAS", "canonical": "biological-state", "targets": x.get("splitsInto") or mapped, "finding": "NONCANONICAL_BRAIN_KEY"}
        return {"id": brain_id, "kind": "LEGACY_COMBINED", "targets": x.get("splitsInto") or mapped, "frozen": True}
    if brain_id in tb:
        return {"id": brain_id, "kind": "TARGET", "deployedAs": tb[brain_id]["deployedAs"], "authorizedInputs": tb[brain_id]["authorizedInputs"]}
    if mapped:
        return {"id": brain_id, "kind": "DEPLOYED", "targets": mapped}
    return {"id": brain_id, "kind": "UNREGISTERED", "finding": "UNREGISTERED_BRAIN"}


def execution_order() -> list:
    """Target dependency order: environmental specialists and Fish first, then the Biological Brain (fish-behavior), then Sector Intelligence (M08). Derived from authorizedInputs."""
    deps = {b["id"]: list(b["authorizedInputs"]) for b in target_brains()}
    order, seen = [], set()

    def visit(x):
        if x in seen:
            return
        seen.add(x)
        for d in sorted(deps.get(x, [])):
            visit(d)
        order.append(x)
    for x in sorted(deps, key=lambda i: (len(deps[i]), i)):
        visit(x)
    return order


def deployed_execution_order(deployed_ids) -> list:
    """The target order projected onto the deployed packages (biological-state appears once, at its LATER target position so it runs after the environmental Brains)."""
    pos = {}
    for i, t in enumerate(execution_order()):
        d = next(b["deployedAs"] for b in target_brains() if b["id"] == t)
        pos[d] = max(pos.get(d, -1), i)
    ids = [d for d in deployed_ids if d in pos]
    return sorted(ids, key=lambda d: (pos[d], d)) + sorted(d for d in deployed_ids if d not in pos)
