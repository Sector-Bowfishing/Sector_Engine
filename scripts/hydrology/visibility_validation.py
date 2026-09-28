"""Which turbidity -> visibility (Secchi) conversion should the engine own?
(Clarity Fusion Stage 1)

Candidates
  engine   Secchi_ft = 11.123 * T^-0.637      (ConditionsConfig.Clarity, "USGS default")
  adem     Secchi_m  = 4.84 * T^-0.672        (FishIntelMapStyle; fit to 753 ADEM pairs on Guntersville)
  fitted   log10 S_ft = a + b log10 T, fitted on the national pairs, scored by
           lake-grouped cross-validation (a site's lake never trains its own score)

Evaluated on
  in-situ   same site, same day, surface turbidity (NTU/FNU/FTU/NTRU; JTU dropped)
            paired with a Secchi reading that did not hit bottom
  satellite Sentinel-2 red-band turbidity at WQP Secchi sites (the Water
            Clarity layer's own input), from the q9 match-ups

Per candidate: median absolute error (ft), share within +-30%, log10 RMSE,
median bias (log10), and the 10th/90th percentile of the log10 residual: the
range a single number sits in, 80% of the time.

usage: geo/bin/python visibility_validation.py <q9 dir> <out.json>
"""
import sys, csv, json, math, collections, os
import numpy as np
from sklearn.model_selection import GroupKFold

Q9 = sys.argv[1]; OUT = sys.argv[2]
FT = 3.28084
CANDIDATES = {
    "engine": lambda t: 11.123 * t ** -0.637,
    "adem": lambda t: 4.84 * t ** -0.672 * FT,
}


def metrics(y, yhat):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    r = np.log10(yhat) - np.log10(y)
    return {"n": int(y.size), "medianAbsErrFt": round(float(np.median(np.abs(yhat - y))), 2),
            "within30pct": round(float(np.mean(np.abs(yhat / y - 1) <= 0.30)), 3),
            "log10Rmse": round(float(np.sqrt(np.mean(r ** 2))), 3),
            "medianBiasLog10": round(float(np.median(r)), 3),
            "residualP10P90Log10": [round(float(np.percentile(r, 10)), 3), round(float(np.percentile(r, 90)), 3)]}


def load_pairs():
    sec = {}
    for r in csv.DictReader(open(os.path.join(Q9, "wqp", "secchi.csv"))):
        if r["bottom_visible"] == "true":
            continue
        try:
            s = float(r["secchi_m"])
        except ValueError:
            continue
        if 0.05 <= s <= 25:
            sec.setdefault((r["site_id"], r["date"]), []).append((s, r))
    pairs = []
    for r in csv.DictReader(open(os.path.join(Q9, "wqp", "turbidity.csv"))):
        if r["unit"] not in ("NTU", "FNU", "FTU", "NTRU"):
            continue
        if r["depth_m"] not in ("", None):
            try:
                if float(r["depth_m"]) > 1.0:
                    continue
            except ValueError:
                pass
        k = (r["site_id"], r["date"])
        if k not in sec:
            continue
        try:
            t = float(r["value"])
        except ValueError:
            continue
        if not (0.2 <= t <= 1000):
            continue
        s, sr = sec[k][0]
        pairs.append({"site": r["site_id"], "state": r["state"], "org": r["org"], "name": r["site_name"],
                      "lat": float(r["lat"]), "lon": float(r["lon"]), "t": t, "unit": r["unit"], "s_ft": s * FT})
    # one pair per site-date
    seen = set(); out = []
    for p in pairs:
        k = (p["site"], p.get("date"), p["t"])
        if (p["site"], p["t"], p["s_ft"]) in seen:
            continue
        seen.add((p["site"], p["t"], p["s_ft"])); out.append(p)
    return out


def lake_group(p):
    # a site's water body: WQP gives none; the site name up to the first comma
    # or "at"/"near" groups sites on one lake well enough to keep a lake out of
    # its own training fold
    n = p["name"].lower()
    for cut in (",", " at ", " near ", " nr ", " - ", " site ", " sta"):
        if cut in n:
            n = n.split(cut)[0]
    return f"{p['state']}|{n.strip()}"


