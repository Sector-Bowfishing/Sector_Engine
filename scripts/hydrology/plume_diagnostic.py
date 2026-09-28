"""Does the Sentinel-2 read miss muddy water? (Clarity Fusion Stage 2 check.)

For a few passes, per arm, over lake cells at least 2 frame cells (~60 m)
inside the lake outline (so real shoreline is excluded):
  sclWaterPct   share of 10 m pixels Sen2Cor called water (only these are read)
  sclLandPct    share it called dark / vegetation / bare / unclassified (2,4,5,7),
                inside the lake -- the read treats these as bank
  rawFNUWater   Dogliotti FNU of the SCL-water pixels, no other gate
  rawFNULand    the same formula on the SCL "land" pixels inside the lake
  readFNU       the production read's median (the pass_history number)

usage: geo/bin/python plume_diagnostic.py <arm_cells.json> <out.json> <date:platform> ...
"""
import os, sys, json, zlib, base64, datetime as dt
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import derive_water_surface as dws
from shapely.geometry import shape
from shapely.ops import unary_union

WATERBODY = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/.fishintel-cache/guntersville/waterbody.geojson")
ARMS = ["town-creek-marshall", "south-sauty-creek", "browns-creek", "short-creek", "mud-creek", "north-sauty-creek", "mainstem"]

cells = json.load(open(sys.argv[1]))
arm = np.frombuffer(zlib.decompress(base64.b64decode(cells["armGrid"])), np.uint8).reshape(cells["height"], cells["width"])
names = [n or "mainstem" for n in cells["arms"]]
lake_g = unary_union([shape(f["geometry"]) for f in json.load(open(WATERBODY))["features"]])
dws.UTM = "EPSG:32616"
frame = dws.Frame(lake_g, cell=dws.CLARITY_CELL)
masks = dws.lake_masks(lake_g, frame)
inner = ndimage.binary_erosion(masks["lake"], iterations=2)
out = json.load(open(sys.argv[2])) if os.path.exists(sys.argv[2]) else {}
for spec in sys.argv[3:]:
    date, platform = spec.split(":")
    if spec in out:
        continue
    got = dws.passes(dws.ES_SEARCH, dws.S2_COLLECTION, list(lake_g.bounds), dt.datetime.fromisoformat(date + "T23:59:59"), max_cloud=40)
    items = next((it for (d, pl), it in got if d == date and pl == platform), None)
    if items is None:
        out[spec] = "not found"; continue
    H, W = frame.height, frame.width
    acc = {k: (np.zeros((H, W)), np.zeros((H, W))) for k in ("water", "land", "cloud", "fW", "fL")}
    for it in items:
        t = dws._read_s2_native(it, frame.bounds)
        h, w = t["red"].shape
        up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
        scl = up(t["scl"])
        rr = t["red"].astype("float32") * dws.S2_SCALE + dws.S2_OFFSET
        rr[(t["red"] == 0) | (t["red"] == 65535)] = np.nan
        rr = np.clip(rr, 0, None)
        raw = np.where(rr >= dws.TURB_SATURATED, dws.TURB_SATURATED_FNU,
                       dws.TURB_A * rr / np.maximum(1e-6, 1 - rr / dws.TURB_C)).astype("float32")
        valid = scl > 0
        isw = scl == dws.SCL_WATER
        isl = np.isin(scl, dws.S2_SCL_BANK)
        isc = np.isin(scl, [c for c in dws.SCL_CLOUDY if c != 0])
        for key, m in (("water", isw), ("land", isl), ("cloud", isc)):
            g = dws.to_grid(np.where(valid, m.astype("float32"), np.nan), t["tr10"], t["crs"], frame)
            ok = ~np.isnan(g); acc[key][0][ok] += g[ok]; acc[key][1][ok] += 1
        for key, m in (("fW", isw), ("fL", isl)):
            g = dws.to_grid(np.where(m & ~np.isnan(rr), np.log10(np.maximum(raw, 0.05)), np.nan).astype("float32"),
                            t["tr10"], t["crs"], frame)
            ok = ~np.isnan(g); acc[key][0][ok] += g[ok]; acc[key][1][ok] += 1
    f = {k: np.where(d > 0, n / np.maximum(d, 1), np.nan) for k, (n, d) in acc.items()}
    res = {}
    for k, name in enumerate(names):
        if name not in ARMS:
            continue
        m = inner & (arm == k)
        if not m.any():
            continue
        def med(x):
            v = x[m & ~np.isnan(x)]
            return None if v.size == 0 else round(float(10 ** np.median(v)), 2)
        def p90(x):
            v = x[m & ~np.isnan(x)]
            return None if v.size == 0 else round(float(10 ** np.percentile(v, 90)), 2)
        res[name] = {"cells": int(m.sum()),
                     "sclWaterPct": round(100 * float(np.nanmean(f["water"][m])), 1),
                     "sclLandPct": round(100 * float(np.nanmean(f["land"][m])), 1),
                     "sclCloudPct": round(100 * float(np.nanmean(f["cloud"][m])), 1),
                     "rawFNUWater": med(f["fW"]), "rawFNUWaterP90": p90(f["fW"]),
                     "rawFNULand": med(f["fL"]), "rawFNULandP90": p90(f["fL"]),
                     "landCellsWithRaw": int((m & ~np.isnan(f["fL"])).sum())}
    out[spec] = res
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    print(spec, json.dumps(res), flush=True)
