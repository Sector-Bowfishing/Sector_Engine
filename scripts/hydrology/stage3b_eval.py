"""Clarity Fusion Stage 3B: preregistered out-of-sample validation.

THIS SCRIPT IS PART OF THE PREREGISTRATION (CLARITY_STAGE_3B_PREREGISTRATION.md
records its SHA-256). It was written and hashed before any pre-2025 data was
read. Any change after that is a deviation and must be logged in the hand-off.

Two modes:

  derive    reads ONLY the discovery years (2025-2026) and writes the frozen
            constants: noise bands, dry shares, the challengers' adjustments
  evaluate  reads the constants and scores the untouched years, never
            re-estimating anything from them

usage:
  python3 stage3b_eval.py derive   --data DISCOVERY_SPEC.json --out constants.json
  python3 stage3b_eval.py evaluate --data VALIDATION_SPEC.json --constants constants.json
                                   --years 2021,2022,2023,2024 --separate 2020 --out results.json

A data spec is JSON: {"zoneHistory": [files], "anchors": [dirs], "armZones": file,
"rainDaily": [files], "rainHours": [files], "nwm": [files], "usgs": [files],
"graph": file}. Lists are merged in order.
"""
import sys, os, json, glob, math, bisect, random, argparse, statistics as st, datetime as dt, collections
from math import comb

COLD = {11, 12, 1, 2, 3}
STORM_IN = 1.0            # a storm day: >= 1.0 in on the drainage in one 17Z-17Z window
DRY_WEEK_IN = 0.25        # a dry week: < 0.25 in over the ~7 days before the pass
STORM_WINDOW = (0, 3)     # the preregistered response window, days after the storm day
LOOKBACK_DAYS = 45        # baseline and persistence reach
MIN_BASE = 2              # dry-week passes needed for a baseline
EPISODE_GAP_DAYS = 3      # storm days this close are one hydrologic episode
FLOW_HIGH, FLOW_LOW = 3.0, 1.5   # NWM relative to its own baseline-pass median
MIN_DELTA_UNITS = 8       # discovery units needed to set an adjustment (else 0)
BOOT = 2000
POSITIONS = ("head", "upper", "middle", "lower", "mouth", "whole")


def ptime(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]


def binp(k, n, p): return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)) if n else 1.0


def load(spec):
    S = json.load(open(spec))
    zh = {}
    for f in S["zoneHistory"]:
        opener = __import__("gzip").open if f.endswith(".gz") else open
        zh.update(json.load(opener(f, "rt"))["passes"])
    zz = json.load(open(S["armZones"]))
    rain_d, rain_h, nwm_days, nwm_ver, usgs = {}, {}, {}, {}, {}
    reach_to_arms = {}
    for f in S["rainDaily"]: rain_d.update(json.load(open(f))["days"])
    for f in S["rainHours"]:
        opener = __import__("gzip").open if f.endswith(".gz") else open
        rain_h.update(json.load(opener(f, "rt"))["hours"])
    for f in S["nwm"]:
        n = json.load(open(f)); nwm_days.update(n["days"]); nwm_ver.update(n.get("versions", {}))
        reach_to_arms.update(n.get("reachToArms", {}))
    for f in S["usgs"]:
        for site, pts in json.load(open(f)).items():
            usgs.setdefault(site, []).extend(pts)
    for site in usgs:
        usgs[site] = sorted({p[0]: p for p in usgs[site]}.values(), key=lambda p: ptime(p[0]))
    anchors = {}
    for d in S["anchors"]:
        for f in glob.glob(os.path.join(d, "*.json")):
            anchors[os.path.basename(f)[:-5]] = json.load(open(f))
    graph = json.load(open(S["graph"]))
    return zh, zz, rain_d, rain_h, nwm_days, nwm_ver, reach_to_arms, usgs, anchors, graph


