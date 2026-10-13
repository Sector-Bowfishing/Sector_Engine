"""Stage 3D.2 §10–11: RTMA-anchored nowcast (pre-registered: docs/intelligence/wind/stage3d2/WIND_OBSERVATION_NOWCAST_TEST.md).

  python research/nowcast_rtma.py fit             # CAL only (2026-05-06 .. 2026-08-15, synoptic inits) -> nowcast_rtma_fits.json
  python research/nowcast_rtma.py holdout OUT     # H3 prospective (2027-01-01 .. 2027-03-31); refuses before 2027-04-01

residual r0 = RTMA-RU(t0) - NBM(t0-1h, +1h)   (both existed at t0; NBM_now = the newest cycle's +1 h valid at t0)
corrected(L) = NBM(t0, L) + alpha(L) * r0,  alpha(L) = a * exp(-(L-1)/tau) for L <= 6, 0 beyond (returns to raw NBM)
Variants:  R-NB  RTMA sampled at the nearest OTHER frozen station (a lake point with no sensor; leakage-free; PRIMARY)
           R-SELF RTMA at the verified station itself (RTMA assimilates that METAR -> leaky upper bound; DIAGNOSTIC ONLY)
H1 is not used (already spent on the Stage 3D.1 METAR-anchored nowcast); H2 is sealed and not used."""
import hashlib, json, math, os, pickle, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend_wind
from sector_wind.sample import circular_error

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d2")
FITS = os.path.join(OUT, "nowcast_rtma_fits.json")
A_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
TAU_GRID = (1.0, 2.0, 3.0, 6.0)
LEADS = (1, 3, 6, 12, 18)
H3_START, H3_END, H3_OPEN = datetime(2027, 1, 1, tzinfo=timezone.utc), datetime(2027, 3, 31, 23, tzinfo=timezone.utc), datetime(2027, 4, 1, tzinfo=timezone.utc)
MPH = 0.44704


def alpha(a, tau, L):
    return a * math.exp(-(L - 1) / tau) if L <= 6 else 0.0


def signed(a, b):
    return ((a - b + 180) % 360) - 180


