"""Bowfishing §25–28: Gridded LAMP vs NBM (pre-registered: bowfishing/WIND_GLMP_PREREG.md, sha cc39e410…).

  python research/glmp_eval.py fetch [--workers 8]   # synoptic CAL+H1 inits; only leads 1/3/6/12/18 via GRIB message byte ranges
  python research/glmp_eval.py eval OUT.json

GLMP run HH:30 has reference time HH:00 and steps 1..25 h (message k = step k+1), verified per message from GRIB keys."""
import hashlib, json, os, pickle, struct, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
import numpy as np
from sector_wind.grib import decode, grid, cells_in_bbox
from sector_wind.interp import CutoutIndex, blend, blend_wind
from sector_wind.ingest import load_config
from sector_wind.sample import circular_error
from sector_wind import bowfishing as BF

B = "https://noaa-glmp-pds.s3.amazonaws.com"
OUT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50/glmp")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
LEADS = (1, 3, 6, 12, 18)
VARS = ("wspd", "wdir", "wgst")
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 18, tzinfo=timezone.utc)
TRANSFER = {"8A1", "9A4", "15M"}
MPH, KT = 0.44704, 0.514444


def rng(url, a, b):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}", "User-Agent": "SectorWind research"})
    for k in range(4):
        try:
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception:
            if k == 3:
                raise


def offsets(url, n=25):
    out, off = [], 0
    for _ in range(n):
        h = rng(url, off, off + 15)
        if h[:4] != b"GRIB":
            break
        ln = struct.unpack(">Q", h[8:16])[0]; out.append((off, off + ln - 1)); off += ln
    return out


_W = {}


def weights(gkey):
    if gkey not in _W:
        cfg = load_config(); lat, lon = grid(gkey); nx = int(gkey.split(":")[1].split("x")[0])
        w = {}
        for lake, lc in cfg["lakes"].items():
            cells = cells_in_bbox(gkey, tuple(lc["bbox"]))
            ci = CutoutIndex(list(map(int, cells)), lat[cells].tolist(), lon[cells].tolist(), nx)
            for sid, s in cfg["stations"].items():
                if s["lake"] == lake:
                    w[sid] = (cells, ci.weights(s["lat"], s["lon"]))
        _W[gkey] = w
    return _W[gkey]


def one(t):
    p = os.path.join(OUT, f"{t:%Y%m%d%H}.json")
    if os.path.exists(p):
        return t, "skip"
    rec = {"init": t.isoformat(), "run": f"{t:%Y%m%d}/glmp.t{t:%H}30z", "values": {}, "provenance": {}}
    try:
        fields = {}
        for v in VARS:
            url = f"{B}/glmp.{t:%Y%m%d}/glmp.t{t:%H}30z.fcsts_{v}.g.co.grib2"
            offs = offsets(url)
            for L in LEADS:
                a, b = offs[L - 1]; blob = rng(url, a, b); f = decode(blob)
                fields[(v, L)] = f
                rec["provenance"][f"{v}|{L}"] = {"url": url, "bytes": [a, b], "sha256": hashlib.sha256(blob).hexdigest()}
        W = weights(fields[("wspd", 1)].grid_key)
        for sid, (cells, wt) in W.items():
            rec["values"][sid] = {}
            for L in LEADS:
                val = lambda f: np.where(f.missing, np.nan, f.values)[cells]
                s, d, g = val(fields[("wspd", L)]), val(fields[("wdir", L)]), val(fields[("wgst", L)])
                sp, dr = blend_wind(list(s), list(d), wt)
                rec["values"][sid][str(L)] = [sp, dr, blend(list(g), wt)]
    except Exception as e:
        return t, f"error {e!r}"[:200]
    os.makedirs(OUT, exist_ok=True); json.dump(rec, open(p, "w"))
    return t, "ok"


def fetch(workers):
    ts, t = [], START
    while t <= END:
        ts.append(t); t += timedelta(hours=6)
    with ThreadPoolExecutor(workers) as ex:
        for t, r in ex.map(one, ts):
            print(t.isoformat(), r, flush=True)
    print("GLMP DONE", flush=True)


def d1(P, key, rows_filter):
    """BWIS D1: share of rows where P(forecast wind) == P(observed wind), equal weight over 6 fetches."""
    sel = [p for p in P if rows_filter(p)]
    if not sel:
        return None, 0
    acc = [np.mean([BF.decision_class(p[key], f) == BF.decision_class(p["obsS"], f) for p in sel]) for f in (100, 250, 500, 1000, 2000, 5000)]
    return float(np.mean(acc)), len(sel)