class Data:
    def __init__(self, spec):
        (self.zh, zz, self.rain_d, self.rain_h, self.nwm, self.nwm_ver, r2a, self.usgs, self.anchors, graph) = load(spec)
        self.zones = {str(z["zone"]): z for z in zz["zones"]}
        self.armmeta = zz["arms"]
        self.arms = {a["id"]: a for a in graph["arms"]}
        self.arm_to_reach = {arm: r for r, al in r2a.items() for arm in al}
        self.usgs_ts = {s: [ptime(p[0]) for p in v] for s, v in self.usgs.items()}
        self.passes = sorted(self.zh.values(), key=lambda p: p["time"])
        for p in self.passes:
            p["t"] = ptime(p["time"]); p["day"] = p["t"].date()
        self.ctx_cache = {}
        self._storms()

    # ---- rain
    def window(self, key, day, tail):
        if tail:
            D = dt.datetime(day.year, day.month, day.day)
            hs = [D - dt.timedelta(hours=6 - k) for k in range(6)] + [D + dt.timedelta(hours=k) for k in range(17)]
            vals = [(self.rain_h.get(f"{h:%Y-%m-%dT%H}") or {}).get(key) for h in hs]
            return None if any(v is None for v in vals) else sum(vals)
        r = self.rain_d.get(day.isoformat())
        return None if (r is None or r.get(key) is None) else r[key]

    def ctx(self, key, day):
        k = (key, day)
        if k not in self.ctx_cache:
            tail = self.window(key, day, True)
            wk = [tail] + [self.window(key, day - dt.timedelta(days=i), False) for i in range(1, 7)]
            week = None if any(v is None for v in wk) else sum(wk)
            lag = amt = None
            for i in range(0, 11):
                v = tail if i == 0 else self.window(key, day - dt.timedelta(days=i), False)
                if v is not None and v >= STORM_IN:
                    lag, amt = i, v; break
            self.ctx_cache[k] = (week, lag, amt)
        return self.ctx_cache[k]

    def _storms(self):
        days = set()
        for d, r in self.rain_d.items():
            if r and any((v or 0) >= STORM_IN for k, v in r.items() if not k.startswith("_")):
                days.add(dt.date.fromisoformat(d))
        self.storm_days = sorted(days)
        eps = []
        for d in self.storm_days:
            if eps and (d - eps[-1][-1]).days <= EPISODE_GAP_DAYS: eps[-1].append(d)
            else: eps.append([d])
        self.episodes = eps
        self.ep_of = {d: i for i, e in enumerate(eps) for d in e}

    def episode(self, day, lag):
        if lag is None: return None
        d = day - dt.timedelta(days=lag)
        if d in self.ep_of: return self.ep_of[d]
        for dd in (d - dt.timedelta(days=1), d + dt.timedelta(days=1)):
            if dd in self.ep_of: return self.ep_of[dd]
        return None

    # ---- flow
    def nwm_at(self, arm, day):
        r = self.arm_to_reach.get(arm)
        v = (self.nwm.get(day.isoformat()) or {}).get(r) if r else None
        return v, self.nwm_ver.get(day.isoformat(), "unrecorded")

    def usgs_at(self, site, t):
        ts = self.usgs_ts.get(site); pts = self.usgs.get(site)
        if not ts: return None
        i = bisect.bisect_left(ts, t); best = None
        for j in (i - 1, i):
            if 0 <= j < len(ts) and abs((ts[j] - t).total_seconds()) <= 3600:
                if best is None or abs((ts[j] - t).total_seconds()) < abs((ts[best] - t).total_seconds()): best = j
        return None if best is None else pts[best][1]

    # ---- units
    def cls_of(self, arm):
        K = self.armmeta.get(arm, {}).get("zones")
        return "large" if K == 5 else "medium" if K in (2, 3) else "small" if K == 1 else None

    def units(self):
        """Every measurable observation of every unit (zone, or the main stem),
        with its rain, flow and baseline context, in time order per unit."""
        series = collections.defaultdict(list)
        for p in self.passes:
            for zid, z in p["zones"].items():
                zm = self.zones.get(zid)
                if not zm or not self.cls_of(zm["arm"]): continue
                if z["measurable"] and z["fnu"]:
                    series[("zone", zid)].append((p, math.log10(z["fnu"][1]), z["coverage"]))
            a = self.anchors.get(f"{p['date']}_{p['platform']}")
            ms = a and a.get("mainStem")
            if ms and ms["observedFNU"] and ms["waterCells"] and ms["observedCells"] >= 30 \
                    and ms["observedCells"] / ms["waterCells"] >= 0.30:
                series[("main", "mainstem")].append((p, math.log10(ms["observedFNU"]["p50"]), ms["observedCells"] / ms["waterCells"]))
        out = []
        for (kind, uid), seq in series.items():
            if kind == "zone":
                zm = self.zones[uid]; arm = zm["arm"]; rainkey = arm
                meta = {"arm": arm, "pos": zm["name"], "idx": zm["index"], "of": zm["of"], "class": self.cls_of(arm)}
            else:
                arm = None; rainkey = "_lakeSurface"
                meta = {"arm": "mainstem", "pos": "mainstem", "idx": 0, "of": 1, "class": "mainStem"}
            a = self.arms.get(arm) if arm else None
            for i, (p, lv, cov) in enumerate(seq):
                week, lag, amt = self.ctx(rainkey, p["day"])
                base, basepasses = [], []
                for pq, lq, _ in seq[:i]:
                    if (p["t"] - pq["t"]).days <= LOOKBACK_DAYS:
                        wq = self.ctx(rainkey, pq["day"])[0]
                        if wq is not None and wq < DRY_WEEK_IN: base.append(lq); basepasses.append(pq)
                prev = next(((pq, lq, cq) for pq, lq, cq in reversed(seq[:i]) if (p["t"] - pq["t"]).days <= LOOKBACK_DAYS), None)
                u = dict(meta, unit=uid, date=p["day"], time=p["time"], t=p["t"], l=lv, cov=cov, week=week, lag=lag, amt=amt,
                         season="cold" if p["day"].month in COLD else "warm",
                         base=st.median(base) if len(base) >= MIN_BASE else None,
                         prev=prev, ep=self.episode(p["day"], lag), nwmRatio=None, usgsRatio=None)
                if u["base"] is not None: u["anom"] = lv - u["base"]
                # NWM, relative to its own value on the baseline passes' days, same model version only
                if a and a.get("flowSource") == "modeledNWM" and basepasses:
                    qn, vn = self.nwm_at(arm, p["day"])
                    bq = [self.nwm_at(arm, pq["day"]) for pq in basepasses]
                    bq = [v for v, ver in bq if v is not None and ver == vn]
                    if qn is not None and len(bq) >= MIN_BASE and st.median(bq) > 0:
                        u["nwmRatio"] = qn / st.median(bq)
                if a and a.get("usgsDischargeSite") and basepasses:
                    site = a["usgsDischargeSite"]
                    qn = self.usgs_at(site, p["t"]); bq = [self.usgs_at(site, pq["t"]) for pq in basepasses]
                    bq = [x for x in bq if x]
                    if qn and len(bq) >= MIN_BASE: u["usgsRatio"] = qn / st.median(bq)
                out.append(u)
        return out


