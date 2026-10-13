"""Fleet NBM point sampling (foundation; NOT wired into the hourly job).

Today `ingest_nbm_cycle` already downloads each CONUS field once per cycle, then writes one cut-out object PER LAKE. That
scales as lakes x cycles objects (621 x 24 = ~15k small GCS writes/day). The fleet design keeps the single CONUS decode and
replaces the per-lake cut-outs with ONE point-sampled object per cycle:

    nbm_fleet/<YYYYMMDDHH>.json.gz = {schema, init, retrievedAt, status, leads[], lakes{lakeId: {speedMS[], dirFromDeg[], gustMS[], speedP90[]}}}

Bilinear weights (4 grid cells per lake) are computed once per grid and stored (`fleet/grids/nbm.json`), so a cycle costs one
GRIB decode (already paid) plus a numpy gather. No per-lake jobs, no extra network calls, same interpolation and same
direction-from-blended-u/v rule as the archive (`interp.blend`/`blend_wind`), so values are identical to a per-lake cut-out.
The state builder would read the fleet object instead of `nbm/<lake>/...`; nothing changes for the 4 live lakes until that
switch is approved. Pure numpy; unit-tested on synthetic grids."""
from __future__ import annotations

import math

import numpy as np

from .interp import CutoutIndex

SCHEMA = "sector-wind-nbm-fleet-v1"
CALM_MS = 0.5  # same calm rule as ingest (direction undefined below 0.5 m/s per cell)
PATCH = 2     # cells either side of the nearest cell used to build the local bilinear basis


MAX_NEAREST_KM = 6.0   # a lake farther than this from every grid cell is OUTSIDE the domain (about 2.4 cells of a 2.5 km grid): no value, never the nearest far cell


def build_point_index(grid_lat: np.ndarray, grid_lon: np.ndarray, nx: int, points: dict[str, tuple[float, float]], max_nearest_km: float = MAX_NEAREST_KM) -> dict:
    """Per lake: the four full-grid cell indices and bilinear weights. points: {lakeId: (lat, lon)}. Deterministic.
    A point farther than `max_nearest_km` from every cell is marked method='outside' with no cells (sampled as unknown)."""
    ny = len(grid_lat) // nx
    coslat = math.cos(math.radians(float(np.mean([p[0] for p in points.values()])))) if points else 1.0
    out = {}
    for lid in sorted(points):
        lat, lon = points[lid]
        d2 = (grid_lon - lon) ** 2 * math.cos(math.radians(lat)) ** 2 + (grid_lat - lat) ** 2
        n0 = int(np.argmin(d2)); r0, c0 = divmod(n0, nx)
        if math.sqrt(float(d2[n0])) * 111.0 > max_nearest_km:
            out[lid] = {"cells": [], "w": [], "method": "outside"}
            continue
        rows = range(max(0, r0 - PATCH), min(ny, r0 + PATCH + 1)); cols = range(max(0, c0 - PATCH), min(nx, c0 + PATCH + 1))
        cells = np.array([r * nx + c for r in rows for c in cols])
        ci = CutoutIndex(cells.tolist(), grid_lat[cells].tolist(), grid_lon[cells].tolist(), nx)
        wt = ci.weights(lat, lon)
        out[lid] = {"cells": [int(cells[i]) for i in wt.idx], "w": [round(float(w), 6) for w in wt.w], "method": wt.method}
    return {"schema": SCHEMA + "-index", "nx": nx, "lakes": out}


def _blend(values: np.ndarray, cells: list[int], w: list[float]) -> float | None:
    v = values[cells]
    ok = ~np.isnan(v)
    if ok.all():
        return float(np.dot(v, w))
    if not ok.any():
        return None
    i = int(np.argmax(np.where(ok, w, -1)))
    return float(v[i])


