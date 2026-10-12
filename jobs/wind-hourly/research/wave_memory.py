"""Stage 3E wave memory + duration (pre-registered: score-acceleration/WIND_STAGE_3E_PREREG.md, sha 2402a463…).

  python research/wave_memory.py check          # Python CEM/M0 mirror reproduces wind-cem hm0MidM on the corpus
  python research/wave_memory.py fit            # choose M1/M2/M3 parameters on CAL (2017-2019) -> wave_memory_fits.json
  python research/wave_memory.py val OUT.json   # one-shot VAL (2024-2025) with the frozen fits
CEM is unchanged (frozen formulas); memory/continuity wrap it."""
import json, math, os, sys
from collections import defaultdict
import numpy as np

DER = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/waves")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration")
FITS = os.path.join(OUT, "wave_memory_fits.json")
G = 9.80665
NB = 120
CLS = [0.0254, 0.0762, 0.1524, 0.3048]
M1_GRID = [(30.0, (0.6, 1.4)), (30.0, (0.5, 1.5)), (45.0, (0.6, 1.4)), (45.0, (0.5, 1.5))]
TAU_GRID = [1.0, 2.0, 3.0, 4.0, 6.0]


def ustar(u):
    return u * math.sqrt(0.001 * (1.1 + 0.035 * u))


def cem(u, x, t_s=None):
    if u <= 0 or x <= 0:
        return 0.0
    us = ustar(u); xd = x
    if t_s is not None:
        xt = 5.23e-3 * (G * t_s / us) ** 1.5 * us * us / G
        xd = min(xd, xt)
    h = 4.13e-2 * math.sqrt(G * xd / (us * us)) * us * us / G
    return min(h, 2.115e2 * us * us / G)


