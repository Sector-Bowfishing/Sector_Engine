"""NBM point forecasts beyond the four grid lakes (Sector_Ops #45, draft).

W1 (Sector_Ops #30) graded NOAA NBM night speed at the nearest ASOS/AWOS station within 10 km of 150 random catalog lakes and found
it SUPPORTED (142 pass). This module archives NBM speed and gust at exactly those stations for the 142 lakes that passed
(`points.json`). It is a point forecast where truth exists: not lake-surface wind, no direction, no exposure, no percentiles.

Archive layout (same store as ingest.py, separate keys):
  grids/nbm-points.json                        nearest NBM cell per point, keyed by the grid
  nbm-points/<YYYYMMDDHH>.json.gz              one cycle: every point, per-lead speed and gust

Off unless WIND_NBM_POINTS=1. Nothing here publishes or is read by production. `points.json` is not yet part of the Wind
knowledge release (Cortex BR-11): enabling it needs a release that includes it and the owner's approval.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta

import numpy as np

from . import DECODER_VERSION
from .grib import DecodeError, FetchError, cells_in_bbox, grid, read_idx, row_scramble_ratio
from .ingest import DEFAULT_LEADS, NBM_CORE, RUNTIME_ROOT, _field, _now, _round, nbm_version
from .sample import iso

POINTS_SCHEMA = "sector-wind-points-v1"
ENV_FLAG = "WIND_NBM_POINTS"
# A point must sit within half an NBM cell diagonal (2.5 km grid) of its cell centre, or the grid does not cover it.
MAX_CELL_KM = 2.0


def enabled(env=os.environ) -> bool:
    return env.get(ENV_FLAG) == "1"


def load_points(path: str | None = None) -> dict:
    return json.load(open(path or os.path.join(RUNTIME_ROOT, "points.json")))


def _km(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 110.54, (lon2 - lon1) * 111.32 * k)


def nearest_cells(grid_key: str, points: dict) -> dict[str, int | None]:
    """Nearest grid cell per point; None when the nearest cell centre is farther than MAX_CELL_KM (outside the grid)."""
    lat, lon = grid(grid_key)
    out = {}
    for lake, p in points.items():
        near = cells_in_bbox(grid_key, (p["lon"] - 0.05, p["lat"] - 0.05, p["lon"] + 0.05, p["lat"] + 0.05))
        if near.size == 0:
            out[lake] = None
            continue
        d = [(_km(p["lat"], p["lon"], float(lat[i]), float(lon[i])), int(i)) for i in near]
        km, i = min(d)
        out[lake] = i if km <= MAX_CELL_KM else None
    return out


def _ensure_cells(store, grid_key: str, points: dict) -> dict[str, int | None]:
    key = "grids/nbm-points.json"
    m = store.get_json(key)
    if m and m.get("gridKey") == grid_key and set(m.get("cells", {})) == set(points):
        return m["cells"]
    cells = nearest_cells(grid_key, points)
    store.put_json(key, {"schema": POINTS_SCHEMA, "gridKey": grid_key, "maxCellKm": MAX_CELL_KM, "cells": cells})
    return cells


def ingest_nbm_points(store, pcfg: dict, init: datetime, leads=DEFAULT_LEADS) -> dict:
    """Pull one NBM cycle's speed and gust at every point and write one archive object. Returns a summary."""
    retrieved = _now()
    points = pcfg["points"]
    per_point: dict[str, list] = {k: [] for k in points}
    missing, cells = [], None
    for f in leads:
        url = NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=f)
        try:
            ent = read_idx(url)
            step = f"{f} hour fcst"
            spd = _field(url, ent, "WIND", "", step); gs = _field(url, ent, "GUST", "", step)
        except (FetchError, DecodeError) as e:
            missing.append({"lead": f, "error": str(e)[:200]}); continue
        cells = cells if cells is not None else _ensure_cells(store, spd.grid_key, points)
        idx = np.asarray([c for c in cells.values() if c is not None], dtype=int)
        nx = int(spd.grid_key.split(":")[1].split("x")[0])
        if idx.size and not (row_scramble_ratio(spd.values, idx, nx) < 3.0):   # decoder self-check, as ingest.py
            missing.append({"lead": f, "error": "decoder self-check failed"}); continue
        valid = iso(init + timedelta(hours=f))
        for lake, c in cells.items():
            if c is None:
                continue
            s = np.nan if spd.missing[c] else spd.values[c]
            g = np.nan if gs.missing[c] else gs.values[c]
            per_point[lake].append({"leadHours": f, "validTime": valid, "speedMS": _round([s], 2)[0], "gustMS": _round([g], 2)[0]})
    outside = sorted(k for k, c in (cells or {}).items() if c is None)
    status = "complete" if cells is not None and not missing else ("partial" if cells is not None else "failed")
    obj = {"schema": POINTS_SCHEMA, "kind": "forecast", "model": "NBM", "modelVersion": nbm_version(init),
           "scope": "point forecast at the station W1 graded; not lake-surface wind; speed and gust only",
           "pointsVersion": pcfg.get("version"), "initTime": iso(init), "retrievedAt": iso(retrieved),
           "decoderVersion": DECODER_VERSION, "status": status, "missing": missing, "outsideGrid": outside,
           "points": {k: v for k, v in per_point.items() if v}}
    if obj["points"]:
        store.put_json(f"nbm-points/{init:%Y%m%d%H}.json.gz", obj)
    store.append_ledger({"product": "NBM-POINTS", "cycle": iso(init), "status": status, "points": len(obj["points"]),
                         "outsideGrid": len(outside), "missing": len(missing)})
    return {"status": status, "points": len(obj["points"]), "outsideGrid": len(outside)}
