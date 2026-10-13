"""Score Acceleration §20–24: WindNinja local-vector test (pre-registered: score-acceleration/WIND_WINDNINJA_PREREG.md, sha 71976931…).

  python research/windninja_eval.py rows        # synoptic CAL+H1 rows for 10 PRIMARY stations (8 frozen from rows.pkl + 4A9, HUA built here)
  python research/windninja_eval.py eval OUT    # apply the WindNinja response tables (response.txt) to raw NBM; same rows; untuned

Response table: WindNinja 4.0.0 mass-conserving, 12 km domain, 120 m mesh, grass, 36 directions at 5 m/s.
WindNinja(case) = speed x ratio(dir), dir + turn(dir), linearly interpolated in direction."""
import csv, io, json, math, os, pickle, sys, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend, blend_wind
from sector_wind.sample import circular_error

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration")
WN = os.path.expanduser("~/Library/Caches/sector-wind/windninja/response.txt")
EXTRA = {"4A9": (34.4737, -85.7214, "guntersville"), "HUA": (34.6786, -86.6848, "wheeler")}
CAL_END, H1_START, H1_END = datetime(2026, 8, 15, 23, tzinfo=timezone.utc), datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
KT = 0.514444


def iem_obs(sid):
    url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={sid}&data=sknt&data=drct&data=gust&tz=UTC&format=onlycomma"
           "&year1=2026&month1=5&day1=5&year2=2026&month2=10&day2=8&missing=null&report_type=3&report_type=4")
    txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SectorWind research"}), timeout=300).read().decode()
    best = {}
    for r in csv.DictReader(io.StringIO(txt)):
        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        h = (t + timedelta(minutes=30)).replace(minute=0); dt = abs((t - h).total_seconds())
        if dt > 600 or r["sknt"] in ("null", ""):
            continue
        if h not in best or dt < best[h][0]:
            f = lambda k: None if r[k] in ("null", "", "M") else float(r[k])
            s = f("sknt") * KT; d = f("drct")
            best[h] = (dt, s, d if s > 0 else None, f("gust") * KT if f("gust") else None)
    return {h: v[1:] for h, v in best.items()}


