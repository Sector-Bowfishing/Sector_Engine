"""Stage 4 item 16: the winter-aware relaxed shore rule as a CHALLENGER dataset.

Production gates stay the champion; nothing here reaches a published product.
For each clear winter discovery pass (Nov-Mar, >= 50% of open water read), per
10 m Sentinel-2 pixel, the production gate stack and ONE relaxed variant
(bank standoff 0 m, structure standoff 30 m, frame-cell minimum 10% of pixels;
cloud, haze and reflectance limits unchanged) — the gate stack is the one in
head_gate_diagnostic.py, copied so that file's recorded 3B output stays as it
was. Aggregated to the Water Clarity frame:

  challenger cell   read by the relaxed rule, not by production
  adjacency bias    its log10 FNU minus the median of production-read cells
                    within 300 m on the same pass (>= 10 of them)
  baseline          the same statistic for production-read cells themselves
                    (each against its OTHER production neighbours): ordinary
                    spatial variation, which a clean reading shows too

A relaxed cell is contaminated by the shore's glow if its bias exceeds the
baseline, and more so nearer the shore. Written per pass (npz: the challenger
cells' encoded FNU, their bias, and distance to the lake's edge) and pooled
(json), with no in-situ or Sector-report comparison possible yet: Guntersville
has no turbidity sensor within the engine's 10 mi, and reports have just begun.

usage: geo/bin/python relaxed_challenger.py <out dir> <date:platform> ...
"""
import os, sys, json, math, datetime as dt
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import derive_water_surface as dws
from shapely.geometry import shape
from shapely.ops import unary_union

WATERBODY = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/.fishintel-cache/guntersville/waterbody.geojson")
POS = os.path.join(HERE, "..", "..", "docs", "data", "hydrology", "guntersville", "stage3a", "arm_positions.npz")
LO, HI = math.log10(0.5), math.log10(200.0)
WINDOW_M = 300.0
out_dir, specs = sys.argv[1], sys.argv[2:]
os.makedirs(out_dir, exist_ok=True)
P = np.load(POS)
armgrid = P["arm"]
lake_g = unary_union([shape(f["geometry"]) for f in json.load(open(WATERBODY))["features"]])
dws.UTM = "EPSG:32616"
frame = dws.Frame(lake_g, cell=dws.CLARITY_CELL)
masks = dws.lake_masks(lake_g, frame)
lake = masks["lake"]
G = frame.cell_ground_m()
to_edge_m = ndimage.distance_transform_edt(lake) * G


def gates(t, relaxed):
    """head_gate_diagnostic.gates, verbatim in effect: the production stack, or the one relaxed variant."""
    h, w = t["red"].shape
    up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
    def rho(dn):
        r = dn.astype("float32") * dws.S2_SCALE + dws.S2_OFFSET
        r[(dn == 0) | (dn == 65535)] = np.nan
        return r
    scl = up(t["scl"]); r_red = rho(t["red"]); r_nir, r_sw = up(rho(t["nir08"])), up(rho(t["swir16"]))
    water = scl == dws.SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > dws.BRIGHT_SWIR
        veg = ndvi >= dws.GRASS_NDVI_MIN
        haze_px = water & (r_sw > dws.HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < dws.S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, dws.S2_SCL_BANK)
    px = dws.S2_NATIVE_PX
    to_bank, to_structure = dws._edge_dist_px(bank), dws._edge_dist_px(structure)
    cloudy_classes = [c for c in dws.SCL_CLOUDY if c != 0]
    to_cloud = dws._edge_dist_px(np.isin(scl, cloudy_classes))
    clear = to_cloud >= dws.S2_CLOUD_STANDOFF_M / px
    cl20 = np.isin(t["scl"], cloudy_classes)
    lab, n = ndimage.label(cl20)
    real20 = np.isin(lab, np.nonzero(ndimage.sum(cl20, lab, index=np.arange(1, n + 1)) >= dws.S2_REAL_CLOUD_MIN_PX20)[0] + 1) if n else cl20
    to_real = dws._edge_dist_px(up(real20))
    near_cloud = to_real < dws.S2_CLOUD_EDGE_M / px
    under_cloud = to_real < dws.S2_REAL_CLOUD_STANDOFF_M / px
    offshore = (to_bank >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px) & (to_structure >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px)
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > dws.S2_CLOUD_EDGE_SWIR)
        haze_edge = (dws._edge_dist_px(haze_px) < dws.HAZE_EDGE_M / px) & offshore & (r_sw > dws.HAZE_EDGE_SWIR)
    beside_bright = dws._edge_dist_px(haze) < dws.S2_HAZE_STANDOFF_M / px
    unhazed = ~beside_bright & ~cloud_edge & ~haze_edge
    bank_m = 0.0 if relaxed else dws.S2_BANK_STANDOFF_M
    struct_m = 30.0 if relaxed else dws.S2_STRUCTURE_STANDOFF_M
    ok = water & (to_bank >= bank_m / px) & (to_structure >= struct_m / px) & clear & ~under_cloud & unhazed
    with np.errstate(invalid="ignore"):
        ok &= (r_sw <= dws.SWIR_MAX) & (fai <= dws.FAI_MAX) & (ndvi <= dws.NDVI_MAX) & (r_red > 0)
    rr = np.clip(np.nan_to_num(r_red, nan=0), 0, None)
    fnu = np.where(rr >= dws.TURB_SATURATED, dws.TURB_SATURATED_FNU, dws.TURB_A * rr / np.maximum(1e-6, 1 - rr / dws.TURB_C)).astype("float32")
    return ok, fnu


