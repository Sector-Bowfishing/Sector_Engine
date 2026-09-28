"""Historical Sentinel-2 pass pairs per arm, against the rain and flow between
them (Clarity Fusion Stage 2, item 5: calibration).

A pair is two passes on which the SAME arm was read well enough to anchor
(>= MIN_OBS_PCT of its lake cells and >= MIN_OBS_CELLS observed), no more than
MAX_GAP_DAYS apart, with no usable pass for that arm in between. For each pair:

  dlog10        change in the arm's median observed FNU (log10; + = murkier)
  dVisFt        the same change through VisibilityModel secchi-power-v1
  rainBetween   basin-mean MRMS rain over the arm's drainage between the passes
                (24 h Pass 2 products valid 17Z; passes are ~16:30Z)
  antecedent7d  basin-mean rain in the 7 days up to the first pass
  rainBefore3d  basin-mean rain in the 3 days up to the first pass (was the
                first pass itself a plume snapshot?)
  usgs          measured discharge at each pass and the peak between (15-min IV)
  nwm           modeled discharge at 16Z each pass day and the daily-16Z peak between

The noise floor comes from dry pairs: what two passes of unchanged water
disagree by (atmosphere, glint, sensor A/B/C), which a real change has to beat.

usage: geo/bin/python pass_pairs.py <passes dir> <rain_daily.json> <usgs_iv.json> <nwm_daily.json> <hydrology.json> <out.json>
"""
import os, sys, json, glob, math, datetime as dt, bisect, statistics as st

MIN_OBS_PCT = 30.0
MIN_OBS_CELLS = 30
MAX_GAP_DAYS = 12
A, B = 11.123, -0.637          # VisibilityModel secchi-power-v1


def vis(f): return A * max(f, 0.1) ** B


