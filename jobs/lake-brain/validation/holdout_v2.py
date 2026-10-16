#!/usr/bin/env python3
"""Lake Brain rules v2 — pre-registered hold-out protocol (section 2 of docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md), implemented literally.

Rules under test: the Python mirror rules_v2.py (verified against the Swift rules on contracts/conformance/lake_rules_v2.json BEFORE use).
Thresholds are fixed by the pre-registration and are NOT parameters of this script. Failed criteria are reported as failures.

Test years  : each lake's last 5 complete years (>= 329 daily values, < 2026).   Training for year Y: complete years < Y, basis cap per R1 (30 / 60).
H-A         : tiers STANDARD+FULL (training >= 10 y). c(L,Y) = share of days of Y inside [p10,p90]. Reference C_L = leave-one-year-out coverage of L's own
              training years (each scored with a baseline built from the other training years). Lake-year passes if c in [P5,P95] of C_L; lake passes if
              >= 4 of its 5 test years pass. A lake is TESTED when all 5 test years have >= 10 training years (the literal reading of ">= 4 of its 5").
              Criterion: >= 80 % of tested lakes pass AND pooled coverage (all days of the tested lakes' test years) in [0.75, 0.85].
H-B         : FULL lake-years (training >= 15 y): pooled share of days outside [p02,p98] <= 0.06. Info only: PROVISIONAL (and STANDARD) lake-years' share
              that v1 would have called VERY_UNUSUAL and v2 reports UNUSUAL.
H-C         : lake-years with training >= 5 y, days with a rate baseline: pooled share of rate24 > max(p95, 0.25 ft) in [0.03, 0.08] AND >= 70 % of lakes in [0.02, 0.09].
H-D         : lake-years with training >= 5 y: (i) pooled share of consecutive-day pairs (both in the test year) whose trend label changes <= 0.30;
              (ii) pooled share of STABLE days that sit inside a 3-day move of >= 0.5 ft <= 0.08 ("inside" = the day lies in some window [s, s+3 d] with
              |level(s+3 d) - level(s)| >= 0.5 ft; a trailing-only window would be vacuous because a 72 h move >= 0.5 ft can never be labelled STABLE).
Series      : daily values rounded to 0.01 ft (the archive / current-value precision). Trend labels use the daily series: d24 = level(t)-level(t-1 d),
              d72 = level(t)-level(t-3 d) when that day exists, else the 24 h fallback (counted).
usage: holdout_v2.py [--run 1] [--processes N]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import holdout_data as D  # noqa: E402
import rules_v2 as R  # noqa: E402

TEST_YEARS = 5
# ---- pre-registered thresholds (docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md section 2) ----------------------------------------------------
HA_LAKE_PASS_MIN, HA_COV_LO, HA_COV_HI, HA_BAND = 0.80, 0.75, 0.85, (5, 95)
HB_TAIL_MAX = 0.06
HC_POOLED = (0.03, 0.08); HC_LAKE_RANGE = (0.02, 0.09); HC_LAKE_SHARE_MIN = 0.70
HD_CHANGE_MAX, HD_STABLE_IN_MOVE_MAX, MOVE_FT = 0.30, 0.08, 0.5


def r2f(x: float) -> float:
    return math.copysign(math.floor(abs(x) * 100 + 0.5) / 100, x)


def coverage_arrays(A: np.ndarray, Q: np.ndarray):
    """A (365,2) test-year samples, Q (365,23) band grid -> (valid, inside p10-p90, outside p02-p98) sample counts."""
    ok = ~np.isnan(A) & ~np.isnan(Q[:, [R.G[10]]])
    p02, p10, p90, p98 = (Q[:, [R.G[p]]] for p in (2, 10, 90, 98))
    with np.errstate(invalid="ignore"):
        inside = ok & (A >= p10) & (A <= p90)
        outside = ok & ((A < p02) | (A > p98))
    return int(ok.sum()), int(inside.sum()), int(outside.sum())


def in_move(daily: dict, d: dt.date) -> bool:
    one = dt.timedelta(days=1)
    for k in range(4):
        s = d - one * k
        a, b = daily.get(s), daily.get(s + one * 3)
        if a is not None and b is not None and abs(r2f(b - a)) >= MOVE_FT:
            return True
    return False


def run_lake(rec: dict) -> dict:
    daily, regulated = rec["daily"], rec["regulated"]
    cy = D.complete_years(daily)
    tests = cy[-TEST_YEARS:]
    cache: dict = {}
    one = dt.timedelta(days=1)
    out = {"lakeId": rec["lakeId"], "completeYears": len(cy), "testYears": tests, "years": []}
    for Y in tests:
        basis = [y for y in cy if y < Y][-R.basis_cap(regulated):]
        m = len(basis)
        t = R.tier(m)
        row = {"year": Y, "trainYears": m, "tier": t}
        out["years"].append(row)
        if t == R.TIER_NONE:
            continue
        cutoff = dt.date(Y, 1, 1)
        sub = {d: v for d, v in daily.items() if d < cutoff}
        b = R.build_baseline(sub, cutoff, regulated, True, cache)
        assert b.basis_years == basis, (rec["lakeId"], Y)
        A = R.dense_year({d: v for d, v in daily.items() if d.year == Y})
        n_valid, n_in, n_out = coverage_arrays(A, b.level_q)
        row.update(days=n_valid, inside=n_in, outside=n_out, cov=(n_in / n_valid if n_valid else None))
        # ---- H-A leave-one-year-out reference
        if m >= 10 and n_valid:
            L = {y: cache[("L", y)] for y in basis}
            C = []
            for tyr in basis:
                q, _ = R.level_grid([L[y] for y in basis if y != tyr])
                v, i, _o = coverage_arrays(L[tyr], q)
                if v:
                    C.append(i / v)
            if len(C) >= 10:
                lo, hi = np.percentile(C, HA_BAND)
                row.update(loyoN=len(C), loyoLo=float(lo), loyoHi=float(hi), haPass=bool(lo <= row["cov"] <= hi))
        # ---- daily labels (H-C, H-D)
        labels, hc_days, hc_rapid, fallback = {}, 0, 0, 0
        for d in sorted(x for x in daily if x.year == Y):
            pv = daily.get(d - one)
            if pv is None:
                continue
            d24 = r2f(daily[d] - pv)
            v3 = daily.get(d - one * 3)
            d72 = r2f(daily[d] - v3) if v3 is not None else None
            p95 = b.rate_q[R.doy365(d) - 1, R.G[95]]
            has_rate = not np.isnan(p95)
            lab, thr, fl = R.trend(d24, d72, float(p95) if has_rate else None, regulated)
            labels[d] = lab
            fallback += "trend24hFallback" in fl
            if has_rate:
                hc_days += 1
                hc_rapid += lab in ("RISING_RAPIDLY", "FALLING_RAPIDLY")
        pairs = changes = stable = stable_move = 0
        for d, lab in labels.items():
            prev = labels.get(d - one)
            if prev is not None:
                pairs += 1
                changes += prev != lab
            if lab == "STABLE":
                stable += 1
                stable_move += in_move(daily, d)
        row.update(hcDays=hc_days, hcRapid=hc_rapid, labelled=len(labels), fallbackDays=fallback, pairs=pairs, changes=changes,
                   stable=stable, stableInMove=stable_move)
    return out


def load_records() -> tuple:
    rows, ex = D.selection()
    fullrows = {r["lakeId"]: r for r in csv.DictReader(open(D.FULL_V2))}
    full = {k: v["histSeries"] for k, v in fullrows.items()}
    pb = D.directory_pool_basis()
    feats = {r["id"]: r for r in csv.DictReader(open(D.FEATURES))}
    recs, nodata = [], []
    for r in rows:
        lab, path, daily, alts = D.load_lake_series(r, full.get(r["lake_id"], ""))
        if not daily:
            nodata.append({"lakeId": r["lake_id"], "provider": r["provider"], "reason": "no history file located"})
            continue
        daily = {d: r2f(v) for d, v in daily.items()}
        # data-QA flag fixed before the run (sensitivity only, never a criterion): the history series' median since 2025 vs the live binding's 30-day median
        recent = sorted(v for d, v in daily.items() if d.year >= 2025)
        try:
            live_med = float(fullrows[r["lake_id"]]["medFt"])
        except (KeyError, ValueError):
            live_med = None
        qa = {"seriesMedianSince2025": (recent[len(recent) // 2] if recent else None), "liveMedFt": live_med}
        qa["mismatchOver15ft"] = bool(recent and live_med is not None and abs(qa["seriesMedianSince2025"] - live_med) > 15)
        qa["noDataSince2025"] = not recent
        basis = pb.get(r["lake_id"])
        recs.append({"lakeId": r["lake_id"], "provider": r["provider"], "capability": r["capability_class"], "series": lab,
                     "path": os.path.relpath(path, D.DATA), "alternatives": alts, "poolBasis": basis or "unset-treated-as-natural",
                     "regulated": basis == "fullPool", "qa": qa, "lakeClass": (feats.get(r["lake_id"]) or {}).get("lake_class") or "?", "daily": daily})
    return recs, ex, nodata


def frac(a, b):
    return (a / b) if b else None


def verdict(ok):
    return "PASS" if ok else "FAIL"


def aggregate(lakes: list, recs: dict) -> dict:
    """Criteria + breakdowns from the per-lake results."""
    ly = [dict(y, lakeId=L["lakeId"]) for L in lakes for y in L["years"]]
    out = {}

    def group_keys(L):
        r = recs[L["lakeId"]]
        return {"provider": r["provider"], "poolBasis": r["poolBasis"].split(" ")[0], "lakeClass": r["lakeClass"], "capability": r["capability"]}

    # ---------------- H-A
    tested = [L for L in lakes if len(L["years"]) == TEST_YEARS and all(y["trainYears"] >= 10 for y in L["years"])]
    ha_lakes = []
    for L in tested:
        ys = L["years"]
        passes = sum(1 for y in ys if y.get("haPass"))
        have = sum(1 for y in ys if "haPass" in y)
        ha_lakes.append({"lakeId": L["lakeId"], "yearsPassed": passes, "yearsScored": have, "pass": have == TEST_YEARS and passes >= 4,
                         "days": sum(y["days"] for y in ys), "inside": sum(y["inside"] for y in ys)})
    n_t = len(ha_lakes)
    pass_n = sum(1 for x in ha_lakes if x["pass"])
    pooled_days = sum(x["days"] for x in ha_lakes); pooled_in = sum(x["inside"] for x in ha_lakes)
    pooled_cov = frac(pooled_in, pooled_days)
    all_elig = [y for y in ly if y["tier"] in (R.TIER_STANDARD, R.TIER_FULL) and y.get("days")]
    ha_pass_rate = frac(pass_n, n_t)
    out["H-A"] = {"lakesTested": n_t, "lakesPassed": pass_n, "lakePassRate": ha_pass_rate, "pooledCoverage": pooled_cov,
                  "lakeYears": n_t * TEST_YEARS,
                  "criterion": {"lakePassRate>=": HA_LAKE_PASS_MIN, "pooledCoverageIn": [HA_COV_LO, HA_COV_HI]},
                  "verdict": verdict(n_t > 0 and ha_pass_rate >= HA_LAKE_PASS_MIN and HA_COV_LO <= pooled_cov <= HA_COV_HI),
                  "lakeYearPassRate": frac(sum(1 for L in tested for y in L["years"] if y.get("haPass")), n_t * TEST_YEARS),
                  "info": {"pooledCoverageAllEligibleLakeYears(STANDARD+FULL)": frac(sum(y["inside"] for y in all_elig), sum(y["days"] for y in all_elig)),
                           "eligibleLakeYears": len(all_elig),
                           "lakesWithAnyEligibleYear": len({y["lakeId"] for y in all_elig})}}
    # distribution of lake-year coverage relative to nominal, for interpretation
    covs = [y["cov"] for L in tested for y in L["years"] if y.get("cov") is not None]
    if covs:
        out["H-A"]["info"]["lakeYearCoverageQuantiles(p5,p25,p50,p75,p95)"] = [float(x) for x in np.percentile(covs, [5, 25, 50, 75, 95])]
        out["H-A"]["info"]["lakeYearsBelowP5OfOwnReference"] = sum(1 for L in tested for y in L["years"] if y.get("haPass") is False and y["cov"] < y["loyoLo"])
        out["H-A"]["info"]["lakeYearsAboveP95OfOwnReference"] = sum(1 for L in tested for y in L["years"] if y.get("haPass") is False and y["cov"] > y["loyoHi"])
    # breakdowns
    def ha_group(field):
        g = collections.defaultdict(list)
        for x in ha_lakes:
            g[group_keys({"lakeId": x["lakeId"]})[field]].append(x)
        return {k: {"lakesTested": len(v), "lakePassRate": frac(sum(1 for x in v if x["pass"]), len(v)),
                    "pooledCoverage": frac(sum(x["inside"] for x in v), sum(x["days"] for x in v))} for k, v in sorted(g.items())}
    out["H-A"]["byProvider"] = ha_group("provider"); out["H-A"]["byPoolBasis"] = ha_group("poolBasis"); out["H-A"]["byLakeClass"] = ha_group("lakeClass")
    out["H-A"]["lakes"] = ha_lakes

    # ---------------- H-B
    full = [y for y in ly if y["tier"] == R.TIER_FULL and y.get("days")]
    fd, fo = sum(y["days"] for y in full), sum(y["outside"] for y in full)
    tail = frac(fo, fd)
    out["H-B"] = {"fullLakeYears": len(full), "fullLakes": len({y["lakeId"] for y in full}), "days": fd, "pooledShareOutsideP02P98": tail, "nominal": 0.04,
                  "criterion": {"pooledShareOutside<=": HB_TAIL_MAX}, "verdict": verdict(full != [] and tail <= HB_TAIL_MAX)}
    for nm, tr in (("PROVISIONAL", R.TIER_PROVISIONAL), ("STANDARD", R.TIER_STANDARD)):
        ys = [y for y in ly if y["tier"] == tr and y.get("days")]
        out["H-B"].setdefault("info", {})[f"{nm}_v1VeryUnusualReportedUnusualUnderV2"] = {
            "lakeYears": len(ys), "lakes": len({y["lakeId"] for y in ys}), "days": sum(y["days"] for y in ys),
            "share": frac(sum(y["outside"] for y in ys), sum(y["days"] for y in ys))}
    def hb_group(field):
        g = collections.defaultdict(lambda: [0, 0, set()])
        for y in full:
            k = group_keys({"lakeId": y["lakeId"]})[field]
            g[k][0] += y["days"]; g[k][1] += y["outside"]; g[k][2].add(y["lakeId"])
        return {k: {"lakes": len(v[2]), "days": v[0], "share": frac(v[1], v[0])} for k, v in sorted(g.items())}
    out["H-B"]["byProvider"] = hb_group("provider"); out["H-B"]["byPoolBasis"] = hb_group("poolBasis"); out["H-B"]["byLakeClass"] = hb_group("lakeClass")

    # ---------------- H-C
    t5 = [y for y in ly if y["tier"] != R.TIER_NONE and y.get("hcDays")]
    per_lake = collections.defaultdict(lambda: [0, 0])
    for y in t5:
        per_lake[y["lakeId"]][0] += y["hcDays"]; per_lake[y["lakeId"]][1] += y["hcRapid"]
    pd_, pr_ = sum(y["hcDays"] for y in t5), sum(y["hcRapid"] for y in t5)
    pooled = frac(pr_, pd_)
    in_rng = sum(1 for d, r in per_lake.values() if HC_LAKE_RANGE[0] <= r / d <= HC_LAKE_RANGE[1])
    lake_share = frac(in_rng, len(per_lake))
    out["H-C"] = {"lakes": len(per_lake), "lakeYears": len(t5), "days": pd_, "rapidDays": pr_, "pooledRapidRate": pooled, "lakesWithinRange": in_rng,
                  "lakeShareWithinRange": lake_share, "criterion": {"pooledIn": list(HC_POOLED), "lakeRange": list(HC_LAKE_RANGE), "lakeShare>=": HC_LAKE_SHARE_MIN},
                  "verdict": verdict(per_lake != {} and HC_POOLED[0] <= pooled <= HC_POOLED[1] and lake_share >= HC_LAKE_SHARE_MIN),
                  "info": {"lakeRateQuantiles(p5,p25,p50,p75,p95)": [float(x) for x in np.percentile([r / d for d, r in per_lake.values()], [5, 25, 50, 75, 95])] if per_lake else None,
                           "lakesBelowRange": sum(1 for d, r in per_lake.values() if r / d < HC_LAKE_RANGE[0]),
                           "lakesAboveRange": sum(1 for d, r in per_lake.values() if r / d > HC_LAKE_RANGE[1])}}
    def hc_group(field):
        g = collections.defaultdict(dict)
        for lid, (d, r) in per_lake.items():
            g[group_keys({"lakeId": lid})[field]][lid] = (d, r)
        return {k: {"lakes": len(v), "pooledRapidRate": frac(sum(r for d, r in v.values()), sum(d for d, r in v.values())),
                    "lakeShareWithinRange": frac(sum(1 for d, r in v.values() if HC_LAKE_RANGE[0] <= r / d <= HC_LAKE_RANGE[1]), len(v))} for k, v in sorted(g.items())}
    out["H-C"]["byProvider"] = hc_group("provider"); out["H-C"]["byPoolBasis"] = hc_group("poolBasis"); out["H-C"]["byLakeClass"] = hc_group("lakeClass")

    # ---------------- H-D
    t5d = [y for y in ly if y["tier"] != R.TIER_NONE and y.get("labelled")]
    pairs, changes = sum(y["pairs"] for y in t5d), sum(y["changes"] for y in t5d)
    stable, sm = sum(y["stable"] for y in t5d), sum(y["stableInMove"] for y in t5d)
    chg, stm = frac(changes, pairs), frac(sm, stable)
    out["H-D"] = {"lakes": len({y["lakeId"] for y in t5d}), "lakeYears": len(t5d), "labelledDays": sum(y["labelled"] for y in t5d),
                  "fallbackDays(24h)": sum(y["fallbackDays"] for y in t5d), "pairs": pairs, "labelChanges": changes, "pooledLabelChangeRate": chg,
                  "stableDays": stable, "stableInside3dMove>=0.5ft": sm, "pooledStableInMoveRate": stm,
                  "criterion": {"labelChangeRate<=": HD_CHANGE_MAX, "stableInMoveRate<=": HD_STABLE_IN_MOVE_MAX},
                  "verdict(i)": verdict(pairs > 0 and chg <= HD_CHANGE_MAX), "verdict(ii)": verdict(stable > 0 and stm <= HD_STABLE_IN_MOVE_MAX)}
    out["H-D"]["verdict"] = verdict(out["H-D"]["verdict(i)"] == "PASS" and out["H-D"]["verdict(ii)"] == "PASS")
    def hd_group(field):
        g = collections.defaultdict(lambda: [0, 0, 0, 0, set()])
        for y in t5d:
            k = group_keys({"lakeId": y["lakeId"]})[field]
            a = g[k]; a[0] += y["pairs"]; a[1] += y["changes"]; a[2] += y["stable"]; a[3] += y["stableInMove"]; a[4].add(y["lakeId"])
        return {k: {"lakes": len(a[4]), "labelChangeRate": frac(a[1], a[0]), "stableInMoveRate": frac(a[3], a[2])} for k, a in sorted(g.items())}
    out["H-D"]["byProvider"] = hd_group("provider"); out["H-D"]["byPoolBasis"] = hd_group("poolBasis"); out["H-D"]["byLakeClass"] = hd_group("lakeClass")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1, help="1 = the pre-registered run; 2 only after a harness (not rule) bug fix, recorded as such")
    ap.add_argument("--processes", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    resdir = os.path.join(HERE, "results")
    os.makedirs(resdir, exist_ok=True)
    jpath = os.path.join(resdir, "holdout_v2_results.json" if a.run == 1 else f"holdout_v2_results_run{a.run}.json")
    if os.path.exists(jpath):
        sys.exit(f"{jpath} exists: the protocol is run once per harness version. Delete it only to record a documented re-run.")
    recs, ex, nodata = load_records()
    by = {r["lakeId"]: r for r in recs}
    with mp.get_context("fork").Pool(a.processes) as pool:
        lakes = pool.map(run_lake, recs, chunksize=1)
    agg = aggregate(lakes, by)
    qa_ids = {r["lakeId"] for r in recs if r["qa"]["mismatchOver15ft"]}
    sens = aggregate([L for L in lakes if L["lakeId"] not in qa_ids], by)
    sensitivity = {"definition": "same protocol without the lakes whose history series median since 2025 differs from the live binding's 30-day median by > 15 ft (series/binding datum mismatch). "
                   "INFORMATION ONLY: the pre-registered verdicts are the full-set ones.", "lakesRemoved": sorted(qa_ids),
                   "criteria": {k: {"verdict": v["verdict"], **{kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list)) and kk != "verdict"}} for k, v in sens.items()}}
    try:
        sha = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = None
    tiers = collections.Counter(y["tier"] for L in lakes for y in L["years"])
    result = {
        "protocol": "docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md section 2", "run": a.run, "note": a.note, "gitHead": sha,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "numpy": np.__version__, "python": sys.version.split()[0],
        "selection": ex, "lakesWithNoSeries": nodata, "lakesWithSeries": len(recs),
        "lakeYearsByTier": dict(tiers), "completeYearsDistribution": dict(sorted(collections.Counter(min(L["completeYears"], 60) for L in lakes).items())),
        "criteria": {k: {"verdict": v["verdict"]} for k, v in agg.items()}, "results": agg, "sensitivityExcludingSeriesMismatch": sensitivity,
        "seriesQa": {"mismatchOver15ft": sorted(qa_ids), "noDataSince2025": sorted(r["lakeId"] for r in recs if r["qa"]["noDataSince2025"])},
        "lakes": [{"lakeId": L["lakeId"], "provider": by[L["lakeId"]]["provider"], "series": by[L["lakeId"]]["series"], "seriesFile": by[L["lakeId"]]["path"],
                   "poolBasis": by[L["lakeId"]]["poolBasis"], "lakeClass": by[L["lakeId"]]["lakeClass"], "completeYears": L["completeYears"], "qa": by[L["lakeId"]]["qa"],
                   "testYears": L["testYears"], "years": L["years"]} for L in lakes],
    }
    with open(jpath, "w") as f:
        json.dump(result, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    cpath = jpath.replace(".json", "_lakes.csv")
    with open(cpath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lakeId", "provider", "poolBasis", "lakeClass", "series", "completeYears", "year", "trainYears", "tier", "days", "cov_p10_p90", "outside_p02_p98",
                    "loyoN", "loyoP5", "loyoP95", "haPass", "hcDays", "hcRapid", "labelled", "fallbackDays", "pairs", "changes", "stable", "stableInMove"])
        for L in lakes:
            r = by[L["lakeId"]]
            for y in L["years"]:
                w.writerow([L["lakeId"], r["provider"], r["poolBasis"].split(" ")[0], r["lakeClass"], r["series"], L["completeYears"], y["year"], y["trainYears"], y["tier"],
                            y.get("days", ""), y.get("cov", ""), y.get("outside", ""), y.get("loyoN", ""), y.get("loyoLo", ""), y.get("loyoHi", ""), y.get("haPass", ""),
                            y.get("hcDays", ""), y.get("hcRapid", ""), y.get("labelled", ""), y.get("fallbackDays", ""), y.get("pairs", ""), y.get("changes", ""),
                            y.get("stable", ""), y.get("stableInMove", "")])
    print(json.dumps({"selection": ex, "lakesWithSeries": len(recs), "lakeYearsByTier": dict(tiers),
                      "criteria": {k: v["verdict"] for k, v in agg.items()}}, indent=1))
    for k in ("H-A", "H-B", "H-C", "H-D"):
        v = agg[k]
        print(k, v["verdict"], {kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list)) or kk == "criterion"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
