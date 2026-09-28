"""Within-arm runoff response: event studies, a holdout test and the evidence
gate (Clarity Fusion Stage 3A, items 6-8 and 10).

EVERYTHING BELOW WAS FIXED BEFORE THE HOLDOUT WAS RUN (2026-09-28).

Data: zone_history.json (observed cells only), the arm zones, catchment rain
(daily MRMS 24 h Pass 2 valid 17Z, and hourly 01H Pass 2 for the day before
each pass), USGS IV at the two gauged arms, NWM daily 16Z elsewhere.

DEFINITIONS
  measurable      a zone on a pass with >= 30 observed cells and >= 30% of its
                  non-grass water observed
  rain day        a 24 h window (17Z-17Z) of catchment-mean rain; the window
                  ending at the pass (17Z the day before -> 16Z) is hourly
  storm day       a rain day >= 1.0 in on the arm's drainage
  lag             pass day minus the most recent storm day within 10 days
                  (0 = the window through 16Z on the pass day)
  dry week        < 0.25 in over the ~7 days before the pass
  zone baseline   median log10 FNU of the same zone's measurable passes in the
                  45 days before, each after a dry week (>= 2 of them)
  anomaly         log10(zone median FNU) - zone baseline
  noise           p10 / p90 of dry-week anomalies for that zone position
  arms            by zone count K: TC / SS / Browns named, other K=5 ("large"),
                  K=2-3 ("medium"), K=1 ("small", the whole arm is one zone)
  independent storm  lake-wide storm days (>= 1 in on any drainage) merged
                  when within 3 days of each other

THE CHALLENGER (holdout, both folds: train 2025 -> test 2026, and back)
  unit            (zone, pass) measurable, with an earlier measurable
                  observation of the zone within 45 days and a zone baseline
  static satellite baseline (persistence): the zone's last measurable value
  challenger      if a storm day fell after that last observation and within
                  10 days before the pass: zone baseline + the TRAINING median
                  anomaly for (position group, lag bin) -- groups head / rest /
                  whole -- when >= 8 training events support it, else the lag
                  bin alone, else no change; otherwise persistence
  also reported   "revert": zone baseline alone on runoff cases (separates the
                  reversion to baseline from the runoff adjustment)

EVIDENCE GATE -- every item must hold, else
"insufficient evidence for spatial runoff adjustment"
  G1 events       >= 12 independent storms with evaluable zone events, >= 4 in
                  each year
  G2 years        the effect claimed (murkier-beyond-noise share at the lag
                  bin used, over the dry-week share) significant (one-sided
                  binomial p < 0.05) in EACH year separately
  G3 direction    on runoff cases in BOTH folds: the challenger's direction
                  accuracy >= persistence + 10 points, and its Peirce skill
                  for "murkier" >= 0.2 with the 95% interval above 0
  G4 magnitude    on runoff cases in BOTH folds: challenger MAE (log10) below
                  persistence, the 95% interval of the difference below 0
                  (bootstrap by pass date)
  G5 ordering     if a spatial claim is made (head responds more than the
                  rest): head anomaly > mean of the other zones in >= 60% of
                  holdout events with >= 3 measurable zones, both folds
  G6 quality      only measurable zones enter (enforced above)
  G7 overall      the challenger is not worse than persistence over ALL test
                  units in either fold (MAE)

usage: python3 zone_events.py <zone_history.json> <arm_zones.json> <rain_daily.json> <rain_pass_hours.json>
                              <usgs_iv.json> <nwm_daily.json> <hydrology.json> <anchors dir> <out.json>
"""
import sys, os, json, glob, math, bisect, random, statistics as st, datetime as dt, collections
from math import comb

ZH, ZZ, RD, RH, USGS, NWM, GRAPH, ANCH, OUT = sys.argv[1:10]
zh = json.load(open(ZH)); zones_meta = {str(z["zone"]): z for z in json.load(open(ZZ))["zones"]}
arm_meta = json.load(open(ZZ))["arms"]
rain_d = json.load(open(RD))["days"]; rain_h = json.load(open(RH))["hours"]
usgs = json.load(open(USGS)); nwm = json.load(open(NWM)); graph = json.load(open(GRAPH))
arms = {a["id"]: a for a in graph["arms"]}
arm_to_reach = {arm: r for r, al in nwm.get("reachToArms", {}).items() for arm in al}
NAMED = ("town-creek-marshall", "south-sauty-creek", "browns-creek")
MIN_TRAIN = 8


