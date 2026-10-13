"""Wind Brain campaign V1-V5 (docs/wind-research/WIND_RESEARCH_PREREG.md). Read-only over the frozen NBM v5.0 corpus.
Run with the wind venv:  ~/Library/Caches/sector-wind/venv/bin/python research/wind-brain/bowfishing_validation.py OUT.json
Reuses sector_wind (brain/wind branch worktree). Never touches H2 (inits >= 2026-10-07)."""
import json, os, pickle, sys
from collections import defaultdict
from datetime import datetime, timezone
sys.path.insert(0, os.path.expanduser("~/Desktop/Development/Sector_Engine-wind/jobs/wind-hourly"))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.validate import collect
from sector_wind.sample import circular_error

MPH = 0.44704
ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
CACHE = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/wind-brain/rows_v50.pkl")
cat = lambda mph: 0 if mph < 5 else 1 if mph < 10 else 2 if mph < 15 else 3
CATN = ["calm<5", "light5-10", "breezy10-15", "windy>=15"]

def rows():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    r = collect(LocalStore(ROOT), load_config(), START, END, (1, 3, 6, 12, 18))
    pickle.dump(r, open(CACHE, "wb")); return r

def dirstats(pairs):
    e = np.array([circular_error(f, o) for f, o in pairs])
    return {"n": len(e), "within22_5": round(float((e <= 22.5).mean()), 3) if len(e) else None,
            "within45": round(float((e <= 45).mean()), 3) if len(e) else None, "circMAE": round(float(e.mean()), 1) if len(e) else None}

def main(out):
    R = rows(); res = {"nRows": len(R)}
    night = lambda r: 1 <= r["validTime"].hour <= 8
    # ---- V1 direction
    v1 = {}
    for scope, sel in (("allHours", lambda r: True), ("night", night)):
        for lg, lo, hi in (("lead<=6", 0, 6), ("lead12-18", 7, 18)):
            rs = [r for r in R if sel(r) and lo <= r["lead"] <= hi and r["rec"][1] is not None and r["rec"][4] is not None]
            for basis, idx in (("byObserved", 3), ("byForecast", 0)):
                for b0, b1 in ((3, 5), (5, 10), (10, 99)):
                    p = [(r["rec"][1], r["rec"][4]) for r in rs if b0 <= r["rec"][idx] / MPH < b1]
                    v1[f"{scope}|{lg}|{basis}|{b0}-{b1}mph"] = dirstats(p)
    res["V1_direction"] = v1
    # ---- V2 speed bias by forecast band and lead
    v2 = {}
    for lead in (1, 3, 6, 12, 18):
        for b0, b1, lab in ((0, 5, "<5"), (5, 10, "5-10"), (10, 15, "10-15"), (15, 99, ">=15")):
            e = [(r["rec"][0] - r["rec"][3]) / MPH for r in R if night(r) and r["lead"] == lead and b0 <= r["rec"][0] / MPH < b1]
            o = [(r["rec"][0] - r["rec"][3]) / MPH for r in R if night(r) and r["lead"] == lead and b0 <= r["rec"][3] / MPH < b1]
            v2[f"night|+{lead}h|{lab}"] = {"byForecast": {"n": len(e), "biasMph": round(float(np.mean(e)), 2) if e else None, "maeMph": round(float(np.mean(np.abs(e))), 2) if e else None},
                                          "byObserved": {"n": len(o), "biasMph": round(float(np.mean(o)), 2) if o else None, "maeMph": round(float(np.mean(np.abs(o))), 2) if o else None}}
    res["V2_speed"] = v2
    # ---- V3 tonight categories (init 12Z lead12/18 -> 00Z/06Z ; init 18Z lead 6/12 -> 00Z/06Z)
    def tonight(r):
        i, l, h = r["init"].hour, r["lead"], r["validTime"].hour
        return (i == 12 and l in (12, 18)) or (i == 18 and l in (6, 12))
    T = [r for r in R if tonight(r)]
    obsc = np.array([cat(r["rec"][3] / MPH) for r in T]); fc = np.array([cat(r["rec"][0] / MPH) for r in T])
    modal = int(np.bincount(obsc).argmax())
    conf = np.zeros((4, 4), int)
    for o, f in zip(obsc, fc): conf[o, f] += 1
    res["V3_tonightCategories"] = {"n": len(T), "exact": round(float((obsc == fc).mean()), 3), "within1": round(float((abs(obsc - fc) <= 1).mean()), 3),
        "modalBaselineExact": round(float((obsc == modal).mean()), 3), "modal": CATN[modal], "confusion_rows_obs_cols_fc": conf.tolist(), "cats": CATN,
        "obsShare": [round(float((obsc == k).mean()), 3) for k in range(4)], "fcShare": [round(float((fc == k).mean()), 3) for k in range(4)]}
    # ---- V4 trend 00Z -> 06Z, V5 direction shift
    by = defaultdict(dict)
    for r in R:
        i, l = r["init"], r["lead"]
        if (i.hour == 18 and l in (6, 12)) or (i.hour == 12 and l in (12, 18)):
            by[(r["station"], i)][r["validTime"].hour] = r["rec"]
    cls = lambda d: 0 if d <= -2 else 2 if d >= 2 else 1
    tr_o, tr_f, lay_o, lay_f, ds_o, ds_f = [], [], [], [], [], []
    for k, d in by.items():
        if 0 in d and 6 in d:
            a, b = d[0], d[6]
            do = (b[3] - a[3]) / MPH; df = (b[0] - a[0]) / MPH
            tr_o.append(cls(do)); tr_f.append(cls(df))
            lay_o.append(a[3] / MPH >= 8 and b[3] / MPH <= 5); lay_f.append(a[0] / MPH >= 8 and b[0] / MPH <= 5)
            if min(a[3], b[3], a[0], b[0]) / MPH >= 5 and None not in (a[1], b[1], a[4], b[4]):
                ds_o.append(circular_error(a[4], b[4]) >= 45); ds_f.append(circular_error(a[1], b[1]) >= 45)
    to, tf = np.array(tr_o), np.array(tr_f)
    c3 = np.zeros((3, 3), int)
    for o, f in zip(to, tf): c3[o, f] += 1
    pod = lambda o, f: (round(float((np.array(o) & np.array(f)).sum() / max(1, np.sum(o))), 3), round(float((np.array(f) & ~np.array(o)).sum() / max(1, np.sum(f))), 3), int(np.sum(o)), int(np.sum(f)))
    res["V4_trend_00Z_to_06Z"] = {"n": len(to), "accuracy": round(float((to == tf).mean()), 3), "alwaysSteadyBaseline": round(float((to == 1).mean()), 3),
        "confusion_rows_obs_cols_fc[easing,steady,rising]": c3.tolist(),
        "layDown": dict(zip(["POD", "FAR", "obsEvents", "fcEvents"], pod(lay_o, lay_f)))}
    res["V5_dirShift45"] = dict(zip(["POD", "FAR", "obsEvents", "fcEvents"], pod(ds_o, ds_f))) | {"n": len(ds_o)}
    # ---- station / lake split of night direction >=5mph forecast (does it hold everywhere)
    st = defaultdict(list)
    for r in R:
        if night(r) and r["lead"] <= 12 and r["rec"][0] / MPH >= 5 and r["rec"][1] is not None and r["rec"][4] is not None:
            st[r["station"]].append((r["rec"][1], r["rec"][4]))
    res["V1_nightByStation_fc>=5mph_lead<=12"] = {k: dirstats(v) for k, v in sorted(st.items())}
    json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1)[:200000])

if __name__ == "__main__":
    main(sys.argv[1])
