"""Score Acceleration §11–14: NBM exceedance-probability recalibration, frozen on CAL for the sealed H2 test.
Pre-registration: docs/intelligence/wind/score-acceleration/WIND_NBM_PROBABILITY_RECAL_PREREG.md.

  python research/prob_recal.py fit       # CAL only -> prob_recal_fits.json (p*, q* for the Stage 3D.1 E1'/G2' test + isotonic maps)
  python research/prob_recal.py h2 OUT    # refuses before 2027-01-01; one shot

Events (frozen): E15 = observed sustained >= 15 mph; G20 = observed gust >= 20 kt (no reported gust = no event).
Raw probability = the Stage 3D qmd-derived P(> threshold) (rows.pkl pW15 / pG20, synoptic inits only).
Isotonic = pool-adjacent-violators on CAL, pooled over stations and leads; monotone, so ranking (AUC) is unchanged by design."""
import hashlib, json, os, pickle, sys
from datetime import datetime, timezone
import numpy as np

ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration")
FITS = os.path.join(OUT, "prob_recal_fits.json")
MPH, KT = 0.44704, 0.514444
LOW = (0.02, 0.05, 0.10, 0.15)
CAL_GRID = (0.1, 0.2, 0.3, 0.4, 0.5)
H2_OPEN = datetime(2027, 1, 1, tzinfo=timezone.utc)
EVENTS = {"E15": ("pW15", lambda r: r["obsS"] >= 15 * MPH, 0.5), "G20": ("pG20", lambda r: (r["obsG"] or 0) >= 20 * KT, 0.6)}


def pav(x, y):
    o = np.argsort(x, kind="mergesort"); x, y = np.asarray(x)[o], np.asarray(y, float)[o]
    blocks = [[y[i], 1.0, x[i], x[i]] for i in range(len(x))]   # mean, weight, xmin, xmax
    st = []
    for b in blocks:
        st.append(b)
        while len(st) > 1 and st[-2][0] > st[-1][0]:
            b2 = st.pop(); b1 = st.pop(); w = b1[1] + b2[1]
            st.append([(b1[0] * b1[1] + b2[0] * b2[1]) / w, w, b1[2], b2[3]])
    return [{"xmin": float(b[2]), "xmax": float(b[3]), "p": float(b[0]), "n": int(b[1])} for b in st]


BINS = (0.0, 0.005, 0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.01)
MIN_BLOCK, MIN_HITS = 50, 10


def binned_pav(x, y):
    """Amendment v2 (before any holdout): PAV on fixed raw-P bins, then merge adjacent blocks until each has >= MIN_BLOCK rows."""
    x, y = np.asarray(x), np.asarray(y, float); bl = []
    for lo, hi in zip(BINS, BINS[1:]):
        m = (x >= lo) & (x < hi)
        if m.any():
            bl.append([y[m].mean(), int(m.sum()), lo, hi])
    changed = True
    while changed:
        changed = False
        for i in range(len(bl) - 1):
            if bl[i][0] > bl[i + 1][0] or bl[i][1] < MIN_BLOCK or bl[i + 1][1] < MIN_BLOCK:
                a, b = bl[i], bl[i + 1]; w = a[1] + b[1]
                bl[i:i + 2] = [[(a[0] * a[1] + b[0] * b[1]) / w, w, a[2], b[3]]]; changed = True; break
    return [{"xmin": float(b[2]), "xmax": float(b[3]), "p": float(b[0]), "n": int(b[1])} for b in bl]


def apply_iso(m, p):
    for b in m:
        if p < b["xmax"]:
            return b["p"]
    return m[-1]["p"]


def table(p, y, thr):
    f = p >= thr; h = int((f & y).sum()); fa = int((f & ~y).sum()); mi = int((~f & y).sum())
    return {"thr": thr, "hit": h, "fa": fa, "miss": mi, "pod": h / (h + mi) if h + mi else None, "far": fa / (h + fa) if h + fa else None,
            "csi": h / (h + mi + fa) if h + mi + fa else 0.0}


def choose(p, y, grid, far_max):
    t = [table(p, y, g) for g in grid]
    ok = [x for x in t if x["far"] is not None and x["far"] <= far_max and x["hit"] >= MIN_HITS]
    best = max(ok or t, key=lambda x: (x["csi"], -x["thr"]))
    return best, t, bool(ok)


def auc(p, y):
    pos, neg = p[y], p[~y]
    if not len(pos) or not len(neg):
        return None
    r = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit():
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["set"] == "CAL" and "pW15" in r]
    res = {"method": "binned PAV v2 (min block 50, min CAL hits 10)", "frozenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "calRows": len(R), "events": {}}
    for ev, (key, fn, far_max) in EVENTS.items():
        rr = [r for r in R if r.get(key) is not None]
        p = np.array([r[key] for r in rr]); y = np.array([fn(r) for r in rr])
        star, low_tab, met = choose(p, y, LOW, far_max)
        iso = binned_pav(p, y); pc = np.array([apply_iso(iso, v) for v in p])
        cstar, cal_tab, cmet = choose(pc, y, CAL_GRID, far_max)
        res["events"][ev] = {"n": len(rr), "events": int(y.sum()), "baseRate": float(y.mean()),
                             "rawLowThreshold": {"chosen": star["thr"], "farConstraintMet": met, "calTable": low_tab},
                             "isotonic": iso, "calibratedThreshold": {"chosen": cstar["thr"], "farConstraintMet": cmet, "calTable": cal_tab},
                             "calDiagnostics": {"brierRaw": float(((p - y) ** 2).mean()), "brierIsoInSample": float(((pc - y) ** 2).mean()),
                                                "auc": auc(p, y), "meanRawP": float(p.mean())}}
    os.makedirs(OUT, exist_ok=True)
    body = json.dumps(res, indent=1); open(FITS, "w").write(body)
    print("sha256", hashlib.sha256(body.encode()).hexdigest())
    for ev, v in res["events"].items():
        print(ev, "n", v["n"], "events", v["events"], "p*", v["rawLowThreshold"]["chosen"], "met", v["rawLowThreshold"]["farConstraintMet"],
              "c*", v["calibratedThreshold"]["chosen"], "met", v["calibratedThreshold"]["farConstraintMet"], v["calDiagnostics"])
        for t in v["rawLowThreshold"]["calTable"]:
            print("   raw", t)
        print("   iso blocks", len(v["isotonic"]), [(round(b["xmin"], 3), round(b["p"], 3), b["n"]) for b in v["isotonic"]][-6:])


def h2(outp):
    if datetime.now(timezone.utc) < H2_OPEN:
        sys.exit(f"REFUSED: H2 (2026-10-07..2026-12-31) is sealed until {H2_OPEN:%Y-%m-%d}")
    raise SystemExit("H2: fetch H2 qmd at evaluation time, apply frozen p*/q*, isotonic maps and c*; Brier, BSS vs raw, reliability, AUC, POD/FAR; one shot.")


if __name__ == "__main__":
    {"fit": fit, "h2": lambda: h2(sys.argv[2])}[sys.argv[1]]()