def sample_lead(index: dict, speed: np.ndarray, dir_from: np.ndarray, gust: np.ndarray | None = None, p90: np.ndarray | None = None) -> dict:
    """One lead hour -> {lakeId: {speedMS, dirFromDeg, gustMS, speedP90}} (None where unknown). Calm (<0.5 m/s) has no direction."""
    out = {}
    for lid, e in index["lakes"].items():
        c, w = e["cells"], e["w"]
        if not c:                                                  # outside the domain: unknown, not zero
            out[lid] = {"speedMS": None, "dirFromDeg": None, "gustMS": None, "speedP90": None}
            continue
        s = _blend(speed, c, w)
        d = None
        if s is not None:
            us = vs = ws = 0.0
            for ci, wi in zip(c, w):
                sp, dr = speed[ci], dir_from[ci]
                if np.isnan(sp) or np.isnan(dr) or sp < CALM_MS:      # ingest masks direction in calm cells (< 0.5 m/s) before archiving
                    continue
                r = math.radians(dr)
                us += wi * -sp * math.sin(r); vs += wi * -sp * math.cos(r); ws += wi
            if ws and math.hypot(us, vs) >= 1e-9:
                d = (math.degrees(math.atan2(-us, -vs)) + 360.0) % 360.0
        out[lid] = {"speedMS": None if s is None else round(s, 2), "dirFromDeg": None if d is None else round(d),
                    "gustMS": None if gust is None else _r(_blend(gust, c, w)), "speedP90": None if p90 is None else _r(_blend(p90, c, w))}
    return out


def _r(x):
    return None if x is None else round(x, 2)


def cost_model(n_lakes: int = 621, leads: int = 36, cycles_per_day: int = 24, bytes_per_value: int = 3) -> dict:
    """Back-of-envelope: why one point-sampled object per cycle replaces per-lake cut-outs."""
    per_lake_objects = n_lakes * cycles_per_day
    fleet_bytes = int(n_lakes * leads * 4 * bytes_per_value * 0.5)       # 4 vars, ~gz halves it
    return {"perLakeCutoutObjectsPerDay": per_lake_objects, "fleetObjectsPerDay": cycles_per_day,
            "fleetObjectBytesApprox": fleet_bytes, "fleetGBPerMonthApprox": round(fleet_bytes * cycles_per_day * 30 / 1e9, 2),
            "extraGribReads": 0, "extraNetworkCalls": 0}


def sample_cycle(index: dict, init_iso: str, retrieved_iso: str, fields_by_lead: dict[int, dict | None]) -> dict:
    """One archive object for the whole fleet. fields_by_lead: {lead: {'speed','dir','gust'?,'p90'?} | None}. A lead whose fields are missing or
    malformed (partial GRIB) is listed in `missingLeads`, its values are null, and the cycle is `partial` - never silently filled."""
    leads = sorted(fields_by_lead)
    lakes = {lid: {"speedMS": [], "dirFromDeg": [], "gustMS": [], "speedP90": []} for lid in index["lakes"]}
    missing = []
    n = max((int(max(e["cells"])) for e in index["lakes"].values() if e["cells"]), default=-1) + 1
    for lead in leads:
        f = fields_by_lead[lead]
        ok = isinstance(f, dict) and all(isinstance(f.get(k), np.ndarray) and f[k].shape[0] >= n for k in ("speed", "dir"))
        row = sample_lead(index, f["speed"], f["dir"], f.get("gust"), f.get("p90")) if ok else None
        if row is None:
            missing.append(lead)
        for lid in lakes:
            v = row[lid] if row else {"speedMS": None, "dirFromDeg": None, "gustMS": None, "speedP90": None}
            for k in ("speedMS", "dirFromDeg", "gustMS", "speedP90"):
                lakes[lid][k].append(v[k])
    return {"schema": SCHEMA, "init": init_iso, "retrievedAt": retrieved_iso, "leads": leads, "status": "complete" if not missing else "partial",
            "missingLeads": missing, "outsideDomain": sorted(l for l, e in index["lakes"].items() if e["method"] == "outside"), "lakes": lakes}
