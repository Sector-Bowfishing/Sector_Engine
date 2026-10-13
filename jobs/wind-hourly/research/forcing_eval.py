"""Stage 3D forcing-correction audit (pre-registered: stage3d/WIND_FORCING_CORRECTION_PREREG.md, sha256 8e83aa33…).

  python research/forcing_eval.py rows          # join forecasts + obs -> rows.pkl (CAL and H1 tagged)
  python research/forcing_eval.py fit           # fit/select every candidate on CAL ONLY -> fits.json (frozen)
  python research/forcing_eval.py cv            # station-out CV + station-type transfer, CAL only
  python research/forcing_eval.py holdout OUT   # evaluate ONCE on H1 with the frozen fits (refuses without fits.json)
"""
import hashlib, json, math, os, pickle, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend, blend_wind
from sector_wind.validate import load_obs, _metrics, _night, MPH, KT
from sector_wind.sample import circular_error, iso
from sector_wind import scoreboard as SB

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d")
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
CAL_END_INIT = datetime(2026, 8, 15, 23, tzinfo=timezone.utc)
CAL_VALID_LIMIT = datetime(2026, 8, 15, 0, tzinfo=timezone.utc)      # CAL rows must be valid before this (24 h gap rule)
H1_START = datetime(2026, 8, 16, tzinfo=timezone.utc)
LEADS = (1, 3, 6, 12, 18)
T15, T20MPH, T10 = 15 * MPH, 20 * MPH, 10 * MPH
G20, G15, G25 = 20 * KT, 15 * KT, 25 * KT
ASOS = {"DCU", "HSV", "MSL"}
P_GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
Q_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
W_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


def window(lead):
    return "le3" if lead <= 3 else ("6" if lead <= 6 else "ge12")


def exceed(points, T):
    """P(X > T) from CDF points [(x, F)], monotone after sorting; linear in x; anchored at (0, 0)."""
    pts = sorted([(0.0, 0.0)] + [(x, f) for x, f in points if x is not None and f is not None and np.isfinite(x) and np.isfinite(f)])
    xs, fs = [p[0] for p in pts], list(np.maximum.accumulate([min(1.0, max(0.0, p[1])) for p in pts]))
    if T >= xs[-1]:
        return max(0.0, 1.0 - fs[-1]) if T == xs[-1] else max(0.0, (1.0 - fs[-1]) * 0.5)  # beyond the curve: at most half the last tail
    return float(1.0 - np.interp(T, xs, fs))


# ── rows ─────────────────────────────────────────────────────────────────────────────────────