def main():
    pdir, rain_p, usgs_p, nwm_p, graph_p, out = sys.argv[1:7]
    passes = []
    for f in sorted(glob.glob(os.path.join(pdir, "*.json"))):
        x = json.load(open(f))
        if x.get("status") == "read":
            passes.append(x)
    passes.sort(key=lambda x: x["time"])
    rain = json.load(open(rain_p))["days"]
    usgs = json.load(open(usgs_p))
    nwm = json.load(open(nwm_p)) if os.path.exists(nwm_p) else {"days": {}, "reachToArms": {}}
    graph = json.load(open(graph_p))
    arms = {a["id"]: a for a in graph["arms"]}
    arm_to_reach = {arm: r for r, al in nwm.get("reachToArms", {}).items() for arm in al}

    def parse_t(s):
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

    usgs_series = {}
    for site, pts in usgs.items():
        ts = [parse_t(t) for t, _ in pts]; vs = [v for _, v in pts]
        usgs_series[site] = (ts, vs)

    def usgs_at(site, t, tol_h=1.0):
        ts, vs = usgs_series[site]
        i = bisect.bisect_left(ts, t)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(ts) and abs((ts[j] - t).total_seconds()) <= tol_h * 3600:
                if best is None or abs((ts[j] - t).total_seconds()) < abs((ts[best] - t).total_seconds()):
                    best = j
        return None if best is None else vs[best]

    def usgs_peak(site, t0, t1):
        ts, vs = usgs_series[site]
        i, j = bisect.bisect_left(ts, t0), bisect.bisect_right(ts, t1)
        return max(vs[i:j]) if j > i else None

    def rain_sum(arm, d0, d1):
        """days d with d0 < d <= d1; None if any day missing"""
        s, d = 0.0, d0 + dt.timedelta(days=1)
        while d <= d1:
            r = rain.get(d.isoformat())
            if r is None or r.get(arm) is None:
                return None
            s += r[arm]; d += dt.timedelta(days=1)
        return round(s, 3)

    def nwm_at(arm, d):
        r = arm_to_reach.get(arm)
        day = nwm["days"].get(d.isoformat()) if r else None
        return None if not day else day.get(r)

    by_arm = {}
    for p in passes:
        for arm, v in p["arms"].items():
            if v["fnu"] and v["observedPct"] >= MIN_OBS_PCT and v["observedCells"] >= MIN_OBS_CELLS:
                by_arm.setdefault(arm, []).append((p, v))
    pairs = []
    for arm, seq in by_arm.items():
        rain_key = "_lakeSurface" if arm == "mainstem" else arm
        a = arms.get(arm)
        for (p1, v1), (p2, v2) in zip(seq, seq[1:]):
            t1, t2 = parse_t(p1["time"]), parse_t(p2["time"])
            gap = (t2 - t1).total_seconds() / 86400
            if gap > MAX_GAP_DAYS or gap < 0.5:
                continue
            d1, d2 = t1.date(), t2.date()
            f1, f2 = v1["fnu"]["p50"], v2["fnu"]["p50"]
            row = {"arm": arm, "armClass": a["armClass"] if a else "mainstem",
                   "flowSource": a["flowSource"] if a else "tva",
                   "pass1": p1["date"], "pass2": p2["date"], "platform1": p1["platform"], "platform2": p2["platform"],
                   "gapDays": round(gap, 2),
                   "obsPct1": v1["observedPct"], "obsPct2": v2["observedPct"],
                   "fnu1": f1, "fnu2": f2, "dlog10": round(math.log10(f2 / f1), 4),
                   "vis1Ft": round(vis(f1), 2), "vis2Ft": round(vis(f2), 2), "dVisFt": round(vis(f2) - vis(f1), 2),
                   "rainBetweenIn": rain_sum(rain_key, d1, d2),
                   "antecedent7dIn": rain_sum(rain_key, d1 - dt.timedelta(days=7), d1),
                   "rainBefore3dIn": rain_sum(rain_key, d1 - dt.timedelta(days=3), d1)}
            site = a.get("usgsDischargeSite") if a else None
            if site in usgs_series:
                q1, q2 = usgs_at(site, t1), usgs_at(site, t2)
                row["usgs"] = {"site": site, "q1": q1, "q2": q2, "peakBetween": usgs_peak(site, t1, t2)}
            if a and a.get("nwmFeatureId"):
                days = [d1 + dt.timedelta(days=k) for k in range((d2 - d1).days + 1)]
                vals = [nwm_at(arm, d) for d in days]
                ok = [v for v in vals if v is not None]
                row["nwm"] = {"reach": a["nwmFeatureId"], "q1": vals[0], "q2": vals[-1],
                              "peakBetween": max(ok) if ok else None, "daysMissing": sum(v is None for v in vals)}
            pairs.append(row)

    # ---- summaries
    def dist(xs):
        xs = sorted(xs)
        if not xs: return None
        q = lambda p: xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
        return {"n": len(xs), "p10": round(q(.1), 3), "p25": round(q(.25), 3), "p50": round(q(.5), 3),
                "p75": round(q(.75), 3), "p90": round(q(.9), 3)}

    MIN_EVENTS = 8
    def summarize(rows, noise):
        ds = [r["dlog10"] for r in rows]
        s = {"pairs": len(rows), "dlog10": dist(ds)}
        if rows and noise is not None:
            s["shareMurkierBeyondNoise"] = round(sum(d > noise["p90"] for d in ds) / len(ds), 3)
            s["shareClearerBeyondNoise"] = round(sum(d < noise["p10"] for d in ds) / len(ds), 3)
        s["evidence"] = "sufficient" if len(rows) >= MIN_EVENTS else f"insufficient evidence (n = {len(rows)} < {MIN_EVENTS})"
        return s

    usable = [r for r in pairs if r["rainBetweenIn"] is not None and r["antecedent7dIn"] is not None]
    # the noise floor: dry between, dry before
    dry = [r for r in usable if r["rainBetweenIn"] < 0.05 and r["antecedent7dIn"] < 0.25 and r["gapDays"] <= 6]
    noise = dist([r["dlog10"] for r in dry])
    bins = [(0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 99)]
    def binned(rows, key="rainBetweenIn"):
        return {f"{lo}-{hi if hi < 99 else '+'}": summarize([r for r in rows if lo <= r[key] < hi], noise) for lo, hi in bins}
    trib = [r for r in usable if r["arm"] != "mainstem"]
    summary = {
        "rules": {"minObservedPct": MIN_OBS_PCT, "minObservedCells": MIN_OBS_CELLS, "maxGapDays": MAX_GAP_DAYS,
                  "minEventsForACalibratedClaim": MIN_EVENTS,
                  "noiseDefinition": "pairs <= 6 days apart with < 0.05 in between and < 0.25 in in the 7 days before"},
        "passesRead": len(passes), "pairs": len(pairs), "pairsWithRain": len(usable),
        "noiseFloorDlog10": noise,
        "allTributaryArms": {"byRainBetween": binned(trib)},
        "byAntecedent": {
            "dry (7d < 0.5 in)": binned([r for r in trib if r["antecedent7dIn"] < 0.5]),
            "wet (7d >= 0.5 in)": binned([r for r in trib if r["antecedent7dIn"] >= 0.5])},
        "byArmClass": {c: binned([r for r in trib if r["armClass"] == c]) for c in sorted({r["armClass"] for r in trib})},
        "recovery": {
            "firstPassAfterRain (3d before >= 0.5 in), dry between (< 0.1 in)":
                summarize([r for r in trib if r["rainBefore3dIn"] is not None and r["rainBefore3dIn"] >= 0.5
                           and r["rainBetweenIn"] < 0.1], noise)},
        "mainStem": {"byLakeSurfaceRainBetween": binned([r for r in usable if r["arm"] == "mainstem"])},
    }
    gauged = {}
    for arm in ("town-creek-marshall", "south-sauty-creek"):
        rows = [r for r in usable if r["arm"] == arm and r.get("usgs") and r["usgs"]["q1"] and r["usgs"]["q2"]]
        for r in rows:
            r["usgs"]["ratio"] = round(r["usgs"]["q2"] / max(r["usgs"]["q1"], 0.01), 3)
            r["usgs"]["peakRatio"] = round((r["usgs"]["peakBetween"] or 0) / max(r["usgs"]["q1"], 0.01), 3)
        qb = [(0, 0.7), (0.7, 1.5), (1.5, 3), (3, 1e9)]
        gauged[arm] = {"pairs": len(rows),
                       "byRainBetween": binned(rows),
                       "byMeasuredDischargeRatioQ2overQ1": {f"{lo}-{hi if hi < 1e9 else '+'}": summarize(
                           [r for r in rows if lo <= r["usgs"]["ratio"] < hi], noise) for lo, hi in qb},
                       "byPeakRatioBetween": {f"{lo}-{hi if hi < 1e9 else '+'}": summarize(
                           [r for r in rows if lo <= r["usgs"]["peakRatio"] < hi], noise) for lo, hi in qb},
                       "rows": rows}
    summary["measuredArms"] = gauged
    # NWM-only arms: the same by modeled ratio
    nrows = [r for r in trib if r.get("nwm") and r["nwm"]["q1"] and r["nwm"]["q2"] and r["flowSource"] == "modeledNWM"]
    for r in nrows:
        r["nwm"]["ratio"] = round(r["nwm"]["q2"] / max(r["nwm"]["q1"], 0.01), 3)
        r["nwm"]["peakRatio"] = round((r["nwm"]["peakBetween"] or 0) / max(r["nwm"]["q1"], 0.01), 3)
    qb = [(0, 0.7), (0.7, 1.5), (1.5, 3), (3, 1e9)]
    summary["modeledArms"] = {"pairs": len(nrows),
                              "byModeledPeakRatioBetween": {f"{lo}-{hi if hi < 1e9 else '+'}": summarize(
                                  [r for r in nrows if lo <= r["nwm"]["peakRatio"] < hi], noise) for lo, hi in qb}}
    # ---- events: each pass against the arm's own recent dry-weather baseline.
    # Consecutive pairs mix a storm's rise with its recovery and with
    # scene-to-scene noise; here a pass is compared with the median of the
    # same arm's passes in the 45 days before it that followed a dry week.
    events = []
    for arm, seq in by_arm.items():
        rain_key = "_lakeSurface" if arm == "mainstem" else arm
        a = arms.get(arm)
        site = a.get("usgsDischargeSite") if a else None
        hist = []
        for p, v in seq:
            t = parse_t(p["time"]); d = t.date()
            r7 = rain_sum(rain_key, d - dt.timedelta(days=7), d)
            r48 = rain_sum(rain_key, d - dt.timedelta(days=2), d)
            lf = math.log10(v["fnu"]["p50"]); l75 = math.log10(max(v["fnu"]["p75"], 0.05))
            base = [h for h in hist if (t - h["t"]).days <= 45 and h["r7"] is not None and h["r7"] < 0.25]
            if len(base) >= 2 and r48 is not None:
                b50 = st.median([h["l50"] for h in base]); b75 = st.median([h["l75"] for h in base])
                # days since the last >= 1 in day on this drainage (up to 10)
                since = None
                for k in range(0, 11):
                    x = rain.get((d - dt.timedelta(days=k)).isoformat())
                    if x and (x.get(rain_key) or 0) >= 1.0:
                        since = k; break
                row = {"arm": arm, "pass": p["date"], "waterCells": v["waterCells"], "obsPct": v["observedPct"],
                       "armClass": a["armClass"] if a else "mainstem", "rain48hIn": r48, "rain7dIn": r7,
                       "daysSinceInchDay": since, "baselinePasses": len(base),
                       "anomalyP50": round(lf - b50, 4), "anomalyP75": round(l75 - b75, 4),
                       "fnu": v["fnu"]["p50"], "baselineFNU": round(10 ** b50, 3)}
                if site in usgs_series:
                    q = usgs_at(site, t)
                    qb = [usgs_at(site, h["t"]) for h in base]
                    qb = [x for x in qb if x]
                    if q and qb:
                        row["usgsRatioToBaseline"] = round(q / st.median(qb), 3)
                events.append(row)
            hist.append({"t": t, "r7": r7, "l50": lf, "l75": l75})
    # the event noise floor: dry-week passes against the dry baseline
    dryev = [e for e in events if e["rain7dIn"] is not None and e["rain7dIn"] < 0.25]
    enoise = dist([e["anomalyP50"] for e in dryev])
    def esum(rows, key="anomalyP50"):
        xs = [r[key] for r in rows]
        s = {"events": len(rows), key: dist(xs)}
        if rows and enoise:
            s["shareMurkierBeyondNoise"] = round(sum(x > enoise["p90"] for x in xs) / len(xs), 3)
            s["shareClearerBeyondNoise"] = round(sum(x < enoise["p10"] for x in xs) / len(xs), 3)
            s["medianFNURatio"] = round(10 ** st.median(xs), 2)
        s["evidence"] = "sufficient" if len(rows) >= MIN_EVENTS else f"insufficient evidence (n = {len(rows)} < {MIN_EVENTS})"
        return s
    rb = [(0, 0.1), (0.1, 0.5), (0.5, 1.0), (1.0, 99)]
    def ebin(rows, key="anomalyP50"):
        return {f"{lo}-{hi if hi < 99 else '+'}": esum([r for r in rows if lo <= r["rain48hIn"] < hi], key) for lo, hi in rb}
    etrib = [e for e in events if e["arm"] != "mainstem"]
    small = [e for e in etrib if e["waterCells"] < 3000]; large = [e for e in etrib if e["waterCells"] >= 3000]
    summary["events"] = {
        "definition": "anomaly = log10(arm median FNU) - median of the same arm's passes in the prior 45 days that followed a week with < 0.25 in (>= 2 such passes)",
        "noiseFloor (dry-week passes)": enoise,
        "tributaryArms by rain in the 48 h before the pass": ebin(etrib),
        "tributaryArms p75 by rain in the 48 h before the pass": ebin(etrib, "anomalyP75"),
        "small arms (< 3000 cells, ~2.6 km2)": ebin(small),
        "large arms (>= 3000 cells)": ebin(large),
        "recovery: days since a >= 1 in day (tributaries)": {
            f"{lo}-{hi}": esum([e for e in etrib if e["daysSinceInchDay"] is not None and lo <= e["daysSinceInchDay"] <= hi])
            for lo, hi in ((0, 1), (2, 3), (4, 6), (7, 10))},
        "mainStem by lake-surface rain in the 48 h before the pass": ebin([e for e in events if e["arm"] == "mainstem"]),
    }
    for arm in ("town-creek-marshall", "south-sauty-creek"):
        rows = [e for e in events if e["arm"] == arm]
        summary["events"][arm] = {"byRain48h": ebin(rows),
                                  "byMeasuredFlowRatioToBaseline": {f"{lo}-{hi if hi < 1e9 else '+'}": esum(
                                      [r for r in rows if r.get("usgsRatioToBaseline") and lo <= r["usgsRatioToBaseline"] < hi])
                                      for lo, hi in ((0, 1.5), (1.5, 3), (3, 1e9))},
                                  "rows": rows}
    json.dump({"summary": summary, "pairs": pairs, "events": events}, open(out, "w"), indent=1)
    print("EVENTS", len(events), "noise", enoise)
    for k in ("tributaryArms by rain in the 48 h before the pass", "small arms (< 3000 cells, ~2.6 km2)", "large arms (>= 3000 cells)",
              "recovery: days since a >= 1 in day (tributaries)", "mainStem by lake-surface rain in the 48 h before the pass"):
        print(k)
        for b, v in summary["events"][k].items(): print("   ", b, v)
    for arm in ("town-creek-marshall", "south-sauty-creek"):
        print(arm)
        for b, v in summary["events"][arm]["byRain48h"].items(): print("   rain48", b, v)
        for b, v in summary["events"][arm]["byMeasuredFlowRatioToBaseline"].items(): print("   Q/base", b, v)
    print(json.dumps({k: summary[k] for k in ("passesRead", "pairs", "pairsWithRain", "noiseFloorDlog10")}, indent=1))
    for k, v in summary["allTributaryArms"]["byRainBetween"].items():
        print("  rain", k, v)
    for arm, g in gauged.items():
        print(arm, g["pairs"])
        for k, v in g["byRainBetween"].items(): print("   rain", k, v)
        for k, v in g["byPeakRatioBetween"].items(): print("   peakQ", k, v)


if __name__ == "__main__":
    main()
