"""Fleet sampler vs the production per-lake cut-out interpolation on the REAL NBM CONUS grid, 621 real lake points.
Uses ONE archived pre-H2 cycle (2026-09-01 12Z, +6 h) purely for grid geometry and a realistic field; nothing from the live/H2 period.
  python research/fleet_sampling_validation.py OUT.json"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from datetime import datetime, timezone
from sector_wind.ingest import NBM_CORE, read_idx, _field
from sector_wind.grib import grid, cells_in_bbox
from sector_wind.interp import CutoutIndex, blend_wind
from sector_wind import fleet_sampling as FSM

init = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
assert init < datetime(2026, 10, 7, tzinfo=timezone.utc)
url = NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=6)
ent = read_idx(url); step = "6 hour fcst"
spd = _field(url, ent, "WIND", "", step); dr = _field(url, ent, "WDIR", "", step); gs = _field(url, ent, "GUST", "", step)
lat, lon = grid(spd.grid_key); nx = int(spd.grid_key.split(":")[1].split("x")[0])
speed = np.where(spd.missing, np.nan, spd.values); dirf = np.where(dr.missing, np.nan, dr.values); gust = np.where(gs.missing, np.nan, gs.values)
D = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/directory_lakes_2026-10-13.json")))["lakes"]
pts = {l["id"]: (l["lat"], l["lon"]) for l in D}
conus = {k: v for k, v in pts.items() if l_ok(k) } if False else None
inside = {}
for k, (la, lo) in pts.items():
    if 24 <= la <= 50 and -125 <= lo <= -66:
        inside[k] = (la, lo)
t0 = time.time(); idx = FSM.build_point_index(lat, lon, nx, inside); t_index = time.time() - t0
t0 = time.time(); out = FSM.sample_lead(idx, speed, dirf, gust, None); t_one = time.time() - t0
t0 = time.time()
for _ in range(36):
    FSM.sample_lead(idx, speed, dirf, gust, None)
t_36 = time.time() - t0
dv, dd, dg, nearest, bad = [], [], [], 0, []
for k, (la, lo) in inside.items():
    cells = cells_in_bbox(spd.grid_key, (lo - 0.35, la - 0.35, lo + 0.35, la + 0.35))
    ci = CutoutIndex(cells.tolist(), lat[cells].tolist(), lon[cells].tolist(), nx)
    wt = ci.weights(la, lo)
    dm = np.where(speed < 0.5, np.nan, dirf)      # the archive stores direction masked in calm cells (ingest_nbm_cycle)
    s, d = blend_wind(speed[cells].tolist(), dm[cells].tolist(), wt)
    nearest += wt.method != "bilinear"
    o = out[k]
    if s is None or o["speedMS"] is None:
        bad.append(k); continue
    dv.append(abs(o["speedMS"] - s))
    if d is not None and o["dirFromDeg"] is not None:
        dd.append(min(abs(o["dirFromDeg"] - d), 360 - abs(o["dirFromDeg"] - d)))
    elif (d is None) != (o["dirFromDeg"] is None):
        dd.append(999)
res = {"gridKey": spd.grid_key, "lakesTotal": len(pts), "lakesInsideConus": len(inside), "lakesOutsideConusBox": sorted(set(pts) - set(inside)),
       "maxSpeedDiffMS": round(float(max(dv)), 3), "maxDirDiffDeg": round(float(max(dd)), 1) if dd else None, "directionPresenceMismatch": int(sum(1 for x in dd if x == 999)),
       "nonBilinearPoints": int(nearest), "unresolved": bad, "indexBuildSeconds": round(t_index, 3), "oneLeadSeconds": round(t_one, 4), "thirtySixLeadsSeconds": round(t_36, 3),
       "deterministic": FSM.build_point_index(lat, lon, nx, inside) == idx, "indexBytesJson": len(json.dumps(idx)),
       "cycleObjectBytesApprox(621 lakes x 36 leads x 4 vars json)": len(json.dumps({k: {"s": [out[k]["speedMS"]] * 36, "d": [out[k]["dirFromDeg"]] * 36, "g": [out[k]["gustMS"]] * 36, "p": [out[k]["speedMS"]] * 36} for k in out})), "costModel": FSM.cost_model()}
json.dump(res, open(sys.argv[1], "w"), indent=1); print(json.dumps(res, indent=1))