def rows():
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["synoptic"] and r["set"] in ("CAL", "H1")]
    out = [{k: r[k] for k in ("station", "init", "valid", "lead", "night", "set", "nbmS", "nbmD", "obsS", "obsD")} for r in R]
    st = LocalStore(ROOT)
    for sid, (la, lo, lake) in EXTRA.items():
        obs = iem_obs(sid); W = None; t = datetime(2026, 5, 6, tzinfo=timezone.utc)
        while t <= H1_END:
            c = st.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if c:
                if W is None:
                    g = st.get_json(c["grid"]); W = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"]).weights(la, lo)
                for s in c["steps"]:
                    vt = datetime.strptime(s["validTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    o = obs.get(vt)
                    if not o:
                        continue
                    ns, nd = blend_wind(s["speedMS"], s["dirFromDeg"], W)
                    setn = "CAL" if (t <= CAL_END and vt < datetime(2026, 8, 15, tzinfo=timezone.utc)) else ("H1" if t >= H1_START else "GAP")
                    if ns is None or setn == "GAP":
                        continue
                    out.append({"station": sid, "init": t, "valid": vt, "lead": s["leadHours"], "night": 1 <= vt.hour <= 8, "set": setn,
                                "nbmS": ns, "nbmD": nd, "obsS": o[0], "obsD": o[1]})
            t += timedelta(hours=6)
        print(sid, sum(r["station"] == sid for r in out), flush=True)
    os.makedirs(OUT, exist_ok=True)
    pickle.dump(out, open(os.path.join(OUT, "windninja_rows.pkl"), "wb")); print(len(out))


def tables():
    T = defaultdict(dict); lin = defaultdict(dict)
    for l in open(WN):
        p = l.split()
        if len(p) != 5 or p[3] in ("NA", ""):
            continue
        sid, d, spd, v, a = p[0], int(p[1]), float(p[2]), float(p[3]), float(p[4])
        if spd == 5:
            T[sid][d] = (v / 5.0, ((a - d + 180) % 360) - 180)
        else:
            lin[sid][(d, spd)] = v / spd
    return T, lin


def apply(T, sid, s, d):
    tb = T[sid]; d0 = int(d // 10 * 10) % 360; d1 = (d0 + 10) % 360; w = (d - d0 // 1) / 10 if d0 <= d else 0
    w = ((d - d0) % 360) / 10
    r = (1 - w) * tb[d0][0] + w * tb[d1][0]; tn = (1 - w) * tb[d0][1] + w * tb[d1][1]
    return s * r, (d + tn) % 360, r, tn


def metrics(rows_, key):
    e = np.array([r[key + "S"] - r["obsS"] for r in rows_])
    dd = np.array([circular_error(r[key + "D"], r["obsD"]) for r in rows_])
    ni = np.array([r["night"] for r in rows_])
    return {"n": len(rows_), "speedMAE": float(np.abs(e).mean()), "bias": float(e.mean()), "nightSpeedMAE": float(np.abs(e[ni]).mean()) if ni.any() else None,
            "dir22": float((dd <= 22.5).mean()), "dir45": float((dd <= 45).mean()), "circMAE": float(dd.mean()),
            "nightDir22": float((dd[ni] <= 22.5).mean()) if ni.any() else None}


def evaluate(outp):
    R = pickle.load(open(os.path.join(OUT, "windninja_rows.pkl"), "rb")); T, lin = tables()
    use = []
    for r in R:
        if r["station"] not in T or len(T[r["station"]]) < 36 or r["nbmD"] is None or r["obsD"] is None or r["obsS"] < 2.6 or r["nbmS"] < 2.6:
            continue
        s, d, ratio, turn = apply(T, r["station"], r["nbmS"], r["nbmD"])
        use.append({**r, "wnS": s, "wnD": d, "ratio": ratio, "turn": turn})
    res = {"rows": len(use), "linearity": {sid: {f"{k[0]}@{k[1]}": round(v / T[sid][k[0]][0], 3) for k, v in lin[sid].items()} for sid in lin},
           "responseSummary": {sid: {"ratioMin": round(min(x[0] for x in tb.values()), 3), "ratioMax": round(max(x[0] for x in tb.values()), 3),
                                     "turnAbsMax": round(max(abs(x[1]) for x in tb.values()), 1), "turnAbsMean": round(float(np.mean([abs(x[1]) for x in tb.values()])), 1)}
                               for sid, tb in T.items()}}
    for part in ("all", "CAL", "H1"):
        rs = use if part == "all" else [r for r in use if r["set"] == part]
        res[part] = {"nbm": metrics(rs, "nbm"), "windninja": metrics(rs, "wn")}
    res["byStation"] = {sid: {"nbm": metrics([r for r in use if r["station"] == sid], "nbm"), "windninja": metrics([r for r in use if r["station"] == sid], "wn")}
                        for sid in sorted({r["station"] for r in use})}
    a, b = res["all"]["windninja"], res["all"]["nbm"]
    worse = [s for s, v in res["byStation"].items() if v["windninja"]["dir22"] < v["nbm"]["dir22"] - 0.03]
    res["gate"] = {"dir22Gain": a["dir22"] - b["dir22"], "circMAEGain": b["circMAE"] - a["circMAE"], "speedMAEChange": a["speedMAE"] - b["speedMAE"],
                   "stationsWorseBy0.03": worse,
                   "pass": a["dir22"] >= b["dir22"] + 0.03 and a["circMAE"] <= b["circMAE"] - 1.0 and a["speedMAE"] <= b["speedMAE"] + 0.05 and len(worse) <= 2}
    json.dump(res, open(outp, "w"), indent=1, default=str); print(json.dumps({k: res[k] for k in ("rows", "gate", "linearity")}, indent=1, default=str))


if __name__ == "__main__":
    {"rows": rows, "eval": lambda: evaluate(sys.argv[2])}[sys.argv[1]]()
