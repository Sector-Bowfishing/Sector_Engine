"""Canonical lake identity for WindBrain. The ONLY lake registry is the Sector Engine directory (GET /lakes);
wind research keys (`guntersville`, …) are mapped to canonical IDs here and verified, never used as RTDB keys."""
from __future__ import annotations

import json
import urllib.request

from .contract import lake_key

ENGINE_URL = "https://sector-engine-e43utajroa-uc.a.run.app"

# Explicit, reviewed mapping. Name matching alone is wrong here: "Wilson Lake|KS" and "|HI" also exist.
WIND_LAKE_IDS = {
    "guntersville": "Guntersville|AL",
    "wheeler": "Wheeler|AL",
    "wilson": "Wilson|AL",
    "pickwick": "Pickwick Lake|TN",
}


class DirectoryError(RuntimeError):
    pass


def fetch_directory(url: str = ENGINE_URL, timeout: float = 20.0) -> list[dict]:
    """Canonical lake directory from Engine (public, ETag/max-age=3600). Read-only."""
    req = urllib.request.Request(f"{url}/lakes", headers={"User-Agent": "sector-wind-brain/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    lakes = body.get("lakes") or []
    if not lakes or body.get("count") != len(lakes):
        raise DirectoryError(f"directory malformed: count={body.get('count')} lakes={len(lakes)}")
    return lakes


def check_keys(directory: list[dict]) -> dict[str, str]:
    """lakeId -> lakeKey for the whole directory; refuses (raises) on any slug collision."""
    seen: dict[str, str] = {}
    for l in directory:
        k = lake_key(l["id"])
        if k in seen and seen[k] != l["id"]:
            raise DirectoryError(f"lake key collision: {seen[k]!r} and {l['id']!r} -> {k}")
        seen[k] = l["id"]
    return {v: k for k, v in seen.items()}


def verify_wind_lakes(directory: list[dict], cfg: dict) -> dict[str, dict]:
    """Each wind lake must exist in the directory AND the directory coordinate must lie inside the wind cut-out box."""
    by_id = {l["id"]: l for l in directory}
    out = {}
    for wl, lid in WIND_LAKE_IDS.items():
        d = by_id.get(lid)
        if d is None:
            raise DirectoryError(f"{wl} -> {lid} is not in the canonical directory")
        w, s, e, n = cfg["lakes"][wl]["bbox"]
        if not (w <= d["lon"] <= e and s <= d["lat"] <= n):
            raise DirectoryError(f"{lid} directory point ({d['lat']}, {d['lon']}) is outside the {wl} wind box")
        out[wl] = d
    return out


def national_profiled(manifest: dict | None, directory: list[dict]) -> dict[str, dict]:
    """Stage 3A national fetch tables (PASS / FLAGGED with a table in storage) -> canonical lakeId -> manifest entry."""
    if not manifest:
        return {}
    by_id = {l["id"] for l in directory}
    out = {}
    for m in manifest.get("lakes", []):
        lid = f"{m['name']}|{m['state']}"
        if m.get("status") in ("PASS", "FLAGGED") and lid in by_id and m.get("tableSha256"):
            out[lid] = m
    return out
