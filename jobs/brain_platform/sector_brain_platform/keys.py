"""Lake keys and key legality (contract sections 1 and 2)."""
from __future__ import annotations

import re

_SLUG = re.compile(r"[^A-Za-z0-9]+")
_ILLEGAL = re.compile(r"[.$#\[\]/\x00-\x1f\x7f]")

#: brainId -> (slot, snapshot field, display name). The contract's section 2 table.
BRAINS = {
    "lake-brain": ("lake", "lakeState", "Lake Brain"),
    "water-temp": ("waterTemp", "waterTemperature", "Water Temperature"),
    "water-clarity": ("waterClarity", "waterClarity", "Water Clarity"),
    "wind": ("wind", "wind", "Wind"),
    "biological-state": ("biology", "biologicalState", "Biological Brain"),
    "sector-intelligence": ("intelligence", "sectorIntelligence", "Sector Intelligence"),
    "depth": ("depth", "depth", "Depth"),
    "vegetation": ("vegetation", "vegetation", "Vegetation"),
}


def slot_for(brain_id: str) -> str:
    return BRAINS[brain_id][0]


def snapshot_field_for(brain_id: str) -> str:
    return BRAINS[brain_id][1]


def lake_key(lake_id: str) -> str:
    """Brain RTDB key for a canonical lake id: every run of non-alphanumerics becomes one '_'."""
    return _SLUG.sub("_", lake_id)


def key_collisions(lake_ids) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for lid in lake_ids:
        seen.setdefault(lake_key(lid), []).append(lid)
    return {k: v for k, v in seen.items() if len(set(v)) > 1}


def lake_keys(lake_ids) -> dict[str, str]:
    """lakeId -> key for a whole directory; raises on a slug collision (the run must not write)."""
    bad = key_collisions(lake_ids)
    if bad:
        k, ids = next(iter(bad.items()))
        raise ValueError(f"lake key collision: {ids[0]!r} and {ids[1]!r} both map to {k!r}")
    return {lid: lake_key(lid) for lid in lake_ids}


class IllegalKey(ValueError):
    pass


def check_keys(payload, path: str = "") -> None:
    """Walk a payload and raise IllegalKey on any RTDB-illegal node key (`. $ # [ ] /`, control chars, empty)."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if not isinstance(k, str) or not k or _ILLEGAL.search(k):
                raise IllegalKey(f"illegal RTDB key {k!r} at {path or '/'}")
            check_keys(v, f"{path}/{k}")
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            check_keys(v, f"{path}[{i}]")


def check_update(updates: dict) -> None:
    """A multi-path update: each top-level key is a root-relative path whose segments are node keys."""
    for k, v in updates.items():
        segments = [s for s in k.split("/") if s != ""]
        if not segments:
            raise IllegalKey(f"empty path {k!r}")
        for seg in segments:
            if _ILLEGAL.search(seg):
                raise IllegalKey(f"illegal RTDB key {seg!r} in path {k!r}")
        check_keys(v, k)
