"""Build the FRESH 2020-2023 buoy rows (M4 pre-registration) with the frozen Stage 3C method, and evaluate M0/M3/M4.

  python research/wave_fresh.py build
  python research/wave_fresh.py eval OUT.json
  python research/wave_fresh.py swan OUT.json      # re-score the fixed SWAN scenarios incl. M4"""
import json, os, sys
from collections import defaultdict
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import wave_physics as WP
import wave_memory as W

DER = WP.DER
FRESH = os.path.join(DER, "rows_fresh_2020_2023.jsonl")
SEASONS = {"45178": [2020, 2023], "45014": [2020, 2021, 2023], "45163": [2020, 2021, 2022, 2023], "45175": [2020, 2021, 2022, 2023],
           "45202": [2022, 2023], "45165": [2020, 2021, 2022, 2023], "45173": [2020]}


def build():
    st = json.load(open(os.path.join(DER, "stations.json")))
    n = 0
    with open(FRESH, "w") as out:
        for sid, yrs in SEASONS.items():
            lat, lon, zh, depth, _, name = WP.STATIONS[sid]
            table = st[sid]["fetchTableM"]; conv = (10.0 / zh) ** (1 / 7)
            for yr in yrs:
                obs = WP.parse(WP.raw_file(sid, yr))
                for h in sorted(obs):
                    wd, ws, hs = obs[h]
                    if wd is None or ws is None or hs is None or hs <= 0:
                        continue
                    ser = []
                    for k in range(12, -1, -1):
                        o = obs.get(h - timedelta(hours=k))
                        ser.append({"speedMS": o[1] * conv, "dirFromDeg": o[0]} if o and o[1] is not None and o[0] is not None else {"speedMS": None, "dirFromDeg": None})
                    out.write(json.dumps({"station": sid, "time": h.strftime("%Y-%m-%dT%H:%MZ"), "windMS": round(ws * conv, 3), "dirFromDeg": wd,
                                          "fetchM": round(W.nine_ray(table, wd), 1), "hm0Obs": hs, "series": ser, "id": f"{sid}|{h:%Y%m%d%H}|nodepth"}) + "\n")
                    n += 1
            print(sid, yrs, flush=True)
    print("rows", n)


def params():
    ch = json.load(open(W.FITS))["chosen"]
    cont = (ch["M3"]["cont"][0], tuple(ch["M3"]["cont"][1]))
    return {"M0": {}, "M3": {"cont": cont, "tau": ch["M3"]["tau"]}, "M4": {"cont": cont}}


def evaluate(outp):
    st = json.load(open(os.path.join(DER, "stations.json"))); tables = {k: v["fetchTableM"] for k, v in st.items()}
    V = [json.loads(l) for l in open(FRESH)]
    P = params(); preds = {m: [W.predict(r, tables[r["station"]], m, p) for r in V] for m, p in P.items()}
    subs = [W.subsets(r) for r in V]
    res = {"rows": len(V), "bySubset": {}}
    for sub in ("all", "dur<2h", "falling", "veering", "recentlyCalm"):
        idx = [i for i, s in enumerate(subs) if sub in s]
        res["bySubset"][sub] = {m: W.score([pr[i] for i in idx], [V[i]["hm0Obs"] for i in idx]) for m, pr in preds.items()}
    a = res["bySubset"]
    gain3 = a["all"]["M0"]["mae"] - a["all"]["M3"]["mae"]; gain4 = a["all"]["M0"]["mae"] - a["all"]["M4"]["mae"]
    res["buoyRule"] = {"gainM3": gain3, "gainM4": gain4, "retain80": gain4 >= 0.8 * gain3,
                       "biasOK": a["all"]["M4"]["bias"] <= 0.02 and a["falling"]["M4"]["bias"] <= 0.03 and a["recentlyCalm"]["M4"]["bias"] <= 0.03,
                       "categoriesOK": a["all"]["M4"]["exact"] >= a["all"]["M0"]["exact"] and a["all"]["M4"]["within1"] >= a["all"]["M0"]["within1"] and a["all"]["M4"]["severe"] <= a["all"]["M0"]["severe"]}
    json.dump(res, open(outp, "w"), indent=1); print(json.dumps(res["buoyRule"], indent=1))


def swan(outp):
    import swan_scenarios as S
    d = json.load(open(os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration/swan_scenarios.json")))
    P = params(); res = {}
    for key, rows in d.items():
        bname, name = key.split("|"); L = S.BASINS[bname]; tab = S.fetch_table(L)
        A, Bs = S.SCEN[name]; hours = [A] * 13 + Bs
        m4 = []
        for x in rows:
            t = x["hour"]; ser = [{"speedMS": s, "dirFromDeg": fr} for s, fr in hours[max(0, t - 12):t + 1]]
            s, fr = hours[t]; r = {"windMS": s, "dirFromDeg": fr, "fetchM": W.nine_ray(tab, fr), "series": ser}
            m4.append(W.predict(r, tab, "M4", P["M4"]))
        ok = [(x, y) for x, y in zip(rows, m4) if x["swan"] is not None]
        res[key] = {m: float(np.mean([abs((x[m] if m != "M4" else y) - x["swan"]) for x, y in ok])) for m in ("M0", "M3", "M4")}
        res[key]["M4series"] = [round(y, 3) for y in m4[:8]]
    crit = {k: v["M4"] < v["M0"] for k, v in res.items() if k.split("|")[1] in ("drop10toCalm", "pulse2h")}
    res["criticalBeatsM0"] = crit; res["swanRule"] = all(crit.values())
    json.dump(res, open(outp, "w"), indent=1)
    for k, v in res.items():
        if "|" in k:
            print(f"{k:<22} M0 {v['M0']:.3f}  M3 {v['M3']:.3f}  M4 {v['M4']:.3f}")
    print("critical", crit, "swanRule", res["swanRule"])


if __name__ == "__main__":
    {"build": build, "eval": lambda: evaluate(sys.argv[2]), "swan": lambda: swan(sys.argv[2])}[sys.argv[1]]()
