"""Stage 3C Track B: frozen-Candidate CEM vs measured lake waves (pre-registered: WIND_WAVE_PHYSICS_PREREG.md).

  python research/wave_physics.py build     # raw buoy files (immutable cache) + fetch tables + wind-cem input rows
  python research/wave_physics.py run       # wind-cem (the app's frozen Swift physics) on the rows
  python research/wave_physics.py metrics OUT.json
"""
import gzip, io, json, math, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IOS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind")
sys.path.insert(0, os.path.join(IOS, "scripts/wind"))
import build_fetch_tables as B   # frozen raster/ray code

CACHE = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation")
RAW = os.path.join(CACHE, "wave-buoys/raw"); DER = os.path.join(CACHE, "derived/waves")
WIND_CEM = os.path.expanduser("~/Library/Caches/sector-wind/swiftpm/release/wind-cem")
WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
STATIONS = {  # id: (lat, lon, anemometer m, depth m, seasons, water body)  — pre-registered
    "45166": (44.785, -73.258, 2.5, 38.1, [2017, 2018, 2019], "Lake Champlain Inland Sea"),
    "45178": (44.603, -73.394, 1.0, None, [2024], "Lake Champlain Valcour"),
    "45014": (44.794, -87.758, 2.0, 13.0, [2024, 2025], "South Green Bay"),
    "45163": (43.983, -83.600, 2.3, 12.5, [2019, 2024], "Saginaw Bay"),
    "45175": (45.825, -84.772, 1.7, None, [2024, 2025], "Mackinac Straits West"),
    "45202": (41.532, -82.941, 1.5, 4.9, [2024, 2025], "Port Clinton, W Lake Erie"),
    "45165": (41.704, -83.264, 2.5, 24.5, [2024], "Toledo, W Lake Erie"),
    "45020": (44.789, -85.604, 2.4, None, [2017, 2018], "Grand Traverse Bay South"),
    "45173": (46.573, -86.572, 2.0, 40.0, [2019], "Munising, Lake Superior"),
}


def raw_file(sid, yr):
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, f"{sid}h{yr}.txt.gz")
    if not os.path.exists(p):
        url = f"https://www.ndbc.noaa.gov/data/historical/stdmet/{sid}h{yr}.txt.gz"
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SectorWind research"}), timeout=120).read()
        open(p + ".part", "wb").write(data); os.replace(p + ".part", p); os.chmod(p, 0o444)
    return p


def parse(p):
    """NDBC stdmet -> {hour: (wdir, wspd, wvht)} at the top of the hour (minute 0, else nearest <= 10 min)."""
    txt = gzip.open(p, "rt").read().splitlines()
    hdr = txt[0].lstrip("#").split(); rows = {}
    for l in txt:
        if l.startswith("#"):
            continue
        v = l.split(); d = dict(zip(hdr, v))
        try:
            t = datetime(int(d["YY"]), int(d["MM"]), int(d["DD"]), int(d["hh"]), int(d.get("mm", 0)), tzinfo=timezone.utc)
        except Exception:
            continue
        h = (t + timedelta(minutes=30)).replace(minute=0)
        if abs((t - h).total_seconds()) > 600:
            continue
        f = lambda k, bad: (None if d.get(k) in (None, "MM") or float(d[k]) >= bad else float(d[k]))
        rec = (f("WDIR", 999), f("WSPD", 99), f("WVHT", 99), abs((t - h).total_seconds()))
        if h not in rows or rec[3] < rows[h][3]:
            rows[h] = rec
    return {h: r[:3] for h, r in rows.items()}


