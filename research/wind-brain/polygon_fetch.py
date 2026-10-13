"""Wind Brain campaign G1-G4: polygon-only fetch/exposure, independent of the frozen NHD raster tables.
Convention: wind FROM bearing theta (0=N, clockwise). Fetch for a bank = open-water distance measured from the bank point
TOWARD theta (upwind) to the first land (shore or island). Bank hit hardest = the one whose upwind side is longest water.
Run: ~/Library/Caches/sector-wind/venv/bin/python research/wind-brain/polygon_fetch.py {test|fleet|compare} ..."""
import base64, gzip, json, math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import shape, Polygon, MultiPolygon

DIRS16 = [22.5 * i for i in range(16)]
NAMES16 = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
OFFS = (-12.0, -6.0, 0.0, 6.0, 12.0)        # 5 rays across +-12 deg (frozen method uses 9 rays at 3 deg; same span)
MAXM = 30000.0

def rasterize(geom, maxpix=3000, minres=20.0):
    lon0, lat0, lon1, lat1 = geom.bounds
    latm = math.radians((lat0 + lat1) / 2)
    kx, ky = 111320.0 * math.cos(latm), 110574.0
    w, h = (lon1 - lon0) * kx, (lat1 - lat0) * ky
    res = max(minres, max(w, h) / maxpix)
    nx, ny = int(w / res) + 3, int(h / res) + 3
    img = Image.new("L", (nx, ny), 0); d = ImageDraw.Draw(img)
    tr = lambda ring: [((x - lon0) * kx / res + 1, (lat1 - y) * ky / res + 1) for x, y in ring.coords]
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        d.polygon(tr(p.exterior), fill=1)
    for p in polys:
        for r in p.interiors:
            d.polygon(tr(r), fill=0)           # islands / holes are land
    return np.array(img, dtype=bool), res

