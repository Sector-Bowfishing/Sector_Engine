"""Rain over each arm's REAL drainage area, from NOAA MRMS (Clarity Fusion
Stage 1). Replaces, for the new clarity architecture, the engine's 4-point
+-0.35 deg "watershed" ring (MrmsPrecipService); the old production path is
untouched.

  weights   each arm's contributing drainage (NLDI NHDPlus basin at its mouth,
            or above its head where the mouth basin is the river's) as
            fractional MRMS 0.01 deg cells: [row, col, weight], weights sum to 1
  rain      at an hour T (UTC), per arm: basin-mean rain over the last 1, 6, 12,
            24, 48 and 72 h (MRMS MultiSensor QPE Pass 2 accumulation products
            valid at T), the current storm total (hourly back from T to the
            last 6 dry hours), and the 7 days before the 72 h window
            (antecedent), in inches, with the product times used

MRMS: s3://noaa-mrms-pds (public, https), CONUS 0.01 deg, mm; -3 = missing.
Pass 2 is gauge-corrected with ~2 h latency; the job would run hourly at T-2 h.

usage:
  geo/bin/python catchment_rain.py weights <hydrology.json> <catchments dir> <out weights.json>
  geo/bin/python catchment_rain.py rain <weights.json> <YYYY-MM-DDTHH> <out.json> [--cache DIR]
"""
import os, sys, json, gzip, math, argparse, datetime as dt, urllib.request, tempfile
import numpy as np

GRID = {"lon0": -130.0, "lat0": 55.0, "step": 0.01, "width": 7000, "height": 3500}
BUCKET = "https://noaa-mrms-pds.s3.amazonaws.com/CONUS"
PRODUCTS = {1: "MultiSensor_QPE_01H_Pass2_00.00", 6: "MultiSensor_QPE_06H_Pass2_00.00",
            12: "MultiSensor_QPE_12H_Pass2_00.00", 24: "MultiSensor_QPE_24H_Pass2_00.00",
            48: "MultiSensor_QPE_48H_Pass2_00.00", 72: "MultiSensor_QPE_72H_Pass2_00.00"}
MM_PER_IN = 25.4
DRY_HOURS = 6            # a storm ends after this many hours under DRY_IN
DRY_IN = 0.01
MAX_STORM_HOURS = 96


def cell_weights(geom, supersample=10):
    """Fraction of the basin in each 0.01 deg cell, by supersampling."""
    from shapely.geometry import shape
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    g = shape(geom)
    minx, miny, maxx, maxy = g.bounds
    c0 = int(math.floor((minx - GRID["lon0"]) / GRID["step"])); c1 = int(math.ceil((maxx - GRID["lon0"]) / GRID["step"]))
    r0 = int(math.floor((GRID["lat0"] - maxy) / GRID["step"])); r1 = int(math.ceil((GRID["lat0"] - miny) / GRID["step"]))
    f = supersample
    fine = rasterize([(g, 1)], out_shape=((r1 - r0) * f, (c1 - c0) * f),
                     transform=from_origin(GRID["lon0"] + c0 * GRID["step"], GRID["lat0"] - r0 * GRID["step"],
                                           GRID["step"] / f, GRID["step"] / f),
                     all_touched=False, dtype="uint8")
    frac = fine.reshape(r1 - r0, f, c1 - c0, f).mean(axis=(1, 3))
    rr, cc = np.nonzero(frac > 0)
    w = frac[rr, cc]; w = w / w.sum()
    return [[int(r0 + r), int(c0 + c), round(float(x), 6)] for r, c, x in zip(rr, cc, w)]


def build_weights(hydrology, catch_dir, out):
    g = json.load(open(hydrology))
    raw = {}
    for fn in os.listdir(catch_dir):
        if fn.endswith(".geojson"):
            f = json.load(open(os.path.join(catch_dir, fn)))
            raw[(f["properties"]["comid"], f["properties"]["kind"])] = f["geometry"]
    arms = {}
    for a in g["arms"]:
        geom, basis = None, None
        if a.get("nhdplusComidAtMouth") and (a["nhdplusComidAtMouth"], "atMouth") in raw:
            geom, basis, km2 = raw[(a["nhdplusComidAtMouth"], "atMouth")], "nhdplusBasinAtMouth", a["drainageKm2AtMouth"]
        elif a.get("nhdplusComidAtHead") and (a["nhdplusComidAtHead"], "aboveHead") in raw:
            geom, basis, km2 = raw[(a["nhdplusComidAtHead"], "aboveHead")], "nhdplusBasinAboveHead", a["drainageKm2AboveHead"]
        if geom is None:
            arms[a["id"]] = {"basis": "unavailable", "cells": []}
            continue
        arms[a["id"]] = {"basis": basis, "drainageKm2": km2, "cells": cell_weights(geom)}
    json.dump({"grid": GRID, "arms": arms}, open(out, "w"))
    n_ok = sum(1 for v in arms.values() if v["cells"])
    print(f"weights for {n_ok} of {len(arms)} arms "
          f"({sum(1 for v in arms.values() if v['basis'] == 'nhdplusBasinAtMouth')} at the mouth, "
          f"{sum(1 for v in arms.values() if v['basis'] == 'nhdplusBasinAboveHead')} above the head only)")


