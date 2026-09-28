"""Within-arm position and longitudinal zones (Clarity Fusion Stage 3A, items 1-2).

For every water cell of every arm, on the Water Clarity frame (36 mercator m
~ 29.6 m on the ground), through the arm's OWN water:

  dHeadM   metres from the arm's head (where the creek enters the lake outline)
  dMouthM  metres to the arm's mouth (where it hands its water to its parent)
  norm     dHead / (dHead + dMouth): 0 at the head, 1 at the mouth

8-neighbour Dijkstra with no diagonal through a land corner (fill_lake._graph8),
restricted to the arm's cells, so a cell across land from the head is never
close to it. Head and mouth points snap to the nearest cell of the arm's largest
connected body of water (the snap distance is recorded); cells in fragments
not connected to it through the arm's water are left unpositioned and
reported.

ZONES. Fixed before any zone statistic was computed (only geometry seen):
  The arm's positioned lake cells, ordered by dHead, are cut into K groups of
  EQUAL AREA, K the largest of 5, 3, 2, 1 such that
    - the arm is at least K x 1,000 m long head to mouth, and
    - K x 400 cells fit (every zone >= 400 lake cells, ~0.35 km2).
  Names: K=5 head, upper, middle, lower, mouth; K=3 head, middle, mouth;
         K=2 head, mouth; K=1 whole.
  Equal area, not equal distance: many arms are a long narrow channel and a
  wide embayment (Town Creek's first 11 km of 22.6 hold 6% of its water), and
  equal-distance bins there are either empty or too small to read. The head
  zone is "the fifth of the arm's water nearest the head through the water".

usage: geo/bin/python arm_positions.py <arm_cells.json> <hydrology.json> <lake-mask npz> <out dir>
  (the lake mask: any pass_history --cells file; cls > 0 is the lake)
"""
import os, sys, json, math, zlib, base64
import numpy as np
from scipy.sparse import csgraph
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import fill_lake as FL

ZONE_MIN_LEN_M = 1_000.0
ZONE_MIN_CELLS = 400
NAMES = {5: ["head", "upper", "middle", "lower", "mouth"], 3: ["head", "middle", "mouth"],
         2: ["head", "mouth"], 1: ["whole"]}

cells_p, graph_p, mask_p, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
C = json.load(open(cells_p))
H, W = C["height"], C["width"]
arm = np.frombuffer(zlib.decompress(base64.b64decode(C["armGrid"])), np.uint8).reshape(H, W)
lake = np.load(mask_p)["cls"] > 0
graph = json.load(open(graph_p)); arms = {a["id"]: a for a in graph["arms"]}
(l_lon, t_lat), _, (r_lon, b_lat), _ = C["cornersLonLat"]
merc = lambda lon, lat: (lon * math.pi / 180 * 6378137, math.log(math.tan(math.pi / 4 + lat * math.pi / 360)) * 6378137)
(L, T), (R, B) = merc(l_lon, t_lat), merc(r_lon, b_lat)
mid_lat = (t_lat + b_lat) / 2
G = C["cellMetresMercator"] * math.cos(math.radians(mid_lat))


def cell_of(lat, lon):
    x, y = merc(lon, lat)
    return int((T - y) / (T - B) * H), int((x - L) / (R - L) * W)


dHead = np.full((H, W), np.nan, "float32"); dMouth = np.full((H, W), np.nan, "float32")
norm = np.full((H, W), np.nan, "float32"); zone = np.full((H, W), -1, "int16")
summary = {"frame": {"height": H, "width": W, "cellGroundM": round(G, 2), "cornersLonLat": C["cornersLonLat"]},
           "rules": {"zoneMinLengthM": ZONE_MIN_LEN_M, "zoneMinCells": ZONE_MIN_CELLS, "names": NAMES},
           "arms": {}, "zones": []}