def storm_window(u):
    return u["lag"] is not None and STORM_WINDOW[0] <= u["lag"] <= STORM_WINDOW[1]


def storm_after_prev(u):
    return u["lag"] is not None and u["prev"] is not None and (u["date"] - dt.timedelta(days=u["lag"])) > u["prev"][0]["day"]


def season_condition(u): return u["season"] == "cold" and storm_window(u) and storm_after_prev(u)


def flow_condition(u): return u["nwmRatio"] is not None and u["nwmRatio"] >= FLOW_HIGH


def noise_key(u): return "mainstem" if u["class"] == "mainStem" else u["pos"]


# ------------------------------------------------------------------ derive
def derive(D, out):
    us = [u for u in D.units() if "anom" in u and u["date"].year in (2025, 2026)]
    C = {"discoveryYears": [2025, 2026], "rules": {
        "coldMonths": sorted(COLD), "stormIn": STORM_IN, "dryWeekIn": DRY_WEEK_IN, "stormWindowDays": STORM_WINDOW,
        "lookbackDays": LOOKBACK_DAYS, "minBaselinePasses": MIN_BASE, "episodeGapDays": EPISODE_GAP_DAYS,
        "flowHigh": FLOW_HIGH, "flowLow": FLOW_LOW, "minDeltaUnits": MIN_DELTA_UNITS}, "noise": {}, "dryShare": {}, "delta": {}}
    for key in POSITIONS + ("mainstem",):
        xs = [u["anom"] for u in us if noise_key(u) == key and u["week"] is not None and u["week"] < DRY_WEEK_IN]
        if len(xs) >= 20:
            C["noise"][key] = [round(q(xs, .1), 4), round(q(xs, .9), 4), len(xs)]
            C["dryShare"][key] = round(sum(x > C["noise"][key][1] for x in xs) / len(xs), 4)
        else:
            C["noise"][key] = None
    pooled = [u["anom"] for u in us if u["week"] is not None and u["week"] < DRY_WEEK_IN and u["class"] != "mainStem"]
    for key in POSITIONS + ("mainstem",):
        if C["noise"][key] is None:
            C["noise"][key] = [round(q(pooled, .1), 4), round(q(pooled, .9), 4), len(pooled)]; C["noise"][key + "_fromPooled"] = True
            C["dryShare"][key] = round(sum(x > C["noise"][key][1] for x in pooled) / len(pooled), 4)
    for cl in ("large", "medium", "small", "mainStem"):
        d = {}
        s_ = [u["anom"] for u in us if u["class"] == cl and u["season"] == "cold" and storm_window(u)]
        f_ = [u["anom"] for u in us if u["class"] == cl and flow_condition(u)]
        b_ = [u["anom"] for u in us if u["class"] == cl and u["season"] == "cold" and storm_window(u) and flow_condition(u)]
        d["season"] = round(st.median(s_), 4) if len(s_) >= MIN_DELTA_UNITS else 0.0
        d["flow"] = round(st.median(f_), 4) if len(f_) >= MIN_DELTA_UNITS else 0.0
        d["combined"] = round(st.median(b_), 4) if len(b_) >= MIN_DELTA_UNITS else round((d["season"] + d["flow"]) / 2, 4)
        d["n"] = {"season": len(s_), "flow": len(f_), "combined": len(b_)}
        C["delta"][cl] = d
    json.dump(C, open(out, "w"), indent=1, default=str)
    print(json.dumps(C, indent=1, default=str))


