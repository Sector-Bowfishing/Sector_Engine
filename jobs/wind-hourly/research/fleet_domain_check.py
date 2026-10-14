"""AK / HI / PR NBM domain check for the fleet sampler: does the NBM regional product decode, cover the lake points, and does the fleet
sampler reproduce a per-lake cut-out interpolation on that grid? Uses ONE pre-H2 archived cycle (2026-09-01 12Z +6 h) only.
  python research/fleet_domain_check.py OUT.json"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from datetime import datetime, timezone
from sector_wind import ingest
from sector_wind.grib import grid, cells_in_bbox
from sector_wind.interp import CutoutIndex, blend_wind
from sector_wind import fleet_sampling as FSM
D = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/directory_lakes_2026-10-13.json")))["lakes"]
init = datetime(2026, 9, 1, 12, tzinfo=timezone.utc); assert init < datetime(2026, 10, 7, tzinfo=timezone.utc)
res = {}
for dom, states in (("ak", {"AK"}), ("hi", {"HI"}), ("pr", {"PR", "VI"})):
    pts = {l["id"]: (l["lat"], l["lon"]) for l in D if l["state"] in states}
    if not pts:
        res[dom] = {"lakes": 0, "note": "no directory lakes"}; continue
    url = f"https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.{init:%Y%m%d}/{init.hour:02d}/core/blend.t{init.hour:02d}z.core.f006.{dom}.grib2"
    try:
        ent = ingest.read_idx(url)
        lv = {e.level for e in ent if e.var == "WIND"}
        ingest.LEVEL = "10 m above ground"
        spd = ingest._field(url, ent, "WIND", "", "6 hour fcst"); dr = ingest._field(url, ent, "WDIR", "", "6 hour fcst")
    except Exception as e:
        res[dom] = {"lakes": len(pts), "status": "NOT DECODABLE", "error": repr(e)[:200], "windLevelsListed": sorted(lv) if 'lv' in dir() else None}; continue
    lat, lon = grid(spd.grid_key); nx = int(spd.grid_key.split(":")[1].split("x")[0])
    speed = np.where(spd.missing, np.nan, spd.values); dirf = np.where(dr.missing, np.nan, dr.values)
    # coverage: nearest cell within 2 grid spacings (spacing estimated from the median neighbour distance)
    cosl = np.cos(np.radians(np.mean(lat)))
    sp_km = float(np.median(np.hypot((lat[1:nx] - lat[:nx - 1]) * 111.0, (lon[1:nx] - lon[:nx - 1]) * 111.0 * cosl)))
    inside, out = {}, []
    for k, (la, lo) in pts.items():
        d = np.hypot((lat - la) * 111.0, (lon - lo) * 111.0 * np.cos(np.radians(la)))
        (inside if d.min() <= 2 * max(sp_km, 2.5) else {}).update({k: (la, lo)}) if d.min() <= 2 * max(sp_km, 2.5) else out.append((k, round(float(d.min()), 1)))
    idx = FSM.build_point_index(lat, lon, nx, inside)
    o = FSM.sample_lead(idx, speed, dirf, None, None)
    dv, dd, bad, nn = [], [], 0, 0
    for k, (la, lo) in inside.items():
        cells = cells_in_bbox(spd.grid_key, (lo - 0.6, la - 0.4, lo + 0.6, la + 0.4))
        ci = CutoutIndex(cells.tolist(), lat[cells].tolist(), lon[cells].tolist(), nx); wt = ci.weights(la, lo)
        nn += wt.method != "bilinear"
        dm = np.where(speed < 0.5, np.nan, dirf)
        s, d = blend_wind(speed[cells].tolist(), dm[cells].tolist(), wt)
        if s is None or o[k]["speedMS"] is None: bad += 1; continue
        dv.append(abs(o[k]["speedMS"] - s))
        if (d is None) != (o[k]["dirFromDeg"] is None): dd.append(999)
        elif d is not None: dd.append(min(abs(o[k]["dirFromDeg"] - d), 360 - abs(o[k]["dirFromDeg"] - d)))
    res[dom] = {"lakes": len(pts), "gridKey": spd.grid_key, "gridSpacingKmApprox": round(sp_km, 2), "decoded": True, "windLevelsListed": sorted(lv),
                "lakesCovered": len(inside), "lakesOutsideCoverage": out, "nonBilinear": int(nn), "unresolved": bad,
                "maxSpeedDiffMS": round(max(dv), 4) if dv else None, "maxDirDiffDeg": round(max(dd), 1) if dd else None,
                "meanSpeedMS_atLakes": round(float(np.mean([o[k]["speedMS"] for k in inside if o[k]["speedMS"] is not None])), 2) if inside else None}
json.dump(res, open(sys.argv[1], "w"), indent=1); print(json.dumps(res, indent=1))