for k, name in enumerate(C["arms"]):
    if name is None:
        continue
    # The graph runs on the arm's allocation, which includes the Stage 1
    # bridge cells that rejoin narrow arms the lake outline's centre burn cut;
    # statistics later use lake cells only.
    m = arm == k
    n = int((m & lake).sum())
    a = arms.get(name)
    if n == 0 or a is None:
        summary["arms"][name] = {"cells": n, "note": "no lake cells on the frame"}; continue
    idx = FL._index(m)
    A = FL._graph8(m, idx, G)
    ncomp, lab = csgraph.connected_components(A, directed=False)
    main = np.bincount(lab, weights=lake[m].astype(float) + 1e-3).argmax()
    rr, cc = np.nonzero(m)
    in_main = lab == main
    def snap(pt):
        r, c = cell_of(pt[0], pt[1])
        d2 = np.where(in_main, (rr - r) ** 2 + (cc - c) ** 2, np.iinfo(np.int64).max)
        j = int(np.argmin(d2))
        return idx[rr[j], cc[j]], round(math.sqrt(float(d2[j])) * G, 1)
    (hi, hsnap), (mi, msnap) = snap(a["head"]), snap(a["mouth"])
    with np.errstate(invalid="ignore"):
        dh = csgraph.dijkstra(A, indices=hi); dm = csgraph.dijkstra(A, indices=mi)
    ok = np.isfinite(dh) & np.isfinite(dm)
    length = float(dh[mi]) if np.isfinite(dh[mi]) else float("nan")
    with np.errstate(invalid="ignore", divide="ignore"):
        nv = np.where(ok, dh / np.maximum(dh + dm, 1e-6), np.nan)
    onlake = lake[rr, cc]
    dHead[rr, cc] = np.where(ok, dh, np.nan); dMouth[rr, cc] = np.where(ok, dm, np.nan); norm[rr, cc] = nv
    # zones
    use = ok & onlake
    npos = int(use.sum())
    K = 1
    for k_ in (5, 3, 2):
        if length >= k_ * ZONE_MIN_LEN_M and npos >= k_ * ZONE_MIN_CELLS:
            K = k_; break
    b = np.full(len(rr), -1, int)
    if npos:
        order = np.argsort(dh[use], kind="stable")
        q = np.empty(npos, int); q[order] = (np.arange(npos) * K) // npos
        b[np.nonzero(use)[0]] = q
    base = len(summary["zones"])
    for z in range(K):
        sel = b == z
        summary["zones"].append({"zone": base + z, "arm": name, "name": NAMES[K][z], "index": z, "of": K,
                                 "cells": int(sel.sum()),
                                 "dHeadM": [round(float(dh[sel].min()), 0), round(float(dh[sel].max()), 0)] if sel.any() else None})
        zone[rr[sel], cc[sel]] = base + z
    summary["arms"][name] = {"cells": n, "positioned": int((ok & onlake).sum()), "unreachableCells": int((~ok & onlake).sum()),
                             "lengthM": round(length, 0) if math.isfinite(length) else None,
                             "zones": K, "headSnapM": hsnap, "mouthSnapM": msnap, "fragments": int(ncomp),
                             "parent": a["parent"], "topLevel": a["topLevel"], "receivingRegion": a["receivingRegion"],
                             "armClass": a["armClass"], "flowSource": a["flowSource"]}
np.savez_compressed(os.path.join(out, "arm_positions.npz"), dHeadM=dHead, dMouthM=dMouth, norm=norm, zone=zone,
                    arm=arm, lake=lake)
json.dump(summary, open(os.path.join(out, "arm_zones.json"), "w"), indent=1)
from collections import Counter
print("arms", len(summary["arms"]), "zones", len(summary["zones"]), "by K", Counter(v.get("zones") for v in summary["arms"].values()))
for nme in ("town-creek-marshall", "south-sauty-creek", "browns-creek", "north-sauty-creek", "short-creek", "boshart-creek", "yellow-creek", "jagger-branch"):
    print(" ", nme, summary["arms"].get(nme))