def fit_power(t, s):
    b, a = np.polyfit(np.log10(t), np.log10(s), 1)
    return a, b


def evaluate(pairs, label):
    t = np.array([p["t"] for p in pairs]); s = np.array([p["s_ft"] for p in pairs])
    res = {name: metrics(s, f(t)) for name, f in CANDIDATES.items()}
    groups = np.array([lake_group(p) for p in pairs])
    yhat = np.zeros_like(s)
    k = min(5, len(set(groups)))
    if k >= 2:
        for tr, te in GroupKFold(n_splits=k).split(t, s, groups):
            a, b = fit_power(t[tr], s[tr]); yhat[te] = 10 ** (a + b * np.log10(t[te]))
        res["fitted(cv)"] = metrics(s, yhat)
    print(f"\n{label}: {len(pairs)} pairs, {len(set(groups))} lakes/groups")
    for n_, m in res.items():
        print(f"  {n_:11} medAbsErr {m['medianAbsErrFt']:5.2f} ft  ±30% {m['within30pct']:.0%}  logRMSE {m['log10Rmse']:.3f}  bias {m['medianBiasLog10']:+.3f}  P10/P90 {m['residualP10P90Log10']}")
    return res


def main():
    pairs = load_pairs()
    print(f"{len(pairs)} in-situ turbidity/Secchi pairs")
    report = {"inSitu": {}, "satellite": {}}
    report["inSitu"]["national"] = evaluate(pairs, "in-situ, national")
    report["inSitu"]["alabama"] = evaluate([p for p in pairs if p["state"] == "AL"], "in-situ, Alabama")
    tn = [p for p in pairs if p["state"] in ("AL", "TN") and ("tennessee" in p["name"].lower() or "guntersville" in p["name"].lower()
                                                             or "wheeler" in p["name"].lower() or "pickwick" in p["name"].lower())]
    if len(tn) >= 20:
        report["inSitu"]["tennesseeRiverReservoirs"] = evaluate(tn, "in-situ, Tennessee River reservoirs (AL/TN)")
    # national fit on all pairs: the canonical coefficients and their range
    t = np.array([p["t"] for p in pairs]); s = np.array([p["s_ft"] for p in pairs])
    a, b = fit_power(t, s)
    r = np.log10(s) - (a + b * np.log10(t))
    report["fittedNational"] = {"a": round(float(a), 4), "b": round(float(b), 4),
                                "formula": f"Secchi_ft = {10 ** a:.3f} * T^{b:.3f}",
                                "residualP10P50P90Log10": [round(float(np.percentile(r, q)), 3) for q in (10, 50, 90)],
                                "residualP25P75Log10": [round(float(np.percentile(r, q)), 3) for q in (25, 75)]}
    # units: does FNU behave like NTU here?
    report["byUnit"] = {u: len([p for p in pairs if p["unit"] == u]) for u in ("NTU", "FNU", "FTU", "NTRU")}
    # satellite FNU at Secchi sites
    sat = []
    for fn in ("all_matchups.csv",):
        path = os.path.join(Q9, fn)
        if os.path.exists(path):
            for m in csv.DictReader(open(path)):
                try:
                    f = float(m["fnu"]); sm = float(m["secchi_m"])
                except (ValueError, KeyError):
                    continue
                if f > 0.2 and 0.05 < sm < 25 and int(float(m.get("n_valid") or 0)) >= 3:
                    sat.append({"site": m["site_id"], "state": m.get("state", ""), "name": m.get("site_name", m["site_id"]),
                                "t": f, "s_ft": sm * FT, "unit": "S2", "lat": 0, "lon": 0})
    if sat:
        report["satellite"]["national"] = evaluate(sat, "Sentinel-2 red-band FNU vs Secchi (match-ups)")
    json.dump(report, open(OUT, "w"), indent=1)
    print("\nfitted national:", report["fittedNational"])


if __name__ == "__main__":
    main()
