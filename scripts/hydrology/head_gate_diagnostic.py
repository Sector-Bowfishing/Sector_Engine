"""Stage 3B item 12 FEASIBILITY ONLY -- never part of the primary result.

Why are the heads of big arms unreadable, and would a looser shore rule get
them back without the land's glow contaminating the water?

For a few clear discovery passes (2025-2026, never the validation years), per
10 m Sentinel-2 pixel inside chosen zones, it records which production gate
rejected it (in order: not SCL water, within 10 m of an SCL bank pixel, within
100 m of a bright structure, cloud/haze/standoff, the SWIR/FAI/NDVI limits),
and then reads the same pixels under ONE relaxed variant: bank standoff 0 m,
structure standoff 30 m, frame-cell minimum 10% of pixels (the cloud, haze and
reflectance limits unchanged). For cells only the relaxed variant reads, it
compares their FNU with production-read cells of the same zone on the same
pass (log10 difference): a positive bias is the shore's adjacency glow.

usage: geo/bin/python head_gate_diagnostic.py <positions dir> <out.json> <date:platform> ...
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
pos_dir, out = sys.argv[1], sys.argv[2]
specs = sys.argv[3:]
P = np.load(os.path.join(pos_dir, "arm_positions.npz")); Z = json.load(open(os.path.join(pos_dir, "arm_zones.json")))
zone = P["zone"]
targets = {z["zone"]: z for z in Z["zones"] if z["name"] == "head" and z["of"] == 5}
lake_g = unary_union([shape(f["geometry"]) for f in json.load(open(WATERBODY))["features"]])
dws.UTM = "EPSG:32616"
frame = dws.Frame(lake_g, cell=dws.CLARITY_CELL)


def gates(t, relaxed):
    """The production gate stack, each stage kept (mirrors _s2_native_fields)."""
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
    stages = {"sclWater": water, "bank": to_bank >= bank_m / px, "structure": to_structure >= struct_m / px,
              "cloudHaze": clear & ~under_cloud & unhazed}
    with np.errstate(invalid="ignore"):
        stages["reflectance"] = (r_sw <= dws.SWIR_MAX) & (fai <= dws.FAI_MAX) & (ndvi <= dws.NDVI_MAX) & (r_red > 0)
    ok = water.copy()
    for k in ("bank", "structure", "cloudHaze", "reflectance"):
        ok &= stages[k]
    rr = np.clip(np.nan_to_num(r_red, nan=0), 0, None)
    fnu = np.where(rr >= dws.TURB_SATURATED, dws.TURB_SATURATED_FNU, dws.TURB_A * rr / np.maximum(1e-6, 1 - rr / dws.TURB_C)).astype("float32")
    return stages, ok, fnu


res = json.load(open(out)) if os.path.exists(out) else {}
bbox = list(lake_g.bounds)
for spec in specs:
    if spec in res: continue
    date, platform = spec.split(":")
    got = dws.passes(dws.ES_SEARCH, dws.S2_COLLECTION, bbox, dt.datetime.fromisoformat(date + "T23:59:59"), max_cloud=40)
    items = next((it for (d, pl), it in got if d == date and pl == platform), None)
    if items is None:
        res[spec] = "not found"; continue
    H, W = frame.height, frame.width
    acc = {k: np.zeros((H, W)) for k in ("n", "sclWater", "bank", "structure", "cloudHaze", "reflectance", "okProd", "okRel")}
    fprod = np.zeros((H, W)); fprod_n = np.zeros((H, W)); frel = np.zeros((H, W)); frel_n = np.zeros((H, W))
    for it in items:
        t = dws._read_s2_native(it, frame.bounds)
        if t["red"].size == 0: continue
        sp, okp, fnu = gates(t, False)
        _, okr, _ = gates(t, True)
        valid = np.isfinite(fnu)
        grid = lambda a: dws.to_grid(a.astype("float32"), t["tr10"], t["crs"], frame)
        # the first gate that fails, cumulatively (share of pixels surviving each stage)
        surv = valid.copy()
        for k in ("sclWater", "bank", "structure", "cloudHaze", "reflectance"):
            surv = surv & sp[k]
            g = grid(np.where(valid, surv, np.nan)); m = ~np.isnan(g); acc[k][m] += g[m]
        g = grid(np.where(valid, 1.0, np.nan)); m = ~np.isnan(g); acc["n"][m] += 1
        for key, ok in (("okProd", okp), ("okRel", okr)):
            g = grid(np.where(valid, ok, np.nan)); m = ~np.isnan(g); acc[key][m] += g[m]
        for (fs, fn), ok in (((fprod, fprod_n), okp), ((frel, frel_n), okr)):
            g = grid(np.where(ok, np.log10(np.maximum(fnu, 0.05)), np.nan)); m = ~np.isnan(g); fs[m] += g[m]; fn[m] += 1
    share = {k: np.where(acc["n"] > 0, acc[k] / np.maximum(acc["n"], 1), np.nan) for k in acc if k != "n"}
    lp = np.where(fprod_n > 0, fprod / np.maximum(fprod_n, 1), np.nan); lr = np.where(frel_n > 0, frel / np.maximum(frel_n, 1), np.nan)
    readP = share["okProd"] >= dws.S2_MIN_CELL_FRAC
    readR = share["okRel"] >= 0.10
    out_ = {}
    for zid, z in targets.items():
        m = zone == zid
        if not m.any(): continue
        new = m & readR & ~readP
        both = m & readP
        bias = None
        if new.sum() >= 10 and both.sum() >= 10:
            bias = round(float(np.nanmedian(lr[new]) - np.nanmedian(lp[both])), 3)
        out_[z["arm"]] = {"cells": int(m.sum()),
                          "survivingShare": {k: round(float(np.nanmean(share[k][m])), 3) for k in ("sclWater", "bank", "structure", "cloudHaze", "reflectance")},
                          "readProduction": int((m & readP).sum()), "readRelaxed": int((m & readR).sum()),
                          "newOnlyRelaxed": int(new.sum()), "adjacencyBiasLog10(relaxedOnly - production)": bias}
    res[spec] = out_
    json.dump(res, open(out, "w"), indent=1)
    print(spec, {a: (v["readProduction"], v["readRelaxed"], v["adjacencyBiasLog10(relaxedOnly - production)"]) for a, v in out_.items()}, flush=True)