# --------------------------------------------------------------- evaluate
def murkier(u, C): return u["anom"] > C["noise"][noise_key(u)][1]


def direction(delta, u, C):
    lo, hi = C["noise"][noise_key(u)][:2]
    return "murkier" if delta > hi else "clearer" if delta < lo else "same"


def predict(u, C):
    pers = u["prev"][1]; base = u["base"]; dl = C["delta"][u["class"]]
    sc, fc = season_condition(u), flow_condition(u)
    return {"persistence": pers, "reversion": base,
            "season": base + dl["season"] if sc else pers,
            "flow": base + dl["flow"] if fc else pers,
            "combined": (base + dl["combined"]) if (sc and fc) else (base + dl["season"]) if sc else (base + dl["flow"]) if fc else pers,
            "_sc": sc, "_fc": fc}


def cluster_of(u):
    return f"ep{u['ep']}" if u["ep"] is not None else f"d{u['date']}"


def boot(rows, f, clusterf=cluster_of, n=BOOT, seed=13):
    by = collections.defaultdict(list)
    for r in rows: by[clusterf(r)].append(r)
    ks = list(by)
    if not ks: return (float("nan"), float("nan"))
    rnd = random.Random(seed); vals = []
    for _ in range(n):
        s = [r for k in (rnd.choice(ks) for _ in ks) for r in by[k]]
        v = f(s)
        if v == v: vals.append(v)
    vals.sort()
    return (round(vals[int(.025 * len(vals))], 4), round(vals[int(.975 * len(vals))], 4)) if vals else (float("nan"), float("nan"))


def share(rows, C): return sum(murkier(u, C) for u in rows) / len(rows) if rows else float("nan")