def rows():
    st, cfg = LocalStore(ROOT), load_config()
    obs = load_obs(st, START - timedelta(days=1), END + timedelta(days=2))
    sl = defaultdict(list)
    for sid, s in cfg["stations"].items():
        sl[s["lake"]].append(sid)
    W = {}
    def w(prod, lake, gridkey):
        k = (prod, lake)
        if k not in W:
            g = st.get_json(gridkey); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
            W[k] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in sl[lake]}
        return W[k]
    out, t = [], START
    while t <= END:
        for lake in cfg["lakes"]:
            c = st.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if not c:
                continue
            q = st.get_json(f"qmdx/{lake}/{t:%Y%m%d%H}.json.gz") if t.hour % 6 == 0 else None
            hg = st.get_json(f"hrrr/{lake}/{t:%Y%m%d%H}.json.gz"); huv = st.get_json(f"hrrruv/{lake}/{t:%Y%m%d%H}.json.gz")
            qs = {s["leadHours"]: s for s in (q or {}).get("steps", [])}
            hgs = {s["leadHours"]: s for s in (hg or {}).get("steps", [])}; hus = {s["leadHours"]: s for s in (huv or {}).get("steps", [])}
            wn = w("nbm", lake, c["grid"])
            wh = w("hrrr", lake, (huv or hg)["grid"]) if (huv or hg) else None
            for stp in c["steps"]:
                vt = datetime.strptime(stp["validTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                for sid, wt in wn.items():
                    o = obs.get((sid, vt))
                    if not o or o["speedMS"] is None:
                        continue
                    s, d = blend_wind(stp["speedMS"], stp["dirFromDeg"], wt)
                    if s is None:
                        continue
                    r = {"station": sid, "type": "ASOS" if sid in ASOS else "AWOS", "lake": lake, "init": t, "valid": vt,
                         "lead": stp["leadHours"], "night": _night(vt), "set": "CAL" if (t <= CAL_END_INIT and vt < CAL_VALID_LIMIT) else ("H1" if t >= H1_START else "GAP"),
                         "nbmS": s, "nbmD": d, "nbmG": blend(stp["gustMS"], wt),
                         "obsS": o["speedMS"], "obsD": o["dirFromDeg"], "obsG": o["gustMS"], "synoptic": t.hour % 6 == 0}
                    L = stp["leadHours"]
                    if q and L in qs:
                        qq = qs[L]; b = lambda k: blend(qq[k], wt)
                        wpts = [(3.6011, 1 - b("windProbGt3.6011") / 100), (5.6588, 1 - b("windProbGt5.6588") / 100),
                                (8.7456, 1 - b("windProbGt8.7456") / 100), (11.3178, 1 - b("windProbGt11.3178") / 100),
                                (blend(stp["speedP50"], wt) if "speedP50" in stp else None, 0.5), (b("windP75"), 0.75),
                                (blend(stp["speedP90"], wt) if "speedP90" in stp else None, 0.9)]
                        gpts = [(8.7456, 1 - b("gustProbGt8.7456") / 100), (11.3178, 1 - b("gustProbGt11.3178") / 100),
                                (15.4333, 1 - b("gustProbGt15.4333") / 100), (b("gustP50"), 0.5), (b("gustP75"), 0.75),
                                (blend(stp["gustP90"], wt) if "gustP90" in stp else None, 0.9)]
                        r.update({"pW15": exceed(wpts, T15), "pW10": exceed(wpts, T10), "pW20m": exceed(wpts, T20MPH),
                                  "pG20": exceed(gpts, G20), "pG15": exceed(gpts, G15), "pG25": exceed(gpts, G25)})
                    if wh and L in hus:
                        hs, hd = blend_wind([math.hypot(a, b2) if a is not None and b2 is not None else None for a, b2 in zip(hus[L]["u"], hus[L]["v"])],
                                            [(math.degrees(math.atan2(-a, -b2)) + 360) % 360 if a is not None and b2 is not None else None
                                             for a, b2 in zip(hus[L]["u"], hus[L]["v"])], wh[sid])
                        r.update({"hrrrS": hs, "hrrrD": hd})
                    if wh and L in hgs:
                        r["hrrrG"] = blend(hgs[L]["gustMS"], wh[sid])
                    out.append(r)
        t += timedelta(hours=1)
    os.makedirs(OUT, exist_ok=True)
    pickle.dump(out, open(os.path.join(OUT, "rows.pkl"), "wb"))
    from collections import Counter
    print(len(out), Counter(r["set"] for r in out), "with qmd", sum("pW15" in r for r in out), "with hrrr", sum("hrrrS" in r for r in out))


def load_rows(sets):
    R = pickle.load(open(os.path.join(OUT, "rows.pkl"), "rb"))
    return [r for r in R if r["set"] in sets]


# ── candidate functions (pure, given frozen fits) ───────────────────────────────────────────

def qmap(x, m):
    return float(max(0.0, np.interp(x, m["f"], m["o"]) if x <= m["f"][-1] else m["o"][-1] + (x - m["f"][-1])))


def vec(s1, d1, s2, d2, w):
    if s1 is None or d1 is None or s2 is None or d2 is None:
        return None, None
    u = w * -s1 * math.sin(math.radians(d1)) + (1 - w) * -s2 * math.sin(math.radians(d2))
    v = w * -s1 * math.cos(math.radians(d1)) + (1 - w) * -s2 * math.cos(math.radians(d2))
    return math.hypot(u, v), (math.degrees(math.atan2(-u, -v)) + 360) % 360


def speed(r, cand, F):
    if cand == "S0": return r["nbmS"]
    if cand == "S1": return qmap(r["nbmS"], F["S1"])
    if cand == "S2": return qmap(r["nbmS"], F["S2"][r["type"]])
    if cand == "S3": return r.get("hrrrS")
    if cand == "S4":
        if r.get("hrrrS") is None: return None
        wt = F["S4"][window(r["lead"])]; return wt * r["nbmS"] + (1 - wt) * r["hrrrS"]


def event15(r, cand, F):
    if cand == "E0": return r["nbmS"] >= T15
    if cand == "E1": return None if "pW15" not in r else r["pW15"] >= F["E1"]
    if cand == "E2": return None if r.get("hrrrS") is None else r["hrrrS"] >= T15
    if cand == "E3": return speed(r, "S2", F) >= T15
    if cand == "E4":
        a, b = event15(r, "E1", F), event15(r, "E2", F)
        return None if a is None or b is None else (a or b)


def direction(r, cand, F):
    if cand == "D0": return r["nbmS"], r["nbmD"]
    if cand == "D1": return r.get("hrrrS"), r.get("hrrrD")
    if cand == "D2": return vec(r["nbmS"], r["nbmD"], r.get("hrrrS"), r.get("hrrrD"), F["D2"][window(r["lead"])])
    if cand == "D3": return (r.get("hrrrS"), r.get("hrrrD")) if r["lead"] <= 6 else (r["nbmS"], r["nbmD"])


def gust(r, cand, F):
    """(value, event20)"""
    if cand == "G1": return r["nbmG"], (r["nbmG"] or 0) >= G20
    if cand == "G2": return r["nbmG"], (None if "pG20" not in r else r["pG20"] >= F["G2"])
    if cand == "G3": return r.get("hrrrG"), (None if r.get("hrrrG") is None else r["hrrrG"] >= G20)
    if cand == "G5": return (None if r["nbmG"] is None else r["nbmG"] * F["G5"]), (None if "pG20" not in r else r["pG20"] >= F["G2"])


ARCH = {0: ("S0", "E0", "D0", "G1"), 1: ("S0", "E1", "D0", "G2"), 2: ("S4", "E4", "D2", "G3"), 3: ("S2", "E3", "D0", "G5")}


# ── metric helpers ──────────────────────────────────────────────────────────────────────────

def cont(pairs):
    """pairs: (forecastEvent bool, observedEvent bool)."""
    h = sum(f and o for f, o in pairs); m = sum(o and not f for f, o in pairs); fa = sum(f and not o for f, o in pairs)
    return {"obs": h + m, "fc": h + fa, "hits": h, "pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None,
            "csi": h / (h + m + fa) if h + m + fa else None}


def brier_auc(ps, ys):
    ps, ys = np.array(ps, float), np.array(ys, float)
    if len(ps) == 0 or ys.sum() == 0 or ys.sum() == len(ys):
        return {"n": int(len(ps)), "brier": float(((ps - ys) ** 2).mean()) if len(ps) else None, "auc": None}
    order = np.argsort(ps); ranks = np.empty(len(ps)); ranks[order] = np.arange(1, len(ps) + 1)
    pos = ys == 1; auc = (ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum())
    bins = [(lo, lo + 0.1) for lo in np.arange(0, 1.0, 0.1)]
    rel = [{"bin": f"{lo:.1f}-{hi:.1f}", "n": int(((ps >= lo) & (ps < hi + (hi >= 1))).sum()),
            "obsFreq": float(ys[(ps >= lo) & (ps < hi + (hi >= 1))].mean()) if ((ps >= lo) & (ps < hi + (hi >= 1))).any() else None} for lo, hi in bins]
    return {"n": int(len(ps)), "brier": float(((ps - ys) ** 2).mean()), "auc": float(auc), "reliability": rel}


def dir_stats(pairs):
    e = np.array([circular_error(f, o) for f, o in pairs])
    return {"n": len(e), "within22_5": float((e <= 22.5).mean()) if len(e) else None, "circMAE": float(e.mean()) if len(e) else None,
            "within45": float((e <= 45).mean()) if len(e) else None, "median": float(np.median(e)) if len(e) else None}


def dir_pairs(R, cand, F):
    out = []
    for r in R:
        fs, fd = direction(r, cand, F)
        if fs is not None and fd is not None and r["obsD"] is not None and fs >= 2.6 and r["obsS"] >= 2.6:
            out.append((fd, r["obsD"]))
    return out


# ── fit on CAL ──────────────────────────────────────────────────────────────────────────────

def fit_qmap(R):
    qs = np.linspace(0.005, 0.995, 100)
    f = np.quantile([r["nbmS"] for r in R], qs); o = np.quantile([r["obsS"] for r in R], qs)
    f, o = np.maximum.accumulate(f), np.maximum.accumulate(o)
    keep = np.concatenate([[True], np.diff(f) > 1e-6])
    return {"f": [0.0] + list(map(float, f[keep])), "o": [0.0] + list(map(float, o[keep]))}


def select_p(R, key, obs_ok, grid, far_cap):
    best = None
    for p in grid:
        c = cont([(r[key] >= p, obs_ok(r)) for r in R if key in r])
        ok = c["far"] is not None and c["far"] <= far_cap
        score = (ok, c["csi"] or 0)
        if best is None or score > best[0]:
            best = (score, p, c)
    return best[1], best[2]


def fit(R=None):
    R = R or load_rows({"CAL"})
    F = {"S1": fit_qmap(R)}
    F["S2"] = {t: (fit_qmap([r for r in R if r["type"] == t]) if any(r["type"] == t for r in R) else F["S1"]) for t in ("ASOS", "AWOS")}
    F["S4"] = {}
    for wdw in ("le3", "6", "ge12"):
        sub = [r for r in R if window(r["lead"]) == wdw and r.get("hrrrS") is not None]
        F["S4"][wdw] = min(W_GRID, key=lambda wt: np.mean([abs(wt * r["nbmS"] + (1 - wt) * r["hrrrS"] - r["obsS"]) for r in sub]))
    F["E1"], F["E1_cal"] = select_p([r for r in R if r["synoptic"]], "pW15", lambda r: r["obsS"] >= T15, P_GRID, 0.5)
    F["D2"] = {}
    for wdw in ("le3", "6", "ge12"):
        sub = [r for r in R if window(r["lead"]) == wdw]
        F["D2"][wdw] = max(W_GRID, key=lambda wt: dir_stats([p for p in dir_pairs(sub, "D2", {"D2": {wdw: wt}})])["within22_5"] or 0)
    F["G2"], F["G2_cal"] = select_p([r for r in R if r["synoptic"]], "pG20", lambda r: (r["obsG"] or 0) >= G20, Q_GRID, 0.6)
    cond = [r for r in R if r["obsG"] is not None and r["nbmG"] is not None]
    F["G5"] = float(np.mean([r["obsG"] for r in cond]) / np.mean([r["nbmG"] for r in cond]))
    return F


def cmd_fit():
    F = fit()
    F["_frozenAt"] = iso(datetime.now(timezone.utc)); F["_prereg"] = "8e83aa33a0d481cc1cc1b794bd73934f28e5cb6c43d2250a0f26aaebd27bc667"
    p = os.path.join(OUT, "fits.json"); json.dump(F, open(p, "w"), indent=1, default=float)
    F["_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    print(json.dumps({k: v for k, v in F.items() if k not in ("S1", "S2")}, indent=1, default=float))


# ── evaluation ──────────────────────────────────────────────────────────────────────────────

def evaluate(R, F):
    """Frozen-dimension quantities and diagnostics for every candidate on rows R."""
    res = {"rows": len(R)}
    night = [r for r in R if r["night"]]
    syn = [r for r in R if r["synoptic"]]
    def spd(rows_, cand):
        p = [(speed(r, cand, F), r["obsS"]) for r in rows_]; p = [(a, b) for a, b in p if a is not None]
        e = np.array([a - b for a, b in p])
        return {"n": len(e), "mae": float(np.abs(e).mean()) if len(e) else None, "bias": float(e.mean()) if len(e) else None}
    res["speed"] = {c: {"night": spd(night, c), "all": spd(R, c), "nightSynoptic": spd([r for r in night if r["synoptic"]], c)} for c in ("S0", "S1", "S2", "S3", "S4")}
    def ev(rows_, cand):
        p = [(event15(r, cand, F), r["obsS"] >= T15) for r in rows_]; p = [(a, b) for a, b in p if a is not None]
        return {**cont(p), "n": len(p), "obsStationHours": len({(r["station"], r["valid"]) for r in rows_ if r["obsS"] >= T15})}
    res["event15"] = {c: {"night": ev(night, c), "all": ev(R, c), "nightSynoptic": ev([r for r in night if r["synoptic"]], c),
                          "allSynoptic": ev(syn, c)} for c in ("E0", "E1", "E2", "E3", "E4")}
    res["event15_prob"] = {"night": brier_auc([r["pW15"] for r in night if "pW15" in r], [r["obsS"] >= T15 for r in night if "pW15" in r]),
                           "all": brier_auc([r["pW15"] for r in syn if "pW15" in r], [r["obsS"] >= T15 for r in syn if "pW15" in r])}
    res["eventDiag"] = {f"{k}": {"raw": cont([(r["nbmS"] >= T, r["obsS"] >= T) for r in R]),
                                 "prob@E1": cont([(r[pk] >= F["E1"], r["obsS"] >= T) for r in syn if pk in r])}
                        for k, T, pk in (("10mph", T10, "pW10"), ("20mph", T20MPH, "pW20m"))}
    res["direction"] = {c: dir_stats(dir_pairs(R, c, F)) for c in ("D0", "D1", "D2", "D3")}
    res["directionNight"] = {c: dir_stats(dir_pairs(night, c, F)) for c in ("D0", "D1", "D2", "D3")}
    res["directionByWindow"] = {w_: {c: dir_stats(dir_pairs([r for r in R if window(r["lead"]) == w_], c, F)) for c in ("D0", "D1", "D2", "D3")}
                                for w_ in ("le3", "6", "ge12")}
    def gs(rows_, cand):
        v = [(gust(r, cand, F), r) for r in rows_]
        cond = [(g[0], r["obsG"]) for g, r in v if g[0] is not None and r["obsG"] is not None]
        e = np.array([a - b for a, b in cond])
        evp = [(g[1], (r["obsG"] or 0) >= G20) for g, r in v if g[1] is not None]
        return {"condN": len(e), "condBias": float(e.mean()) if len(e) else None, **cont(evp), "n": len(evp)}
    res["gust"] = {c: {"all": gs(R, c), "allSynoptic": gs(syn, c), "ASOS": gs([r for r in R if r["type"] == "ASOS"], c),
                       "AWOS": gs([r for r in R if r["type"] == "AWOS"], c)} for c in ("G1", "G2", "G3", "G5")}
    res["gust_prob"] = brier_auc([r["pG20"] for r in syn if "pG20" in r], [(r["obsG"] or 0) >= G20 for r in syn if "pG20" in r])
    res["gustDiag"] = {k: {"G1": cont([((r["nbmG"] or 0) >= T, (r["obsG"] or 0) >= T) for r in R]),
                           "G3": cont([((r.get("hrrrG") or 0) >= T, (r["obsG"] or 0) >= T) for r in R if r.get("hrrrG") is not None])}
                       for k, T in (("15kt", G15), ("25kt", G25))}
    res["byLead"] = {L: {"S0night": spd([r for r in night if r["lead"] == L], "S0"),
                         **{c: spd([r for r in night if r["lead"] == L], c) for c in ("S1", "S2", "S4")},
                         **{c: dir_stats(dir_pairs([r for r in R if r["lead"] == L], c, F))["within22_5"] for c in ("D0", "D2", "D3")}}
                     for L in LEADS}
    return res


def skill_json(R, arch, F, obs_all):
    """validate.skill-format dict for one architecture on rows R, so scoreboard.dims_1_to_4 scores it unchanged."""
    S, E, D, G = ARCH[arch]
    def per(rows_):
        out = {}
        for L in LEADS:
            sub = [r for r in rows_ if r["lead"] == L]
            recs = []
            for r in sub:
                fs = speed(r, S, F); ds = direction(r, D, F); gv, _ = gust(r, G, F)
                if fs is None or ds[1] is None:
                    continue
                recs.append((fs, ds[1], gv, r["obsS"], r["obsD"], r["obsG"]))
            m = _metrics(recs) if recs else {"n": 0}
            if D != "D0":     # direction from the architecture's direction source with its own speed gate
                dd = dir_stats(dir_pairs(sub, D, F)); m.update({"dir_n": dd["n"], "dir_within22_5": dd["within22_5"], "dir_mean": dd["circMAE"]})
            c15 = cont([(event15(r, E, F), r["obsS"] >= T15) for r in sub if event15(r, E, F) is not None])
            obs15 = len({(r["station"], r["valid"]) for r in sub if r["obsS"] >= T15})
            m.update({"n_obs_15mph": obs15 if obs15 >= 10 else 0,     # pre-registered: < 10 observed events -> unmeasured
                      "pod_15mph": c15["pod"] if obs15 >= 10 else None, "far_15mph": c15["far"]})
            cg = cont([(gust(r, G, F)[1], (r["obsG"] or 0) >= G20) for r in sub if gust(r, G, F)[1] is not None])
            m.update({"gust20_pod": cg["pod"], "gust20_far": cg["far"]})
            out[str(L)] = m
        return out
    night = [r for r in R if r["night"]]
    win = [min(r["valid"] for r in R).isoformat(), max(r["valid"] for r in R).isoformat()]
    from sector_wind.evidence import persistence_recs
    pers = {str(L): _metrics(persistence_recs(obs_all, min(r["valid"] for r in R), max(r["valid"] for r in R), L, True)) for L in LEADS}
    return {"nbm": {"window": win, "night": per(night), "allHours": per(R), "persistenceNight": pers}}


def cmd_cv():
    R = load_rows({"CAL"}); out = {"stationOut": {}, "typeTransfer": {}}
    for sid in sorted({r["station"] for r in R}):
        tr = [r for r in R if r["station"] != sid]; te = [r for r in R if r["station"] == sid]
        Fx = fit(tr); ev = evaluate(te, Fx)
        out["stationOut"][sid] = {"nightMAE": {c: ev["speed"][c]["night"]["mae"] for c in ("S0", "S1", "S2", "S4")},
                                  "within22_5": {c: ev["direction"][c]["within22_5"] for c in ("D0", "D2", "D3")},
                                  "e15all": {c: (ev["event15"][c]["all"]["pod"], ev["event15"][c]["all"]["far"], ev["event15"][c]["all"]["obs"]) for c in ("E0", "E1", "E3")},
                                  "g20": {c: (ev["gust"][c]["all"]["pod"], ev["gust"][c]["all"]["far"]) for c in ("G1", "G2", "G3")}}
    for a, b in (("ASOS", "AWOS"), ("AWOS", "ASOS")):
        Fx = fit([r for r in R if r["type"] == a]); ev = evaluate([r for r in R if r["type"] == b], Fx)
        out["typeTransfer"][f"{a}->{b}"] = {"nightMAE": {c: ev["speed"][c]["night"]["mae"] for c in ("S0", "S1", "S4")},
                                            "within22_5": {c: ev["direction"][c]["within22_5"] for c in ("D0", "D2")},
                                            "e15all": {c: (ev["event15"][c]["all"]["pod"], ev["event15"][c]["all"]["far"]) for c in ("E0", "E1")}}
    json.dump(out, open(os.path.join(OUT, "cv.json"), "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float)[:6000])


def cmd_holdout(outp):
    p = os.path.join(OUT, "fits.json")
    if not os.path.exists(p):
        raise SystemExit("refusing: fits.json (frozen CAL fits) must exist before H1 is read")
    ledger = os.path.join(OUT, "holdout_ledger.jsonl"); fh = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if os.path.exists(ledger) and any(json.loads(l)["fitsSha256"] == fh for l in open(ledger)):
        raise SystemExit("refusing: H1 was already evaluated with these frozen fits (one-shot)")
    F = json.load(open(p)); H = load_rows({"H1"}); C = load_rows({"CAL"})
    st = LocalStore(ROOT); obs = load_obs(st, START - timedelta(days=1), END + timedelta(days=2))
    res = {"fitsSha256": fh, "H1": evaluate(H, F), "CAL": evaluate(C, F), "skill": {}}
    for a in ARCH:
        rows_ = [r for r in H if r["synoptic"]] if a == 1 else H
        sj = skill_json(rows_, a, F, obs); res["skill"][a] = sj
        d = SB.dims_1_to_4(sj, f"arch{a} H1")
        res.setdefault("dims", {})[a] = {k: {"points": round(SB.WEIGHTS[k] * v["credit"], 2), "credit": v["credit"], "why": v["why"],
                                             "conditions": v["conditions"]} for k, v in d.items()}
    sj = skill_json([r for r in H if r["synoptic"]], 0, F, obs); d = SB.dims_1_to_4(sj, "arch0 H1 synoptic")
    res["dims"]["0syn"] = {k: {"points": round(SB.WEIGHTS[k] * v["credit"], 2), "why": v["why"]} for k, v in d.items()}
    json.dump(res, open(outp, "w"), indent=1, default=str)
    open(ledger, "a").write(json.dumps({"fitsSha256": fh, "at": iso(datetime.now(timezone.utc)), "out": outp}) + "\n")
    print("wrote", outp)


if __name__ == "__main__":
    {"rows": rows, "fit": cmd_fit, "cv": cmd_cv}.get(sys.argv[1], lambda: cmd_holdout(sys.argv[2]))()