def neighbour_median_bias(val, have, window_cells, exclude_self):
    """val - the median of `have` cells in a square window (a mean of logs as a
    robust-enough stand-in for the median at this scale), with >= 10 of them."""
    s = ndimage.uniform_filter(np.where(have, val, 0.0), size=window_cells, mode="constant") * window_cells ** 2
    n = ndimage.uniform_filter(have.astype(float), size=window_cells, mode="constant") * window_cells ** 2
    if exclude_self:
        s = s - np.where(have, val, 0.0); n = n - have
    with np.errstate(invalid="ignore", divide="ignore"):
        ref = np.where(n >= 10, s / np.maximum(n, 1), np.nan)
    return val - ref


pooled = json.load(open(os.path.join(out_dir, "pooled.json"))) if os.path.exists(os.path.join(out_dir, "pooled.json")) else {}
bbox = list(lake_g.bounds)
win = int(round(2 * WINDOW_M / G)) | 1
for spec in specs:
    if spec in pooled:
        continue
    date, platform = spec.split(":")
    got = dws.passes(dws.ES_SEARCH, dws.S2_COLLECTION, bbox, dt.datetime.fromisoformat(date + "T23:59:59"), max_cloud=40)
    items = next((it for (d, pl), it in got if d == date and pl == platform), None)
    if items is None:
        pooled[spec] = "not found"; continue
    H, W = frame.height, frame.width
    acc = {k: np.zeros((H, W)) for k in ("n", "okP", "okR")}
    fs = {k: np.zeros((H, W)) for k in ("P", "R", "Pn", "Rn")}
    for it in items:
        t = dws._read_s2_native(it, frame.bounds)
        if t["red"].size == 0:
            continue
        okp, fnu = gates(t, False)
        okr, _ = gates(t, True)
        valid = np.isfinite(fnu)
        grid = lambda a: dws.to_grid(a.astype("float32"), t["tr10"], t["crs"], frame)
        g = grid(np.where(valid, 1.0, np.nan)); m = ~np.isnan(g); acc["n"][m] += 1
        for key, ok in (("okP", okp), ("okR", okr)):
            g = grid(np.where(valid, ok, np.nan)); m = ~np.isnan(g); acc[key][m] += g[m]
        lf = np.log10(np.maximum(fnu, 0.05))
        for key, ok in (("P", okp), ("R", okr)):
            g = grid(np.where(ok, lf, np.nan)); m = ~np.isnan(g); fs[key][m] += g[m]; fs[key + "n"][m] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        shareP = np.where(acc["n"] > 0, acc["okP"] / np.maximum(acc["n"], 1), 0)
        shareR = np.where(acc["n"] > 0, acc["okR"] / np.maximum(acc["n"], 1), 0)
        lp = np.where(fs["Pn"] > 0, fs["P"] / np.maximum(fs["Pn"], 1), np.nan)
        lr = np.where(fs["Rn"] > 0, fs["R"] / np.maximum(fs["Rn"], 1), np.nan)
    readP = lake & (shareP >= dws.S2_MIN_CELL_FRAC) & np.isfinite(lp)
    readR = lake & (shareR >= 0.10) & np.isfinite(lr)
    chal = readR & ~readP
    # reference for challengers: production neighbours' mean at each cell
    s = ndimage.uniform_filter(np.where(readP, lp, 0.0), size=win, mode="constant") * win ** 2
    n = ndimage.uniform_filter(readP.astype(float), size=win, mode="constant") * win ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        ref = np.where(n >= 10, s / np.maximum(n, 1), np.nan)
    bias_c = np.where(chal, lr - ref, np.nan)
    bias_p = np.where(readP, neighbour_median_bias(np.where(readP, lp, 0.0), readP, win, True), np.nan)
    edge = to_edge_m
    rows = {}
    for name, sel in (("0-30m", edge < 30), ("30-60m", (edge >= 30) & (edge < 60)),
                      ("60-100m", (edge >= 60) & (edge < 100)), (">=100m", edge >= 100)):
        bc = bias_c[sel & np.isfinite(bias_c)]; bp = bias_p[sel & np.isfinite(bias_p)]
        rows[name] = {"challengerCells": int(bc.size), "challengerMedian": round(float(np.median(bc)), 3) if bc.size else None,
                      "challengerP90": round(float(np.percentile(bc, 90)), 3) if bc.size else None,
                      "challengerShareAbove0p1": round(float((bc > 0.1).mean()), 3) if bc.size else None,
                      "baselineCells": int(bp.size), "baselineMedian": round(float(np.median(bp)), 3) if bp.size else None,
                      "baselineP90": round(float(np.percentile(bp, 90)), 3) if bp.size else None,
                      "baselineShareAbove0p1": round(float((bp > 0.1).mean()), 3) if bp.size else None}
    enc = np.zeros(lake.shape, np.uint8)
    t_ = np.clip((np.where(chal, lr, LO) - LO) / (HI - LO), 0, 1)
    enc[chal] = (1 + np.round(t_[chal] * 253)).astype(np.uint8)
    np.savez_compressed(os.path.join(out_dir, f"{date}_{platform}.npz"), challengerFNU=enc,
                        biasLog10=np.where(chal, bias_c, np.nan).astype(np.float16),
                        edgeM=np.where(chal, edge, np.nan).astype(np.float16))
    pooled[spec] = {"productionCells": int(readP.sum()), "challengerCells": int(chal.sum()),
                    "challengerShareOfLake": round(float(chal.sum() / lake.sum()), 4), "byDistanceToEdge": rows}
    json.dump(pooled, open(os.path.join(out_dir, "pooled.json"), "w"), indent=1)
    print(spec, pooled[spec]["productionCells"], pooled[spec]["challengerCells"],
          {k: (v["challengerMedian"], v["baselineMedian"]) for k, v in rows.items()}, flush=True)
