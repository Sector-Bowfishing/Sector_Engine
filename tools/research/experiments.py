#!/usr/bin/env python3
"""Research avenues beyond plain downloading: candidate-rule experiments, alternate-source connectors, dataset search and cross-Brain tests.
Registered in EXPERIMENTS and scheduled by the coordinator from discovery.json `avenues` (campaign.py stage_followup + ledger.py).

Every experiment follows the same contract:
  acquire(ev, home, spec, it, targets, gaps) -> dict   downloads (allowlisted, with provenance) or {} for analysis-only avenues
  analyze(home, spec, mine, allacq, upstream) -> {metrics, findings, weak, limitations, [owner]}   OFFLINE and deterministic: re-run by the
      validate stage from the hashed evidence; a result that does not reproduce is rejected
Findings declare the tier they claim (ledger.TIERS); the validator re-computes the evidence and enforces the tier's requirements. A
candidate change that does not beat its baseline on data NOT used to build it is rejected - and kept as a rejected hypothesis.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import io
import json
import math
import os
import re
import statistics as S
import urllib.parse

import discovery as D

SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA"}
RUNGS = {"season": lambda r: r["season"], "region_season": lambda r: f"{r['region']}|{r['season']}", "class_season": lambda r: f"{r['cls']}|{r['season']}"}


def season_of(month: int) -> str:
    return SEASON.get(month, "SON")


def rmse(v):
    return math.sqrt(sum(x * x for x in v) / len(v)) if v else float("nan")


# ------------------------------------------------------------------------------------------------------------------------------- Water Temp
def _resid(home: str, rel: str) -> list[dict]:
    rows = []
    with gzip.open(os.path.join(home, rel), "rt") as fh:
        for r in csv.DictReader(fh):
            if not r.get("m0") or not r.get("e"):
                continue
            rows.append({"stem": D.safe_key(r["lake"].replace("|", "_").replace("/", "-").replace(" ", "_")), "year": int(r["year"]), "season": r["season"],
                         "region": r["region"], "cls": r["cls"], "state": r.get("state", ""), "e": float(r["e"])})
    return rows


def _fit(rows, keyf, min_cell, shrink):
    g: dict = {}
    for r in rows:
        g.setdefault(keyf(r), []).append(r["e"])
    return {k: S.median(v) * len(v) / (len(v) + shrink) for k, v in g.items() if len(v) >= min_cell}


def _sensor_errors(home: str, cfg: dict, allacq: list[dict]) -> dict:
    """{lake key: {'errs': [(date, M0 - sensor)], 'site': ..}} from the primary connector's evidence (best site per lake)."""
    per = {}
    for a in allacq:
        for key, m in (a.get("matched") or {}).items():
            if "sites" in m:
                per[key] = {**m, "sites": per[key]["sites"] + m["sites"]} if key in per else m
    out = {}
    for key in sorted(per):
        m = per[key]
        forc = D.m0_daily(json.load(open(os.path.join(home, m["forcing"]), encoding="utf-8"))["daily"])
        best = None
        for s in m["sites"]:
            series, _ = D.dv_series(os.path.join(home, s["path"]))
            errs = [(d, v0 - obs) for d, obs in sorted(series.items()) if (v0 := D.m0_for_date(forc, d)) is not None]
            if len(errs) >= cfg.get("minDays", 60) and (best is None or len(errs) > len(best["errs"])):
                best = {"errs": errs, "site": s["site"], "paths": [s["path"], m["forcing"]]}
        if best:
            out[key] = best
    return out


def _q(v, q):
    v = sorted(v)
    if not v:
        return float("nan")
    k = (len(v) - 1) * q
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def _is(e, lo, hi, alpha):
    """Interval score (Gneiting & Raftery) in error space: width plus a penalty for each miss, scaled by 2/alpha. Lower is better; rewards narrow AND calibrated."""
    return (hi - lo) + (2 / alpha) * max(0.0, lo - e) + (2 / alpha) * max(0.0, e - hi)