def test_hypothesis(cond, ctrl, C, years):
    """Pooled and per-year difference in the murkier-beyond-noise share, cluster bootstrap."""
    def diff(c, k): return share(c, C) - share(k, C) if c and k else float("nan")
    res = {"pooled": {"conditionUnits": len(cond), "controlUnits": len(ctrl),
                      "conditionShare": round(share(cond, C), 4) if cond else None,
                      "controlShare": round(share(ctrl, C), 4) if ctrl else None,
                      "diff": round(diff(cond, ctrl), 4) if cond and ctrl else None,
                      "independentStorms": len({u["ep"] for u in cond if u["ep"] is not None})}}
    # joint bootstrap: resample condition clusters and control clusters independently
    rnd = random.Random(17)
    bc = collections.defaultdict(list); bk = collections.defaultdict(list)
    for u in cond: bc[cluster_of(u)].append(u)
    for u in ctrl: bk[f"d{u['date']}"].append(u)
    kc, kk = list(bc), list(bk); vals = []
    if kc and kk:
        for _ in range(BOOT):
            c = [u for k in (rnd.choice(kc) for _ in kc) for u in bc[k]]
            k_ = [u for k in (rnd.choice(kk) for _ in kk) for u in bk[k]]
            vals.append(share(c, C) - share(k_, C))
        vals.sort()
        res["pooled"]["diffCI"] = (round(vals[int(.025 * len(vals))], 4), round(vals[int(.975 * len(vals))], 4))
    res["byYear"] = {}
    for y in years:
        c = [u for u in cond if u["date"].year == y]; k = [u for u in ctrl if u["date"].year == y]
        storms = len({u["ep"] for u in c if u["ep"] is not None})
        res["byYear"][str(y)] = {"conditionUnits": len(c), "controlUnits": len(k), "independentStorms": storms,
                                 "conditionShare": round(share(c, C), 4) if c else None,
                                 "controlShare": round(share(k, C), 4) if k else None,
                                 "diff": round(diff(c, k), 4) if c and k else None,
                                 "qualifies": storms >= 3 and len(c) >= 8 and len(k) >= 8}
    q_ = [v for v in res["byYear"].values() if v["qualifies"]]
    pos = [v for v in q_ if v["diff"] is not None and v["diff"] > 0]
    p = res["pooled"]
    p["qualifyingYears"] = len(q_); p["yearsPositive"] = len(pos)
    p["pass"] = bool(p["diff"] is not None and p["diff"] >= 0.10 and p.get("diffCI", (0,))[0] > 0
                     and len(q_) >= 3 and len(pos) >= 3 and len(pos) >= 0.75 * len(q_))
    return res


def metrics(rows, key, C):
    if not rows: return None
    mae = st.mean(abs(r["pred"][key] - r["l"]) for r in rows)
    acc = st.mean(direction(r["pred"][key] - r["pred"]["persistence"], r, C) == direction(r["l"] - r["pred"]["persistence"], r, C) for r in rows)
    om = [r for r in rows if direction(r["l"] - r["pred"]["persistence"], r, C) == "murkier"]
    on = [r for r in rows if direction(r["l"] - r["pred"]["persistence"], r, C) != "murkier"]
    pod = st.mean(direction(r["pred"][key] - r["pred"]["persistence"], r, C) == "murkier" for r in om) if om else float("nan")
    far = st.mean(direction(r["pred"][key] - r["pred"]["persistence"], r, C) == "murkier" for r in on) if on else float("nan")
    return {"n": len(rows), "mae": round(mae, 4), "dirAcc": round(acc, 4), "pss": round(pod - far, 4) if pod == pod and far == far else None}


