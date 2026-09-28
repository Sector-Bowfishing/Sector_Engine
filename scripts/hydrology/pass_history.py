"""Per-arm Sentinel-2 observations for every usable historical pass over a
lake (Clarity Fusion Stage 2, the pass-pair calibration input).

For each pass: the same red-band read and per-pixel gates the Water Clarity
layer uses (derive_water_surface.s2_pass), the same post-read drops (muddy
specks, shadow patches near cloud, patches under 5 cells), then per hydrologic
arm (the Stage 1 arm grid on the same frame): water cells, observed cells, and
the observed cells' FNU distribution. No fill and no grass-under-cloud lookups
-- only what the satellite actually saw that day.

usage: geo/bin/python pass_history.py <passes.json> <arm_cells.json> <out dir> [--worker k --workers n]
                                     [--cells DIR] [--only-read PREVIOUS_OUT_DIR]

--cells DIR  also keep every cell of the pass (Stage 3A): DIR/<date>_<platform>.npz
             with `fnu` (uint8, 0 = none, else log10 FNU on the product's
             encoding) and `cls` (0 off the lake, 1 observed, 2 cloud-hidden,
             3 grass, 4 unreadable or dropped), on the clarity frame.
--only-read  re-read only passes an earlier run read (skips known rejects).
"""
import os, sys, json, math, argparse, datetime as dt, zlib, base64, time
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import derive_water_surface as dws
from shapely.geometry import shape
from shapely.ops import unary_union

ENC_LO, ENC_HI = math.log10(0.5), math.log10(200.0)   # the published product's encoding (top 254)
WATERBODY = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/.fishintel-cache/guntersville/waterbody.geojson")


def stats(x):
    if x.size == 0:
        return None
    return {"n": int(x.size), "p25": round(float(np.percentile(x, 25)), 3), "p50": round(float(np.median(x)), 3),
            "p75": round(float(np.percentile(x, 75)), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("passes"); ap.add_argument("arm_cells"); ap.add_argument("out")
    ap.add_argument("--worker", type=int, default=0); ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--cells", default=None); ap.add_argument("--only-read", default=None)
    ap.add_argument("--reverse", action="store_true", help="walk this worker's passes newest first")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.cells:
        os.makedirs(a.cells, exist_ok=True)
    passes = json.load(open(a.passes))
    if a.only_read:
        passes = [p for p in passes if (json.load(open(os.path.join(a.only_read, f"{p['date']}_{p['platform']}.json")))
                                        .get("status") == "read"
                                        if os.path.exists(os.path.join(a.only_read, f"{p['date']}_{p['platform']}.json")) else False)]
    passes = passes[a.worker::a.workers]
    if a.reverse:
        passes = passes[::-1]
    cells = json.load(open(a.arm_cells))
    arm = np.frombuffer(zlib.decompress(base64.b64decode(cells["armGrid"])), np.uint8).reshape(cells["height"], cells["width"])
    names = cells["arms"]
    lake_g = unary_union([shape(f["geometry"]) for f in json.load(open(WATERBODY))["features"]])
    dws.UTM = "EPSG:32616"
    frame = dws.Frame(lake_g, cell=dws.CLARITY_CELL)
    assert (frame.height, frame.width) == arm.shape, "frame mismatch with the arm grid"
    masks = dws.lake_masks(lake_g, frame)
    lake = masks["lake"]
    bbox = list(lake_g.bounds)
    for p in passes:
        path = os.path.join(a.out, f"{p['date']}_{p['platform']}.json")
        cpath = os.path.join(a.cells, f"{p['date']}_{p['platform']}.npz") if a.cells else None
        if os.path.exists(cpath if cpath else path):
            continue
        t0 = time.time()
        until = dt.datetime.fromisoformat(p["date"] + "T23:59:59")
        try:
            got = dws.passes(dws.ES_SEARCH, dws.S2_COLLECTION, bbox, until, max_cloud=40)
            items = next((it for (d, pl), it in got if d == p["date"] and pl == p["platform"]), None)
            if items is None:
                json.dump({"date": p["date"], "platform": p["platform"], "status": "not found"}, open(path, "w")); continue
            v, grass, aux = dws.s2_pass(items, frame, lake, masks["clarity"])
        except Exception as e:
            json.dump({"date": p["date"], "platform": p["platform"], "status": f"rejected: {str(e)[:120]}"}, open(path, "w"))
            print(p["date"], "rejected", str(e)[:80], flush=True); continue
        read = ~np.isnan(v)
        water = masks["clarity"] & ~grass
        cov = float((read & water).sum() / max(1, water.sum()))
        logv = np.where(v > 0, np.log10(np.maximum(v, 0.05)), np.nan).astype("float32")
        local = dws.smooth_known(logv, 14)
        hot = ~np.isnan(logv) & ((logv - local) > dws.SPECK_LOG10)
        lab, n = ndimage.label(hot)
        if n:
            sz = ndimage.sum(hot, lab, index=np.arange(1, n + 1))
            logv[np.isin(lab, np.nonzero(sz <= dws.SPECK_MAX_CELLS)[0] + 1)] = np.nan
        near = np.nan_to_num(aux["near"]) >= 0.5
        dark = ~np.isnan(logv) & near & ((logv - local) < -dws.S2_SHADOW_SPECK_LOG10)
        lab, n = ndimage.label(dark)
        if n:
            sz = ndimage.sum(dark, lab, index=np.arange(1, n + 1))
            logv[np.isin(lab, np.nonzero(sz <= dws.SPECK_MAX_CELLS)[0] + 1)] = np.nan
        lab, n = ndimage.label(~np.isnan(logv))
        if n:
            sz = ndimage.sum(~np.isnan(logv), lab, index=np.arange(1, n + 1))
            logv[np.isin(lab, np.nonzero(sz < dws.S2_MIN_PATCH_CELLS)[0] + 1)] = np.nan
        obs = lake & ~np.isnan(logv)
        fnu = 10 ** logv
        if cpath:
            enc = np.zeros(lake.shape, "uint8")
            t = np.clip((logv[obs] - ENC_LO) / (ENC_HI - ENC_LO), 0, 1)
            enc[obs] = (1 + np.round(t * 253)).astype("uint8")
            hidden = np.nan_to_num(aux["hidden"]) >= 0.5
            cls = np.zeros(lake.shape, "uint8")
            cls[lake] = 4
            cls[lake & hidden] = 2
            cls[lake & grass] = 3
            cls[obs] = 1
            np.savez_compressed(cpath, fnu=enc, cls=cls)
        res = {"date": p["date"], "platform": p["platform"], "status": "read",
               "time": items[0]["properties"]["datetime"], "openWaterReadPct": round(100 * cov, 1),
               "lakeObservedPct": round(100 * float(obs.sum() / lake.sum()), 1),
               "lake": stats(fnu[obs]), "arms": {}}
        for k in range(len(names)):
            m = lake & (arm == k)
            if not m.any():
                continue
            o = m & obs
            res["arms"][names[k] or "mainstem"] = {"waterCells": int(m.sum()), "observedCells": int(o.sum()),
                                                   "observedPct": round(100 * float(o.sum() / m.sum()), 1),
                                                   "fnu": stats(fnu[o])}
        json.dump(res, open(path, "w"))
        print(p["date"], p["platform"], f"lake {res['lakeObservedPct']}% observed, open water {res['openWaterReadPct']}%, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