def ptime(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


passes = sorted(zh["passes"].values(), key=lambda p: p["time"])
for p in passes:
    p["t"] = ptime(p["time"]); p["day"] = p["t"].date()


def rain_window(arm, day, tail):
    """24 h rain window ending 17Z on `day`; tail=True -> the hourly window
    17Z day-1 -> 16Z day (the one a pass on `day` can see)."""
    if tail:
        D = dt.datetime(day.year, day.month, day.day)
        hs = [D - dt.timedelta(hours=6 - k) for k in range(6)] + [D + dt.timedelta(hours=k) for k in range(17)]
        vals = [(rain_h.get(f"{h:%Y-%m-%dT%H}") or {}).get(arm) for h in hs]
        if any(v is None for v in vals):
            return None
        return sum(vals)
    r = rain_d.get(day.isoformat())
    return None if (r is None or r.get(arm) is None) else r[arm]


def rain_context(arm, day):
    """(7-day rain before the pass, lag to the most recent storm day, its total)."""
    tail = rain_window(arm, day, True)
    wk = [tail] + [rain_window(arm, day - dt.timedelta(days=k), False) for k in range(1, 7)]
    week = None if any(v is None for v in wk) else sum(wk)
    lag = amt = None
    for k in range(0, 11):
        v = tail if k == 0 else rain_window(arm, day - dt.timedelta(days=k), False)
        if v is not None and v >= 1.0:
            lag, amt = k, v; break
    return week, lag, amt


def lag_bin(l):
    if l is None: return None
    return "0-1" if l <= 1 else "2-3" if l <= 3 else "4-6" if l <= 6 else "7-10"


# ---------------------------------------------------------------- zone series
series = collections.defaultdict(list)          # zone -> [(pass, log10 p50)]
for p in passes:
    for zid, z in p["zones"].items():
        if z["measurable"] and z["fnu"]:
            series[zid].append((p, math.log10(z["fnu"][1])))
arm_series = collections.defaultdict(list)       # arm -> [(pass, log10 p50)] whole-arm observed median
for f in sorted(glob.glob(os.path.join(ANCH, "*.json"))):
    a = json.load(open(f)); t = ptime(a["sceneTime"])
    p = next((q for q in passes if q["time"] == a["sceneTime"]), None)
    if p is None: continue
    for arm, e in a["arms"].items():
        if e["observedFNU"] and e["observedCells"] >= 30 and e["waterCells"] and e["observedCells"] / e["waterCells"] >= 0.30:
            arm_series[arm].append((p, math.log10(e["observedFNU"]["p50"])))
for v in arm_series.values(): v.sort(key=lambda x: x[0]["time"])

ctx_cache = {}
def ctx(arm, day):
    k = (arm, day)
    if k not in ctx_cache: ctx_cache[k] = rain_context(arm, day)
    return ctx_cache[k]


def events_for(seq, arm):
    out = []
    for i, (p, lv) in enumerate(seq):
        week, lag, amt = ctx(arm, p["day"])
        base = []
        for q, lq in seq[:i]:
            if (p["t"] - q["t"]).days <= 45:
                wq, _, _ = ctx(arm, q["day"])
                if wq is not None and wq < 0.25:
                    base.append(lq)
        prev = next(((q, lq) for q, lq in reversed(seq[:i]) if (p["t"] - q["t"]).days <= 45), None)
        out.append({"pass": p, "l": lv, "week": week, "lag": lag, "amt": amt,
                    "base": st.median(base) if len(base) >= 2 else None, "nbase": len(base),
                    "prev": prev})
    return out


def group_of(arm):
    K = arm_meta[arm]["zones"]
    if arm in NAMED: return arm
    return "large (other K=5)" if K == 5 else "medium (K=2-3)" if K in (2, 3) else "small (K=1)"


zone_events = []
for zid, seq in series.items():
    zm = zones_meta[zid]; arm = zm["arm"]
    if arm not in arm_meta or not arm_meta[arm].get("zones"): continue
    for e in events_for(seq, arm):
        e.update({"zone": zid, "arm": arm, "pos": zm["name"], "idx": zm["index"], "of": zm["of"], "group": group_of(arm)})
        if e["base"] is not None: e["anom"] = e["l"] - e["base"]
        zone_events.append(e)
arm_events = []
for arm, seq in arm_series.items():
    if arm not in arm_meta or not arm_meta[arm].get("zones"): continue
    for e in events_for(seq, arm):
        e.update({"arm": arm, "group": group_of(arm)})
        if e["base"] is not None: e["anom"] = e["l"] - e["base"]
        arm_events.append(e)


def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]