def analyze_wt_interval(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Hypothesis: the single published error band (+-q, one number for every lake and season) is miscalibrated because M0's error is seasonal and
    asymmetric; an empirical 80% interval per `rung` cell (season / region x season) has a better interval score and calibration on data not used to
    build it. Tests (pre-declared in discovery.json): T1 temporal holdout; T2 leave-lake-out on independent USGS sensors."""
    rung, alpha = spec["rung"], 1 - spec["nominal"]
    keyf = RUNGS[rung]
    rows = _resid(home, spec["storedResiduals"])
    train = [r for r in rows if r["year"] <= spec["trainThroughYear"]]
    test = [r for r in rows if r["year"] > spec["trainThroughYear"]]

    def fit(rs):
        cells = {}
        for r in rs:
            cells.setdefault(keyf(r), []).append(r["e"])
        pooled = _q([abs(r["e"]) for r in rs], spec["nominal"])
        return {k: (_q(v, alpha / 2), _q(v, 1 - alpha / 2)) for k, v in cells.items() if len(v) >= spec["minCell"]}, pooled

    cells, q0 = fit(train)

    def score(items, cells, q0):
        base_is = cand_is = 0.0
        cov_b = cov_c = 0
        wid_c = 0.0
        by = {}
        for key, e in items:
            lo, hi = cells.get(key, (-q0, q0))
            base_is += _is(e, -q0, q0, alpha)
            cand_is += _is(e, lo, hi, alpha)
            cov_b += (-q0 <= e <= q0)
            cov_c += (lo <= e <= hi)
            wid_c += hi - lo
            b = by.setdefault(key.split("|")[-1], [0, 0, 0])
            b[0] += 1
            b[1] += (-q0 <= e <= q0)
            b[2] += (lo <= e <= hi)
        n = len(items)
        return {"n": n, "isBase": base_is / n, "isCand": cand_is / n, "covBase": cov_b / n, "covCand": cov_c / n, "widthBase": 2 * q0, "widthCand": wid_c / n,
                "worstSeasonCalibBase": max(abs(b[1] / b[0] - spec["nominal"]) for b in by.values()), "worstSeasonCalibCand": max(abs(b[2] / b[0] - spec["nominal"]) for b in by.values())}
    h = score([(keyf(r), r["e"]) for r in test], cells, q0)
    m = {"rung": rung, "nominal": spec["nominal"], "cells": len(cells), "holdoutN": h["n"], "holdoutIsBase": round(h["isBase"], 4), "holdoutIsCand": round(h["isCand"], 4),
         "holdoutDeltaIs": round(h["isBase"] - h["isCand"], 4), "holdoutCoverageBase": round(h["covBase"], 4), "holdoutCoverageCand": round(h["covCand"], 4),
         "holdoutWidthBase": round(h["widthBase"], 4), "holdoutWidthCand": round(h["widthCand"], 4),
         "holdoutWorstSeasonCalibBase": round(h["worstSeasonCalibBase"], 4), "holdoutWorstSeasonCalibCand": round(h["worstSeasonCalibCand"], 4),
         "holdoutCalibGain": round(h["worstSeasonCalibBase"] - h["worstSeasonCalibCand"], 4)}
    sensors = _sensor_errors(home, spec, allacq)
    meta, state_region = {}, {}
    for r in rows:
        meta.setdefault(r["stem"], (r["region"], r["cls"]))
        if r["state"]:
            state_region.setdefault(r["state"], r["region"])
    lakes, used = {}, set([spec["storedResiduals"]])
    for key, se in sorted(sensors.items()):
        stem = D.safe_key(key)
        reg = meta[stem][0] if stem in meta else state_region.get(key.rsplit("_", 1)[-1])
        if rung == "region_season" and not reg:
            continue
        lc, lq0 = fit([r for r in rows if r["stem"] != stem])
        items = [(keyf({"season": season_of(int(d[5:7])), "region": reg, "cls": None}), e) for d, e in se["errs"]]
        x = score(items, lc, lq0)
        lakes[key] = {"n": x["n"], "isBase": round(x["isBase"], 4), "isCand": round(x["isCand"], 4), "covBase": round(x["covBase"], 4), "covCand": round(x["covCand"], 4)}
        used |= set(se["paths"])
    m["sensorLakes"] = len(lakes)
    if lakes:
        pb = sum(v["isBase"] for v in lakes.values()) / len(lakes)
        pc = sum(v["isCand"] for v in lakes.values()) / len(lakes)
        m.update({"sensorIsBase": round(pb, 4), "sensorIsCand": round(pc, 4), "sensorDeltaIs": round(pb - pc, 4), "lakes": lakes,
                  "lakesWorseShare": round(sum(v["isCand"] > v["isBase"] + spec["worseTol"] for v in lakes.values()) / len(lakes), 4)})
    m["bandsC"] = {k: [round(a, 3), round(b, 3)] for k, (a, b) in sorted(cells.items())}
    g = f"discovery.exp.{spec['avenueId']}"
    tests = [{"metric": f"{g}.holdoutDeltaIs", "op": ">=", "threshold": spec["holdoutMinDeltaIs"]},
             {"metric": f"{g}.holdoutCalibGain", "op": ">=", "threshold": spec["minCalibGain"]},
             {"metric": f"{g}.sensorDeltaIs", "op": ">=", "threshold": spec["sensorMinDeltaIs"]},
             {"metric": f"{g}.lakesWorseShare", "op": "<=", "threshold": spec["maxWorseShare"]},
             {"metric": f"{g}.sensorLakes", "op": ">=", "threshold": spec["minSensorLakes"]}]
    change = {"scientificChange": f"Publish a {rung.replace('_', ' x ')} empirical 80% error interval for the modeled water temperature instead of one fixed +-band.",
              "previous": f"One symmetric band (+-{round(q0, 2)} C at 80% in the fitting years) for every lake and season.",
              "proposed": {"intervals": "observed = M0 - [lo, hi] of the cell's residual quantiles (10% and 90%)", "cell": rung, "bandsC": m["bandsC"],
                           "fit": f"fleet grab-sample residuals, years <= {spec['trainThroughYear']}, min {spec['minCell']} per cell"},
              "evidenceSummary": f"{len(train)} residuals for fitting; {len(test)} later ones held out; {len(lakes)} independent USGS sensor lakes fitted without their own lake.",
              "validationMethod": "interval score (width + 2/alpha x misses) and per-season coverage, temporal holdout and leave-lake-out sensors; thresholds pre-declared",
              "validationResults": {k: m.get(k) for k in ("holdoutIsBase", "holdoutIsCand", "holdoutCoverageBase", "holdoutCoverageCand", "holdoutWorstSeasonCalibBase", "holdoutWorstSeasonCalibCand",
                                                          "sensorIsBase", "sensorIsCand", "lakesWorseShare")},
              "practicalEffect": "A bowfisher sees an honest, season-aware range around the modeled temperature (for example spring readings are more likely warmer than the model) instead of a single +-number that is too tight in some seasons and too wide in others.",
              "scoreImpact": "None under water-temp-level-ladder-v1 (gate-based); recorded as a measured uncertainty-handling gain for the candidate capability contract.",
              "limitations": "Grab samples are daytime single-depth; sensor lakes are few; the interval describes the model's error, not the fish; publication requires a Water Temp release change and approval."}
    cap = {"baselineKind": "the single fixed error band used today", "kind": "uncertainty", "name": "interval score of the published water-temperature uncertainty band (C, lower is better)", "direction": "lower_better",
           "baselineMetric": f"{g}.sensorIsBase", "candidateMetric": f"{g}.sensorIsCand", "minDelta": spec["sensorMinDeltaIs"], "nMetric": f"{g}.sensorLakes", "minN": spec["minSensorLakes"], "tests": tests}
    f = D.finding(f"WT-INTERVAL-{rung}", f"A {rung.replace('_', ' x ')} empirical interval is better calibrated and sharper than one fixed band on data not used to build it.", "PARAMETER",
                  sorted(used), home, "offline refit, interval score, temporal holdout + leave-lake-out sensors", f"{g}.holdoutDeltaIs", ">=", spec["holdoutMinDeltaIs"],
                  tier="INDEPENDENTLY_VALIDATED", change=change, capability=cap)
    return {"metrics": m, "findings": [f], "weak": [], "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- Fish field test (LTRM)
def acquire_ltrm(ev, home, spec, it, targets, gaps):
    """Download the USGS UMESC LTRM fisheries database (17.7 MB zip, allowlisted) and derive ONE compact, deterministic sample table from its 464 MB CSV
    (day/night electrofishing samples with temperature, depth, stratum and target-species catches). The derived file is hashed and registered like any evidence."""
    import gzip
    import zipfile
    p = spec["params"]
    rel = ev.fetch("ltrm", "LTRM_FISH_DATA_ENTIRE.zip", p["url"], None, purpose="LTRM fisheries database (day/night electrofishing with temperature) for Fish rule field tests")
    if not rel:
        return {"zip": None}
    drel = rel[:-4] + "_samples_v1.csv.gz"
    full = os.path.join(home, drel)
    if drel in ev.prov["files"] and os.path.exists(full):
        return {"zip": rel, "samples": drel}
    codes = list(p["speciesCodes"])
    agg = {}
    with zipfile.ZipFile(os.path.join(home, rel)) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as fh:
            rd = csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"))
            for r in rd:
                g = r["gear"]
                if g not in ("D", "N") or r["summary"] in ("1", "1.0", "2", "2.0"):
                    continue
                b = r["barcode"]
                a = agg.get(b)
                if a is None:
                    try:
                        mm, dd, yy = r["sdate"].split("/")
                        eff = float(r["effmin"] or 0) / 60.0 or float(r["effhr"] or 0)
                    except ValueError:
                        continue
                    if eff <= 0:
                        continue
                    try:
                        temp = float(r["temp"]) if r["temp"] and not r["t_qf"] else None
                        depth = float(r["depth"]) if r["depth"] else None
                    except ValueError:
                        temp = depth = None
                    a = agg[b] = {"date": f"{yy}-{mm}-{dd}", "pool": r["pool"], "stratum": r["stratum"], "gear": g, "eff": round(eff, 4),
                                  "temp": temp if temp is not None and 0 <= temp <= 40 else "", "depth": depth if depth is not None and 0 < depth < 30 else "", "c": dict.fromkeys(codes, 0)}
                if r["fishcode"] in a["c"]:
                    try:
                        a["c"][r["fishcode"]] += int(float(r["catch"] or 0))
                    except ValueError:
                        pass
    tmp = full + ".part"
    with open(tmp, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            w = csv.writer(io.TextIOWrapper(gz, encoding="utf-8", newline=""))
            w.writerow(["barcode", "date", "pool", "stratum", "gear", "effHr", "tempC", "depthM"] + codes)
            for b in sorted(agg):
                a = agg[b]
                w.writerow([b, a["date"], a["pool"], a["stratum"], a["gear"], a["eff"], a["temp"], a["depth"]] + [a["c"][c] for c in codes])
            w.writerow([])
    os.replace(tmp, full)
    ev.prov["files"][drel] = {"url": f"derived://{ev.prov['files'][rel]['sha256'][:16]}/ltrm-samples-v1", "sha256": D.sha256(full), "bytes": os.path.getsize(full), "status": "SAVED", "connector": "ltrm",
                              "retrievedAt": D.now_iso(), "license": ev.prov["files"][rel]["license"], "derivedFrom": rel,
                              "purpose": "day/night electrofishing samples with temperature, depth, stratum and target-species catches (derived, deterministic)"}
    ev.new += 1
    return {"zip": rel, "samples": drel, "samplesDerived": len(agg)}


def _ltrm_rows(path):
    import gzip
    out = []
    with gzip.open(path, "rt", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if not r.get("barcode"):
                continue
            out.append(r)
    return out


def _boot_ratio(clusters, min_eff, rng, boots, alpha=0.05):
    """Ratio of pooled CPUE A/B over matched cells present in both groups; 95% CI by bootstrap over clusters (pool x year)."""
    def ratio(cl):
        cells = {}
        for c in cl:
            for k, (ca, ea, cb, eb) in c.items():
                x = cells.setdefault(k, [0, 0.0, 0, 0.0])
                x[0] += ca
                x[1] += ea
                x[2] += cb
                x[3] += eb
        sa = ea_ = sb = eb_ = 0.0
        for ca, ea, cb, eb in cells.values():
            if ea >= min_eff and eb >= min_eff:
                sa += ca
                ea_ += ea
                sb += cb
                eb_ += eb
        if ea_ <= 0 or eb_ <= 0 or sb <= 0 or sa <= 0:
            return None, ea_, eb_, sa, sb
        return (sa / ea_) / (sb / eb_), ea_, eb_, sa, sb
    r0, ea, eb, ca, cb = ratio(clusters)
    if r0 is None:
        return None
    vals = []
    n = len(clusters)
    for _ in range(boots):
        rr = ratio([clusters[rng.randrange(n)] for _ in range(n)])[0]
        if rr is not None:
            vals.append(rr)
    vals.sort()
    if len(vals) < boots * 0.8:
        return None
    return {"ratio": r0, "lo": vals[int(alpha / 2 * len(vals))], "hi": vals[int((1 - alpha / 2) * len(vals)) - 1], "effortA": ea, "effortB": eb, "catchA": ca, "catchB": cb}


def _verdict(expect, r, spec):
    lo, hi = r["lo"], r["hi"]
    if expect in ("night_gt_day", "cold_gt_warm"):
        return "SUPPORTED" if lo > 1 else ("CONTRADICTED" if hi < 1 else "INCONCLUSIVE")
    if expect in ("night_lt_day", "cold_lt_warm"):
        return "SUPPORTED" if hi < 1 else ("CONTRADICTED" if lo > 1 else "INCONCLUSIVE")
    if expect == "no_night_advantage":
        return "SUPPORTED" if hi < spec["noAdvantageUpper"] else ("CONTRADICTED" if lo > spec["noAdvantageUpper"] else "INCONCLUSIVE")
    if expect in ("cold_not_lower", "warm_not_lower"):
        t = spec["warmNotLowerLower"]
        return "SUPPORTED" if lo > t else ("CONTRADICTED" if hi < t else "INCONCLUSIVE")
    return "INCONCLUSIVE"


def analyze_ltrm(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    import random
    p = spec["params"]
    path = None
    for a in mine:
        if a.get("samples"):
            path = a["samples"]
    if not path:
        return {"metrics": {"testsRun": 0}, "findings": [], "weak": ["ltrm-download"], "limitations": [{"limitation": "LTRM database was not downloaded (source unreachable)", "kind": "external", "gap": "FISH-VAL-001",
                                                                                                        "nextSource": "retry the LTRM download (www.umesc.usgs.gov) in a later campaign"}]}
    rows = _ltrm_rows(os.path.join(home, path))
    g = f"discovery.exp.{spec['avenueId']}"
    res, findings = {}, []

    def one_test(t, boots, alpha):
        sp, ty = t["species"], t["type"]
        by = {}
        for r in rows:
            try:
                eff = float(r["effHr"])
                c = int(r[sp])
            except (KeyError, ValueError):
                continue
            yr = r["date"][:4]
            mo = r["date"][5:7]
            cl = (r["pool"], yr)
            tmp = float(r["tempC"]) if r["tempC"] else None
            dep = float(r["depthM"]) if r["depthM"] else None
            if ty in ("diel", "diel_shallow"):
                if ty == "diel_shallow" and (dep is None or dep > p["shallowDepthM"]):
                    continue
                grp = "A" if r["gear"] == "N" else "B"                       # A = night, B = day
                cell = (r["pool"], r["stratum"], yr)                          # matched on YEAR too: night sampling was concentrated in early years (before the carp invasions)
            else:
                if r["gear"] != "D" or tmp is None:
                    continue
                if ty == "thermal_warm":
                    lo_, hi_ = 26.0, 30.0
                    grp = "A" if lo_ <= tmp < hi_ else ("B" if 20.0 <= tmp < 26.0 else None)
                else:
                    grp = "A" if tmp < p["coldC"] else ("B" if tmp >= p["warmC"] else None)
                cell = (r["pool"], r["stratum"], yr)
            if grp is None:
                continue
            d = by.setdefault(cl, {}).setdefault(cell, [0, 0.0, 0, 0.0])
            if grp == "A":
                d[0] += c
                d[1] += eff
            else:
                d[2] += c
                d[3] += eff
        clusters = [{k: tuple(v) for k, v in cl.items()} for _, cl in sorted(by.items())]
        rng = random.Random(p["seed"])
        out = _boot_ratio(clusters, 0.25, rng, boots, alpha) if clusters else None
        if out is None or out["effortA"] < p["minEffortHours"] or out["effortB"] < p["minEffortHours"]:
            return None, {"verdict": "INSUFFICIENT_DATA", "decisive": 0, "effortA": round((out or {}).get("effortA", 0), 2), "effortB": round((out or {}).get("effortB", 0), 2)}
        return out, None

    for t in p["tests"]:
        out, bad = one_test(t, p["bootstrap"], 0.05)
        if bad:
            res[t["ruleId"]] = bad
            continue
        v = _verdict(t["expect"], out, p)
        entry = {"verdict": v, "decisive": int(v in ("SUPPORTED", "CONTRADICTED")), "ratio": round(out["ratio"], 4), "ciLo": round(out["lo"], 4), "ciHi": round(out["hi"], 4),
                 "effortA": round(out["effortA"], 2), "effortB": round(out["effortB"], 2), "catchA": out["catchA"], "catchB": out["catchB"]}
        if t.get("magnitude"):
            entry["magnitudeClaimMet"] = int(out["lo"] >= t["magnitude"])
        res[t["ruleId"]] = entry
    # ---- discovery scan: NEW candidate rules. Every species x {night vs day, cold vs warm} not already declared, with a Bonferroni-corrected interval over the whole scan.
    scan_cands, scan_n = [], 0
    sc = p.get("scan")
    if sc:
        declared = {(t["species"], "diel" if t["type"].startswith("diel") else "thermal") for t in p["tests"]}
        todo = [(sp, ty) for sp in sc["species"] for ty in ("diel", "thermal_cold") if (sp, "diel" if ty == "diel" else "thermal") not in declared]
        alpha = 0.05 / max(len(todo), 1)
        for sp, ty in todo:
            scan_n += 1
            out, bad = one_test({"species": sp, "type": ty}, sc["bootstrap"], alpha)
            if bad:
                continue
            if out["lo"] > 1 or out["hi"] < 1:
                up = out["lo"] > 1
                what = {"diel": ("more", "fewer") , "thermal_cold": ("more", "fewer")}[ty]
                scan_cands.append({"species": sp, "name": SPECIES.get(sp, sp), "type": ty, "direction": "UP" if up else "DOWN", "ratio": round(out["ratio"], 4),
                                   "ci": [round(out["lo"], 4), round(out["hi"], 4)], "alpha": round(alpha, 5), "effortHours": [round(out["effortA"], 1), round(out["effortB"], 1)],
                                   "catch": [out["catchA"], out["catchB"]],
                                   "candidateRule": (f"{SPECIES.get(sp, sp)} catch rate is {'higher' if up else 'lower'} at night than by day in electrofishing (rate ratio {round(out['ratio'], 2)})" if ty == "diel" else
                                                     f"{SPECIES.get(sp, sp)} catch rate is {'higher' if up else 'lower'} in cold water (<{p['coldC']} C) than in warm water (>={p['warmC']} C) (rate ratio {round(out['ratio'], 2)})")})
    decisive = [k for k, v in res.items() if v["decisive"]]
    m = {"scanTestsRun": scan_n, "scanCandidateRules": len(scan_cands), "scanCandidates": scan_cands, "testsRun": len(res), "rulesFieldTestedBase": 0, "rulesFieldTestedCand": len(decisive), "decisiveRules": len(decisive),
         "supported": sum(v["verdict"] == "SUPPORTED" for v in res.values()), "contradicted": sum(v["verdict"] == "CONTRADICTED" for v in res.values()),
         "inconclusive": sum(v["verdict"] == "INCONCLUSIVE" for v in res.values()), "insufficient": sum(v["verdict"] == "INSUFFICIENT_DATA" for v in res.values()),
         "samples": len(rows), "tests": res}
    paths = sorted({path, path[:-len("_samples_v1.csv.gz")] + ".zip"})
    for t in p["tests"]:
        v = res[t["ruleId"]]
        if v["decisive"]:
            findings.append(D.finding(f"FISH-FIELD-{t['ruleId']}", f"Field data (USGS LTRM, Upper Mississippi navigation pools, a river surrogate): rule {t['ruleId']} ('{t['claim']}') is {v['verdict']} "
                                      f"(rate ratio {v['ratio']}, 95% CI {v['ciLo']}-{v['ciHi']}).", "EVIDENCE", paths, home, "matched-stratum CPUE ratio with cluster bootstrap (pool x year)",
                                      f"{g}.tests.{t['ruleId']}.decisive", ">=", 1, tier="SCIENTIFIC_SUPPORT"))
    if decisive:
        proposed = [{"ruleId": k, "verdict": res[k]["verdict"], "ratio": res[k]["ratio"], "ci": [res[k]["ciLo"], res[k]["ciHi"]], "effortHours": [res[k]["effortA"], res[k]["effortB"]],
                     "proposedAction": ("attach this field comparison to the rule as river-surrogate evidence; keep confidence and the southeast-reservoir transferability flag unchanged"
                                        if res[k]["verdict"] == "SUPPORTED" else "restrict or retire the rule for river-type waters and record the conflict; do not publish it as a prediction")} for k in decisive]
        change = {"scientificChange": "Attach an independent field comparison (USGS LTRM electrofishing) to the species rules that could be tested, and restrict rules the data contradict.",
                  "previous": "No species rule has been compared with a field outcome (FISH-VAL-001).",
                  "proposed": {"fieldComparisons": proposed, "scope": "Upper Mississippi navigation pools (rivers), day/night electrofishing, mostly June-October; southeast reservoir transferability remains UNTESTED"},
                  "evidenceSummary": f"{len(rows)} electrofishing samples; {len(decisive)} of {len(res)} pre-declared rule tests decisive ({m['supported']} supported, {m['contradicted']} contradicted).",
                  "validationMethod": "matched-stratum catch-per-effort ratios, cluster bootstrap 95% CI, direction and thresholds declared before the data were examined",
                  "validationResults": {k: v for k, v in m.items() if k != "tests"},
                  "practicalEffect": "Night-activity and cold-water rules that now have a field comparison can be shown as experimental with their evidence; contradicted rules are withheld.",
                  "scoreImpact": "None under biological-state-score-v1 (it does not measure field validation); counted as validation coverage in the capability contract.",
                  "limitations": "River navigation pools, daytime-skewed sampling, June-October only; electrofishing catchability differs day vs night; not Tennessee-system reservoirs; cold tests need cold-water samples that are rare in this database."}
        cap = {"baselineKind": "none: no species rule had a field comparison", "kind": "coverage", "name": "species rules with an independent field test (validation coverage)", "direction": "higher_better", "baselineMetric": f"{g}.rulesFieldTestedBase",
               "candidateMetric": f"{g}.rulesFieldTestedCand", "minDelta": 1, "nMetric": f"{g}.testsRun", "minN": 1, "tests": [{"metric": f"{g}.decisiveRules", "op": ">=", "threshold": 1}]}
        findings.append(D.finding("FISH-FIELD-COVERAGE", f"{len(decisive)} Fish rules now have a decisive independent field comparison.", "RULE", paths, home, "pre-declared rule tests on LTRM",
                                  f"{g}.decisiveRules", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    if scan_cands:
        cchange = {"scientificChange": "Add field-derived candidate behaviour rules for species/conditions no written rule covered (night versus day and cold versus warm catchability).",
                   "previous": "These species/conditions had no rule or a rule without a field comparison.",
                   "proposed": {"candidateRules": scan_cands, "status": "CANDIDATE_NOT_APPROVED", "scope": "Upper Mississippi navigation pools (river surrogate); electrofishing catchability, not abundance"},
                   "evidenceSummary": f"{scan_n} untested species x condition pairs scanned on {len(rows)} samples; {len(scan_cands)} remain decisive after a Bonferroni-corrected interval.",
                   "validationMethod": "matched-stratum catch-per-effort ratios (pool x stratum x year), cluster bootstrap, Bonferroni over the whole scan",
                   "validationResults": {"scanTestsRun": scan_n, "scanCandidateRules": len(scan_cands)},
                   "practicalEffect": "Gives the Fish Brain evidence-backed candidate rules (for example which species are more catchable at night) to review, instead of leaving most species with no field-derived rule.",
                   "scoreImpact": "None under biological-state-score-v1; counted as validation coverage in the capability contract.",
                   "limitations": "Catchability, not abundance; day/night gear efficiency differs; river surrogate; candidate rules need review and Tennessee-system data before any publication."}
        scap = {"kind": "coverage", "baselineKind": "none: these species/conditions had no field-derived rule", "name": "species behaviours with a field-derived candidate rule", "direction": "higher_better",
                "baselineMetric": f"{g}.rulesFieldTestedBase", "candidateMetric": f"{g}.scanCandidateRules", "minDelta": 1, "nMetric": f"{g}.scanTestsRun", "minN": 1, "tests": [{"metric": f"{g}.scanCandidateRules", "op": ">=", "threshold": 1}]}
        findings.append(D.finding("FISH-SCAN-RULES", f"{len(scan_cands)} new field-derived candidate behaviour rules after multiple-comparison correction.", "RULE", paths, home, "pre-declared scan of every untested species x condition pair",
                                  f"{g}.scanCandidateRules", ">=", 1, tier="CANDIDATE_CHANGE", change=cchange, capability=scap))
    lim = [{"limitation": "field tests use Upper Mississippi river pools; Tennessee-system reservoir transferability is untested", "kind": "scope", "gap": "FISH-VAL-001"}]
    owner = [{"id": "fish-tennessee-field-data", "gap": "FISH-VAL-001", "publisher": "TVA reservoir fish programs and the Alabama / Tennessee fisheries agencies",
              "dataset": "day/night electrofishing or creel records with water temperature for Tennessee-system reservoirs (the LTRM comparison is a river surrogate)",
              "access": "request from the agency; public bulk availability NOT verified", "verified": False, "addresses": "transferability of the tested rules to the pilot reservoirs"}]
    return {"metrics": m, "findings": findings, "weak": [], "limitations": lim, "owner": owner}


# ------------------------------------------------------------------------------------------------------------------------------- Wind (night-calm climatology)
def acquire_iem_wind(ev, home, spec, it, targets, gaps):
    p = spec["params"]
    files = {}
    for st in p["stations"]:
        for yr in range(p["yearFrom"], p["yearTo"] + 1):
            files[f"{st}:{yr}"] = ev.fetch("iem-asos", f"{st}_{yr}.csv", "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
                                          {"station": st, "data": ["sknt", "gust"], "year1": yr, "month1": 1, "day1": 1, "year2": yr + 1, "month2": 1, "day2": 1, "tz": p["tz"], "format": "onlycomma",
                                           "latlon": "no", "missing": "M", "trace": "T", "direct": "no", "report_type": [3, 4]}, purpose=f"hourly wind, airport {st}, {yr}")
    return {"files": files}


def _nights(path, p):
    """{(date_of_evening): (max sustained kt, max gust kt, n obs)} for the bowfishing window (evening hour .. morning hour, local)."""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            v = r.get("valid") or ""
            if len(v) < 16:
                continue
            hr = int(v[11:13])
            if not (hr >= p["nightStartHour"] or hr < p["nightEndHour"]):
                continue
            d = dt.date.fromisoformat(v[:10])
            if hr < p["nightEndHour"]:
                d -= dt.timedelta(days=1)
            try:
                sk = float(r["sknt"])
            except (ValueError, KeyError):
                continue
            try:
                gu = float(r["gust"])
            except (ValueError, KeyError):
                gu = 0.0
            o = out.setdefault(d, [0.0, 0.0, 0])
            o[0], o[1], o[2] = max(o[0], sk), max(o[1], gu), o[2] + 1
    return out


def analyze_iem_wind(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Candidate knowledge: P(calm night) by month and station, from airport observations. A night is CALM when every hourly sustained wind in the window is
    <= calmKt and no gust exceeds calmGustKt. Test: monthly probabilities fitted on the training years predict the held-out years better than a single
    all-months probability (the naive baseline), at most stations, by the mean absolute error of the monthly probability."""
    p = spec["params"]
    g = f"discovery.exp.{spec['avenueId']}"
    files = {}
    for a in mine:
        files.update(a.get("files") or {})
    per, paths = {}, []
    for key, rel in sorted(files.items()):
        if not rel:
            continue
        st, yr = key.split(":")
        paths.append(rel)
        for d, (sk, gu, n) in _nights(os.path.join(home, rel), p).items():
            if n >= p["minObsPerNight"]:
                per.setdefault(st, []).append((d, sk <= p["calmKt"] and gu <= p["calmGustKt"]))
    stations, tabs = {}, {}
    for st, nights in sorted(per.items()):
        tr = [(d, c) for d, c in nights if d.year <= p["trainThroughYear"]]
        te = [(d, c) for d, c in nights if d.year > p["trainThroughYear"]]
        if len(tr) < 200 or len(te) < 100:
            continue
        overall = sum(c for _, c in tr) / len(tr)
        month = {}
        for d, c in tr:
            month.setdefault(d.month, []).append(c)
        mp = {mo: sum(v) / len(v) for mo, v in month.items() if len(v) >= p["minNightsPerMonth"]}
        tm = {}
        for d, c in te:
            tm.setdefault(d.month, []).append(c)
        errs_b, errs_c = [], []
        for mo, v in tm.items():
            if mo in mp and len(v) >= 5:
                o = sum(v) / len(v)
                errs_b.append(abs(o - overall))
                errs_c.append(abs(o - mp[mo]))
        if len(errs_c) < 6:
            continue
        stations[st] = {"nightsTrain": len(tr), "nightsTest": len(te), "maeBase": round(sum(errs_b) / len(errs_b), 4), "maeCand": round(sum(errs_c) / len(errs_c), 4), "overallCalmShare": round(overall, 4)}
        tabs[st] = {str(mo): round(v, 3) for mo, v in sorted(mp.items())}
    m = {"stations": len(stations), "perStation": stations, "monthlyCalmNightProbability": tabs}
    if stations:
        mb = sum(x["maeBase"] for x in stations.values()) / len(stations)
        mc = sum(x["maeCand"] for x in stations.values()) / len(stations)
        m.update({"pooledMaeBase": round(mb, 4), "pooledMaeCand": round(mc, 4), "pooledDeltaMae": round(mb - mc, 4),
                  "stationsImprovedShare": round(sum(x["maeCand"] < x["maeBase"] for x in stations.values()) / len(stations), 4)})
    tests = [{"metric": f"{g}.pooledDeltaMae", "op": ">=", "threshold": p["minDeltaMae"]}, {"metric": f"{g}.stationsImprovedShare", "op": ">=", "threshold": p["minStationShare"]},
             {"metric": f"{g}.stations", "op": ">=", "threshold": p["minStations"]}]
    findings = []
    if stations:
        change = {"scientificChange": "Publish a month-by-month probability that a night is calm enough to fish (climatology), per airport station near the reservoirs, as a planning prior.",
                  "previous": "The Wind Brain publishes observations and a forecast, with no seasonal prior for how often nights are calm at a lake.",
                  "proposed": {"definition": f"night window {p['nightStartHour']}:00-{p['nightEndHour']}:00 local; calm = every hourly sustained wind <= {p['calmKt']} kt and gust <= {p['calmGustKt']} kt",
                               "monthlyCalmNightProbability": tabs, "stations": sorted(stations)},
                  "evidenceSummary": f"{sum(x['nightsTrain'] + x['nightsTest'] for x in stations.values())} nights at {len(stations)} airport stations, {p['yearFrom']}-{p['yearTo']}.",
                  "validationMethod": f"monthly probabilities fitted on years <= {p['trainThroughYear']} predict held-out years better (mean absolute error of the monthly probability) than one all-months probability; pre-declared thresholds",
                  "validationResults": {k: m[k] for k in ("stations", "pooledMaeBase", "pooledMaeCand", "pooledDeltaMae", "stationsImprovedShare")},
                  "practicalEffect": "A bowfisher can see the typical odds of a calm night for the month at a nearby station before any forecast exists; it also tells which months are mostly windy.",
                  "scoreImpact": "None under wind-certification-rubric-v1 / capability v2 (they do not read a climatology); counted as measured prediction gain in the capability contract.",
                  "limitations": "Airport wind is an over-land proxy for shoreline wind; thresholds (calm = 8.7 kt sustained, 13 kt gust) are practical hypotheses, not validated against shot success; stations are representative, not every fleet lake."}
        cap = {"baselineKind": "NAIVE: one all-months calm-night probability (a weak baseline; no seasonal prior is deployed)", "kind": "prediction", "name": "mean absolute error of the predicted monthly calm-night probability (probability points)", "direction": "lower_better", "baselineMetric": f"{g}.pooledMaeBase",
               "candidateMetric": f"{g}.pooledMaeCand", "minDelta": p["minDeltaMae"], "nMetric": f"{g}.stations", "minN": p["minStations"], "tests": tests}
        findings.append(D.finding("WIND-CALM-NIGHT-CLIMATOLOGY", "Month-specific calm-night probabilities predict held-out years better than one all-months probability.", "PARAMETER", sorted(set(paths)), home,
                                  "airport hourly wind, nightly maxima, train/test by year", f"{g}.pooledDeltaMae", ">=", p["minDeltaMae"], tier="INDEPENDENTLY_VALIDATED", change=change, capability=cap))
    return {"metrics": m, "findings": findings, "weak": [] if stations else ["no-wind-data"], "limitations": [] if stations else [{"limitation": "IEM wind data not available", "kind": "external", "gap": "WIND-CNF-001",
            "nextSource": "retry mesonet.agron.iastate.edu in a later campaign"}]}


# ------------------------------------------------------------------------------------------------------------------------------- Depth (USACE eHydro)
EH = "https://services7.arcgis.com/n1YM8pTrFmm7L4hs/arcgis/rest/services/eHydro_Survey_Data/FeatureServer/0/query"


def acquire_ehydro(ev, home, spec, it, targets, gaps):
    p = spec["params"]
    lakes = D.fleet(home, p)
    h = p["halfDeg"]
    files = {}
    for l in lakes:
        env = f"{l['lon'] - h:.4f},{l['lat'] - h:.4f},{l['lon'] + h:.4f},{l['lat'] + h:.4f}"
        files[l["key"]] = ev.fetch("ehydro-footprints", f"{l['key']}.json", EH, {"where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                                   "outFields": "surveytype,surveydateend,usacedistrictcode,sourcedatalocation,channelareaidfk", "returnGeometry": "false", "resultRecordCount": 500, "f": "json"},
                                   purpose=f"USACE hydrographic survey footprints near {l['name']}")
    zips = {}
    for sub in p["datumSample"]:                                           # a few small survey packages per pilot reservoir: the vertical datum is stated in their metadata
        key = next((k for k in files if sub.lower() in k.lower() and files[k]), None)
        if not key:
            continue
        feats = json.load(open(os.path.join(home, files[key]), encoding="utf-8")).get("features") or []
        cands = sorted((f["attributes"] for f in feats if f["attributes"].get("sourcedatalocation") and f["attributes"].get("surveydateend")), key=lambda a: -a["surveydateend"])
        for a in cands[:p["maxZipsPerLake"] * 4]:
            url = a["sourcedatalocation"]
            n = ev.fetcher.head(url)
            if n is None or n > p["maxZipBytes"]:
                continue
            rel = ev.fetch("ehydro-surveys", f"{key}__{os.path.basename(url)}", url, None, purpose=f"survey package ({n} bytes) with vertical datum metadata near {key}")
            if rel:
                zips.setdefault(key, []).append({"path": rel, "survey": os.path.basename(url), "year": dt.datetime.fromtimestamp(a["surveydateend"] / 1000, dt.timezone.utc).year})
            if len(zips.get(key, [])) >= p["maxZipsPerLake"]:
                break
    return {"lakesQueried": len(lakes), "footprints": files, "zips": zips}


DATUM_RE = re.compile(r"(?i)(NAVD\s*-?\s*88|NGVD\s*-?\s*29|NAVD\s*1988|MLLW|mean lower low water|vertical\s+datum[^<\n]{0,60}|pool\s+(?:elevation|stage|datum)[^<\n]{0,40}|low\s+water\s+reference\s+plane|LWRP)")


def analyze_ehydro(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    import zipfile
    p = spec["params"]
    g = f"discovery.exp.{spec['avenueId']}"
    fp, zips = {}, {}
    for a in mine:
        fp.update(a.get("footprints") or {})
        zips.update(a.get("zips") or {})
    per, paths = {}, []
    for key, rel in sorted(fp.items()):
        if not rel:
            continue
        feats = json.load(open(os.path.join(home, rel), encoding="utf-8")).get("features") or []
        yrs = sorted(dt.datetime.fromtimestamp(f["attributes"]["surveydateend"] / 1000, dt.timezone.utc).year for f in feats if f["attributes"].get("surveydateend"))
        if feats:
            per[key] = {"surveys": len(feats), "latestYear": yrs[-1] if yrs else None, "since2015": sum(y >= 2015 for y in yrs), "districts": sorted({f["attributes"].get("usacedistrictcode") for f in feats if f["attributes"].get("usacedistrictcode")})}
            paths.append(rel)
    datum = {}
    for key, lst in sorted(zips.items()):
        for z in lst:
            toks = set()
            try:
                with zipfile.ZipFile(os.path.join(home, z["path"])) as zf:
                    for n in zf.namelist():
                        if n.lower().endswith((".xml", ".txt", ".htm", ".html")) and zf.getinfo(n).file_size < 2_000_000:
                            toks |= {m.group(0).strip()[:80] for m in DATUM_RE.finditer(zf.read(n).decode("utf-8", "replace"))}
            except (zipfile.BadZipFile, OSError):
                continue
            if toks:
                datum.setdefault(key, {"survey": z["survey"], "year": z["year"], "datumStatements": sorted(toks)[:6], "path": z["path"]})
                paths.append(z["path"])
    fleet_n = max(len(fp), 1)
    m = {"fleetLakes": len(fp), "lakesWithSurvey": len(per), "lakesWithSurveySince2015": sum(1 for v in per.values() if v["since2015"]), "lakesWithDocumentedDatum": len(datum),
         "lakesWithSurveyBase": 0, "lakesWithDocumentedDatumBase": 0, "perLake": per, "datum": datum}
    findings = []
    if per:
        change = {"scientificChange": "Add a source map of which fleet lakes have dated USACE hydrographic surveys and which have a vertical datum documented in a sampled survey package.",
                  "previous": "Depth has no per-lake survey source map; datum coverage is unknown for most of the fleet (DEPTH-DAT-001).",
                  "proposed": {"lakesWithSurvey": sorted(per), "lakesWithDocumentedDatum": sorted(datum), "note": "availability and datum documentation only; depth is not computed and the Depth runtime still abstains"},
                  "evidenceSummary": f"{len(per)} of {len(fp)} fleet lakes have survey footprints; {len(datum)} lake(s) have a datum statement read from a downloaded survey package.",
                  "validationMethod": "ArcGIS feature-service envelope queries per lake; metadata of sampled survey packages searched for vertical-datum statements (offline recompute)",
                  "validationResults": {k: m[k] for k in ("fleetLakes", "lakesWithSurvey", "lakesWithSurveySince2015", "lakesWithDocumentedDatum")},
                  "practicalEffect": "Shows where shallow-water depth could be derived at all, and which lakes still need an operator datum document, instead of leaving every lake equally unknown.",
                  "scoreImpact": "None: Depth is unscored; counted as datum/survey coverage in the capability contract.",
                  "limitations": "Footprints are survey extents (mostly navigation channels), not full-lake bathymetry; datum is read from a sample of packages; no depth value is produced; Depth still needs an approved release (G-1)."}
        cap = {"kind": "coverage", "baselineKind": "none: no per-lake survey or datum source map existed", "name": "fleet lakes with a dated USACE survey footprint (availability; datum documented for the sampled subset only)",
               "direction": "higher_better", "baselineMetric": f"{g}.lakesWithSurveyBase", "candidateMetric": f"{g}.lakesWithSurvey", "minDelta": 1, "nMetric": f"{g}.fleetLakes", "minN": 1,
               "tests": [{"metric": f"{g}.lakesWithSurvey", "op": ">=", "threshold": 1}]}
        findings.append(D.finding("DEPTH-SURVEY-MAP", f"{len(per)} fleet lakes have dated USACE survey footprints; {len(datum)} have a vertical datum documented in a sampled survey package.", "DATASET",
                                  sorted(set(paths))[:300], home, "eHydro envelope queries + datum statements in sampled packages", f"{g}.lakesWithSurvey", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    return {"metrics": m, "findings": findings, "weak": [], "limitations": [] if per else [{"limitation": "eHydro returned no survey footprints", "kind": "external", "gap": "DEPTH-DAT-001", "nextSource": "retry later; check the feature-service quota"}]}


# ------------------------------------------------------------------------------------------------------------------------------- Vegetation (USGS NAS observed records)
def acquire_nas(ev, home, spec, it, targets, gaps):
    p = spec["params"]
    states = sorted({l["state"] for l in D.fleet(home, p) if l["state"]})
    files = {}
    for st in states:
        for gen in p["genera"]:
            off, n = 0, 0
            while n < p["maxPages"]:
                rel = ev.fetch("nas-occurrences", f"{gen}_{st}_{off}.json", "https://nas.er.usgs.gov/api/v2/occurrence/search", {"genus": gen, "state": st, "limit": p["pageSize"], "offset": off},
                               purpose=f"observed {gen} records in {st} (presence only)")
                files[f"{gen}:{st}:{off}"] = rel
                if not rel:
                    break
                d = json.load(open(os.path.join(home, rel), encoding="utf-8"))
                if str(d.get("endOfRecords")).lower() == "true" or not d.get("results"):
                    break
                off += p["pageSize"]
                n += 1
    return {"files": files}


def analyze_nas(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    p = spec["params"]
    g = f"discovery.exp.{spec['avenueId']}"
    files = {}
    for a in mine:
        files.update(a.get("files") or {})
    lakes = D.fleet(home, p)
    hits, recs, paths = {}, 0, []
    for key, rel in sorted(files.items()):
        if not rel:
            continue
        paths.append(rel)
        for r in json.load(open(os.path.join(home, rel), encoding="utf-8")).get("results") or []:
            try:
                la, lo, yr = float(r["decimalLatitude"]), float(r["decimalLongitude"]), int(r["year"])
            except (KeyError, ValueError, TypeError):
                continue
            if r.get("status") not in ("established", "collected", "stocked", None, "") and p.get("establishedOnly"):
                continue
            recs += 1
            best = None
            for l in lakes:
                dd = max(abs(l["lat"] - la), abs(l["lon"] - lo))
                if dd <= p["matchDeg"] and (best is None or dd < best[0]):
                    best = (dd, l)
            if best:
                h = hits.setdefault(best[1]["key"], {"records": 0, "latestYear": 0, "taxa": set(), "since2010": 0})
                h["records"] += 1
                h["latestYear"] = max(h["latestYear"], yr)
                h["since2010"] += yr >= 2010
                h["taxa"].add(r.get("scientificName"))
    per = {k: {**v, "taxa": sorted(t for t in v["taxa"] if t)} for k, v in sorted(hits.items())}
    m = {"fleetLakes": len(lakes), "recordsRead": recs, "lakesWithObservedRecord": len(per), "lakesWithRecordSince2010": sum(1 for v in per.values() if v["since2010"]),
         "lakesWithObservedRecordBase": 0, "perLake": per}
    findings = []
    if per:
        change = {"scientificChange": "Add a per-lake source map of dated, georeferenced OBSERVED submerged-plant records (confirmed presence) for the fleet.",
                  "previous": "Vegetation has no observed-vegetation truth source for the fleet; the surface observer failed held-out gates (VEG-VAL-001).",
                  "proposed": {"lakesWithObservedRecord": sorted(per), "source": "USGS NAS occurrence database", "use": "dated presence truth for validating the observer; never absence, never abundance, never habitat potential"},
                  "evidenceSummary": f"{recs} georeferenced records read; {len(per)} of {len(lakes)} fleet lakes have at least one within {p['matchDeg']} degrees.",
                  "validationMethod": "state/genus API queries, coordinate matching to fleet lakes (offline recompute)",
                  "validationResults": {k: m[k] for k in ("fleetLakes", "recordsRead", "lakesWithObservedRecord", "lakesWithRecordSince2010")},
                  "practicalEffect": "Shows which lakes have any confirmed vegetation record to test the observer against, so vegetation intelligence is never validated on potential habitat.",
                  "scoreImpact": "None: Vegetation is unscored; counted as observed-data coverage in the capability contract.",
                  "limitations": "Invasive taxa only (hydrilla, milfoil, najas, curly-leaf pondweed, egeria), presence-only and effort-uneven; no absence or cover; Vegetation still needs an approved release (G-1)."}
        cap = {"kind": "coverage", "baselineKind": "none: no observed-vegetation truth source map existed", "name": "fleet lakes with a dated georeferenced OBSERVED submerged-plant record",
               "direction": "higher_better", "baselineMetric": f"{g}.lakesWithObservedRecordBase", "candidateMetric": f"{g}.lakesWithObservedRecord", "minDelta": 1, "nMetric": f"{g}.fleetLakes", "minN": 1,
               "tests": [{"metric": f"{g}.lakesWithObservedRecord", "op": ">=", "threshold": 1}]}
        findings.append(D.finding("VEG-OBSERVED-MAP", f"{len(per)} fleet lakes have dated observed submerged-plant records (confirmed presence).", "DATASET", sorted(set(paths))[:300], home,
                                  "USGS NAS occurrence queries matched to fleet lakes", f"{g}.lakesWithObservedRecord", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    return {"metrics": m, "findings": findings, "weak": [], "limitations": [] if per else [{"limitation": "NAS returned no matched records", "kind": "external", "gap": "VEG-VAL-001", "nextSource": "retry later"}]}


# ------------------------------------------------------------------------------------------------------------------------------- Fish spawn temperature (ichthyoplankton eggs)
def _wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    ph = k / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def analyze_eggs_temp(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Pre-declared test of a written spawn-temperature rule against dated ichthyoplankton tows (egg counts with water temperature).
    Lower bound: SUPPORTED when the egg-positive share below the rule's minimum has a Wilson 95% upper bound under `lowMax` AND the share inside the rule's range has a lower
    bound above `inMin`; CONTRADICTED when eggs are readily found below the minimum. Upper bound: judged separately against the in-range share. The data are Asian carp eggs
    (silver and bighead together), so the test is for the silver-carp rule and says so."""
    p = spec["params"]
    g = f"discovery.exp.{spec['avenueId']}"
    files = sorted(glob.glob(os.path.join(home, p["datasetGlob"])))
    if not files:
        return {"metrics": {"toWs": 0}, "findings": [], "weak": [], "limitations": [{"limitation": "ichthyoplankton dataset not acquired yet (an agent research task acquires it)", "kind": "external", "gap": "FISH-VAL-001",
                                                                                      "nextSource": "run the agent research queue (campaign.py loop) so the dataset is downloaded with provenance"}]}
    path = files[0]
    rel = os.path.relpath(path, home)
    t, e = [], []
    with open(path, encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                tc, eg = float(r[p["tempCol"]]), float(r[p["eggCol"]])
            except (KeyError, ValueError, TypeError):
                continue
            t.append(tc)
            e.append(eg > 0)
    lo, hi = p["ruleMinC"], p["ruleMaxC"]
    below = [x for tc, x in zip(t, e) if tc < lo]
    inr = [x for tc, x in zip(t, e) if lo <= tc <= hi]
    above = [x for tc, x in zip(t, e) if tc > hi]
    bl, bu = _wilson(sum(below), len(below))
    il, iu = _wilson(sum(inr), len(inr))
    al, au = _wilson(sum(above), len(above))
    first = min((tc for tc, x in zip(t, e) if x), default=None)
    m = {"tows": len(t), "eggPositive": sum(e), "firstEggC": first, "belowN": len(below), "belowPositive": sum(below), "belowUpper": round(bu, 4), "inRangeN": len(inr), "inRangePositive": sum(inr),
         "inRangeShare": round(sum(inr) / max(len(inr), 1), 4), "inRangeLower": round(il, 4), "aboveN": len(above), "abovePositive": sum(above), "aboveShare": round(sum(above) / max(len(above), 1), 4),
         "aboveUpper": round(au, 4), "aboveLower": round(al, 4), "lowerBoundSupported": int(bu < p["lowMax"] and il > p["inMin"]), "lowerBoundContradicted": int(bl >= p["lowMax"]),
         "upperBoundContradicted": int(al > sum(inr) / max(len(inr), 1)), "upperBoundSupported": int(len(above) >= 10 and au < sum(inr) / max(len(inr), 1)),
         "rulesFieldTestedBase": 0, "rulesFieldTestedCand": 0}
    if m["lowerBoundSupported"] or m["lowerBoundContradicted"]:
        m["rulesFieldTestedCand"] = 1
    findings = []
    if m["lowerBoundSupported"]:
        findings.append(D.finding(f"FISH-EGGS-{p['ruleId']}", f"Field egg data support the lower spawn-temperature bound of rule {p['ruleId']} ({lo} C): {sum(below)} egg-positive tows of {len(below)} below it "
                                  f"(Wilson 95% upper {round(bu, 3)}), first eggs at {first} C, {round(100 * m['inRangeShare'])}% positive inside {lo}-{hi} C. Asian carp eggs (silver and bighead together), "
                                  "Upper Mississippi, 2013-2014.", "EVIDENCE", [rel], home, "pre-declared Wilson-interval comparison of egg-positive tows below / inside / above the rule range",
                                  f"{g}.lowerBoundSupported", ">=", 1, tier="SCIENTIFIC_SUPPORT"))
        change = {"scientificChange": f"Attach an independent field egg-presence comparison to the spawn-temperature rule {p['ruleId']}.",
                  "previous": f"{p['ruleId']} (spawn range {lo}-{hi} C) rests on compiled sources only.",
                  "proposed": {"ruleId": p["ruleId"], "evidence": {"dataset": "USGS ichthyoplankton tows (Asian carp eggs), doi 10.5066/F75T3J06", "tows": m["tows"], "eggPositive": m["eggPositive"], "firstEggC": first,
                               "belowMinPositive": f"{sum(below)}/{len(below)}", "inRangeShare": m["inRangeShare"], "aboveMaxShare": m["aboveShare"], "aboveMaxN": len(above)},
                               "proposedAction": "attach as river-surrogate evidence; keep confidence and the southeast-reservoir transferability flag unchanged; review the upper bound separately"},
                  "evidenceSummary": f"{m['tows']} dated tows, {m['eggPositive']} egg-positive; none of {len(below)} below {lo} C.",
                  "validationMethod": "Wilson 95% intervals for egg-positive share below / inside / above the rule range, thresholds declared before the data were examined",
                  "validationResults": {k: m[k] for k in ("belowN", "belowPositive", "belowUpper", "inRangeN", "inRangePositive", "inRangeShare", "inRangeLower", "aboveN", "aboveShare", "firstEggC")},
                  "practicalEffect": "The silver-carp spawn window can be shown as field-compared: eggs were not found below 18 C, so a temperature below that means the window is closed.",
                  "scoreImpact": "None under biological-state-score-v1; counted as validation coverage in the capability contract.",
                  "limitations": "Asian carp eggs are silver and bighead together; two seasons on the Upper Mississippi; plankton tows show spawning occurred, not where bowfishers can find fish."}
        cap = {"kind": "coverage", "baselineKind": "none: the rule had no field comparison", "name": "spawn-temperature rules with an independent field egg-presence test", "direction": "higher_better",
               "baselineMetric": f"{g}.rulesFieldTestedBase", "candidateMetric": f"{g}.rulesFieldTestedCand", "minDelta": 1, "nMetric": f"{g}.tows", "minN": 100, "tests": [{"metric": f"{g}.lowerBoundSupported", "op": ">=", "threshold": 1}]}
        findings.append(D.finding("FISH-EGGS-COVERAGE", f"Spawn rule {p['ruleId']} now has an independent field egg-presence comparison (lower bound supported).", "RULE", [rel], home, "pre-declared egg-presence test",
                                  f"{g}.rulesFieldTestedCand", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    return {"metrics": m, "findings": findings, "weak": [], "limitations": [{"limitation": "the egg data are Asian carp (silver and bighead together) from the Upper Mississippi; other species' spawn-temperature rules remain without field data", "kind": "scope", "gap": "FISH-VAL-001"}]}


def acquire_none(ev, home, spec, it, targets, gaps):
    return {}


def analyze_wt_bias(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Hypothesis: production M0 has a systematic, correctable bias that depends on `rung` (season / region x season / class x season).
    Build: median residual per cell from fleet grab samples up to `trainThroughYear`. Test (neither used to build it):
      T1 temporal holdout: fleet grab samples after trainThroughYear
      T2 leave-lake-out: independent USGS continuous sensors, offsets fitted WITHOUT that lake
    Pre-declared pass rule (discovery.json): T1 RMSE gain >= holdoutMinDelta, T2 pooled gain >= sensorMinDelta, no more than maxWorseShare of
    the sensor lakes worse by > worseTol, bias not larger. Otherwise the hypothesis is rejected and preserved with its numbers."""
    rung = spec["rung"]
    keyf = RUNGS[rung]
    rows = _resid(home, spec["storedResiduals"])
    train = [r for r in rows if r["year"] <= spec["trainThroughYear"]]
    test = [r for r in rows if r["year"] > spec["trainThroughYear"]]
    off = _fit(train, keyf, spec["minCell"], spec["shrink"])
    base = [r["e"] for r in test]
    cand = [r["e"] - off.get(keyf(r), 0.0) for r in test]
    m = {"rung": rung, "cells": len(off), "holdoutN": len(test), "holdoutRmseBase": round(rmse(base), 4), "holdoutRmseCand": round(rmse(cand), 4),
         "holdoutDeltaRmse": round(rmse(base) - rmse(cand), 4), "holdoutBiasBase": round(S.mean(base), 4), "holdoutBiasCand": round(S.mean(cand), 4),
         "holdoutBiasReduction": round(abs(S.mean(base)) - abs(S.mean(cand)), 4)}
    sensors = _sensor_errors(home, spec, allacq)
    meta, state_region = {}, {}
    for r in rows:
        meta.setdefault(r["stem"], (r["region"], r["cls"]))
        if r["state"]:
            state_region.setdefault(r["state"], r["region"])
    lakes, used_paths = {}, set([spec["storedResiduals"]])
    for key, se in sorted(sensors.items()):
        stem = D.safe_key(key)
        # a sensor lake outside the fleet residual table was never in the fit (more independent, not less): its region comes from its state; its class is unknown
        reg, cls = meta[stem] if stem in meta else (state_region.get(key.rsplit("_", 1)[-1]), None)
        if (rung == "region_season" and not reg) or (rung == "class_season" and not cls):
            continue                                             # the correction cannot be applied to this lake: not counted either way
        loo = _fit([r for r in rows if r["stem"] != stem], keyf, spec["minCell"], spec["shrink"])
        b, c = [], []
        for d, e in se["errs"]:
            k = keyf({"season": season_of(int(d[5:7])), "region": reg, "cls": cls})
            b.append(e)
            c.append(e - loo.get(k, 0.0))
        lakes[key] = {"n": len(b), "rmseBase": round(rmse(b), 4), "rmseCand": round(rmse(c), 4), "biasBase": round(S.mean(b), 4), "biasCand": round(S.mean(c), 4)}
        used_paths |= set(se["paths"])
    m["sensorLakes"] = len(lakes)
    if lakes:
        pb = math.sqrt(sum(v["rmseBase"] ** 2 for v in lakes.values()) / len(lakes))
        pc = math.sqrt(sum(v["rmseCand"] ** 2 for v in lakes.values()) / len(lakes))
        m.update({"sensorRmseBase": round(pb, 4), "sensorRmseCand": round(pc, 4), "sensorDeltaRmse": round(pb - pc, 4),
                  "lakesWorseShare": round(sum(v["rmseCand"] > v["rmseBase"] + spec["worseTol"] for v in lakes.values()) / len(lakes), 4), "lakes": lakes})
    offs = {k: round(v, 3) for k, v in sorted(off.items())}
    m["offsets"] = offs
    se_cells = {k: v for k, v in offs.items() if k.startswith("Southeast|")}
    m["southeastSeasonOffsetsC"] = se_cells or ({k: v for k, v in offs.items() if "|" not in k} if rung == "season" else {})
    ident = spec["avenueId"]
    g = f"discovery.exp.{ident}"
    tests = [{"metric": f"{g}.holdoutDeltaRmse", "op": ">=", "threshold": spec["holdoutMinDelta"]},
             {"metric": f"{g}.sensorDeltaRmse", "op": ">=", "threshold": spec["sensorMinDelta"]},
             {"metric": f"{g}.lakesWorseShare", "op": "<=", "threshold": spec["maxWorseShare"]},
             {"metric": f"{g}.sensorLakes", "op": ">=", "threshold": spec["minSensorLakes"]},
             {"metric": f"{g}.holdoutBiasReduction", "op": ">=", "threshold": 0.0}]
    change = {"scientificChange": f"Add a {rung.replace('_', ' x ')} additive correction to the fallback/forecast water-temperature model (production M0).",
              "previous": "M0 uses no bias correction (WaterTemperatureService.swift, k=0.09 relaxation toward an energy-balance equilibrium).",
              "proposed": {"correction": "M0' = M0 - offset[cell]", "cell": rung, "offsetsC": offs, "fit": f"median fleet residual per cell, years <= {spec['trainThroughYear']}, shrink {spec['shrink']}, min {spec['minCell']} samples"},
              "evidenceSummary": f"{len(train)} fleet grab-sample residuals for fitting; {len(test)} later ones held out; {len(lakes)} USGS continuous-sensor lakes excluded from the fit one at a time.",
              "validationMethod": "T1 temporal holdout on fleet grab samples; T2 leave-lake-out on independent USGS continuous sensors. Thresholds pre-declared in discovery.json.",
              "validationResults": {k: m.get(k) for k in ("holdoutRmseBase", "holdoutRmseCand", "holdoutDeltaRmse", "sensorRmseBase", "sensorRmseCand", "sensorDeltaRmse", "lakesWorseShare")},
              "practicalEffect": "Spring (MAM) water temperatures run cold and autumn (SON) warm in the production model; the correction moves predicted temperatures toward observed ones, which shifts every temperature-gated species rule (spawn windows, cold-water inactivity) by the same amount.",
              "scoreImpact": "None under water-temp-level-ladder-v1: the frozen score is gate-based (Level-4 protected truth) and is not moved by a lower RMSE. Reported as a measured capability gain only.",
              "limitations": "Offsets are fleet-level medians; grab samples are daytime single-depth values compared with a daily-mean model; deployment needs a Swift change and approval; the protected Stage 3C.3 lakes (incl. Guntersville) were not used."}
    cap = {"baselineKind": "production M0 without correction", "kind": "prediction", "name": "production M0 water-temperature RMSE (C)", "direction": "lower_better", "baselineMetric": f"{g}.sensorRmseBase",
           "candidateMetric": f"{g}.sensorRmseCand", "minDelta": spec["sensorMinDelta"], "nMetric": f"{g}.sensorLakes", "minN": spec["minSensorLakes"], "tests": tests}
    f = D.finding(f"WT-BIAS-{rung}", f"A {rung.replace('_', ' x ')} correction reduces production M0 error on data not used to build it.", "PARAMETER", sorted(used_paths), home,
                  "offline refit + temporal holdout + leave-lake-out sensor test", f"{g}.holdoutDeltaRmse", ">=", spec["holdoutMinDelta"],
                  tier="INDEPENDENTLY_VALIDATED", change=change, capability=cap)
    return {"metrics": m, "findings": [f], "weak": [], "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- Fish
def analyze_fish_rules(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Grade the support behind every species rule the Fish Brain would show at the pilot lake. No species is VALIDATED (FISH-VAL-001: no rule
    has been compared with a field outcome); the grade separates what may be shown as EXPERIMENTAL from what must ABSTAIN."""
    base = os.path.join(home, spec["bundle"])
    lake = json.load(open(os.path.join(base, "lakes", spec["lake"] + ".json"), encoding="utf-8"))
    pres = {s["speciesId"]: s.get("presenceState") for s in lake.get("species") or []}
    paths = [os.path.join(spec["bundle"], "lakes", spec["lake"] + ".json")]
    per, abstain, experimental = {}, [], []
    for sid in sorted(pres):
        p = os.path.join(base, "rules", sid + ".json")
        if not os.path.exists(p):
            per[sid] = {"presence": pres[sid], "rules": 0, "directRead": 0, "pilotClass": "ABSTAIN", "why": "no rules in the bundle"}
            abstain.append(sid)
            continue
        paths.append(os.path.join(spec["bundle"], "rules", sid + ".json"))
        rules = json.load(open(p, encoding="utf-8"))["rules"]
        direct = sum(1 for r in rules for e in r.get("evidence") or [] if e.get("counts") and e.get("directness") == "DIRECT" and e.get("readStatus") == "READ-FULL")
        better = sum(1 for r in rules if r.get("confidence") in ("MEDIUM", "HIGH") and r.get("status") == "RECONCILED")
        se = sorted({(r.get("transferability") or {}).get("southeastReservoir", "UNKNOWN") for r in rules})
        present = pres[sid] in ("established", "reported")
        cls = "EXPERIMENTAL_INTERNAL" if (present and direct >= spec["minDirectEvidence"] and better >= 1) else "ABSTAIN"
        why = [] if cls != "ABSTAIN" else (["presence not established or reported at the pilot lake"] if not present else []) + \
            ([f"fewer than {spec['minDirectEvidence']} direct, fully read evidence items"] if direct < spec["minDirectEvidence"] else []) + \
            (["no reconciled MEDIUM/HIGH-confidence rule"] if better < 1 else [])
        per[sid] = {"presence": pres[sid], "rules": len(rules), "directRead": direct, "reconciledMedHigh": better, "southeastReservoirTransfer": se, "pilotClass": cls, "why": why}
        (experimental if cls != "ABSTAIN" else abstain).append(sid)
    m = {"speciesAtPilot": len(per), "experimentalInternal": len(experimental), "abstain": len(abstain), "validatedForField": 0, "perSpecies": per}
    g = f"discovery.exp.{spec['avenueId']}"
    change = {"scientificChange": "Replace 'every species rule is shown' with an evidence-graded refusal boundary for the pilot lake.",
              "previous": "All bundle rules for species recorded at the lake are eligible for display; per-rule confidence labels only.",
              "proposed": {"experimentalInternal": experimental, "abstain": abstain, "criteria": {k: spec[k] for k in ("minDirectEvidence",)},
                           "validatedForField": []},
              "evidenceSummary": f"{sum(v['rules'] for v in per.values())} rules across {len(per)} species graded from their recorded evidence entries.",
              "validationMethod": "deterministic grading of the rule metadata (evidence directness, read status, confidence, status, transferability); reproducible offline",
              "validationResults": {k: m[k] for k in ("speciesAtPilot", "experimentalInternal", "abstain", "validatedForField")},
              "practicalEffect": "A bowfisher is never shown a response band or spawn window for a species whose rules rest on indirect, unread or non-reconciled evidence; the app says 'not enough evidence' instead.",
              "scoreImpact": "None: the Biological-state score is not a field-validation measure; FISH-VAL-001 stays open.",
              "limitations": "This grades the strength of the written evidence, not field accuracy. It validates nothing against catch or observation outcomes."}
    m["unsupportedDisplayedBase"] = len(abstain)                      # species rules that would be shown today without direct evidence (everything is shown)
    m["unsupportedDisplayedCand"] = 0                                 # with the boundary they are replaced by 'not enough evidence'
    m["gradedConsistent"] = int(len(experimental) + len(abstain) == len(per))
    cap = {"baselineKind": "current behaviour: every species rule is shown", "kind": "refusal", "name": "species rules shown without direct, fully read evidence (refusal boundary; NOT predictive accuracy)", "direction": "lower_better",
           "baselineMetric": f"{g}.unsupportedDisplayedBase", "candidateMetric": f"{g}.unsupportedDisplayedCand", "minDelta": 1, "nMetric": f"{g}.speciesAtPilot", "minN": 1,
           "tests": [{"metric": f"{g}.gradedConsistent", "op": "==", "threshold": 1}]}
    f = D.finding("FISH-RULE-GRADE", "Species rules at the pilot lake can be graded by evidence strength into experimental vs abstain.", "RULE", paths, home,
                  "evidence-strength grading of rule metadata", f"{g}.speciesAtPilot", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap)
    owner = [{"id": "fish-field-outcomes", "gap": "FISH-VAL-001", "publisher": "state fisheries agency (e.g. Alabama Division of Wildlife and Freshwater Fisheries) and TVA reservoir fish programs; "
              "bowfishing tournament organisers",
              "dataset": "dated catch/observation records with species, water temperature and location (creel surveys, electrofishing with spawning condition, tournament weigh-in logs)",
              "access": "request from the agency or organiser; owner action (no public bulk download verified)", "verified": False,
              "addresses": "FISH-VAL-001 (no species rule compared with a field outcome) - the only way to move any species from EXPERIMENTAL to field-validated"}]
    return {"metrics": m, "findings": [f], "weak": [], "limitations": [{"limitation": "no field outcomes: no species is validated for field use", "kind": "external", "gap": "FISH-VAL-001"}], "owner": owner}


# ------------------------------------------------------------------------------------------------------------------------------- dataset search
def _search_urls(q: str, n: int):
    return [("dryad", "https://datadryad.org/api/v2/search", {"q": q, "per_page": n}),
            ("zenodo", "https://zenodo.org/api/records", {"q": q, "size": n, "type": "dataset"}),
            ("sciencebase", "https://www.sciencebase.gov/catalog/items", {"q": q, "format": "json", "max": n, "fields": "title,summary,webLinks,files,link"})]


def acquire_dataset_search(ev, home, spec, it, targets, gaps):
    got = {}
    for q in spec["params"]["queries"]:
        for src, base, params in _search_urls(q, spec["params"].get("perSource", 8)):
            got[f"{src}:{q}"] = ev.fetch("dataset-search", f"{src}_{D.safe_key(q)[:40]}.json", base, params, purpose=f"dataset leads for: {q}")
    return {"queries": spec["params"]["queries"], "files": got}


def _lead_rows(path: str, src: str) -> list[dict]:
    d = json.load(open(path, encoding="utf-8"))
    out = []
    if src == "zenodo":
        for h in (d.get("hits") or {}).get("hits") or []:
            md = h.get("metadata") or {}
            out.append({"title": md.get("title"), "url": h.get("doi_url") or (h.get("links") or {}).get("self_html"), "license": (md.get("license") or {}).get("id"),
                        "files": [{"name": f.get("key"), "bytes": f.get("size")} for f in h.get("files") or []][:10], "text": md.get("description", "")[:600]})
    elif src == "dryad":
        for h in (d.get("_embedded") or {}).get("stash:datasets") or []:
            out.append({"title": h.get("title"), "url": h.get("sharingLink") or h.get("identifier"), "license": "CC0 (Dryad)", "files": [], "text": (h.get("abstract") or "")[:600]})
    else:
        for h in d.get("items") or []:
            out.append({"title": h.get("title"), "url": (h.get("link") or {}).get("url"), "license": "US Government public domain", "files": [{"name": f.get("name"), "bytes": f.get("size")} for f in h.get("files") or []][:10],
                        "text": (h.get("summary") or "")[:600]})
    return out


def analyze_dataset_search(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    terms = [t.lower() for t in spec["params"]["relevance"]]
    leads, paths = {}, []
    for a in mine:
        for k, rel in (a.get("files") or {}).items():
            if not rel:
                continue
            src = k.split(":")[0]
            paths.append(rel)
            for r in _lead_rows(os.path.join(home, rel), src):
                text = f"{r['title']} {r['text']}".lower()
                score = sum(t in text for t in terms)
                if r["url"] and score >= spec["params"]["minTerms"]:
                    leads[r["url"]] = {**r, "source": src, "relevance": score}
    ranked = sorted(leads.values(), key=lambda x: (-x["relevance"], x["url"]))[:15]
    m = {"leads": len(ranked), "top": [{k: x[k] for k in ("title", "url", "source", "license", "relevance")} for x in ranked[:10]]}
    g = f"discovery.exp.{spec['avenueId']}"
    f = D.finding(f"{spec['avenueId'].upper()}-LEADS", f"{len(ranked)} public datasets match the gap terms; each needs a reviewed adapter or agent analysis before it can support any rule.", "DATASET",
                  sorted(set(paths)), home, "repository search (Dryad, Zenodo, ScienceBase) + term relevance screen", f"{g}.leads", ">=", spec["params"].get("minLeads", 1), tier="EVIDENCE_LEAD") if paths else None
    return {"metrics": m, "findings": [f] if f else [], "weak": [] if ranked else ["no-dataset-leads"], "limitations": [],
            "agentTasks": [{"task": f"read and, if usable, analyse: {x['title']} ({x['url']})", "licence": x["license"]} for x in ranked[:5]]}


# ------------------------------------------------------------------------------------------------------------------------------- Lake (CWMS)
CWMS = "https://cwms-data.usace.army.mil/cwms-data/"
ACC = "application/json;version=2"


def _like(name: str) -> str:
    toks = [t for t in re.split(r"[^A-Za-z]+", name) if len(t) >= 4 and t.lower() not in D.STOP]
    return ".*" + ".*".join(t.title() for t in toks) + ".*Elev.*Inst.*" if toks else ""


def is_pool_elevation(name: str) -> bool:
    """Only a measured pool/headwater elevation: parameter exactly 'Elev'. 'Elev-Zone' (regulation-schedule lines, e.g. '2026 Propose'),
    'Elev-Tail', 'Elev-Downstream' and the like are different quantities and must never be counted as an independent level reading."""
    parts = name.split(".")
    return len(parts) > 3 and parts[1] == "Elev" and parts[2] == "Inst" and not re.search(r"propos|zone|rule.?curve|schedule|tail|downstream|forebay", name, re.I)


def acquire_lake_cwms(ev, home, spec, it, targets, gaps):
    cfg = spec["params"]
    lakes = [l for l in D.fleet(home, cfg) if targets is None or l["key"] in set(targets)]
    matched, rejected = {}, {}
    end = cfg["endDate"]
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=cfg["windowDays"] - 1)).isoformat()
    for l in lakes:
        like = _like(l["name"])
        if not like:
            continue
        rel = ev.fetch("cwms-catalog", f"{l['key']}.json", CWMS + "catalog/TIMESERIES", {"like": like, "page-size": 40}, purpose=f"USACE CWMS pool-elevation series for {l['name']}", accept=ACC)
        if not rel:
            continue
        ents = [e for e in json.load(open(os.path.join(home, rel), encoding="utf-8")).get("entries") or [] if is_pool_elevation(e["name"])]
        ents.sort(key=lambda e: (0 if re.search(r"rev|best", e["name"], re.I) else 1, e["name"]))
        for e in ents[:3]:
            loc = e["name"].split(".")[0]
            lrel = ev.fetch("cwms-location", f"{l['key']}__{D.safe_key(loc)}.json", CWMS + "locations/" + urllib.parse.quote(loc, safe=""), {"office": e["office"]}, purpose=f"coordinates of CWMS location {loc} (identity check)", accept=ACC)
            ll = json.load(open(os.path.join(home, lrel), encoding="utf-8")) if lrel else {}
            lat, lon = ll.get("latitude"), ll.get("longitude")
            if not isinstance(lat, (int, float)) or abs(lat - l["lat"]) > cfg["radiusDeg"] or abs(lon - l["lon"]) > cfg["radiusDeg"]:
                rejected[l["key"]] = f"{loc}: not within {cfg['radiusDeg']} deg of the lake (a different water body with a similar name)"
                continue
            trel = ev.fetch("cwms-series", f"{l['key']}__{D.safe_key(e['name'])[:80]}.json", CWMS + "timeseries",
                            {"name": e["name"], "office": e["office"], "begin": start + "T00:00:00Z", "end": end + "T23:59:59Z", "unit": "ft"}, purpose=f"{cfg['windowDays']}-day pool elevation, CWMS {e['name']}", accept=ACC)
            if trel:
                matched[l["key"]] = {"lake": l["name"], "office": e["office"], "series": e["name"], "path": trel, "start": start, "end": end}
                rejected.pop(l["key"], None)
                break
    return {"lakesSearched": len(lakes), "lakesMatched": len(matched), "matched": matched, "rejected": rejected}


def analyze_lake_cwms(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    cfg = spec["params"]
    per, rej = {}, {}
    for a in mine:
        per.update(a.get("matched") or {})
        rej.update(a.get("rejected") or {})
    lakes, findings = {}, []
    for k in sorted(per):
        m = per[k]
        d = json.load(open(os.path.join(home, m["path"]), encoding="utf-8"))
        vals = d.get("values") or []
        days = {dt.datetime.fromtimestamp(v[0] / 1000, dt.timezone.utc).date().isoformat() for v in vals if v and v[1] is not None}
        end = dt.date.fromisoformat(m["end"])
        cov = round(len({(end - dt.timedelta(days=i)).isoformat() for i in range(30)} & days) / 30, 4)
        nums = [v[1] for v in vals if v and v[1] is not None]
        # a real pool level moves: a flat or step series is a rule curve / constant, not an observation
        varies = len({round(x, 2) for x in nums}) >= 5 and (max(nums) - min(nums)) > 0.05 if nums else False
        sane = bool(nums) and all(0 < x < 15000 for x in nums) and varies
        lakes[k] = {"series": m["series"], "office": m["office"], "points": len(vals), "coverage30": cov, "sane": int(sane)}
    base = cfg["baselineFreshLakes"]
    fresh = sum(1 for v in lakes.values() if v["coverage30"] >= cfg["coverage30"] and v["sane"])
    metrics = {"lakes": lakes, "newFreshLakes": fresh, "freshLakesBase": base, "freshLakesCand": base + fresh, "rejectedIdentity": len(rej)}
    g = f"discovery.exp.{spec['avenueId']}"
    if fresh:
        change = {"scientificChange": "Bind additional fleet lakes to an independent USACE CWMS pool-elevation series as a verified alternate level source.",
                  "previous": f"{base} fleet lakes have a fresh independent (USGS) daily level series; the rest depend on a single primary feed.",
                  "proposed": {"bindings": {k: {"office": v["office"], "series": v["series"]} for k, v in lakes.items() if v["coverage30"] >= cfg["coverage30"] and v["sane"]}},
                  "evidenceSummary": f"{len(lakes)} CWMS series downloaded; identity verified by location coordinates; {fresh} have >= {cfg['coverage30']:.0%} of the last 30 days and plausible elevations.",
                  "validationMethod": "name search in the CWMS catalog, coordinate check against the lake, 30-day coverage and plausibility check (offline recompute)",
                  "validationResults": {"newFreshLakes": fresh, "rejectedIdentity": len(rej)},
                  "practicalEffect": "More lakes keep a fresh, independent level reading when the primary source fails, so fewer lake states go stale or ABSTAIN.",
                  "scoreImpact": "None in lake-brain-score-v1 (no coverage-of-fresh-sources dimension; the score is capped at 3.0 by profiled share). Measured as a coverage gain only.",
                  "limitations": "Coverage, not accuracy: no cross-check against a second source for these lakes; binding needs Lake Brain review and approval."}
        cap = {"baselineKind": "the USGS-matched fresh level sources found by the same campaign", "kind": "coverage", "name": "fleet lakes with a fresh independent level series", "direction": "higher_better", "baselineMetric": f"{g}.freshLakesBase",
               "candidateMetric": f"{g}.freshLakesCand", "minDelta": 1, "nMetric": f"{g}.newFreshLakes", "minN": 1,
               "tests": [{"metric": f"{g}.newFreshLakes", "op": ">=", "threshold": 1}]}
        paths = sorted({m["path"] for m in per.values()})
        findings.append(D.finding("LAKE-CWMS-COVERAGE", f"{fresh} more fleet lakes have a verified fresh independent CWMS level series.", "EVIDENCE", paths, home,
                                  "CWMS catalog + location identity + 30-day coverage", f"{g}.newFreshLakes", ">=", 1, tier="CANDIDATE_CHANGE", change=change, capability=cap))
    weak = []
    owner = []
    for k, why in rej.items():
        owner.append({"id": f"lake-level-{k}", "gap": "LAKE-GEN-COVERAGE", "publisher": "operating agency for " + k.replace("_", " "),
                      "dataset": "daily pool/lake elevation", "access": f"CWMS search found only a different water body ({why}); identify the operator and its public data service",
                      "verified": False, "addresses": "lake-level coverage for a fleet lake with no independent fresh level source"})
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": [], "owner": owner}


# ------------------------------------------------------------------------------------------------------------------------------- cross-Brain
def analyze_xb_wt_fish(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Producer: Water Temp candidate bias correction. Consumer: Fish temperature-gated spawn-window rules. Effect on a practical prediction at
    the pilot lake: how many days earlier/later each species' spawn temperature threshold is crossed in spring once the correction is applied.
    This is an integration PROPOSAL: it measures the effect size, it does not validate either Brain nor publish anything."""
    wt = (upstream or {}).get("water-temp") or {}
    ch = os.path.join(home, wt.get("path", "-"), "candidate-changes.json")
    if not wt.get("packaged") or not os.path.exists(ch):
        return {"metrics": {"producerCandidate": 0}, "findings": [], "weak": [], "limitations": [{"limitation": "no validated Water Temp candidate change this campaign: nothing to propagate", "kind": "dependency"}]}
    changes = json.load(open(ch, encoding="utf-8"))["changes"]
    best = [c for c in changes if c["measured"]["improved"]]
    if not best:
        return {"metrics": {"producerCandidate": 0}, "findings": [], "weak": [], "limitations": [{"limitation": "Water Temp produced no measured improvement", "kind": "dependency"}]}
    c = best[0]
    offs = c["proposed"]["offsetsC"]
    rung = c["proposed"]["cell"]
    forc = D.m0_daily(json.load(open(os.path.join(home, spec["pilotForcing"]), encoding="utf-8"))["daily"])
    year = spec["year"]
    rules = []
    for p in sorted(glob.glob(os.path.join(home, spec["bundle"], "rules", "*.json"))):
        if p.endswith("manifest.json"):
            continue
        for r in json.load(open(p, encoding="utf-8"))["rules"]:
            t = (r.get("phenology") or {}).get("tempC")
            if r.get("kind") == "PHENOLOGY" and t and (r.get("phenology") or {}).get("event") == "spawn":
                rules.append((r["speciesId"], r["ruleId"], t["min"]))
    days = sorted(d for d in forc if d.startswith(str(year)))
    series = {d: D.m0_for_date(forc, d) for d in days}

    def key(d):
        s = season_of(int(d[5:7]))
        return {"season": s, "region_season": f"{spec['region']}|{s}"}.get(rung)
    base_t = {d: v for d, v in series.items() if v is not None}
    cand_t = {d: v - offs.get(key(d), 0.0) for d, v in base_t.items() if key(d)}
    if not cand_t:
        return {"metrics": {"producerCandidate": 1, "applicable": 0}, "findings": [], "weak": [], "limitations": [{"limitation": f"correction rung {rung} cannot be applied to the pilot lake (class unknown)", "kind": "dependency"}]}

    def first_cross(ts, thr):
        for d in sorted(ts):
            if ts[d] >= thr and int(d[5:7]) >= 2:
                return d
        return None
    shifts = {}
    for sid, rid, thr in rules:
        a, b = first_cross(base_t, thr), first_cross(cand_t, thr)
        if a and b:
            shifts[f"{sid}:{rid}"] = (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
    vals = sorted(shifts.values())
    m = {"producerCandidate": 1, "producerRung": rung, "year": year, "rulesTested": len(shifts), "medianShiftDays": vals[len(vals) // 2] if vals else None,
         "maxAbsShiftDays": max((abs(v) for v in vals), default=None), "shifts": shifts}
    report = {"producer": "water-temp (candidate bias correction " + rung + ")", "consumer": "biological-state (temperature-gated spawn-window rules)",
              "contractCompatibility": "water-temp-state-v1 currentTempF/kind + fish rule applicability tempC: compatible (both degrees; Fish converts F to C); the correction would be applied inside Water Temp before publication, so no contract change is needed",
              "validationRequired": "Water Temp correction independently validated (done above) AND at least one species spawn window compared with field outcomes (FISH-VAL-001, not done)",
              "expectedBenefit": f"Spring spawn-threshold crossing dates move by a median {m['medianShiftDays']} days (max {m['maxAbsShiftDays']}) across {len(shifts)} spawn rules at the pilot lake",
              "status": "PROPOSAL (not published, not validated end to end)"}
    m["integrationProposal"] = report
    g = f"discovery.exp.{spec['avenueId']}"
    f = D.finding("XB-WT-FISH", "The Water Temp candidate correction changes Fish spawn-threshold timing at the pilot lake by a measurable number of days.", "EVIDENCE",
                  [spec["pilotForcing"]], home, "effect-size computation on the pilot lake's forcing: production M0 vs corrected M0 against species spawn thresholds",
                  f"{g}.rulesTested", ">=", 1, tier="SCIENTIFIC_SUPPORT")
    return {"metrics": m, "findings": [f], "weak": [], "limitations": [], "integration": report}


def analyze_owner_actions(home: str, spec: dict, mine: list, allacq: list, upstream=None) -> dict:
    """Evidence the system cannot fetch itself: recorded as actionable owner records (publisher, access, what it would address)."""
    acts = spec["params"]["actions"]
    return {"metrics": {"ownerActions": len(acts)}, "findings": [], "weak": [], "limitations": [], "owner": acts}


EXPERIMENTS = {
    "owner-actions": {"acquire": acquire_none, "analyze": analyze_owner_actions},
    "wt-bias": {"acquire": acquire_none, "analyze": analyze_wt_bias},
    "wt-interval": {"acquire": acquire_none, "analyze": analyze_wt_interval},
    "ltrm-fish": {"acquire": acquire_ltrm, "analyze": analyze_ltrm},
    "iem-wind": {"acquire": acquire_iem_wind, "analyze": analyze_iem_wind},
    "ehydro": {"acquire": acquire_ehydro, "analyze": analyze_ehydro},
    "eggs-temp": {"acquire": acquire_none, "analyze": analyze_eggs_temp},
    "nas": {"acquire": acquire_nas, "analyze": analyze_nas},
    "fish-rule-grade": {"acquire": acquire_none, "analyze": analyze_fish_rules},
    "dataset-search": {"acquire": acquire_dataset_search, "analyze": analyze_dataset_search},
    "lake-cwms": {"acquire": acquire_lake_cwms, "analyze": analyze_lake_cwms},
    "xb-wt-fish": {"acquire": acquire_none, "analyze": analyze_xb_wt_fish},
}