def metrics(P, key, dkey, gkey):
    night = [p for p in P if p["night"]]
    e = np.array([p[key] - p["obsS"] for p in P]); en = np.array([p[key] - p["obsS"] for p in night])
    dd = np.array([circular_error(p[dkey], p["obsD"]) for p in P if p[dkey] is not None and p["obsD"] is not None and p[key] >= 2.6 and p["obsS"] >= 2.6])
    w10 = [p for p in P if p["obsS"] >= 10 * MPH]
    ev = lambda thr, fk, ok: (sum(p[fk] is not None and p[fk] >= thr and (p[ok] or 0) >= thr for p in P), sum((p[ok] or 0) >= thr for p in P),
                              sum(p[fk] is not None and p[fk] >= thr and (p[ok] or 0) < thr for p in P))
    h15, o15, f15 = ev(15 * MPH, key, "obsS"); h20, o20, f20 = ev(20 * KT, gkey, "obsG")
    D1, n1 = d1(P, key, lambda p: p["night"] and p["obsS"] >= 5 * MPH)
    D10, n10 = d1(P, key, lambda p: p["night"] and p["obsS"] >= 10 * MPH)
    D10a, n10a = d1(P, key, lambda p: p["obsS"] >= 10 * MPH)
    return {"n": len(P), "mae": float(np.abs(e).mean()), "nightMAE": float(np.abs(en).mean()), "nightBias": float(en.mean()), "bias": float(e.mean()),
            "dir22": float((dd <= 22.5).mean()), "circMAE": float(dd.mean()), "windyMAE": float(np.mean([abs(p[key] - p["obsS"]) for p in w10])), "nWindy": len(w10),
            "ev15": {"hit": h15, "obs": o15, "fa": f15}, "gust20": {"hit": h20, "obs": o20, "fa": f20},
            "D1": D1, "nD1": n1, "D1_obs10_night": D10, "nD1_10n": n10, "D1_obs10_all": D10a, "nD1_10a": n10a}


def evaluate(outp):
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["synoptic"] and r["set"] in ("CAL", "H1")]
    P = []
    for r in R:
        p = os.path.join(OUT, f"{r['init']:%Y%m%d%H}.json")
        if not os.path.exists(p):
            continue
        v = json.load(open(p))["values"].get(r["station"], {}).get(str(r["lead"]))
        if not v or v[0] is None:
            continue
        P.append({**r, "gS": v[0], "gD": v[1], "gG": v[2]})
    res = {"rows": len(P), "stations": sorted({p["station"] for p in P})}
    for name, sel in (("all", lambda p: True), ("transfer", lambda p: p["station"] in TRANSFER), ("le6h", lambda p: p["lead"] <= 6),
                      ("ge12h", lambda p: p["lead"] >= 12), ("CAL", lambda p: p["set"] == "CAL"), ("H1", lambda p: p["set"] == "H1")):
        S = [p for p in P if sel(p)]
        res[name] = {"glmp": metrics(S, "gS", "gD", "gG"), "nbm": metrics(S, "nbmS", "nbmD", "nbmG")}
    def rule(seg):
        g, n = res[seg]["glmp"], res[seg]["nbm"]
        return {"nightMAE": g["nightMAE"] <= n["nightMAE"] + 0.05, "dir": g["dir22"] >= n["dir22"] - 0.02, "D1+0.03": g["D1"] >= n["D1"] + 0.03,
                "D1windy": (g["D1_obs10_night"] or 0) > (n["D1_obs10_night"] or 0)}
    tr = res["transfer"]
    res["rule"] = {"all": rule("all"), "le6h": rule("le6h"), "ge12h": rule("ge12h"),
                   "transfer": {"D1": tr["glmp"]["D1"] > tr["nbm"]["D1"], "nightMAE": tr["glmp"]["nightMAE"] <= tr["nbm"]["nightMAE"] + 0.05}}
    ok = lambda d: all(d.values())
    gen = ok(res["rule"]["transfer"])
    if ok(res["rule"]["le6h"]) and gen:
        res["architecture"] = "GLMP" if ok(res["rule"]["ge12h"]) else "NBM+GLMP lead rule (GLMP <=6 h, NBM 12-18 h)"
    else:
        res["architecture"] = "NBM"
    res["promoteAll"] = ok(res["rule"]["all"]) and gen
    json.dump(res, open(outp, "w"), indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("rows", "rule", "architecture", "promoteAll")}, indent=1))


if __name__ == "__main__":
    {"fetch": lambda: fetch(int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8),
     "eval": lambda: evaluate(sys.argv[2])}[sys.argv[1]]()