def rtma_at_stations(st, cfg, t):
    out = {}
    for lake in cfg["lakes"]:
        o = st.get_json(f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz")
        if not o:
            continue
        g = st.get_json(o["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
        for sid, s in cfg["stations"].items():
            if s["lake"] == lake:
                out[sid] = blend_wind(o["speedMS"], o["dirFromDeg"], ci.weights(s["lat"], s["lon"]))
    return out


def prepare(rows, inits, allrows):
    st, cfg = LocalStore(ROOT), load_config(); S = cfg["stations"]
    def dist(a, b):
        return math.hypot(S[a]["lat"] - S[b]["lat"], (S[a]["lon"] - S[b]["lon"]) * math.cos(math.radians(S[a]["lat"])))
    nearest = {s: min((o for o in S if o != s), key=lambda o: dist(s, o)) for s in S}
    now1 = {(r["station"], r["valid"]): r for r in allrows if r["lead"] == 1}   # NBM(t0-1h, +1h) comes from the hourly cycle before t0
    rt = {t: rtma_at_stations(st, cfg, t) for t in inits}
    leak = []
    for t, m in rt.items():
        for sid, (s, d) in m.items():
            o = now1.get((sid, t))
            if o and s is not None:
                leak.append(abs(s - o["obsS"]))
    def resid(sid, t):
        x = rt.get(t, {}).get(sid); n = now1.get((sid, t))
        if not x or x[0] is None or not n:
            return None
        rd = signed(x[1], n["nbmD"]) if x[1] is not None and n["nbmD"] is not None and x[0] >= 2.6 and n["nbmS"] >= 2.6 else None
        return (x[0] - n["nbmS"], rd)
    sel = [r for r in rows if r["init"] in rt]
    for r in sel:
        r["r_self"] = resid(r["station"], r["init"]); r["r_nb"] = resid(nearest[r["station"]], r["init"])
    return sel, nearest, {"rtmaVsMetarAtStationMAD": round(float(np.mean(leak)), 3) if leak else None, "n": len(leak)}


def corrected(r, key, a_s, tau_s, a_d, tau_d):
    res = r[key]; L = r["lead"]
    s = max(0.0, r["nbmS"] + alpha(a_s, tau_s, L) * res[0])
    d = r["nbmD"]
    if d is not None and res[1] is not None:
        d = (d + alpha(a_d, tau_d, L) * res[1]) % 360
    return s, d


def score(rows, key, p):
    out = {}
    for L in LEADS:
        rs = [r for r in rows if r["lead"] == L and r[key] is not None]
        if not rs:
            continue
        c = [corrected(r, key, *p) for r in rs]
        e = np.array([x[0] - r["obsS"] for x, r in zip(c, rs)]); e0 = np.array([r["nbmS"] - r["obsS"] for r in rs])
        ni = np.array([r["night"] for r in rs])
        dd = [(circular_error(x[1], r["obsD"]), circular_error(r["nbmD"], r["obsD"])) for x, r in zip(c, rs)
              if x[1] is not None and r["nbmD"] is not None and r["obsD"] is not None and r["obsS"] >= 2.6 and r["nbmS"] >= 2.6 and x[0] >= 2.6]
        T = 15 * MPH
        ev = lambda f: (sum(fx >= T and r["obsS"] >= T for fx, r in zip(f, rs)), sum(fx < T and r["obsS"] >= T for fx, r in zip(f, rs)), sum(fx >= T and r["obsS"] < T for fx, r in zip(f, rs)))
        out[L] = {"n": len(rs), "mae": float(np.abs(e).mean()), "maeRaw": float(np.abs(e0).mean()),
                  "nightMae": float(np.abs(e[ni]).mean()) if ni.any() else None, "nightMaeRaw": float(np.abs(e0[ni]).mean()) if ni.any() else None,
                  "bias": float(e.mean()), "biasRaw": float(e0.mean()),
                  "dir22": float(np.mean([a <= 22.5 for a, _ in dd])) if dd else None, "dir22Raw": float(np.mean([b <= 22.5 for _, b in dd])) if dd else None,
                  "ev15": ev([x[0] for x in c]), "ev15Raw": ev([r["nbmS"] for r in rs])}
    return out


def fit():
    R = pickle.load(open(ROWS, "rb"))
    cal = [r for r in R if r["set"] == "CAL" and r["synoptic"]]
    inits = sorted({r["init"] for r in cal})
    rows, nearest, leak = prepare(cal, inits, [r for r in R if r["set"] == "CAL"])
    res = {"frozenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "calInits": len(inits), "nearest": nearest, "leakage": leak, "fits": {}}
    for key in ("r_nb", "r_self"):
        best = None
        for a in A_GRID:
            for tau in TAU_GRID:
                sc = score(rows, key, (a, tau, 0.0, 1.0))
                obj = np.mean([sc[L]["mae"] for L in (1, 3, 6)])
                if any(sc[L]["mae"] > sc[L]["maeRaw"] + 1e-9 for L in (1, 3, 6)):
                    continue
                if best is None or obj < best[0] - 1e-9:
                    best = (obj, a, tau)
        _, a, tau = best
        bd = None
        for ad in A_GRID:
            for td in TAU_GRID:
                sc = score(rows, key, (a, tau, ad, td))
                ob = -np.mean([sc[L]["dir22"] for L in (1, 3, 6) if sc[L]["dir22"] is not None])
                if bd is None or ob < bd[0] - 1e-9:
                    bd = (ob, ad, td)
        p = (a, tau, bd[1], bd[2])
        res["fits"][key] = {"speed": {"a": a, "tau": tau}, "direction": {"a": bd[1], "tau": bd[2]}, "alphaByLead": {L: round(alpha(a, tau, L), 3) for L in LEADS},
                            "cal": score(rows, key, p)}
    os.makedirs(OUT, exist_ok=True)
    body = json.dumps(res, indent=1, default=str)
    open(FITS, "w").write(body)
    print(body[:4000]); print("sha256", hashlib.sha256(body.encode()).hexdigest())


def holdout(outp):
    if datetime.now(timezone.utc) < H3_OPEN:
        sys.exit(f"REFUSED: H3 ({H3_START:%Y-%m-%d}..{H3_END:%Y-%m-%d}) is sealed until {H3_OPEN:%Y-%m-%d}")
    raise SystemExit("H3 evaluation: build H3 rows from the live Candidate archive (NBM hourly, RTMA-RU, METAR) with the frozen fits; one shot.")


if __name__ == "__main__":
    {"fit": fit, "holdout": lambda: holdout(sys.argv[2])}[sys.argv[1]]()
