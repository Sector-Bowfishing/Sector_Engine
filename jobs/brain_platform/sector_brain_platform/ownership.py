"""Shared-field ownership (contract sections 5 and 6). A writer refuses a whole update on any violation."""
from __future__ import annotations

from .keys import BRAINS, slot_for, snapshot_field_for

SOURCE_OWNERS = {
    "tva-restapi": "lake-brain",
    "usace-cwms-pool": "lake-brain",
    "usgs-nwis-lake-elevation": "lake-brain",
    "usace-access2water": "lake-brain",            # fleet/candidate scopes (Lake Brain is the only acquirer)
    "usbr-rise": "lake-brain",
    "nws-nwps": "lake-brain",
    "usgs-nwis-00010": "water-temp",
    "usace-cwms-water-temp": "water-temp",
    "open-meteo-forecast": "water-temp",
    "sentinel-2-l2a": "water-clarity",
    "usgs-nwis-turbidity": "water-clarity",
    "noaa-mrms": "water-clarity",
    "noaa-nbm-v5": "wind",
    "noaa-rtma-ru": "wind",
    "iem-metar-wind": "wind"
}
# Fleet-row and snapshot fields that are Orchestrator rollups: nobody writes them in v1.
# DEPRECATED, not restored (Cortex 2.2 Firebase remediation 2026-10-21): the per-lake projection lives at /control/fleet/{k} (lastUpdatedAt = newest
# slot publication, rolledUpAt = projection time, staleSlots = derived freshness). The production values of /lakeFleet/{k}/lastUpdatedAt and
# /snapshots/{k}/latest/{generatedAt,snapshotVersion} were left by a pre-contract writer (frozen 2026-10-12/13), have no reader and are deletion
# candidates (gated). They stay unwritable so nothing can make them look current again.
ROLLUP_FLEET = {"lastUpdatedAt", "stale", "issueCount", "hasObservations"}
ROLLUP_SNAPSHOT = {"generatedAt", "snapshotVersion", "evaluationTime"}
LAKE_BRAIN_ONLY_FLEET = {"riverSystem", "lakeType"}
PLATFORM_ONLY = {"schemaVersion", "access", "validationOps", "engine", "control", "scores", "jobs"}   # jobs: the /jobs contract (jobs.py)
SCORER_CHILDREN = ("score", "scores")      # children of /brains/{id} that only the shared scorer may write (Cortex 3.1 SC-04); /brains/wind/scores is the one registered LEGACY Wind family
PLATFORM_WRITER = "brain-platform"       # the Engine's own publisher (scores, engine health); not a brain


class OwnershipError(PermissionError):
    pass


def source_owner(source_id: str) -> str | None:
    return SOURCE_OWNERS.get(source_id)


def path_allowed(brain_id: str, path: str) -> bool:
    """May `brain_id` write `path` (a root-relative path, no leading slash)?"""
    p = [s for s in path.strip("/").split("/") if s]
    if not p:
        return False
    root = p[0]
    if brain_id == PLATFORM_WRITER:
        if root == "access" or (root == "control" and len(p) >= 2 and p[1] == "executionControlV1"):
            return False                       # @external-admin families (Cortex 3.1 registry): access lists and the owner's execution-control document are never a platform write
        if root in PLATFORM_ONLY or (root == "health" and len(p) >= 2 and p[1] in ("engine", "rtdb")):
            return True
        if root == "activity":
            return len(p) == 2 and f"-{PLATFORM_WRITER}-" in p[1]
        return False
    if brain_id not in BRAINS:
        return False
    slot = slot_for(brain_id)
    if root in PLATFORM_ONLY or (root == "health" and len(p) > 1 and p[1] in ("engine", "rtdb")):
        return False
    if root == "lakeFleet":
        if len(p) < 3:
            return False                       # never the whole row
        field = p[2]
        if field == "lakeId":
            return True
        if field in ROLLUP_FLEET:
            return False
        if field in LAKE_BRAIN_ONLY_FLEET:
            return brain_id == "lake-brain"
        if field in ("readiness", "modelVersions", "slots"):
            return len(p) >= 4 and p[3] == slot
        return False
    if root == "lakes":
        if len(p) < 3:
            return False
        section = p[2]
        if section == "brain" or section == "speciesPresence":
            return brain_id == "lake-brain"
        if section in ("states", "profiles"):
            return len(p) >= 4 and p[3] == slot
        if section == "validation":
            return len(p) >= 4 and p[3] == brain_id
        return False
    if root == "snapshots":
        if len(p) < 4 or p[2] != "latest":
            return False
        field = p[3]
        if field == "lakeId":
            return True
        if field in ROLLUP_SNAPSHOT:
            return False
        if field == "brainVersions":
            return len(p) >= 5 and p[4] == brain_id
        return field == snapshot_field_for(brain_id)
    if root == "species":
        return brain_id == "biological-state" and len(p) >= 2          # /species/{id}/...: never the whole /species root (a whole-node write erases every other record)
    if root in ("brains", "validation"):
        if root == "brains" and len(p) >= 3 and p[2] in SCORER_CHILDREN and not (brain_id == "wind" and p[2] == "scores"):
            return False                                               # FD-15 / SC-04: the scorer's mirror fields are never a Brain write (legacy /brains/wind/scores is a registered Wind family)
        return len(p) >= 2 and p[1] == brain_id
    if root == "health":
        if len(p) < 3:
            return False
        if p[1] == "brains":
            return p[2] == brain_id
        if p[1] == "jobs":
            return True                        # a brain's own job id; jobs are not shared
        if p[1] == "sources":
            owner = source_owner(p[2])
            return owner is None or owner == brain_id
        return False
    if root == "sources":
        if len(p) < 2:
            return False
        owner = source_owner(p[1])
        if len(p) >= 4 and p[2] == "brains" and p[3] == brain_id:
            return True                        # append-only membership
        return owner is None or owner == brain_id
    if root == "activity":
        return len(p) == 2 and f"-{brain_id}-" in p[1]
    return False


def assert_owned(updates: dict, brain_id: str) -> None:
    bad = [k for k in updates if not path_allowed(brain_id, k)]
    for k, v in updates.items():                                       # a whole-node write of /brains/{id} replaces every child: it must not carry (and so erase) the scorer's fields
        seg = [x for x in k.strip("/").split("/") if x]
        if len(seg) == 2 and seg[0] == "brains" and isinstance(v, dict) and any(c in v for c in SCORER_CHILDREN if not (brain_id == "wind" and c == "scores")):
            bad.append(k)
    if bad:
        raise OwnershipError(f"{brain_id} may not write: {bad[:5]}{' …' if len(bad) > 5 else ''}")
