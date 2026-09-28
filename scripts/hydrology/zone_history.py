"""The historical satellite record per pass x arm x zone, and each pass's
anchor quality per arm with production-equivalent fill distances (Clarity
Fusion Stage 3A, items 3 and 5).

Input: the per-cell pass files (pass_history.py --cells) and the zones
(arm_positions.py). DIRECTLY OBSERVED cells only enter any FNU statistic --
nothing filled can manufacture a plume. Per pass x zone:

  lakeCells, observedCells, coverage (observed / non-grass lake cells),
  fnu p25/p50/p75 (observed), visibility central/low/high (VisibilityModel
  secchi-power-v1 from the median, satellite range), cloudFrac, grassFrac,
  unreadableFrac (of the zone's lake cells), measurable (>= 30 observed and
  coverage >= 30%)

Per pass x arm (and the main stem), the anchor the live product would build
(arm_anchor.py): waterCells (non-grass), observedCells, filledCells,
filledWithin500mCells and medianFillDistanceM, where a filled cell's distance
is THROUGH THE WATER to the nearest observed cell (multi-source Dijkstra on
the lake + Stage 1 bridges, as the product's distance PNG), observedFNU. The
replay reads these instead of guessing weakness from coverage alone. Written
as ArmAnchorFile JSON per pass so the engine's own decoder reads them.

usage: geo/bin/python zone_history.py <cells dir> <positions dir> <passes dir (per-arm json, for times)> <out dir>
"""
import os, sys, json, glob, math
import numpy as np
from scipy.sparse import csgraph
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import fill_lake as FL

ENC_LO, ENC_HI = math.log10(0.5), math.log10(200.0)
A, B = 11.123, -0.637                     # VisibilityModel secchi-power-v1
SAT_LO, SAT_HI = -0.356, 0.520            # its satellite 80% range, log10
MIN_OBS, MIN_COV = 30, 0.30

cells_dir, pos_dir, pass_dir, out = sys.argv[1:5]
os.makedirs(os.path.join(out, "anchors"), exist_ok=True)
P = np.load(os.path.join(pos_dir, "arm_positions.npz"))
Z = json.load(open(os.path.join(pos_dir, "arm_zones.json")))
zone, armg, lake0 = P["zone"], P["arm"], P["lake"]
G = Z["frame"]["cellGroundM"]
names = [None] + sorted({z["arm"] for z in Z["zones"]})       # placeholder, replaced below
arm_names = json.load(open(os.path.join(HERE, "..", "..", "docs", "data", "hydrology", "guntersville",
                                        "guntersville.arm_cells.json")))["arms"]
# the fill graph: lake + bridges (arm allocation outside the lake mask)
fillmask = lake0 | (armg > 0)
fidx = FL._index(fillmask)
FG = FL._graph8(fillmask, fidx, G)
zone_ids = np.array([z["zone"] for z in Z["zones"]])
zone_of = zone.ravel()


def stats(x):
    if x.size == 0:
        return None
    return [round(float(np.percentile(x, 25)), 3), round(float(np.median(x)), 3), round(float(np.percentile(x, 75)), 3)]


rows = {}
for f in sorted(glob.glob(os.path.join(cells_dir, "*.npz"))):
    key = os.path.basename(f)[:-4]
    meta = json.load(open(os.path.join(pass_dir, key + ".json")))
    d = np.load(f); enc, cls = d["fnu"], d["cls"]
    lake = cls > 0
    obs = cls == 1
    fnu = np.where(enc > 0, 10 ** (ENC_LO + (enc.astype("float64") - 1) / 253 * (ENC_HI - ENC_LO)), np.nan)
    # through-water distance from every cell to the nearest observed one
    src = fidx[obs & fillmask]
    src = src[src >= 0]
    dist = np.full(fillmask.shape, np.inf)
    if src.size:
        dv = csgraph.dijkstra(FG, indices=src, min_only=True)
        dist[fillmask] = dv
    rec = {"date": meta["date"], "platform": meta["platform"], "time": meta["time"], "zones": {}, "arms": {}}
    # zones
    for z in Z["zones"]:
        m = (zone == z["zone"]) & lake
        n = int(m.sum())
        if n == 0:
            continue
        o = m & obs
        grass = int((m & (cls == 3)).sum())
        water = n - grass
        no = int(o.sum())
        cov = no / water if water else 0.0
        st = stats(fnu[o])
        vis = None
        if st:
            c = A * max(st[1], 0.1) ** B
            vis = [round(c * 10 ** SAT_LO, 2), round(c, 2), round(c * 10 ** SAT_HI, 2)]
        rec["zones"][str(z["zone"])] = {
            "lakeCells": n, "observedCells": no, "coverage": round(cov, 3), "fnu": st, "visibilityFt": vis,
            "cloudFrac": round(float((m & (cls == 2)).sum()) / n, 3), "grassFrac": round(grass / n, 3),
            "unreadableFrac": round(float((m & (cls == 4)).sum()) / n, 3),
            "measurable": bool(no >= MIN_OBS and cov >= MIN_COV)}
    # anchors per arm and the main stem, in the engine's ArmAnchorFile shape
    def anchor(m):
        water = m & lake & (cls != 3)
        o = water & obs
        fil = water & ~obs
        fd = dist[fil]
        fin = fd[np.isfinite(fd)]
        so = stats(fnu[o]); sa = stats(np.where(o, fnu, np.nan)[water & o])
        return {"waterCells": int(water.sum()), "observedCells": int(o.sum()), "filledCells": int(fil.sum()),
                "filledWithin500mCells": int((fd <= 500).sum()),
                "medianFillDistanceM": round(float(np.median(fd)), 0) if fd.size and np.isfinite(np.median(fd)) else (25_300.0 if fd.size else None),
                "observedFNU": ({"n": int(o.sum()), "p25": so[0], "p50": so[1], "p75": so[2]} if so else None),
                "allFNU": None}
    arms_out = {}
    for k, nm in enumerate(arm_names):
        m = armg == k
        if nm is None:
            continue
        if not (m & lake).any():
            continue
        arms_out[nm] = anchor(m)
    ms = anchor((armg == 0) & lake)
    af = {"sceneDate": meta["date"], "sceneTime": meta["time"], "platform": meta["platform"],
          "source": f"zone_history {key} (observed cells; through-water fill distances)", "arms": arms_out, "mainStem": ms}
    json.dump(af, open(os.path.join(out, "anchors", key + ".json"), "w"))
    rec["arms"] = {k: {x: v[x] for x in ("waterCells", "observedCells", "filledWithin500mCells", "medianFillDistanceM")}
                   for k, v in arms_out.items()}
    rows[key] = rec
    print(key, "zones measurable", sum(v["measurable"] for v in rec["zones"].values()), "of", len(rec["zones"]), flush=True)
json.dump({"rules": {"measurable": f">= {MIN_OBS} observed cells and >= {int(MIN_COV*100)}% of the zone's non-grass water",
                     "fnu": "observed cells only (pass_history drops applied); p25, p50, p75",
                     "visibility": "secchi-power-v1 from the zone median, satellite 80% range",
                     "fill": "through-water distance to the nearest observed cell, lake + Stage 1 bridges"},
           "zones": Z["zones"], "passes": rows}, open(os.path.join(out, "zone_history.json"), "w"))
print("passes", len(rows))
