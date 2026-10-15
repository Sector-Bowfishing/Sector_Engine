"""Stage 3D.2 evaluation (research only; CAL + H1 rows only — H2 is sealed and never read).

  python research/stage3d2_eval.py impact   OUT.json   # §27/§36 forecast error -> frozen CEM surface decision (no data, physics only)
  python research/stage3d2_eval.py parity   OUT.json   # §7 Open-Meteo ncep_nbm_conus vs direct NOAA NBM: values, timestamps, missing rates
  python research/stage3d2_eval.py decision OUT.json   # §26/§28 same-row source vs NBM: regimes, time of day, decision value

Physics: the frozen Candidate CEM via wind-cem (cem_grid_out.jsonl, durationH = 6 fixed and duration-unknown branch).
The CEM is NOT changed; it is used only as a diagnostic lens on forcing error."""
import json, math, os, pickle, sys
from collections import Counter, defaultdict
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from sector_wind.sample import circular_error
import provider_eval as PE

D = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d2")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
MPH, KT = 0.44704, 0.514444
FETCHES = (100, 250, 500, 1000, 2000, 5000)
CHOP = {1: "Protected", 2: "Ripple", 3: "Light chop", 4: "Moderate chop", 5: "Rough"}
TEX = {1: "Glassy", 2: "Rippled", 3: "Textured", 4: "Broken"}


# ── frozen CEM lookup ───────────────────────────────────────────────────────────────────────

def cem_table(dur="6.0"):
    t = defaultdict(dict)
    for l in open(os.path.join(D, "cem_grid_out.jsonl")):
        o = json.loads(l); f, u, d = o["id"].split("|")
        if d == dur:
            t[int(f)][round(float(u), 2)] = (o["chopClass"], o["texture"], o["hm0MidM"])
    return t


def classify(T, fetch, u):
    u = min(max(0.0, u), 30.0); k = round(round(u / 0.05) * 0.05, 2)
    return T[fetch][k]


def tod(vt):
    h = vt.hour
    return "night" if 1 <= h <= 8 else ("evening" if h in (22, 23, 0) else "day")


# ── §36 product impact ──────────────────────────────────────────────────────────────────────

def impact(out):
    res = {}
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["set"] in ("CAL", "H1")]
    clim = {"all": [r["obsS"] for r in R if r["lead"] == 1], "night": [r["obsS"] for r in R if r["lead"] == 1 and r["night"]]}
    for dur in ("6.0", "None"):
        T = cem_table(dur); rd = {}
        for f in FETCHES:
            # class boundaries in mph (first speed where chop / texture class steps up)
            sp = sorted(T[f]); cb, tb = [], []
            for a, b in zip(sp, sp[1:]):
                if T[f][b][0] != T[f][a][0]:
                    cb.append({"toClass": CHOP[T[f][b][0]], "mph": round(b / MPH, 1)})
                if T[f][b][1] != T[f][a][1]:
                    tb.append({"toClass": TEX[T[f][b][1]], "mph": round(b / MPH, 1)})
            matrix = {}
            for w in (5, 8, 10, 12, 15, 18, 20):
                row = {"truth": {"chop": CHOP[classify(T, f, w * MPH)[0]], "texture": TEX[classify(T, f, w * MPH)[1]],
                                 "hm0In": round(classify(T, f, w * MPH)[2] / 0.0254, 1)}}
                for e in (-5, -3, -2, -1, 1, 2, 3, 5):
                    c0, t0, h0 = classify(T, f, w * MPH); c1, t1, h1 = classify(T, f, max(0, w + e) * MPH)
                    row[f"{e:+d}"] = {"chop": CHOP[c1], "chopChanged": c1 != c0, "textureChanged": t1 != t0,
                                      "hm0ErrIn": round((h1 - h0) / 0.0254, 1)}
                matrix[str(w)] = row
            # climatology-weighted: share of observed hours where a symmetric k-mph error flips the chop class
            flips = {}
            for k in (1, 2, 3, 5):
                for name, xs in clim.items():
                    fl = [classify(T, f, x)[0] != classify(T, f, x + k * MPH)[0] or classify(T, f, x)[0] != classify(T, f, max(0, x - k * MPH))[0] for x in xs]
                    fl10 = [z for z, x in zip(fl, xs) if x >= 10 * MPH]
                    flips[f"{name}_{k}mph"] = {"share": round(float(np.mean(fl)), 3), "n": len(fl),
                                               "shareWhenObs10mph+": round(float(np.mean(fl10)), 3) if fl10 else None, "n10": len(fl10)}
            rd[str(f)] = {"chopBoundariesMph": cb, "textureBoundariesMph": tb, "matrix": matrix, "climatologyFlipShare": flips}
        res["duration6h" if dur == "6.0" else "durationUnknown"] = rd
    json.dump(res, open(out, "w"), indent=1); print("wrote", out)