def evaluate(D, C, years, separate, out):
    allu = [u for u in D.units() if "anom" in u and u["prev"] is not None]
    for u in allu: u["pred"] = predict(u, C)
    R = {"constants": C, "counts": {}, "hypotheses": {}, "challengers": {}, "gate": {}, "secondary": {}}
    for label, ys in (("validation", years), ("separate", separate)):
        us = [u for u in allu if u["date"].year in ys]
        R["counts"][label] = counts(D, us, ys)
    V = [u for u in allu if u["date"].year in years]
    # ---- H1 and H2 per class
    for cl in ("large", "medium", "small", "mainStem"):
        X = [u for u in V if u["class"] == cl]
        h1c = [u for u in X if u["season"] == "cold" and storm_window(u)]
        h1k = [u for u in X if u["season"] == "cold" and u["week"] is not None and u["week"] < DRY_WEEK_IN]
        w1c = [u for u in X if u["season"] == "warm" and storm_window(u)]
        w1k = [u for u in X if u["season"] == "warm" and u["week"] is not None and u["week"] < DRY_WEEK_IN]
        R["hypotheses"][f"H1 season {cl}"] = test_hypothesis(h1c, h1k, C, years)
        R["hypotheses"][f"H1 warm contrast {cl}"] = test_hypothesis(w1c, w1k, C, years)
        if cl != "mainStem":
            h2c = [u for u in X if u["nwmRatio"] is not None and u["nwmRatio"] >= FLOW_HIGH]
            h2k = [u for u in X if u["nwmRatio"] is not None and u["nwmRatio"] < FLOW_LOW]
            R["hypotheses"][f"H2 flow {cl}"] = test_hypothesis(h2c, h2k, C, years)
    # ---- challengers
    for cl in ("large", "medium", "small", "mainStem"):
        X = [u for u in V if u["class"] == cl]
        for ch, cond in (("season", season_condition), ("flow", flow_condition)):
            if cl == "mainStem" and ch == "flow": continue
            R["challengers"][f"{ch} {cl}"] = score(X, ch, cond, C, years)
    # ---- secondary: progression, heads, breakdowns
    R["secondary"]["H3 progression"] = progression(V, C, years)
    R["secondary"]["heads"] = heads(D, allu, V, years)
    R["secondary"]["byLag"] = {cl: {lb: metrics([u for u in V if u["class"] == cl and u["lag"] is not None and lo <= u["lag"] <= hi], "season", C)
                                    for lb, (lo, hi) in (("0-1", (0, 1)), ("2-3", (2, 3)), ("4-6", (4, 6)), ("7-10", (7, 10)))}
                               for cl in ("large", "medium", "small", "mainStem")}
    R["secondary"]["byCoverage"] = {}
    for cl in ("large", "medium", "small", "mainStem"):
        d = {}
        for lab, lo, hi in (("prev cov 30-50%", .3, .5), ("50-75%", .5, .75), (">=75%", .75, 1.01)):
            rows = [u for u in V if u["class"] == cl and lo <= u["prev"][2] < hi]
            d[lab] = {k: metrics(rows, k, C) for k in ("persistence", "reversion")}
        R["secondary"]["byCoverage"][cl] = d
    # ---- the gate
    for key, sc in R["challengers"].items():
        ch, cl = key.split()
        hyp = R["hypotheses"][f"H1 season {cl}"] if ch == "season" else R["hypotheses"].get(f"H2 flow {cl}")
        R["gate"][key] = gate(sc, hyp)
    # combined, only where both are supported
    for cl in ("large", "medium", "small"):
        if R["gate"].get(f"season {cl}", {}).get("decision") == "supported" and R["gate"].get(f"flow {cl}", {}).get("decision") == "supported":
            X = [u for u in V if u["class"] == cl]
            sc = score(X, "combined", lambda u: season_condition(u) or flow_condition(u), C, years)
            R["challengers"][f"combined {cl}"] = sc
            R["gate"][f"combined {cl}"] = gate(sc, R["hypotheses"][f"H1 season {cl}"])
    R["spatial"] = {"H3pass": R["secondary"]["H3 progression"]["pass"]}
    supported = [k for k, v in R["gate"].items() if v["decision"] == "supported"]
    R["recommendation"] = ("PROCEED TO SPATIAL RUNOFF MODEL (scoped to: " + ", ".join(supported)
                           + ("; within-arm structure supported" if R["spatial"]["H3pass"] else "; within-arm structure NOT supported") + ")"
                           ) if supported else "DO NOT PROCEED"
    # separate year(s), reported, never in the gate
    S_ = [u for u in allu if u["date"].year in separate]
    R["separateYears"] = {f"{ch} {cl}": score([u for u in S_ if u["class"] == cl], ch, cond, C, separate)["condition"]
                          for cl in ("large", "medium", "small", "mainStem")
                          for ch, cond in (("season", season_condition), ("flow", flow_condition)) if not (cl == "mainStem" and ch == "flow")}
    for u in allu: u.pop("pred", None)
    json.dump(R, open(out, "w"), indent=1, default=str)
    print(json.dumps({"counts": R["counts"], "gate": R["gate"], "recommendation": R["recommendation"]}, indent=1, default=str))