# noise per position (dry-week anomalies)
noise = {}
for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
    xs = [e["anom"] for e in zone_events if "anom" in e and e["pos"] == pos and e["week"] is not None and e["week"] < 0.25]
    noise[pos] = (q(xs, .1), q(xs, .9), len(xs)) if len(xs) >= 20 else None
pooled = [e["anom"] for e in zone_events if "anom" in e and e["week"] is not None and e["week"] < 0.25]
noise_fallback = []
for pos in list(noise):
    if noise[pos] is None and len(pooled) >= 20:
        noise[pos] = (q(pooled, .1), q(pooled, .9), len(pooled)); noise_fallback.append(pos)
arm_dry = [e["anom"] for e in arm_events if "anom" in e and e["week"] is not None and e["week"] < 0.25]
noise["arm"] = (q(arm_dry, .1), q(arm_dry, .9), len(arm_dry))
dry_share = {pos: (sum(1 for e in zone_events if "anom" in e and e["pos"] == pos and e["week"] is not None and e["week"] < 0.25
                       and e["anom"] > noise[pos][1]) / max(1, noise[pos][2])) if noise[pos] else None for pos in noise if pos != "arm"}
dry_share["arm"] = sum(1 for x in arm_dry if x > noise["arm"][1]) / len(arm_dry)


def binp(k, n, p): return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)) if n else 1.0


def cell(rows, pos_key):
    xs = [e["anom"] for e in rows]
    if not xs: return None
    nz = noise[pos_key] if pos_key in noise else None
    k = sum(x > nz[1] for x in xs) if nz else None
    c = sum(x < nz[0] for x in xs) if nz else None
    ds = dry_share.get(pos_key)
    return {"n": len(xs), "medianRatio": round(10 ** st.median(xs), 2), "p75Ratio": round(10 ** q(xs, .75), 2),
            "p90Ratio": round(10 ** q(xs, .9), 2),
            "murkier": round(k / len(xs), 3) if nz else None, "clearer": round(c / len(xs), 3) if nz else None,
            "p": round(binp(k, len(xs), ds), 4) if (nz and ds) else None}


LAGS = ("0-1", "2-3", "4-6", "7-10")
res = {"noise": {k: v for k, v in noise.items()}, "noiseFromPooled": noise_fallback, "dryShare": dry_share,
       "byGroupZoneLag": {}, "armLevel": {}}
ev_z = [e for e in zone_events if "anom" in e]
ev_a = [e for e in arm_events if "anom" in e]
groups = list(NAMED) + ["large (other K=5)", "medium (K=2-3)", "small (K=1)"]
for g in groups:
    res["byGroupZoneLag"][g] = {}
    for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
        for lb in LAGS:
            c = cell([e for e in ev_z if e["group"] == g and e["pos"] == pos and lag_bin(e["lag"]) == lb], pos)
            if c: res["byGroupZoneLag"][g][f"{pos} {lb}"] = c
        c = cell([e for e in ev_z if e["group"] == g and e["pos"] == pos and e["week"] is not None and e["week"] < 0.25], pos)
        if c: res["byGroupZoneLag"][g][f"{pos} dry"] = c
    res["armLevel"][g] = {lb: cell([e for e in ev_a if e["group"] == g and lag_bin(e["lag"]) == lb], "arm") for lb in LAGS}

# ------------------------------------------------ head vs whole arm (paired)
arm_anom = {(e["arm"], e["pass"]["time"]): e["anom"] for e in ev_a}
paired = collections.defaultdict(list)
for e in ev_z:
    if e["pos"] != "head" or e["of"] < 3: continue
    a = arm_anom.get((e["arm"], e["pass"]["time"]))
    if a is None: continue
    paired[(e["group"], lag_bin(e["lag"]) or "no storm")].append((e["anom"], a))