def fetch(product, t, cache):
    key = f"{product}/{t:%Y%m%d}/MRMS_{product}_{t:%Y%m%d-%H}0000.grib2.gz"
    path = os.path.join(cache, key.replace("/", "_"))
    if not os.path.exists(path):
        os.makedirs(cache, exist_ok=True)
        try:
            urllib.request.urlretrieve(f"{BUCKET}/{key}", path)
        except Exception:
            return None
    return path


def read_window(path, rows, cols):
    import rasterio
    with gzip.open(path) as gz, tempfile.NamedTemporaryFile(suffix=".grib2") as tmp:
        tmp.write(gz.read()); tmp.flush()
        with rasterio.open(tmp.name) as src:
            r0, r1, c0, c1 = min(rows), max(rows) + 1, min(cols), max(cols) + 1
            a = src.read(1, window=((r0, r1), (c0, c1)))
    return a, r0, c0


def basin_means(path, arms):
    rows = [c[0] for v in arms.values() for c in v["cells"]]; cols = [c[1] for v in arms.values() for c in v["cells"]]
    a, r0, c0 = read_window(path, rows, cols)
    out = {}
    for aid, v in arms.items():
        if not v["cells"]:
            continue
        vals = np.array([a[r - r0, c - c0] for r, c, _ in v["cells"]]); w = np.array([x for _, _, x in v["cells"]])
        ok = vals >= 0
        if w[ok].sum() < 0.9:          # most of the basin missing: no value
            out[aid] = None; continue
        out[aid] = float((vals[ok] * w[ok]).sum() / w[ok].sum()) / MM_PER_IN
    return out


def rain(weights, t, out, cache):
    W = json.load(open(weights)); arms = W["arms"]
    t = dt.datetime.strptime(t, "%Y-%m-%dT%H")
    res = {aid: {"basis": v["basis"], "drainageKm2": v.get("drainageKm2")} for aid, v in arms.items()}
    used = {}
    for hours, prod in PRODUCTS.items():
        p = fetch(prod, t, cache)
        if p is None:
            continue
        used[f"{hours}h"] = f"{prod} valid {t:%Y-%m-%dT%H}Z"
        for aid, m in basin_means(p, arms).items():
            res[aid][f"last{hours}hIn"] = None if m is None else round(m, 3)
    # antecedent: the 7 days before the 72 h window (72H at T-72, 72H at T-144, 24H at T-216)
    ante = {aid: 0.0 for aid in arms}; ok = True
    for back, prod in ((72, PRODUCTS[72]), (144, PRODUCTS[72]), (216, PRODUCTS[24])):
        p = fetch(prod, t - dt.timedelta(hours=back), cache)
        if p is None:
            ok = False; break
        for aid, m in basin_means(p, arms).items():
            ante[aid] = None if (m is None or ante[aid] is None) else ante[aid] + m
    for aid in arms:
        if "basis" in res[aid] and arms[aid]["cells"]:
            res[aid]["antecedent7dBeforeWindowIn"] = round(ante[aid], 3) if ok and ante[aid] is not None else None
    # current storm: hourly back from T until DRY_HOURS in a row under DRY_IN
    storm = {aid: 0.0 for aid in arms if arms[aid]["cells"]}; dry = {aid: 0 for aid in storm}; done = set()
    for h in range(MAX_STORM_HOURS):
        p = fetch(PRODUCTS[1], t - dt.timedelta(hours=h), cache)
        if p is None:
            break
        for aid, m in basin_means(p, arms).items():
            if aid in done or m is None:
                continue
            if m < DRY_IN:
                dry[aid] += 1
                if dry[aid] >= DRY_HOURS:
                    done.add(aid)
            else:
                dry[aid] = 0; storm[aid] += m
        if len(done) == len(storm):
            break
    for aid, v in storm.items():
        res[aid]["currentStormIn"] = round(v, 3)
    json.dump({"validTime": f"{t:%Y-%m-%dT%H}:00:00Z", "source": "NOAA MRMS MultiSensor QPE Pass 2 (s3://noaa-mrms-pds)",
               "products": used, "arms": res}, open(out, "w"), indent=1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("args", nargs="+"); ap.add_argument("--cache", default="mrms_cache")
    a = ap.parse_args()
    if a.cmd == "weights":
        build_weights(*a.args)
    else:
        rain(a.args[0], a.args[1], a.args[2], a.cache)


if __name__ == "__main__":
    main()