def score(X, ch, cond, C, years):
    Y = [u for u in X if cond(u)]
    res = {"condition": {k: metrics(Y, k, C) for k in ("persistence", "reversion", ch)},
           "all": {k: metrics(X, k, C) for k in ("persistence", "reversion", ch)}}
    res["condition"]["maeDiffVsPersistenceCI"] = boot(Y, lambda s: st.mean(abs(r["pred"][ch] - r["l"]) - abs(r["pred"]["persistence"] - r["l"]) for r in s) if s else float("nan"))
    res["condition"]["pssCI"] = boot(Y, lambda s: (metrics(s, ch, C) or {}).get("pss") or float("nan"))
    res["condition"]["medianAnomaly"] = round(st.median(u["anom"] for u in Y), 4) if Y else None
    res["condition"]["medianAnomalyCI"] = boot(Y, lambda s: st.median(u["anom"] for u in s) if s else float("nan"))
    eps = collections.Counter(u["ep"] for u in Y if u["ep"] is not None)
    res["condition"]["independentStorms"] = len(eps)
    res["condition"]["largestStormShare"] = round(max(eps.values()) / len(Y), 4) if eps and Y else None
    if eps:
        big = eps.most_common(1)[0][0]
        rest = [u for u in Y if u["ep"] != big]
        res["condition"]["maeDiffWithoutLargestStorm"] = round(st.mean(abs(r["pred"][ch] - r["l"]) - abs(r["pred"]["persistence"] - r["l"]) for r in rest), 4) if rest else None
    res["byYear"] = {}
    for y in years:
        Yy = [u for u in Y if u["date"].year == y]
        storms = len({u["ep"] for u in Yy if u["ep"] is not None})
        m = {k: metrics(Yy, k, C) for k in ("persistence", "reversion", ch)}
        m["independentStorms"] = storms
        m["qualifies"] = storms >= 3 and len(Yy) >= 8
        m["maeDiffVsPersistence"] = round(m[ch]["mae"] - m["persistence"]["mae"], 4) if Yy else None
        res["byYear"][str(y)] = m
    res["bySeason"] = {s: metrics([u for u in Y if u["season"] == s], ch, C) for s in ("cold", "warm")}
    res["_ch"] = ch
    return res


def gate(sc, hyp):
    c = sc["condition"]; ch = sc["_ch"]
    q_ = [v for v in sc["byYear"].values() if v["qualifies"]]
    G = {}
    G["G1 independence"] = bool(c["independentStorms"] >= 15 and len(q_) >= 3 and (c["largestStormShare"] or 1) <= 0.25
                                and (c.get("maeDiffWithoutLargestStorm") is not None and c["maeDiffWithoutLargestStorm"] < 0))
    G["G2 hypothesis"] = bool(hyp and hyp["pooled"]["pass"])
    G["G3 effect > noise"] = bool(c["medianAnomaly"] is not None and c["medianAnomaly"] >= 0.05 and c["medianAnomalyCI"][0] > 0)
    G["G4 beats persistence"] = bool(c[ch] and c["maeDiffVsPersistenceCI"][1] < 0 and all(v["maeDiffVsPersistence"] <= 0.02 for v in q_))
    G["G5 direction skill"] = bool(c[ch] and c[ch]["pss"] is not None and c[ch]["pss"] >= 0.15 and c["pssCI"][0] > 0)
    G["G6 beats reversion"] = bool(c[ch] and c["reversion"] and c[ch]["mae"] <= c["reversion"]["mae"])
    G["G7 quality"] = True
    a = sc["all"]
    G["G8 no harm overall"] = bool(a[ch] and a["persistence"] and a[ch]["mae"] <= a["persistence"]["mae"] + 0.005)
    G["decision"] = "supported" if all(v for k, v in G.items()) else ("insufficient evidence" if not G["G1 independence"] else "unsupported")
    G["n"] = c[ch]["n"] if c[ch] else 0
    return G


def counts(D, us, ys):
    eps_all = [e for e in D.episodes if e[0].year in ys]
    out = {"stormDays": sum(1 for d in D.storm_days if d.year in ys), "independentStorms": len(eps_all),
           "stormsByYear": dict(collections.Counter(e[0].year for e in eps_all)),
           "stormsBySeason": dict(collections.Counter("cold" if e[0].month in COLD else "warm" for e in eps_all)),
           "passes": len({u["time"] for u in us}), "units": len(us),
           "measurableStormWindowUnitsByClass": dict(collections.Counter(u["class"] for u in us if storm_window(u))),
           "measurableColdStormWindowUnitsByClass": dict(collections.Counter(u["class"] for u in us if storm_window(u) and u["season"] == "cold")),
           "independentStormsWithMeasurableUnitsByClass": {cl: len({u["ep"] for u in us if u["class"] == cl and storm_window(u) and u["ep"] is not None})
                                                           for cl in ("large", "medium", "small", "mainStem")}}
    return out