res["headVsArm"] = {}
for (g, lb), xs in sorted(paired.items()):
    d = [h - a for h, a in xs]
    res["headVsArm"][f"{g} | {lb}"] = {"n": len(xs), "medianHeadMinusArm": round(st.median(d), 3),
                                        "shareHeadGreater": round(sum(x > 0 for x in d) / len(d), 3),
                                        "headMurkier": round(sum(h > noise["head"][1] for h, _ in xs) / len(xs), 3),
                                        "armMurkier": round(sum(a > noise["arm"][1] for _, a in xs) / len(xs), 3)}

# --------------------------------------------------------------- progression
by_event = collections.defaultdict(dict)
for e in ev_z:
    if e["of"] >= 3:
        by_event[(e["arm"], e["pass"]["time"])][e["idx"]] = e
prog = collections.defaultdict(list); patterns = collections.defaultdict(collections.Counter)


def spearman(x, y):
    rx = [sorted(x).index(v) for v in x]; ry = [sorted(y).index(v) for v in y]
    n = len(x); mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


for (arm, t), zs in by_event.items():
    if len(zs) < 3: continue
    any_e = next(iter(zs.values()))
    lb = lag_bin(any_e["lag"]) or ("dry" if (any_e["week"] is not None and any_e["week"] < 0.25) else "other")
    idxs = sorted(zs); an = [zs[i]["anom"] for i in idxs]
    rho = spearman(idxs, an)
    peak = idxs[max(range(len(an)), key=lambda j: an[j])] / (any_e["of"] - 1)
    beyond = [i for i in idxs if zs[i]["anom"] > noise[zs[i]["pos"]][1]]
    head_i, mouth_i = 0, any_e["of"] - 1
    if not beyond: pat = "none"
    elif len(beyond) == len(idxs): pat = "every measurable zone"
    elif head_i in beyond and mouth_i not in beyond: pat = "head, not mouth"
    elif mouth_i in beyond and head_i not in beyond: pat = "mouth, not head"
    else: pat = "mixed"
    prog[lb].append({"rho": rho, "peak": peak, "arm": arm, "time": t})
    patterns[lb][pat] += 1
res["progression"] = {}
for lb, xs in prog.items():
    neg = sum(x["rho"] < 0 for x in xs); pos_ = sum(x["rho"] > 0 for x in xs)
    res["progression"][lb] = {"events": len(xs), "medianRho": round(st.median([x["rho"] for x in xs]), 3),
                              "headStrongerShare(rho<0)": round(neg / len(xs), 3),
                              "signTestP(head stronger)": round(binp(neg, neg + pos_, 0.5), 4) if neg + pos_ else None,
                              "medianPeakPosition(0=head,1=mouth)": round(st.median([x["peak"] for x in xs]), 2),
                              "patterns": dict(patterns[lb])}

# ------------------------------------------------------- measured / modeled
def usgs_at(site, t):
    pts = usgs[site]
    ts = usgs_ts[site]
    i = bisect.bisect_left(ts, t); best = None
    for j in (i - 1, i):
        if 0 <= j < len(ts) and abs((ts[j] - t).total_seconds()) <= 3600:
            best = j if best is None or abs((ts[j] - t).total_seconds()) < abs((ts[best] - t).total_seconds()) else best
    return None if best is None else pts[best][1]
usgs_ts = {s: [ptime(x[0]) for x in v] for s, v in usgs.items()}
res["flow"] = {}
for arm in NAMED[:2]:
    site = arms[arm]["usgsDischargeSite"]
    rows = []
    for e in ev_z:
        if e["arm"] != arm: continue
        qn = usgs_at(site, e["pass"]["t"])
        bq = [usgs_at(site, p2["t"]) for p2, _ in series[e["zone"]] if p2["t"] < e["pass"]["t"] and (e["pass"]["t"] - p2["t"]).days <= 45
              and (ctx(arm, p2["day"])[0] or 9) < 0.25]
        bq = [x for x in bq if x]
        if qn and bq:
            rows.append((e["pos"], qn / st.median(bq), e["anom"]))
    res["flow"][arm] = {}
    for pos in ("head", "upper", "middle", "lower", "mouth"):
        for lo, hi in ((0, 1.5), (1.5, 3), (3, 1e9)):
            xs = [a for pp, r, a in rows if pp == pos and lo <= r < hi]
            if xs:
                nz = noise[pos]
                res["flow"][arm][f"{pos} measured Q/base {lo}-{hi if hi < 1e9 else '+'}"] = {
                    "n": len(xs), "medianRatio": round(10 ** st.median(xs), 2),
                    "murkier": round(sum(x > nz[1] for x in xs) / len(xs), 3)}