def water_mask(lat, lon, radius_m=32000):
    """ESA WorldCover 10 m class 80 around the buoy, reprojected to the buoy's UTM zone at 10 m (frozen raster spacing)."""
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    from pyproj import Transformer
    dlat = radius_m / 111000 + 0.02; dlon = radius_m / (111000 * math.cos(math.radians(lat))) + 0.02
    tiles = set()
    for la in (lat - dlat, lat + dlat):
        for lo in (lon - dlon, lon + dlon):
            tla, tlo = int(math.floor(la / 3) * 3), int(math.floor(lo / 3) * 3)
            tiles.add(f"{'N' if tla >= 0 else 'S'}{abs(tla):02d}{'E' if tlo >= 0 else 'W'}{abs(tlo):03d}")
    srcs = [rasterio.open("/vsicurl/" + WC.format(t=t)) for t in sorted(tiles)]
    arr, tr = merge(srcs, bounds=(lon - dlon, lat - dlat, lon + dlon, lat + dlat))
    epsg = 32600 + int((lon + 180) // 6) + 1
    x0, y0 = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    n = int(2 * radius_m / 10) + 1
    dst = np.zeros((n, n), dtype=np.uint8)
    dtr = from_origin(x0 - radius_m, y0 + radius_m, 10, 10)
    reproject(arr[0], dst, src_transform=tr, src_crs="EPSG:4326", dst_transform=dtr, dst_crs=f"EPSG:{epsg}", resampling=Resampling.nearest)
    return dst == 80, (x0 - radius_m, y0 + radius_m), (x0, y0), epsg


def build():
    os.makedirs(DER, exist_ok=True)
    rows_out = open(os.path.join(DER, "rows.jsonl"), "w"); meta = {}
    for sid, (lat, lon, zh, depth, seasons, name) in STATIONS.items():
        mask, origin, (x0, y0), epsg = water_mask(lat, lon)
        H, W = mask.shape; r, c = int((origin[1] - y0) / 10), int((x0 - origin[0]) / 10)
        table = B.ray_table(mask, origin, np.array([x0]), np.array([y0]))[0]
        meta[sid] = {"name": name, "lat": lat, "lon": lon, "anemometerM": zh, "depthM": depth, "epsg": epsg,
                     "buoyCellIsWater": bool(mask[r, c]), "waterShareWindow": round(float(mask.mean()), 3),
                     "fetchTableM": [round(float(x)) for x in table], "seasons": seasons}
        conv = (10.0 / zh) ** (1 / 7)
        for yr in seasons:
            obs = parse(raw_file(sid, yr))
            for h in sorted(obs):
                wd, ws, hs = obs[h]
                if wd is None or ws is None or hs is None or hs <= 0:
                    continue
                u10 = ws * conv
                ser = []
                for k in range(12, -1, -1):
                    o = obs.get(h - timedelta(hours=k))
                    ser.append({"speedMS": o[1] * conv, "dirFromDeg": o[0]} if o and o[1] is not None and o[0] is not None else {"speedMS": None, "dirFromDeg": None})
                fetch = B.nine_ray_mean(table, wd)
                base = {"station": sid, "time": h.strftime("%Y-%m-%dT%H:%MZ"), "windMS": round(u10, 3), "windRawMS": ws,
                        "dirFromDeg": wd, "fetchM": round(fetch, 1), "hm0Obs": hs, "series": ser}
                rows_out.write(json.dumps({**base, "id": f"{sid}|{h:%Y%m%d%H}|nodepth"}) + "\n")
                if depth:
                    rows_out.write(json.dumps({**base, "id": f"{sid}|{h:%Y%m%d%H}|depth", "depthM": depth}) + "\n")
        print(sid, name, "fetch median over bearings", int(np.median(table)), "m; buoy cell water", meta[sid]["buoyCellIsWater"], flush=True)
    json.dump(meta, open(os.path.join(DER, "stations.json"), "w"), indent=1)


def run():
    import subprocess
    subprocess.run([WIND_CEM, "--in", os.path.join(DER, "rows.jsonl"), "--out", os.path.join(DER, "pred.jsonl")], check=True)


CLS = [0.0254, 0.0762, 0.1524, 0.3048]


def cls(h):
    return 1 + sum(h >= b for b in CLS)


def stats(p, o):
    p, o = np.asarray(p), np.asarray(o); e = p - o
    if len(e) < 2:
        return {"n": int(len(e))}
    big = o >= 0.1
    return {"n": int(len(e)), "mae": round(float(np.abs(e).mean()), 4), "rmse": round(float(np.sqrt((e ** 2).mean())), 4),
            "bias": round(float(e.mean()), 4), "medianBias": round(float(np.median(e)), 4), "r": round(float(np.corrcoef(p, o)[0, 1]), 3),
            "medianRelErr_obsGe0.1": round(float(np.median(np.abs(e[big]) / o[big])), 3) if big.any() else None,
            "meanObs": round(float(o.mean()), 4), "meanPred": round(float(p.mean()), 4)}


def cat(p, o):
    P = np.array([cls(x) for x in p]); O = np.array([cls(x) for x in o])
    sev = ((P == 1) & (O >= 4)) | ((P >= 4) & (O == 1)) | (np.abs(P - O) >= 3)
    conf = [[int(((P == i) & (O == j)).sum()) for j in range(1, 6)] for i in range(1, 6)]
    return {"n": int(len(P)), "exact": round(float((P == O).mean()), 3), "within1": round(float((np.abs(P - O) <= 1).mean()), 3),
            "severe": round(float(sev.mean()), 3), "confusion_rowsPred_colsObs": conf}


def metrics(outp):
    rows = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(DER, "rows.jsonl"))}
    pred = [json.loads(l) for l in open(os.path.join(DER, "pred.jsonl"))]
    recs = []
    for q in pred:
        r = rows[q["id"]]
        recs.append({**{k: r[k] for k in ("station", "time", "windMS", "fetchM", "hm0Obs")}, "variant": q["id"].split("|")[2],
                     "hm0": q["hm0MidM"], "regime": q["regime"], "dur": q["durationH"], "month": int(r["time"][5:7])})
    out = {}
    for var in ("nodepth", "depth"):
        R = [x for x in recs if x["variant"] == var]
        if not R:
            continue
        P = [x["hm0"] for x in R]; O = [x["hm0Obs"] for x in R]
        sec = {"hourly": stats(P, O), "categories": cat(P, O)}
        small = [x for x in R if x["hm0Obs"] < 0.3]
        sec["obsBelow0.3m"] = stats([x["hm0"] for x in small], [x["hm0Obs"] for x in small])
        # event level: daily means per station
        by = {}
        for x in R:
            by.setdefault((x["station"], x["time"][:10]), []).append(x)
        ev = [(np.mean([y["hm0"] for y in v]), np.mean([y["hm0Obs"] for y in v])) for v in by.values()]
        sec["eventDaily"] = {**stats([a for a, _ in ev], [b for _, b in ev]), **{"categories": cat([a for a, _ in ev], [b for _, b in ev])}}
        def split(key, bins):
            res = {}
            for lo, hi, lab in bins:
                s = [x for x in R if x[key] is not None and lo <= x[key] < hi]
                res[lab] = {**stats([x["hm0"] for x in s], [x["hm0Obs"] for x in s]), "within1": cat([x["hm0"] for x in s], [x["hm0Obs"] for x in s])["within1"] if s else None}
            return res
        sec["byWind"] = split("windMS", [(0, 2, "<2"), (2, 4, "2-4"), (4, 6.5, "4-6.5"), (6.5, 9, "6.5-9"), (9, 99, ">=9")])
        sec["byFetch"] = split("fetchM", [(0, 250, "<250m"), (250, 1000, "250m-1km"), (1000, 3000, "1-3km"), (3000, 10000, "3-10km"), (10000, 1e9, ">10km")])
        sec["byDuration"] = split("dur", [(0, 2, "<2h"), (2, 6, "2-6h"), (6, 99, ">=6h")])
        sec["byStation"] = {s: stats([x["hm0"] for x in R if x["station"] == s], [x["hm0Obs"] for x in R if x["station"] == s]) for s in STATIONS}
        sec["byRegime"] = {g: stats([x["hm0"] for x in R if x["regime"] == g], [x["hm0Obs"] for x in R if x["regime"] == g]) for g in sorted({x["regime"] for x in R})}
        sec["byMonth"] = {m: stats([x["hm0"] for x in R if x["month"] == m], [x["hm0Obs"] for x in R if x["month"] == m]) for m in sorted({x["month"] for x in R})}
        out[var] = sec
    out["stations"] = json.load(open(os.path.join(DER, "stations.json")))
    json.dump(out, open(outp, "w"), indent=1)
    print("wrote", outp)


if __name__ == "__main__":
    {"build": build, "run": run}.get(sys.argv[1], lambda: metrics(sys.argv[2]))()