def spearman(x, y):
    rx = [sorted(x).index(v) for v in x]; ry = [sorted(y).index(v) for v in y]
    n = len(x); mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def progression(V, C, years):
    ev = collections.defaultdict(dict)
    for u in V:
        if u["class"] in ("large", "medium") and u["of"] >= 3 and u["season"] == "cold" and storm_window(u):
            ev[(u["arm"], u["time"])][u["idx"]] = u
    rows = []
    for (arm, t), zs in ev.items():
        if len(zs) < 3: continue
        idx = sorted(zs); an = [zs[i]["anom"] for i in idx]
        rows.append({"arm": arm, "year": zs[idx[0]]["date"].year, "rho": spearman(idx, an), "head": 0 in zs})
    neg = sum(r["rho"] < 0 for r in rows); pos = sum(r["rho"] > 0 for r in rows)
    by = {}
    for y in years:
        rr = [r for r in rows if r["year"] == y]
        by[str(y)] = {"events": len(rr), "headStrongerShare": round(sum(r["rho"] < 0 for r in rr) / len(rr), 3) if rr else None,
                      "qualifies": len(rr) >= 5}
    qy = [v for v in by.values() if v["qualifies"]]
    res = {"events": len(rows), "eventsWithHeadMeasured": sum(r["head"] for r in rows),
           "headStrongerShare": round(neg / len(rows), 3) if rows else None,
           "signTestP": round(binp(neg, neg + pos, 0.5), 4) if neg + pos else None, "byYear": by}
    res["pass"] = bool(len(rows) >= 20 and res["headStrongerShare"] is not None and res["headStrongerShare"] >= 0.6
                       and res["signTestP"] is not None and res["signTestP"] < 0.05 and len(qy) >= 3
                       and sum(v["headStrongerShare"] > 0.5 for v in qy) >= 3)
    return res


def heads(D, allu, V, years):
    """How far unreadable heads cap the spatial question (item 11)."""
    out = {}
    head_zones = {zid: z for zid, z in D.zones.items() if z["name"] == "head" and z["of"] >= 2}
    ev = collections.defaultdict(set)
    for u in V:
        if u["class"] in ("large", "medium") and u["season"] == "cold" and storm_window(u):
            ev[(u["arm"], u["time"])].add(u["pos"])
    out["coldStormEventsWithAnyMeasurableZone"] = len(ev)
    out["ofWhichHeadMeasurable"] = sum("head" in s for s in ev.values())
    out["ofWhichHeadAndMouthMeasurable"] = sum("head" in s and "mouth" in s for s in ev.values())
    per = {}
    for zid, z in head_zones.items():
        n = m = 0; unread = grass = cloud = 0.0
        for p in D.passes:
            if p["day"].year not in years: continue
            r = p["zones"].get(zid)
            if not r: continue
            n += 1; m += bool(r["measurable"]); unread += r["unreadableFrac"]; grass += r["grassFrac"]; cloud += r["cloudFrac"]
        if n:
            per[z["arm"]] = {"passes": n, "measurableShare": round(m / n, 3), "meanUnreadable": round(unread / n, 3),
                             "meanGrass": round(grass / n, 3), "meanCloud": round(cloud / n, 3)}
    out["headZones"] = per
    out["headsNeverMeasurable"] = sorted(a for a, v in per.items() if v["measurableShare"] == 0)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["derive", "evaluate"])
    ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--constants"); ap.add_argument("--years", default="2021,2022,2023,2024"); ap.add_argument("--separate", default="2020")
    a = ap.parse_args()
    D = Data(a.data)
    if a.mode == "derive":
        derive(D, a.out)
    else:
        C = json.load(open(a.constants))
        evaluate(D, C, [int(x) for x in a.years.split(",")], [int(x) for x in a.separate.split(",") if x], a.out)
