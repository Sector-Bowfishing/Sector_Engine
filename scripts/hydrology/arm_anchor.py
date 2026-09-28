"""Per-arm satellite anchors from a published Water Clarity product
(Clarity Fusion Stage 2, item 2).

Reads the daily job's product for one pass -- the clarity PNG (log10 FNU),
the measured PNG (255 read, 2 cloud-hidden, 1 unreadable, 3 grass bed,
0 off the lake) and the distance PNG (1 + through-water metres / 100 from
each estimate to a reading) -- which are on the same frame as the arm grid
(guntersville.arm_cells.json), and writes, per arm and for the main stem:

  waterCells            cells the layer colours as water (grass beds excluded)
  observedCells         read on the pass
  filledCells           estimated (cloud-hidden or unreadable)
  filledWithin500mCells estimated from a reading <= 500 m away through the water
  medianFillDistanceM   over the estimated cells (25,300 = "beyond 25 km")
  grassCells            grass beds (coloured by the layer, never read)
  observedFNU / allFNU  n, p25, p50, p75
  per-cell evidence stays in the product; this file only summarises it.

usage: geo/bin/python arm_anchor.py <product dir or URL prefix> <date> <arm_cells.json> <out.json>
  e.g. https://storage.googleapis.com/sector-lake-surface/lakes/Guntersville_AL/clarity 2026-09-20
"""
import os, sys, io, json, zlib, base64, urllib.request
import numpy as np
from PIL import Image

src, date, cells_p, out = sys.argv[1:5]


def load(name):
    p = f"{src.rstrip('/')}/{date}{name}"
    data = urllib.request.urlopen(p).read() if p.startswith("http") else open(p, "rb").read()
    return data


meta = json.loads(load(".json"))
val = np.asarray(Image.open(io.BytesIO(load(".png"))), dtype=np.uint8)
meas = np.asarray(Image.open(io.BytesIO(load(".measured.png"))), dtype=np.uint8)
dist = np.asarray(Image.open(io.BytesIO(load(".distance.png"))), dtype=np.uint8)
cells = json.load(open(cells_p))
arm = np.frombuffer(zlib.decompress(base64.b64decode(cells["armGrid"])), np.uint8).reshape(cells["height"], cells["width"])
assert arm.shape == val.shape == meas.shape == dist.shape, (arm.shape, val.shape)
enc = meta["encoding"]
logv = np.where(val > 0, enc["lo"] + (val.astype("float64") - 1) / (enc["top"] - 1) * (enc["hi"] - enc["lo"]), np.nan)
fnu = 10 ** logv
distm = np.where(dist > 0, (dist.astype("float64") - 1) * meta["measured"].get("distanceStepM", 100.0), np.nan)
lake = meas > 0
water = np.isin(meas, (1, 2, 255))


def stats(x):
    x = x[~np.isnan(x)]
    if x.size == 0:
        return None
    return {"n": int(x.size), "p25": round(float(np.percentile(x, 25)), 3),
            "p50": round(float(np.median(x)), 3), "p75": round(float(np.percentile(x, 75)), 3)}


def summarise(m):
    w = m & water
    obs = m & (meas == 255)
    fil = m & np.isin(meas, (1, 2))
    fd = distm[fil]
    return {"waterCells": int(w.sum()), "observedCells": int(obs.sum()), "filledCells": int(fil.sum()),
            "filledCloudCells": int((m & (meas == 2)).sum()), "filledUnreadableCells": int((m & (meas == 1)).sum()),
            "filledWithin500mCells": int((fil & (distm <= 500)).sum()),
            "medianFillDistanceM": round(float(np.nanmedian(fd)), 0) if fd.size and not np.all(np.isnan(fd)) else None,
            "grassCells": int((m & (meas == 3)).sum()),
            "observedFNU": stats(fnu[obs]), "allFNU": stats(fnu[w])}


res = {"lakeId": meta.get("lakeId"), "sceneDate": meta["pass"]["date"], "sceneTime": meta["pass"]["time"],
       "platform": meta["pass"].get("platform"), "source": f"{src.rstrip('/')}/{date} (Water Clarity product)",
       "rule": "observed = measured code 255; filled = codes 1, 2; grass (3) excluded from water",
       "arms": {}, "mainStem": None}
for k, name in enumerate(cells["arms"]):
    m = lake & (arm == k)
    if not m.any():
        continue
    if name is None:
        res["mainStem"] = summarise(m)
    else:
        res["arms"][name] = summarise(m)
json.dump(res, open(out, "w"), indent=1)
ms = res["mainStem"]
print(res["sceneDate"], len(res["arms"]), "arms; main stem observed", ms["observedCells"], "of", ms["waterCells"])
for a in ("town-creek-marshall", "south-sauty-creek", "browns-creek", "jagger-branch", "baker-spring-branch"):
    print(" ", a, res["arms"].get(a))