# modeled: NWM relative to itself, at the pass day 16Z vs its median on the baseline passes' days
mod_rows = collections.defaultdict(list)
for e in ev_z:
    a = arms.get(e["arm"])
    if not a or a["flowSource"] != "modeledNWM": continue
    r = arm_to_reach.get(e["arm"])
    if not r: continue
    qn = (nwm["days"].get(e["pass"]["day"].isoformat()) or {}).get(r)
    bq = [(nwm["days"].get(p2["day"].isoformat()) or {}).get(r) for p2, _ in series[e["zone"]]
          if p2["t"] < e["pass"]["t"] and (e["pass"]["t"] - p2["t"]).days <= 45 and (ctx(e["arm"], p2["day"])[0] or 9) < 0.25]
    bq = [x for x in bq if x]
    if qn and bq and st.median(bq) > 0:
        mod_rows[e["pos"]].append((qn / st.median(bq), e["anom"]))
res["modeledFlow"] = {}
for pos, rows in mod_rows.items():
    for lo, hi in ((0, 1.5), (1.5, 3), (3, 1e9)):
        xs = [a for r, a in rows if lo <= r < hi]
        if xs and noise.get(pos):
            res["modeledFlow"][f"{pos} modeled Q/base {lo}-{hi if hi < 1e9 else '+'}"] = {
                "n": len(xs), "medianRatio": round(10 ** st.median(xs), 2),
                "murkier": round(sum(x > noise[pos][1] for x in xs) / len(xs), 3)}

# ------------------------------------------------------------ year splits
# Every pooled cell that looks like a signal, split by year: a response that
# exists in one year only is not a response Sector can use.
def yr_cell(rows, pos_key):
    out = {}
    for yy in (2025, 2026):
        xs = [a for (d, a) in rows if d.year == yy]
        if not xs: out[str(yy)] = None; continue
        nz = noise[pos_key]
        k = sum(x > nz[1] for x in xs)
        out[str(yy)] = {"n": len(xs), "murkier": round(k / len(xs), 3), "medianRatio": round(10 ** st.median(xs), 2),
                        "p": round(binp(k, len(xs), dry_share[pos_key]), 4)}
    return out
res["yearSplit"] = {}
for g in ("large (other K=5)", "medium (K=2-3)", "small (K=1)"):
    for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
        for lb in ("0-1", "2-3"):
            rows = [(e["pass"]["day"], e["anom"]) for e in ev_z if e["group"] == g and e["pos"] == pos and lag_bin(e["lag"]) == lb]
            if len(rows) >= 8: res["yearSplit"][f"{g} {pos} lag {lb}"] = yr_cell(rows, pos)
# South Sauty zones by measured flow >= 3x, and modeled >= 3x by position, per year
ss_site = arms["south-sauty-creek"]["usgsDischargeSite"]
for e in ev_z:
    e["_q"] = None
for e in ev_z:
    if e["arm"] == "south-sauty-creek":
        qn = usgs_at(ss_site, e["pass"]["t"])
        bq = [usgs_at(ss_site, p2["t"]) for p2, _ in series[e["zone"]] if p2["t"] < e["pass"]["t"] and (e["pass"]["t"] - p2["t"]).days <= 45
              and (ctx("south-sauty-creek", p2["day"])[0] or 9) < 0.25]
        bq = [x for x in bq if x]
        if qn and bq: e["_q"] = qn / st.median(bq)
for pos in ("head", "upper", "middle", "lower", "mouth"):
    rows = [(e["pass"]["day"], e["anom"]) for e in ev_z if e["arm"] == "south-sauty-creek" and e["pos"] == pos and e["_q"] and e["_q"] >= 3]
    if rows: res["yearSplit"][f"south-sauty {pos} measured Q>=3x"] = yr_cell(rows, pos)
for e in ev_z:
    a = arms.get(e["arm"]); r = arm_to_reach.get(e["arm"])
    e["_m"] = None
    if not a or a["flowSource"] != "modeledNWM" or not r: continue
    qn = (nwm["days"].get(e["pass"]["day"].isoformat()) or {}).get(r)
    bq = [(nwm["days"].get(p2["day"].isoformat()) or {}).get(r) for p2, _ in series[e["zone"]]
          if p2["t"] < e["pass"]["t"] and (e["pass"]["t"] - p2["t"]).days <= 45 and (ctx(e["arm"], p2["day"])[0] or 9) < 0.25]
    bq = [x for x in bq if x]
    if qn and bq and st.median(bq) > 0: e["_m"] = qn / st.median(bq)