def circ(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def duration(series, tol=22.5, band=(0.7, 1.3), minS=1.0):
    last = series[-1]
    if last["speedMS"] is None:
        return None
    s0, d0, n = last["speedMS"], last["dirFromDeg"], 0
    if d0 is not None and s0 >= minS:
        for s in reversed(series):
            sp, d = s["speedMS"], s["dirFromDeg"]
            if sp is None or d is None or sp < minS or sp < band[0] * s0 or sp > band[1] * s0 or circ(d, d0) > tol:
                break
            n += 1
    return min(12.0, max(0.5, float(n)))


def nine_ray(table, theta):
    b = int(round(theta / 3.0)) % NB
    return float(np.mean([table[(b + k) % NB] for k in range(-4, 5)]))


def predict(row, table, model, p):
    """Hm0 at the row's valid hour. model in M0/M1/M2/M3; p = params."""
    ser = row["series"]
    tol, band = (22.5, (0.7, 1.3)) if model in ("M0", "M2") else p["cont"]
    if model in ("M0", "M1"):
        dh = duration(ser, tol, band)
        return cem(row["windMS"], row["fetchM"], dh * 3600) if dh is not None else 0.0
    tau = p["tau"]; H = None
    for j in range(len(ser)):
        s = ser[j]
        if s["speedMS"] is None or s["dirFromDeg"] is None:
            forced = None
        else:
            dh = duration(ser[:j + 1], tol, band)
            x = row["fetchM"] if j == len(ser) - 1 else nine_ray(table, s["dirFromDeg"])
            forced = cem(s["speedMS"], x, dh * 3600)
        dec = H * math.exp(-1.0 / tau) if H is not None else None
        H = forced if dec is None else (dec if forced is None else max(forced, dec))
    return H or 0.0


def cls(h):
    return 1 + sum(h >= b for b in CLS)


def load():
    st = json.load(open(os.path.join(DER, "stations.json")))
    rows = [json.loads(l) for l in open(os.path.join(DER, "rows.jsonl")) if '|nodepth"' in l]
    return rows, {k: v["fetchTableM"] for k, v in st.items()}


def subsets(r):
    ser = r["series"]; u = r["windMS"]; s3 = ser[-4] if len(ser) >= 4 else None
    out = {"all"}
    if duration(ser) is not None and duration(ser) < 2:
        out.add("dur<2h")
    if s3 and s3["speedMS"] is not None and u < 0.8 * s3["speedMS"]:
        out.add("falling")
    if s3 and s3["dirFromDeg"] is not None and r["dirFromDeg"] is not None and circ(r["dirFromDeg"], s3["dirFromDeg"]) > 45:
        out.add("veering")
    if u >= 4 and any(s["speedMS"] is not None and s["speedMS"] < 2 for s in ser[-7:-1]):
        out.add("recentlyCalm")
    return out


def score(P, O):
    P, O = np.asarray(P), np.asarray(O); e = P - O
    pc = np.array([cls(x) for x in P]); oc = np.array([cls(x) for x in O])
    sev = ((pc == 1) & (oc >= 4)) | ((pc >= 4) & (oc == 1)) | (np.abs(pc - oc) >= 3)
    return {"n": int(len(P)), "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean()),
            "exact": float((pc == oc).mean()), "within1": float((np.abs(pc - oc) <= 1).mean()), "severe": float(sev.mean())}


def run(rows, tables, model, p):
    return [predict(r, tables[r["station"]], model, p) for r in rows]


def check():
    rows, tables = load()
    pred = {json.loads(l)["id"]: json.loads(l)["hm0MidM"] for l in open(os.path.join(DER, "pred.jsonl"))}
    d = [abs(predict(r, tables[r["station"]], "M0", {}) - pred[r["id"]]) for r in rows]
    print("M0 mirror vs wind-cem: n", len(d), "max |diff| m", max(d), "share > 1 mm", float(np.mean(np.array(d) > 0.001)))


def fit():
    rows, tables = load(); cal = [r for r in rows if int(r["time"][:4]) <= 2019]
    O = [r["hm0Obs"] for r in cal]; m0 = score(run(cal, tables, "M0", {}), O)
    ok = lambda s: s["within1"] >= m0["within1"] - 0.01 and s["severe"] <= m0["severe"] + 1e-9
    res = {"calHours": len(cal), "M0": m0, "M1": {}, "M2": {}, "M3": {}}
    for tol, band in M1_GRID:
        res["M1"][f"{tol}|{band}"] = score(run(cal, tables, "M1", {"cont": (tol, band)}), O)
    for tau in TAU_GRID:
        res["M2"][str(tau)] = score(run(cal, tables, "M2", {"tau": tau}), O)
    def pick(d):
        c = [(v["mae"], k) for k, v in d.items() if ok(v)]
        return min(c)[1] if c else None
    b1 = pick(res["M1"]); b2 = pick(res["M2"])
    cont = (float(b1.split("|")[0]), tuple(float(x) for x in b1.split("|")[1].strip("()").split(","))) if b1 else (22.5, (0.7, 1.3))
    for tau in TAU_GRID:
        res["M3"][str(tau)] = score(run(cal, tables, "M3", {"cont": cont, "tau": tau}), O)
    b3 = pick(res["M3"])
    best = min([("M1", res["M1"][b1]["mae"]) if b1 else ("M1", 9), ("M2", res["M2"][b2]["mae"]) if b2 else ("M2", 9),
                ("M3", res["M3"][b3]["mae"]) if b3 else ("M3", 9)], key=lambda x: x[1])[0]
    res["chosen"] = {"M1": {"cont": cont}, "M2": {"tau": float(b2) if b2 else None}, "M3": {"cont": cont, "tau": float(b3) if b3 else None}, "namedForVAL": best}
    os.makedirs(OUT, exist_ok=True); json.dump(res, open(FITS, "w"), indent=1)
    print(json.dumps({"M0": m0, "chosen": res["chosen"], "M1": res["M1"], "M2": res["M2"], "M3": res["M3"]}, indent=1)[:6000])


def val(outp):
    F = json.load(open(FITS)); ch = F["chosen"]
    rows, tables = load(); V = [r for r in rows if int(r["time"][:4]) >= 2024]
    params = {"M0": {}, "M1": {"cont": (ch["M1"]["cont"][0], tuple(ch["M1"]["cont"][1]))}, "M2": {"tau": ch["M2"]["tau"]},
              "M3": {"cont": (ch["M3"]["cont"][0], tuple(ch["M3"]["cont"][1])), "tau": ch["M3"]["tau"]}}
    preds = {m: run(V, tables, m, p) for m, p in params.items() if m == "M0" or p.get("tau") is not None or m == "M1"}
    subs = [subsets(r) for r in V]
    res = {"valHours": len(V), "namedForVAL": ch["namedForVAL"], "params": {k: str(v) for k, v in params.items()}, "bySubset": {}}
    for sub in ("all", "dur<2h", "falling", "veering", "recentlyCalm"):
        idx = [i for i, s in enumerate(subs) if sub in s]
        res["bySubset"][sub] = {m: score([P[i] for i in idx], [V[i]["hm0Obs"] for i in idx]) for m, P in preds.items()}
    by = defaultdict(list)
    for i, r in enumerate(V):
        by[(r["station"], r["time"][:10])].append(i)
    res["eventDaily"] = {m: score([np.mean([P[i] for i in ix]) for ix in by.values()], [np.mean([V[i]["hm0Obs"] for i in ix]) for ix in by.values()]) for m, P in preds.items()}
    nm = ch["namedForVAL"]; a, b = res["bySubset"], nm
    m0 = a["all"]["M0"]; c = a["all"][b]
    res["gate"] = {"model": b,
                   "maeGain": 1 - c["mae"] / m0["mae"], "absBiasNotWorse": abs(c["bias"]) <= abs(m0["bias"]) + 1e-9,
                   "fallingMaeGain": 1 - a["falling"][b]["mae"] / a["falling"]["M0"]["mae"], "fallingBiasToward0": abs(a["falling"][b]["bias"]) < abs(a["falling"]["M0"]["bias"]),
                   "dur2MaeGain": 1 - a["dur<2h"][b]["mae"] / a["dur<2h"]["M0"]["mae"], "dur2BiasToward0": abs(a["dur<2h"][b]["bias"]) < abs(a["dur<2h"]["M0"]["bias"]),
                   "exactOk": c["exact"] >= m0["exact"] - 0.01, "within1Ok": c["within1"] >= m0["within1"] - 1e-9, "severeOk": c["severe"] <= m0["severe"] + 1e-9}
    g = res["gate"]
    g["pass"] = bool(g["maeGain"] >= 0.05 and g["absBiasNotWorse"] and g["fallingMaeGain"] >= 0.10 and g["fallingBiasToward0"] and g["dur2MaeGain"] >= 0.10
                     and g["dur2BiasToward0"] and g["exactOk"] and g["within1Ok"] and g["severeOk"])
    json.dump(res, open(outp, "w"), indent=1); print(json.dumps(res["gate"], indent=1))


if __name__ == "__main__":
    {"check": check, "fit": fit, "val": lambda: val(sys.argv[2])}[sys.argv[1]]()