# ── §7 parity ───────────────────────────────────────────────────────────────────────────────

def parity(out):
    R = pickle.load(open(ROWS, "rb"))
    idx = {(r["station"], r["init"], r["lead"]): r for r in R}
    by_init = defaultdict(list)
    for k, v in idx.items():
        by_init[k[1]].append((k, v))
    syn = sorted({r["init"] for r in R if r["init"].hour % 6 == 0})
    res = {"synopticInits": len(syn)}
    fetched = [t for t in syn if os.path.exists(os.path.join(PE.H, "openmeteo", "ncep_nbm_conus", f"{t:%Y%m%d%H}.json"))]
    res["requestsSucceeded"] = len(fetched); res["requestsFailed(throttle)"] = len(syn) - len(fetched)
    # timestamp alignment: compare OM run t against NOAA NBM init t+off at the same valid time
    align = {}
    for off in (-2, -1, 0, 1, 2):
        d = []
        for t in fetched:
            ser = PE.om_series("ncep_nbm_conus", t)
            for (sid, init, L), r in by_init[t + timedelta(hours=off)]:
                x = ser.get((sid, r["valid"]))
                if x and x[0] is not None:
                    d.append(abs(x[0] - r["nbmS"]))
        align[f"{off:+d}h"] = {"n": len(d), "speedMAD": round(float(np.mean(d)), 3) if d else None}
    res["initAlignment"] = align
    # missing values inside returned payloads vs direct NBM rows at the same station/valid
    nom = nn = both = 0; dd, gd, sd = [], [], []
    for t in fetched:
        ser = PE.om_series("ncep_nbm_conus", t)
        for (sid, init, L), r in by_init[t]:
            x = ser.get((sid, r["valid"]))
            if not x or x[0] is None:
                nom += 1; continue
            both += 1; sd.append(x[0] - r["nbmS"])
            if x[1] is not None and r["nbmD"] is not None and r["nbmS"] >= 2.6:
                dd.append(circular_error(x[1], r["nbmD"]))
            if x[2] is not None and r["nbmG"] is not None:
                gd.append(x[2] - r["nbmG"])
    sd, dd, gd = np.array(sd), np.array(dd), np.array(gd)
    res["valueMissingInPayload"] = nom; res["matchedRows"] = both
    res["speed"] = {"meanDiff": round(float(sd.mean()), 3), "MAD": round(float(np.abs(sd).mean()), 3), "p95Abs": round(float(np.percentile(np.abs(sd), 95)), 3),
                    "maxAbs": round(float(np.abs(sd).max()), 3), "within0.2": round(float((np.abs(sd) <= 0.2).mean()), 3)}
    res["direction"] = {"n": len(dd), "medianDiff": float(np.median(dd)), "meanDiff": round(float(dd.mean()), 2), "within10deg": round(float((dd <= 10).mean()), 3)}
    res["gust"] = {"n": len(gd), "meanDiff": round(float(gd.mean()), 3), "MAD": round(float(np.abs(gd).mean()), 3), "within0.5": round(float((np.abs(gd) <= 0.5).mean()), 3)}
    json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1))


# ── §26/§28 regimes + decision value ────────────────────────────────────────────────────────

def pairs_for(source):
    R = pickle.load(open(ROWS, "rb"))
    idx = {(r["station"], r["init"], r["lead"]): r for r in R}
    by_init = defaultdict(list)
    for k, v in idx.items():
        by_init[k[1]].append((k, v))
    syn = sorted({r["init"] for r in R if r["init"].hour % 6 == 0})
    P = []
    if source == "ndfd":
        for t in syn:
            nd = PE.ndfd(t)
            if not nd:
                continue
            for L in (3, 6, 12, 18):
                for sid in ("8A1", "4A6", "DCU", "HSV", "9A4", "MSL", "SNH", "15M"):
                    r = idx.get((sid, t - timedelta(hours=1), L)); x = nd.get((sid, r["valid"])) if r else None
                    if r and x and x[0] is not None:
                        P.append((r, x))
    else:
        for t in syn:
            ser = PE.om_series(source, t)
            if not ser:
                continue
            for (sid, init, L), r in by_init[t]:
                x = ser.get((sid, r["valid"]))
                if x and x[0] is not None:
                    P.append((r, x))
    return P