for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
    rows = [(e["pass"]["day"], e["anom"]) for e in ev_z if e["pos"] == pos and e["_m"] and e["_m"] >= 3]
    if rows: res["yearSplit"][f"modeled Q>=3x {pos}"] = yr_cell(rows, pos)
# progression by year at 0-3 days
for yy in (2025, 2026):
    xs = [x for lb in ("0-1", "2-3") for x in prog.get(lb, []) if x["time"].startswith(str(yy))]
    if xs:
        neg = sum(x["rho"] < 0 for x in xs); pos_ = sum(x["rho"] > 0 for x in xs)
        res["yearSplit"][f"progression 0-3 d {yy}"] = {"events": len(xs), "headStrongerShare": round(neg / len(xs), 3),
                                                        "signTestP": round(binp(neg, neg + pos_, 0.5), 4) if neg + pos_ else None}
for e in ev_z:
    e.pop("_q", None); e.pop("_m", None)

# ------------------------------------------------------ independent storms
storm_days = set()
for d, r in rain_d.items():
    if r and any((v or 0) >= 1.0 for k, v in r.items() if not k.startswith("_")):
        storm_days.add(dt.date.fromisoformat(d))
storms = []
for d in sorted(storm_days):
    if storms and (d - storms[-1][-1]).days <= 3: storms[-1].append(d)
    else: storms.append([d])
def storm_of(day, lag):
    if lag is None: return None
    ev = day - dt.timedelta(days=lag)
    for i, s in enumerate(storms):
        if s[0] - dt.timedelta(days=1) <= ev <= s[-1] + dt.timedelta(days=1): return i
    return None
res["storms"] = {"lakeWideStormDays": len(storm_days), "independentStorms": len(storms)}

# ----------------------------------------------------------------- holdout
def posgroup(e): return "whole" if e["of"] == 1 else ("head" if e["idx"] == 0 else "rest")


def fit(train):
    tab = collections.defaultdict(list); lagonly = collections.defaultdict(list)
    for e in train:
        lb = lag_bin(e["lag"])
        if lb is None or "anom" not in e: continue
        tab[(posgroup(e), lb)].append(e["anom"]); lagonly[lb].append(e["anom"])
    return ({k: st.median(v) for k, v in tab.items() if len(v) >= MIN_TRAIN},
            {k: st.median(v) for k, v in lagonly.items() if len(v) >= MIN_TRAIN})


def predict(e, model):
    tab, lagonly = model
    prev = e["prev"]
    if prev is None or e["base"] is None: return None
    pers = prev[1]
    storm_after_prev = e["lag"] is not None and (e["pass"]["day"] - dt.timedelta(days=e["lag"])) > prev[0]["day"] - dt.timedelta(days=0)
    if not storm_after_prev:
        return {"pers": pers, "chal": pers, "revert": pers, "runoff": False}
    lb = lag_bin(e["lag"])
    adj = tab.get((posgroup(e), lb), lagonly.get(lb))
    return {"pers": pers, "chal": (e["base"] + adj) if adj is not None else pers, "revert": e["base"], "runoff": True,
            "adjSupported": adj is not None}


def direction(delta, pos):
    lo, hi, _ = noise[pos]
    return "murkier" if delta > hi else "clearer" if delta < lo else "same"


