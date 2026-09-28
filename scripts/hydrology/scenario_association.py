"""Re-run the integration audit's hypothetical storms against the Stage 1
INPUT-ASSOCIATION layer: which arms' drainage areas receive the rain, which
gauges would answer, which arm each test spot belongs to, and what forcing
reaches it -- no visibility, no propagation (Clarity Fusion Stage 1).

Storms as in the audit: rain falls evenly 12:00-18:00 on day 0 inside a circle;
T is hours from 18:00. Forcing windows are basin-mean accumulations.

usage: geo/bin/python scenario_association.py <final dir> <scenario.json> <out.json>
"""
import sys, os, json, gzip, math, zlib, base64, csv
import numpy as np
import pyproj

final, scen_path, out = sys.argv[1:4]
graph = json.load(open(os.path.join(final, "guntersville.hydrology.json")))
W = json.load(open(os.path.join(final, "guntersville.mrms_weights.json")))
cells = json.load(open(os.path.join(final, "guntersville.arm_cells.json")))
scen = json.load(open(scen_path))
arms = {a["id"]: a for a in graph["arms"]}
GRID = W["grid"]
Wd, Hd = cells["width"], cells["height"]
arm_grid = np.frombuffer(zlib.decompress(base64.b64decode(cells["armGrid"])), np.uint8).reshape(Hd, Wd)
water = np.load(os.path.join(os.path.dirname(final), "out", "water.npy"))
geod = pyproj.Geod(ellps="WGS84")
tm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
(l, t) = tm.transform(*cells["cornersLonLat"][0]); (r, b) = tm.transform(*cells["cornersLonLat"][2])


def km(a, b_):
    return geod.inv(a[1], a[0], b_[1], b_[0])[2] / 1000


def membership(lat, lon, radius=5):
    x, y = tm.transform(lon, lat)
    c = int((x - l) / (r - l) * Wd); rr = int((t - y) / (t - b) * Hd)
    # nearest water cell's label within `radius` cells (the spots are bank anchors)
    for d in range(0, radius + 1):
        for dr in range(-d, d + 1):
            for dc in range(-d, d + 1):
                y2, x2 = rr + dr, c + dc
                if 0 <= y2 < Hd and 0 <= x2 < Wd and water[y2, x2]:
                    v = int(arm_grid[y2, x2])
                    return "mainstem" if v == 0 else cells["arms"][v]
    return None


def basin_rain(storm):
    out_ = {}
    if storm.get("basinOf"):
        # rain on exactly one arm's drainage: every MRMS cell of that basin
        wet = {(r_, c_) for r_, c_, _ in W["arms"][storm["basinOf"]]["cells"]}
        for aid, v in W["arms"].items():
            out_[aid] = (sum(w for r_, c_, w in v["cells"] if (r_, c_) in wet) * storm["inches"]) if v["cells"] else None
        return out_
    for aid, v in W["arms"].items():
        if not v["cells"]:
            out_[aid] = None; continue
        tot = 0.0
        for row, col, w in v["cells"]:
            lat = GRID["lat0"] - (row + 0.5) * GRID["step"]; lon = GRID["lon0"] + (col + 0.5) * GRID["step"]
            if km((lat, lon), (storm["lat"], storm["lon"])) <= storm["radiusKm"]:
                tot += w * storm["inches"]
        out_[aid] = tot
    return out_


def windows(total, T):
    # rain fell during the 6 h ending at T=0; window "last N h" at time T covers (T-N, T]
    def frac(N):
        lo, hi = T - N, T
        overlap = max(0.0, min(hi, 0) - max(lo, -6))
        return overlap / 6
    return {f"{N}h": round(total * frac(N), 2) for N in (6, 12, 24, 48, 72)}


res = {"storms": []}
spot_arm = {s["name"]: membership(s["lat"], s["lon"]) for s in scen["spots"]}
for storm in scen["storms"]:
    br = basin_rain(storm)
    hit = sorted([(a, v) for a, v in br.items() if v and v >= 0.05], key=lambda kv: -kv[1])
    gauges = [(a, arms[a]["usgsDischargeSite"], round(v, 2)) for a, v in hit if arms[a]["usgsDischargeSite"]]
    spots = []
    for s in scen["spots"]:
        a = spot_arm[s["name"]]
        if a == "mainstem" or a is None:
            forcing = {"arm": "mainstem", "ownBasinIn": None,
                       "note": "main-stem water: forcing is the dams' release and the arms upstream of this region (no timing)"}
        else:
            own = br.get(a)
            forcing = {"arm": a, "ownBasinIn": round(own, 2) if own is not None else None,
                       "flowSource": arms[a]["flowSource"], "gauge": arms[a]["usgsDischargeSite"],
                       "byT": {f"T+{T}h": windows(own or 0.0, T) for T in (0, 6, 12, 24, 48)}}
        spots.append({"spot": s["name"], "oldEngineGauge": s.get("gauge"), **forcing})
    res["storms"].append({"storm": storm["name"], "armsReceivingRain": [(a, round(v, 2)) for a, v in hit],
                          "gaugesThatWouldAnswer": gauges, "spots": spots})
    print(f"\n{storm['name']}: {len(hit)} arms get >= 0.05 in basin-mean; gauges: {gauges}")
    for a, v in hit[:8]:
        print(f"   {a:30} {v:.2f} in")
    for s in spots:
        print(f"   spot {s['spot']:26} -> {s['arm']:26} own-basin rain {s.get('ownBasinIn')}  (old engine read gauge {s['oldEngineGauge']})")
res["spotMembership"] = spot_arm
json.dump(res, open(out, "w"), indent=1)