def bank_points(mask, nmax=400):
    edge = mask & ~ndimage.binary_erosion(mask, iterations=1)
    ys, xs = np.nonzero(edge)
    if len(xs) == 0: return np.empty(0), np.empty(0)
    step = max(1, len(xs) // nmax)
    return xs[::step].astype(float), ys[::step].astype(float)

def fetch_rays(mask, res, xs, ys, bearing):
    """open-water distance (m) from each point toward `bearing` (the FROM direction) to first land."""
    th = math.radians(bearing); dx, dy = math.sin(th), -math.cos(th)    # image y grows southward
    H, W = mask.shape
    dist = np.full(len(xs), MAXM); alive = np.ones(len(xs), bool)
    n = int(MAXM / res)
    for k in range(1, n + 1):
        px = np.rint(xs + dx * k).astype(int); py = np.rint(ys + dy * k).astype(int)
        inb = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        wet = np.zeros(len(xs), bool); wet[inb] = mask[py[inb], px[inb]]
        hit = alive & ~wet
        dist[hit] = k * res; alive &= wet
        if not alive.any(): break
    return dist

def effective_fetch(mask, res, xs, ys):
    """(npts,16) effective fetch = mean of rays across +-12 deg."""
    out = np.zeros((len(xs), 16))
    for j, b in enumerate(DIRS16):
        out[:, j] = np.mean([fetch_rays(mask, res, xs, ys, (b + o) % 360) for o in OFFS], axis=0)
    return out

# ── simple exposure class (Hm0 from CEM-ish fetch limit is the frozen model; here a transparent speed x fetch rule) ──
def exposure_class(mph, fetch_m):
    """LOW / MODERATE / HIGH from the frozen CEM chop bounds (1/3/6 in), steady 6 h, via the Candidate's own physics."""
    G = 9.80665; u = mph * 0.44704
    if u <= 0: return "LOW"
    us = u * math.sqrt(0.001 * (1.1 + 0.035 * u)); t = 6 * 3600
    xd = min(fetch_m, 5.23e-3 * (G * t / us) ** 1.5 * us * us / G)
    h = min(4.13e-2 * math.sqrt(G * xd / (us * us)) * us * us / G, 2.115e2 * us * us / G)
    inch = h / 0.0254
    return "LOW" if inch < 1 else "MODERATE" if inch < 6 else "HIGH"

def load_poly(feature):
    g = shape(feature["geometry"])
    return g if g.is_valid else g.buffer(0)

def cmd_test():
    """G1: synthetic 10 km x 2 km east-west rectangle, a cove, an island. Wind FROM 270 (west) -> east bank hammered."""
    lon0, lat0 = -90.0, 35.0
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110574.0
    rect = lambda x0, x1, y0, y1: [(lon0 + x / kx, lat0 + y / ky) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    lake = Polygon(rect(0, 10000, 0, 2000))
    mask, res = rasterize(lake, minres=20)
    def at(xm, ym):  # point near (xm,ym) metres
        return np.array([xm / res + 1]), np.array([(2000 - ym) / res + 1])   # approx raster coords (bounds shift 1 px)
    xs_e, ys_e = at(9980, 1000); xs_w, ys_w = at(20, 1000)
    res_t = []
    chk = lambda name, ok: res_t.append((name, bool(ok)))
    for frm, bank, exp_long in ((270, "east", True), (90, "west", True), (270, "west", False), (90, "east", False)):
        xs, ys = (xs_e, ys_e) if bank == "east" else (xs_w, ys_w)
        f = fetch_rays(mask, res, xs, ys, frm)[0]
        chk(f"wind FROM {frm}: {bank} bank fetch {'long' if exp_long else 'short'} (={f:.0f} m)", (f > 8000) if exp_long else (f < 200))
    # crosswind: wind FROM north on a 2 km N-S width -> south bank fetch ~2 km, east bank near zero
    xs_s, ys_s = at(5000, 20)
    chk("wind FROM N (0): south bank fetch ~ lake width 2 km", 1700 < fetch_rays(mask, res, xs_s, ys_s, 0)[0] < 2100)
    # meteorological direction table: FROM SW (225) -> NE-facing/downwind shore is the exposed one
    sq = Polygon(rect(0, 6000, 0, 6000)); m2, r2 = rasterize(sq, minres=20)
    ne = (np.array([5980 / r2 + 1]), np.array([(6000 - 5980) / r2 + 1])); sw = (np.array([20 / r2 + 1]), np.array([(6000 - 20) / r2 + 1]))
    fne = fetch_rays(m2, r2, *ne, 225)[0]; fsw = fetch_rays(m2, r2, *sw, 225)[0]
    chk(f"wind FROM SW over a square lake: NE (downwind) corner fetch {fne:.0f} >> SW (upwind) corner {fsw:.0f}", fne > 7000 and fsw < 200)
    # island shields the lee: island at x 4000-4600 midline; east bank behind island with wind FROM W
    isl = Polygon(lake.exterior.coords, [rect(4000, 4600, 700, 1300)]); mi, ri = rasterize(isl, minres=20)
    f_ok = fetch_rays(mi, ri, *at(9980, 1000), 270)[0]; f_ok2 = fetch_rays(mi, ri, *at(9980, 300), 270)[0]
    chk(f"island blocks centre line (fetch {f_ok:.0f} m ~ 5.4 km) but not the flank ({f_ok2:.0f} m ~ 10 km)", 5000 < f_ok < 6000 and f_ok2 > 9000)
    for n, ok in res_t: print(("PASS " if ok else "FAIL ") + n)
    print("G1", sum(ok for _, ok in res_t), "/", len(res_t))
    return res_t

def lake_profile(feat):
    g = load_poly(feat); mask, res = rasterize(g)
    xs, ys = bank_points(mask)
    if len(xs) < 20: return None
    F = effective_fetch(mask, res, xs, ys)
    return {"id": feat["properties"]["id"], "areaKm2": feat["properties"]["areaKm2"], "res": res, "nBanks": len(xs),
            "medianFetchByDir": np.median(F, axis=0).round(0).tolist(), "p90FetchByDir": np.percentile(F, 90, axis=0).round(0).tolist(),
            "maxFetchM": float(F.max()), "fetchPts": F.astype(np.float32)}

def cmd_fleet(out):
    gj = json.load(gzip.open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz")))
    rows, t = [], 0
    for i, f in enumerate(gj["features"]):
        try: p = lake_profile(f)
        except Exception as e: p = None; print("ERR", f["properties"]["id"], e)
        if p is None: rows.append({"id": f["properties"]["id"], "areaKm2": f["properties"]["areaKm2"], "ok": False}); continue
        F = p.pop("fetchPts")
        cls = {}
        for mph in (8, 12, 18):
            cnt = {"LOW": 0, "MODERATE": 0, "HIGH": 0}
            for v in F.ravel()[::7]: cnt[exposure_class(mph, float(v))] += 1
            s = sum(cnt.values()); cls[str(mph)] = {k: round(v / s, 3) for k, v in cnt.items()}
        p["classShare"] = cls; p["ok"] = True; rows.append(p)
        if i % 50 == 0: print(i, p["id"], p["nBanks"], flush=True)
    json.dump(rows, open(out, "w"))
    print("done", len(rows), sum(r["ok"] for r in rows))

def load_frozen(path):
    d = json.load(gzip.open(path)); banks = d["banks"]
    t = base64.b64decode(d["tableBase64"]); n = len(t) // 2
    tab = np.array(struct.unpack(f"<{n}H", t), dtype=float).reshape(len(banks), 120) * 10.0
    keep = [i for i, b in enumerate(banks) if not b.get("belowResolution")]
    tab = tab[keep]
    cols = []
    for b in DIRS16:
        c = int(round(b / 3.0)) % 120
        cols.append(np.mean([tab[:, (c + k) % 120] for k in range(-4, 5)], axis=0))
    return d["directory"], np.array(cols).T

if __name__ == "__main__":
    {"test": cmd_test, "fleet": lambda: cmd_fleet(sys.argv[2])}[sys.argv[1]]()