def evaluate(test, model):
    units = []
    for e in test:
        pr = predict(e, model)
        if pr is None: continue
        pr.update({"obs": e["l"], "pos": e["pos"], "date": e["pass"]["day"].isoformat(), "e": e})
        units.append(pr)
    def stats_(us, key):
        mae = st.mean(abs(u[key] - u["obs"]) for u in us) if us else float("nan")
        acc = sum(direction(u[key] - u["pers"], u["pos"]) == direction(u["obs"] - u["pers"], u["pos"]) for u in us) / len(us) if us else float("nan")
        om = [u for u in us if direction(u["obs"] - u["pers"], u["pos"]) == "murkier"]
        on = [u for u in us if direction(u["obs"] - u["pers"], u["pos"]) != "murkier"]
        pod = sum(direction(u[key] - u["pers"], u["pos"]) == "murkier" for u in om) / len(om) if om else float("nan")
        far = sum(direction(u[key] - u["pers"], u["pos"]) == "murkier" for u in on) / len(on) if on else float("nan")
        return {"n": len(us), "mae": mae, "dirAcc": acc, "pss": pod - far}
    run = [u for u in units if u["runoff"]]
    def boot(us, f, n=2000):
        by = collections.defaultdict(list)
        for u in us: by[u["date"]].append(u)
        ds = list(by); rnd = random.Random(11); vals = []
        for _ in range(n):
            s = [u for d in (rnd.choice(ds) for _ in ds) for u in by[d]]
            v = f(s)
            if v == v: vals.append(v)
        vals.sort()
        return (vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]) if vals else (float("nan"), float("nan"))
    out = {"all": {k: stats_(units, k) for k in ("pers", "chal", "revert")},
           "runoff": {k: stats_(run, k) for k in ("pers", "chal", "revert")}}
    out["runoff"]["maeDiffChalMinusPers"] = boot(run, lambda s: st.mean(abs(u["chal"] - u["obs"]) - abs(u["pers"] - u["obs"]) for u in s) if s else float("nan"))
    out["runoff"]["chalPssCI"] = boot(run, lambda s: stats_(s, "chal")["pss"])
    out["runoff"]["adjSupported"] = sum(1 for u in run if u.get("adjSupported"))
    # zone ordering on test events with >= 3 measurable zones
    ev = collections.defaultdict(dict)
    for u in run:
        e = u["e"]
        if e["of"] >= 3: ev[(e["arm"], e["pass"]["time"])][e["idx"]] = e["anom"]
    ords = [zs[0] > st.mean([v for i, v in zs.items() if i != 0]) for zs in ev.values() if len(zs) >= 3 and 0 in zs]
    out["runoff"]["headAboveRest"] = (sum(ords), len(ords))
    storms_ = {storm_of(u["e"]["pass"]["day"], u["e"]["lag"]) for u in run} - {None}
    out["runoff"]["independentStorms"] = len(storms_)
    return out


y = lambda e: e["pass"]["day"].year
folds = {"train2025_test2026": ([e for e in ev_z if y(e) == 2025], [e for e in ev_z if y(e) == 2026]),
         "train2026_test2025": ([e for e in ev_z if y(e) == 2026], [e for e in ev_z if y(e) == 2025])}
res["holdout"] = {}
for name, (tr, te) in folds.items():
    model = fit(tr)
    r = evaluate(te, model)
    r["model"] = {"table": {f"{k[0]} {k[1]}": round(v, 3) for k, v in model[0].items()}, "lagOnly": {k: round(v, 3) for k, v in model[1].items()}}
    res["holdout"][name] = r

# ----------------------------------------------------------------- the gate
gate = {}
per_year_storms = collections.Counter()
for e in ev_z:
    s = storm_of(e["pass"]["day"], e["lag"])
    if s is not None: per_year_storms[(storms[s][0].year, s)] += 1
ys = collections.Counter(yr for (yr, s) in per_year_storms)
gate["G1 events"] = {"independentStormsWithZoneEvents": len(per_year_storms), "byYear": dict(ys),
                     "pass": len(per_year_storms) >= 12 and all(ys.get(yy, 0) >= 4 for yy in (2025, 2026))}
# G2: the claim with the most support pooled: pick (position, lag bin) with the lowest pooled p among positions
best = None
for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
    if not noise.get(pos): continue
    for lb in LAGS:
        xs = [e for e in ev_z if e["pos"] == pos and lag_bin(e["lag"]) == lb]
        if len(xs) < 8: continue
        k = sum(e["anom"] > noise[pos][1] for e in xs)
        p = binp(k, len(xs), dry_share[pos])
        if best is None or p < best[0]: best = (p, pos, lb)
g2 = {"claimTested": f"{best[1]} zones, lag {best[2]} days" if best else None}
if best:
    for yy in (2025, 2026):
        xs = [e for e in ev_z if e["pos"] == best[1] and lag_bin(e["lag"]) == best[2] and y(e) == yy]
        dry = [e["anom"] for e in ev_z if e["pos"] == best[1] and y(e) == yy and e["week"] is not None and e["week"] < 0.25]
        hi = q(dry, .9) if dry else None
        k = sum(e["anom"] > noise[best[1]][1] for e in xs)
        g2[str(yy)] = {"n": len(xs), "murkier": k, "p": round(binp(k, len(xs), dry_share[best[1]]), 4) if xs else None}
    g2["pass"] = all((g2[str(yy)]["p"] is not None and g2[str(yy)]["p"] < 0.05) for yy in (2025, 2026))