def block(P, T6):
    """Same rows: source vs NBM. P = [(row, (s, d, g))]."""
    def m(sel, key):
        e = np.array([sel_s(r, x, key) - r["obsS"] for r, x in sel])
        de = np.array([circular_error(sel_d(r, x, key), r["obsD"]) for r, x in sel
                       if sel_d(r, x, key) is not None and r["obsD"] is not None and sel_s(r, x, key) >= 2.6 and r["obsS"] >= 2.6])
        o = {"n": len(sel)}
        if len(e):
            o.update({"mae": round(float(np.abs(e).mean()), 3), "bias": round(float(e.mean()), 3), "rmse": round(float(np.sqrt((e ** 2).mean())), 3)})
        if len(de):
            o.update({"dir22": round(float((de <= 22.5).mean()), 3), "circMAE": round(float(de.mean()), 1)})
        for k, thr in (("10mph", 10 * MPH), ("15mph", 15 * MPH), ("20mph", 20 * MPH)):
            h = sum(sel_s(r, x, key) >= thr and r["obsS"] >= thr for r, x in sel); mi = sum(r["obsS"] >= thr and sel_s(r, x, key) < thr for r, x in sel)
            fa = sum(sel_s(r, x, key) >= thr and r["obsS"] < thr for r, x in sel)
            o[k] = {"obs": h + mi, "hit": h, "fa": fa, "pod": round(h / (h + mi), 3) if h + mi else None, "far": round(fa / (h + fa), 3) if h + fa else None}
        gg = [(sel_g(r, x, key), r["obsG"]) for r, x in sel if sel_g(r, x, key) is not None]
        cond = [a - b for a, b in gg if b is not None]
        o["gustCondBias"] = round(float(np.mean(cond)), 3) if cond else None
        h = sum(a >= 20 * KT and (b or 0) >= 20 * KT for a, b in gg); mi = sum((b or 0) >= 20 * KT and a < 20 * KT for a, b in gg)
        fa = sum(a >= 20 * KT and (b or 0) < 20 * KT for a, b in gg)
        o["gust20kt"] = {"obs": h + mi, "hit": h, "fa": fa, "pod": round(h / (h + mi), 3) if h + mi else None, "far": round(fa / (h + fa), 3) if h + fa else None}
        # decision value: frozen CEM chop class (6 h duration) at each fetch, forecast vs truth
        dv = {}
        for f in FETCHES:
            ok = [classify(T6, f, sel_s(r, x, key))[0] == classify(T6, f, r["obsS"])[0] for r, x in sel]
            ok10 = [classify(T6, f, sel_s(r, x, key))[0] == classify(T6, f, r["obsS"])[0] for r, x in sel if r["obsS"] >= 10 * MPH]
            dv[str(f)] = {"chopCorrect": round(float(np.mean(ok)), 4) if ok else None,
                          "chopCorrectObs10mph+": round(float(np.mean(ok10)), 4) if ok10 else None, "n10": len(ok10)}
        o["decision"] = dv
        return o
    def sel_s(r, x, key): return x[0] if key == "src" else r["nbmS"]
    def sel_d(r, x, key): return x[1] if key == "src" else r["nbmD"]
    def sel_g(r, x, key): return x[2] if key == "src" else r["nbmG"]
    out = {"all": {"source": m(P, "src"), "nbm": m(P, "nbm")}}
    for name in ("night", "evening", "day"):
        sel = [p for p in P if tod(p[0]["valid"]) == name]
        out[name] = {"source": m(sel, "src"), "nbm": m(sel, "nbm")}
    for lo, hi, lab in ((0, 5, "<5mph"), (5, 10, "5-10mph"), (10, 15, "10-15mph"), (15, 20, "15-20mph"), (20, 99, ">20mph")):
        sel = [p for p in P if lo * MPH <= p[0]["obsS"] < hi * MPH]
        out[lab] = {"source": m(sel, "src"), "nbm": m(sel, "nbm")}
    for L in (1, 3, 6, 12, 18):
        sel = [p for p in P if p[0]["lead"] == L]
        if sel:
            out[f"lead{L}"] = {"source": m(sel, "src"), "nbm": m(sel, "nbm")}
    return out


def decision(out):
    T6 = cem_table("6.0"); res = {}
    for src in ("ndfd", "ncep_nbm_conus", "ecmwf_ifs", "icon_global", "gfs_global", "ukmo_global_deterministic_10km"):
        P = pairs_for(src)
        assert all(p[0]["set"] in ("CAL", "H1", "GAP") for p in P)
        res[src] = block(P, T6); print(src, len(P), flush=True)
    json.dump(res, open(out, "w"), indent=1); print("wrote", out)


if __name__ == "__main__":
    {"impact": impact, "parity": parity, "decision": decision}[sys.argv[1]](sys.argv[2])
