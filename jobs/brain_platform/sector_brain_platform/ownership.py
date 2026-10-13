"""Shared-field ownership (contract sections 5 and 6). A writer refuses a whole update on any violation."""
from __future__ import annotations

from .keys import BRAINS, slot_for, snapshot_field_for

SOURCE_OWNERS = {
    "tva-restapi": "lake-brain",
    "usace-cwms-pool": "lake-brain",
    "usgs-nwis-lake-elevation": "lake-brain",
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
ROLLUP_FLEET = {"lastUpdatedAt", "stale", "issueCount", "hasObservations"}
ROLLUP_SNAPSHOT = {"generatedAt", "snapshotVersion", "evaluationTime"}
LAKE_BRAIN_ONLY_FLEET = {"riverSystem", "lakeType"}
PLATFORM_ONLY = {"schemaVersion", "access", "validationOps", "engine", "control", "scores"}
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
        return brain_id == "biological-state"
    if root in ("brains", "validation"):
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
    if bad:
        raise OwnershipError(f"{brain_id} may not write: {bad[:5]}{' …' if len(bad) > 5 else ''}")