else:
    g2["pass"] = False
gate["G2 years"] = g2
h = res["holdout"]
gate["G3 direction"] = {f: {"chalAcc": round(h[f]["runoff"]["chal"]["dirAcc"], 3), "persAcc": round(h[f]["runoff"]["pers"]["dirAcc"], 3),
                            "chalPSS": round(h[f]["runoff"]["chal"]["pss"], 3), "chalPssCI": [round(x, 3) for x in h[f]["runoff"]["chalPssCI"]]}
                        for f in h}
gate["G3 direction"]["pass"] = all(h[f]["runoff"]["chal"]["dirAcc"] >= h[f]["runoff"]["pers"]["dirAcc"] + 0.10
                                   and h[f]["runoff"]["chal"]["pss"] >= 0.2 and h[f]["runoff"]["chalPssCI"][0] > 0 for f in h)
gate["G4 magnitude"] = {f: {"chalMAE": round(h[f]["runoff"]["chal"]["mae"], 4), "persMAE": round(h[f]["runoff"]["pers"]["mae"], 4),
                            "diffCI": [round(x, 4) for x in h[f]["runoff"]["maeDiffChalMinusPers"]]} for f in h}
gate["G4 magnitude"]["pass"] = all(h[f]["runoff"]["maeDiffChalMinusPers"][1] < 0 for f in h)
gate["G5 ordering"] = {f: {"headAboveRest": h[f]["runoff"]["headAboveRest"]} for f in h}
gate["G5 ordering"]["pass"] = all(h[f]["runoff"]["headAboveRest"][1] > 0 and
                                  h[f]["runoff"]["headAboveRest"][0] / h[f]["runoff"]["headAboveRest"][1] >= 0.6 for f in h)
gate["G6 quality"] = {"pass": True, "note": "only measurable zones (>= 30 observed, >= 30% of non-grass water) enter"}
gate["G7 overall"] = {f: {"chalMAE": round(h[f]["all"]["chal"]["mae"], 4), "persMAE": round(h[f]["all"]["pers"]["mae"], 4)} for f in h}
gate["G7 overall"]["pass"] = all(h[f]["all"]["chal"]["mae"] <= h[f]["all"]["pers"]["mae"] for f in h)
gate["decision"] = ("evidence supports a spatial runoff adjustment" if all(v["pass"] for v in gate.values() if isinstance(v, dict) and "pass" in v)
                    else "insufficient evidence for spatial runoff adjustment")
res["gate"] = gate
res["counts"] = {"zoneEvents": len(ev_z), "armEvents": len(ev_a), "zonesWithSeries": len(series)}
# per-zone measurability: the share of passes on which each zone could be read
meas = collections.defaultdict(lambda: [0, 0])
for p in passes:
    for zid, z in p["zones"].items():
        meas[zid][1] += 1; meas[zid][0] += bool(z["measurable"])
res["measurability"] = {}
for g in groups:
    for pos in ("head", "upper", "middle", "lower", "mouth", "whole"):
        xs = [meas[zid][0] / meas[zid][1] for zid, zm in zones_meta.items()
              if zm["name"] == pos and zm["arm"] in arm_meta and arm_meta[zm["arm"]].get("zones") and group_of(zm["arm"]) == g and meas[zid][1]]
        if xs: res["measurability"][f"{g} {pos}"] = {"zones": len(xs), "medianShareOfPassesMeasurable": round(st.median(xs), 3)}
res["zoneEventDump"] = [{"date": e["pass"]["day"].isoformat(), "zone": e["zone"], "arm": e["arm"], "pos": e["pos"],
                         "anom": round(e["anom"], 4) if "anom" in e else None, "lag": e["lag"], "week": e["week"],
                         "observedCells": e["pass"]["zones"][e["zone"]]["observedCells"]} for e in zone_events]
json.dump(res, open(OUT, "w"), indent=1, default=str)
print(json.dumps({"counts": res["counts"], "storms": res["storms"], "noise": res["noise"], "gate": gate}, indent=1, default=str))
