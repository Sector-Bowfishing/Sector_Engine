"""Stage 3D.1 §B: observation-anchored nowcast (pre-registered: stage3d1/WIND_PROVIDER_SHOOTOUT_PREREG.md, sha 2f935d06…).

  python research/nowcast_eval.py fit         # alpha per lead on CAL only -> nowcast_fits.json (frozen)
  python research/nowcast_eval.py holdout OUT # one-shot H1 evaluation (refuses without fits / a second run)
Uses the Stage 3D rows (rows.pkl). The residual r0 = obs(t0) - NBM(t0-1h, +1h) only uses data that existed at t0."""
import hashlib, json, math, os, pickle, sys
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.ingest import load_config
from sector_wind.sample import circular_error

OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d")
FITS = os.path.join(OUT, "nowcast_fits.json")
A_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
LEADS = (1, 3, 6, 12, 18)


def signed(a, b):
    return ((a - b + 180) % 360) - 180


def prepare():
    R = pickle.load(open(os.path.join(OUT, "rows.pkl"), "rb"))
    cfg = load_config(); st = cfg["stations"]
    one = {(r["station"], r["valid"]): r for r in R if r["lead"] == 1}       # NBM issued 1 h before valid
    resid = {}
    for (s, t), r in one.items():
        resid[(s, t)] = (r["obsS"] - r["nbmS"],
                         signed(r["obsD"], r["nbmD"]) if r["obsD"] is not None and r["nbmD"] is not None and r["obsS"] >= 2.6 and r["nbmS"] >= 2.6 else None)
    def dist(a, b):
        return math.hypot(st[a]["lat"] - st[b]["lat"], (st[a]["lon"] - st[b]["lon"]) * math.cos(math.radians(st[a]["lat"])))
    nearest = {s: min((o for o in st if o != s), key=lambda o: dist(s, o)) for s in st}
    for r in R:
        r["r0_same"] = resid.get((r["station"], r["init"]))
        r["r0_nb"] = resid.get((nearest[r["station"]], r["init"]))
    return R, nearest


def apply(r, a_s, a_d, key):
    res = r[key]
    if res is None:
        return None, None
    s = max(0.0, r["nbmS"] + a_s * res[0])
    d = r["nbmD"]
    if d is not None and res[1] is not None:
        d = (d + a_d * res[1]) % 360
    return s, d


def mae(rows_, a, key):
    v = [abs(apply(r, a, 0, key)[0] - r["obsS"]) for r in rows_ if r[key] is not None]
    return float(np.mean(v)) if v else None


def within(rows_, a, key):
    e = []
    for r in rows_:
        if r[key] is None:
            continue
        s, d = apply(r, 0, a, key)
        if d is not None and r["obsD"] is not None and s >= 2.6 and r["obsS"] >= 2.6:
            e.append(circular_error(d, r["obsD"]))
    return float(np.mean(np.array(e) <= 22.5)) if e else None


def fit():
    R, nearest = prepare(); C = [r for r in R if r["set"] == "CAL"]
    F = {"nearest": nearest}
    for key in ("r0_same", "r0_nb"):
        F[key] = {}
        for L in LEADS:
            sub = [r for r in C if r["lead"] == L]
            F[key][str(L)] = {"alphaSpeed": min(A_GRID, key=lambda a: mae(sub, a, key)),
                              "alphaDir": max(A_GRID, key=lambda a: within(sub, a, key) or 0)}
    json.dump(F, open(FITS, "w"), indent=1)
    print(json.dumps({k: v for k, v in F.items() if k != "nearest"}, indent=1), "\nnearest", nearest)


def evaluate(rows_, F, key, label):
    out = {}
    for L in LEADS:
        sub = [r for r in rows_ if r["lead"] == L and r[key] is not None]
        night = [r for r in sub if r["night"]]
        a = F[key][str(L)]
        def m(rs, aa):
            e = [apply(r, aa, 0, key)[0] - r["obsS"] for r in rs]
            return {"n": len(e), "mae": float(np.mean(np.abs(e))) if e else None, "bias": float(np.mean(e)) if e else None}
        out[str(L)] = {"alpha": a, "raw_all": m(sub, 0), "anch_all": m(sub, a["alphaSpeed"]), "raw_night": m(night, 0),
                       "anch_night": m(night, a["alphaSpeed"]), "dir_raw": within(sub, 0, key), "dir_anch": within(sub, a["alphaDir"], key),
                       "e15": {"raw": ev(sub, 0, key), "anch": ev(sub, a["alphaSpeed"], key)}}
    return out


def ev(rows_, a, key):
    h = m = fa = 0
    for r in rows_:
        f = apply(r, a, 0, key)[0] >= 6.7056; o = r["obsS"] >= 6.7056
        h += f and o; m += o and not f; fa += f and not o
    return {"obs": h + m, "fc": h + fa, "hits": h, "pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None}


def holdout(outp):
    if not os.path.exists(FITS):
        raise SystemExit("refusing: nowcast_fits.json must exist (frozen CAL alphas) before H1 is read")
    fh = hashlib.sha256(open(FITS, "rb").read()).hexdigest(); led = os.path.join(OUT, "nowcast_ledger.jsonl")
    if os.path.exists(led) and any(json.loads(l)["fitsSha256"] == fh for l in open(led)):
        raise SystemExit("refusing: H1 already evaluated with these alphas")
    F = json.load(open(FITS)); R, _ = prepare()
    H = [r for r in R if r["set"] == "H1"]; C = [r for r in R if r["set"] == "CAL"]
    res = {"fitsSha256": fh, "H1": {k: evaluate(H, F, k, "H1") for k in ("r0_same", "r0_nb")},
           "CAL": {k: evaluate(C, F, k, "CAL") for k in ("r0_same", "r0_nb")}}
    json.dump(res, open(outp, "w"), indent=1)
    open(led, "a").write(json.dumps({"fitsSha256": fh, "out": outp}) + "\n")
    for k in ("r0_same", "r0_nb"):
        for L, v in res["H1"][k].items():
            print(k, "+%sh" % L, "alpha", v["alpha"], "MAE raw %.3f -> %.3f" % (v["raw_all"]["mae"], v["anch_all"]["mae"]),
                  "night %.3f -> %.3f" % (v["raw_night"]["mae"], v["anch_night"]["mae"]),
                  "dir %.3f -> %.3f" % (v["dir_raw"] or 0, v["dir_anch"] or 0), "e15", v["e15"])


if __name__ == "__main__":
    fit() if sys.argv[1] == "fit" else holdout(sys.argv[2])
