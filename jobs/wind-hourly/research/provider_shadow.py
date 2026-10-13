"""Provider shadow comparison + strong-wind mechanism check on the CAL+H1 corpus ONLY (inits 2026-05-06 .. 2026-10-06).
H2 (inits >= 2026-10-07) is never read: the window end is hard-coded and asserted.
Production proxy = HRRR 10 m wind (U/V) which Stage 3D.1 matched to Open-Meteo Best Match for <= 46 h.

  python research/provider_shadow.py OUT_DIR   -> matrix.csv, provider_shadow.json, strong_wind.json"""
import csv, json, math, os, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend, blend_wind
from sector_wind.validate import load_obs
from sector_wind.sample import parse_iso, circular_error
from sector_wind.brain import tonight as TN

MPH = 0.44704
ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
assert END < datetime(2026, 10, 7, tzinfo=timezone.utc), "H2 is sealed"
LEADS = (6, 12, 18)
CATS = TN.CATEGORIES


def hrrr_point(step, wt):
    u, v = blend(step["u"], wt), blend(step["v"], wt)
    if u is None or v is None:
        return None, None
    s = math.hypot(u, v)
    return s, (math.degrees(math.atan2(-u, -v)) % 360 if s >= 0.5 else None)


def build():
    store, cfg = LocalStore(ROOT), load_config()
    obs = load_obs(store, START - timedelta(days=1), END + timedelta(days=2))
    by_lake = defaultdict(list)
    for sid, s in cfg["stations"].items():
        by_lake[s["lake"]].append(sid)
    wn, wh, rows = {}, {}, []
    t = START
    while t <= END:
        if t.hour in (12, 18):
            for lake in cfg["lakes"]:
                c = store.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
                h = store.get_json(f"hrrruv/{lake}/{t:%Y%m%d%H}.json.gz")
                if not c:
                    continue
                if lake not in wn:
                    g = store.get_json(c["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                    wn[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in by_lake[lake]}
                if h and lake not in wh:
                    g = store.get_json(h["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                    wh[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in by_lake[lake]}
                hs = {x["leadHours"]: x for x in (h or {}).get("steps", [])}
                for stp in c["steps"]:
                    L = stp["leadHours"]
                    if not ((t.hour == 12 and L in (12, 18)) or (t.hour == 18 and L in (6, 12))):
                        continue
                    vt = parse_iso(stp["validTime"])
                    for sid, w in wn[lake].items():
                        o = obs.get((sid, vt))
                        ns, nd = blend_wind(stp["speedMS"], stp["dirFromDeg"], w)
                        p90 = blend(stp["speedP90"], w) if stp.get("speedP90") else None
                        hv = hs.get(L)
                        hsp, hdr = (hrrr_point(hv, wh[lake][sid]) if (hv and lake in wh) else (None, None))
                        rows.append({"lake": lake, "station": sid, "init": t, "valid": vt, "lead": L,
                                     "nbmMph": None if ns is None else ns / MPH, "nbmDir": nd, "nbmP90Mph": None if p90 is None else p90 / MPH,
                                     "omMph": None if hsp is None else hsp / MPH, "omDir": hdr,
                                     "obsMph": None if not o else o["speedMS"] / MPH, "obsDir": None if not o else o["dirFromDeg"],
                                     "initAgeNote": "archived cycle"})
        t += timedelta(hours=1)
    return rows


def cat(x):
    return None if x is None else TN.category(x)


def agg(rows, label):
    r = [x for x in rows if x["obsMph"] is not None and x["nbmMph"] is not None and x["omMph"] is not None]
    if not r:
        return {"label": label, "n": 0}
    en = np.array([x["nbmMph"] - x["obsMph"] for x in r]); eo = np.array([x["omMph"] - x["obsMph"] for x in r])
    win = int(sum(abs(a) + 0.5 < abs(b) for a, b in zip(en, eo))); loss = int(sum(abs(b) + 0.5 < abs(a) for a, b in zip(en, eo)))
    d = [x for x in r if x["obsDir"] is not None and x["obsMph"] * MPH >= 2.6 and x["nbmDir"] is not None and x["omDir"] is not None and x["nbmMph"] >= 5 and x["omMph"] >= 5]
    dn = [circular_error(x["nbmDir"], x["obsDir"]) for x in d]; do = [circular_error(x["omDir"], x["obsDir"]) for x in d]
    cn = np.mean([cat(x["nbmMph"]) == cat(x["obsMph"]) for x in r]); co = np.mean([cat(x["omMph"]) == cat(x["obsMph"]) for x in r])
    return {"label": label, "n": len(r), "nbm": {"biasMph": round(float(en.mean()), 2), "maeMph": round(float(np.abs(en).mean()), 2), "catExact": round(float(cn), 3)},
            "openMeteoProxy": {"biasMph": round(float(eo.mean()), 2), "maeMph": round(float(np.abs(eo).mean()), 2), "catExact": round(float(co), 3)},
            "speedWinner": {"nbm": win, "openMeteoProxy": loss, "tie": len(r) - win - loss},
            "direction(both>=5mph,obs>=2.6m/s)": {"n": len(d), "nbmWithin22_5": round(float(np.mean([e <= 22.5 for e in dn])), 3) if dn else None,
                                                  "omWithin22_5": round(float(np.mean([e <= 22.5 for e in do])), 3) if do else None,
                                                  "nbmCircMAE": round(float(np.mean(dn)), 1) if dn else None, "omCircMAE": round(float(np.mean(do)), 1) if do else None},
            "disagreementMeanAbsMph": round(float(np.mean([abs(x["nbmMph"] - x["omMph"]) for x in r])), 2)}


def main(out):
    os.makedirs(out, exist_ok=True)
    R = build()
    res = {"window": "CAL+H1 only, inits 2026-05-06..2026-10-06; H2 not read", "rows": len(R)}
    miss = defaultdict(int)
    for x in R:
        if x["obsMph"] is None: miss["noObservation(=PROVIDER DISAGREEMENT only)"] += 1
        if x["omMph"] is None: miss["openMeteoProxyMissing"] += 1
        if x["nbmMph"] is None: miss["nbmMissing"] += 1
    res["missing"] = dict(miss)
    res["overall"] = agg(R, "all tonight rows")
    res["byLake"] = {lk: agg([x for x in R if x["lake"] == lk], lk) for lk in sorted({x["lake"] for x in R})}
    res["byLead"] = {f"+{L}h": agg([x for x in R if x["lead"] == L], f"+{L}h") for L in (6, 12, 18)}
    bands = ((0, 5, "obs<5"), (5, 10, "obs5-10"), (10, 99, "obs>=10"))
    res["byObservedClass"] = {lab: agg([x for x in R if x["obsMph"] is not None and lo <= x["obsMph"] < hi], lab) for lo, hi, lab in bands}
    res["byForecastClassNbm"] = {lab: agg([x for x in R if x["nbmMph"] is not None and lo <= x["nbmMph"] < hi], "nbm " + lab) for lo, hi, lab in bands}
    sect = lambda d: None if d is None else int(((d + 22.5) % 360) // 45)
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    res["byObservedDirectionSector"] = {names[k]: agg([x for x in R if sect(x["obsDir"]) == k and x["obsMph"] and x["obsMph"] * MPH >= 2.6], names[k]) for k in range(8)}
    # stronger-wind detection (obs >= 10 mph)
    sw = {}
    for thr in (10,):
        rr = [x for x in R if x["obsMph"] is not None and x["nbmMph"] is not None and x["omMph"] is not None]
        ev = [x["obsMph"] >= thr for x in rr]
        def pf(flag):
            f = [flag(x) for x in rr]; h = sum(a and b for a, b in zip(f, ev)); n = sum(f)
            return {"flagged": n, "POD": round(h / max(sum(ev), 1), 3), "FAR": round((n - h) / max(n, 1), 3)}
        sw = {"events": sum(ev), "nbmPointGE10": pf(lambda x: x["nbmMph"] >= thr), "openMeteoProxyPointGE10": pf(lambda x: x["omMph"] >= thr),
              "nbmP90GE10(riskFlag)": pf(lambda x: x["nbmP90Mph"] is not None and x["nbmP90Mph"] >= thr),
              "openMeteoProxyGE8": pf(lambda x: x["omMph"] >= 8), "nbmP90GE8": pf(lambda x: x["nbmP90Mph"] is not None and x["nbmP90Mph"] >= 8)}
    res["strongerWindDetection(obs>=10mph, tonight rows)"] = sw
    # trend easing 00Z -> 06Z
    by = defaultdict(dict)
    for x in R:
        by[(x["station"], x["init"])][x["valid"].hour] = x
    pairs = [(d[0], d[6]) for d in by.values() if 0 in d and 6 in d and all(v["obsMph"] is not None and v["nbmMph"] is not None and v["omMph"] is not None for v in (d[0], d[6]))]
    cl = lambda dlt: 0 if dlt <= -2 else 2 if dlt >= 2 else 1
    tr = {}
    for nm, key in (("nbm", "nbmMph"), ("openMeteoProxy", "omMph")):
        o = [cl(b["obsMph"] - a["obsMph"]) for a, b in pairs]; f = [cl(b[key] - a[key]) for a, b in pairs]
        fe = [(oo, ff) for oo, ff in zip(o, f) if ff == 0]
        tr[nm] = {"pairs": len(pairs), "accuracy": round(float(np.mean([a == b for a, b in zip(o, f)])), 3), "alwaysSteady": round(float(np.mean([a == 1 for a in o])), 3),
                  "easingForecasts": len(fe), "easingPrecision": round(float(np.mean([a == 0 for a, _ in fe])), 3) if fe else None}
    res["trendEasing_00Zto06Z"] = tr
    json.dump(res, open(os.path.join(out, "provider_shadow.json"), "w"), indent=1, default=int)
    with open(os.path.join(out, "matrix.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lakeId", "station", "initUtc", "validUtc", "leadH", "nbmDir", "omDir", "dirDiffDeg", "nbmMph", "omMph", "speedDiffMph", "nbmCat", "omCat", "obsDir", "obsMph",
                    "nbmErrMph", "omErrMph", "nbmP90Mph", "nbmFreshnessH(init age at valid-lead)", "omFreshness", "winner", "notes"])
        for x in R:
            ne = None if x["obsMph"] is None or x["nbmMph"] is None else x["nbmMph"] - x["obsMph"]
            oe = None if x["obsMph"] is None or x["omMph"] is None else x["omMph"] - x["obsMph"]
            win = "unknown(no truth: PROVIDER DISAGREEMENT)" if ne is None or oe is None else ("nbm" if abs(ne) + 0.5 < abs(oe) else "openMeteoProxy" if abs(oe) + 0.5 < abs(ne) else "tie")
            dd = None if x["nbmDir"] is None or x["omDir"] is None else round(circular_error(x["nbmDir"], x["omDir"]))
            w.writerow([x["lake"], x["station"], x["init"].strftime("%Y-%m-%dT%H:%MZ"), x["valid"].strftime("%Y-%m-%dT%H:%MZ"), x["lead"],
                        None if x["nbmDir"] is None else round(x["nbmDir"]), None if x["omDir"] is None else round(x["omDir"]), dd,
                        None if x["nbmMph"] is None else round(x["nbmMph"], 1), None if x["omMph"] is None else round(x["omMph"], 1),
                        None if x["nbmMph"] is None or x["omMph"] is None else round(x["nbmMph"] - x["omMph"], 1), cat(x["nbmMph"]), cat(x["omMph"]),
                        None if x["obsDir"] is None else round(x["obsDir"]), None if x["obsMph"] is None else round(x["obsMph"], 1),
                        None if ne is None else round(ne, 1), None if oe is None else round(oe, 1), None if x["nbmP90Mph"] is None else round(x["nbmP90Mph"], 1),
                        x["lead"], x["lead"], win, "replayed archive; OM proxy=HRRR"])
    # ---- strong-wind mechanisms (shipped rules) on rows that have NBM + P90 + obs
    S = [x for x in R if x["obsMph"] is not None and x["nbmMph"] is not None and x["nbmP90Mph"] is not None]
    def rule(x):
        flag = TN.breezy_flag(x["nbmP90Mph"]); conf = TN.confidence(x["nbmMph"], flag, False)[0]
        return flag, conf, cat(x["nbmMph"]), cat(x["nbmP90Mph"])
    sres = {"rows": len(S)}
    for thr in (10, 15):
        ev = [x for x in S if x["obsMph"] >= thr]
        fl = [rule(x)[0] for x in ev]
        silent = [x for x in ev if not rule(x)[0] and rule(x)[2] in ("calm", "light")]
        sres[f"obs>={thr}"] = {"rows": len(ev), "flagged": sum(fl), "missRate": round(1 - sum(fl) / max(len(ev), 1), 3),
                              "silentMiss(no flag and category calm/light)": len(silent), "silentMissRate": round(len(silent) / max(len(ev), 1), 3),
                              "p90CoversObserved": round(float(np.mean([x["nbmP90Mph"] >= x["obsMph"] for x in ev])), 3),
                              "meanP90MinusObs": round(float(np.mean([x["nbmP90Mph"] - x["obsMph"] for x in ev])), 2),
                              "categoryFloorWrongBy>=1": round(float(np.mean([CATS.index(rule(x)[2]) < CATS.index(cat(x["obsMph"])) for x in ev])), 3)}
    allflag = [rule(x)[0] for x in S]; ob10 = [x["obsMph"] >= 10 for x in S]
    sres["rowLevel"] = {"flagShare": round(float(np.mean(allflag)), 4), "falseAlarmShareOfFlags(obs<8)": round(float(np.mean([x["obsMph"] < 8 for x, f in zip(S, allflag) if f])), 3),
                        "P90CoverageOverall": round(float(np.mean([x["nbmP90Mph"] >= x["obsMph"] for x in S])), 3)}
    conf = defaultdict(list)
    for x in S:
        conf[rule(x)[1]].append(x["obsMph"] >= 10)
    sres["confidenceLabel_P(obs>=10)"] = {k: {"rows": len(v), "rate": round(float(np.mean(v)), 4)} for k, v in sorted(conf.items())}
    # night level: station-night (init date) -> max obs over the window vs any flag
    nights = defaultdict(lambda: [False, False, 0.0])
    for x in S:
        k = (x["station"], x["init"].date())
        nights[k][0] |= bool(rule(x)[0]); nights[k][1] |= x["obsMph"] >= 10; nights[k][2] = max(nights[k][2], x["obsMph"])
    n = list(nights.values()); hit = sum(a and b for a, b, _ in n); fl_n = sum(a for a, _, _ in n); ev_n = sum(b for _, b, _ in n)
    sres["nightLevel"] = {"stationNights": len(n), "breezyNights(obs>=10 any hour)": ev_n, "flaggedNights": fl_n, "POD": round(hit / max(ev_n, 1), 3), "FAR": round((fl_n - hit) / max(fl_n, 1), 3),
                          "P(breezy|flagged night)": round(hit / max(fl_n, 1), 3), "P(breezy|unflagged night)": round((ev_n - hit) / max(len(n) - fl_n, 1), 4)}
    by_st = defaultdict(lambda: [0, 0, 0, 0])
    for (st, _), (a, b, _m) in nights.items():
        by_st[st][0] += 1; by_st[st][1] += b; by_st[st][2] += a; by_st[st][3] += a and b
    sres["byStationNight"] = {st: {"nights": v[0], "breezy": v[1], "flagged": v[2], "hit": v[3]} for st, v in sorted(by_st.items())}
    sres["thresholdSensitivity(info only; product threshold stays 10)"] = {}
    for th in (8, 9, 10, 12):
        f = [x["nbmP90Mph"] >= th for x in S]; h = sum(a and b for a, b in zip(f, ob10)); nf = sum(f)
        sres["thresholdSensitivity(info only; product threshold stays 10)"][str(th)] = {"flagShare": round(nf / len(S), 4), "POD": round(h / max(sum(ob10), 1), 3), "FAR": round((nf - h) / max(nf, 1), 3)}
    json.dump(sres, open(os.path.join(out, "strong_wind.json"), "w"), indent=1, default=int)
    print(json.dumps({"overall": res["overall"], "stronger": sw, "trend": tr, "missing": res["missing"]}, indent=1)); print(json.dumps(sres, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
