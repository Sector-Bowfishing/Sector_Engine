#!/usr/bin/env python3
"""Fleet-wide temporal hold-out calibration of the Lake Brain's historical-baseline classifications (Tier C validation).

Question: when the Lake Brain says a level is "inside p10-p90" / "outside p02-p98" / "rapid change", is that how often it
actually happens on data the baseline never saw?  No field work: daily pool series the binding thread verified (CWMS / USGS / RISE).

Method (doy15-percentile-v1 re-implemented exactly as in docs/brains/LAKE_BRAIN_INTEGRATION.md section 6):
  for each lake, for each of the last K complete calendar years Y (rolling origin; Y is never in its own baseline):
     training = complete years < Y (>= 329 days each), most recent 30; require >= MIN_TRAIN of them
     level band for day-of-year d = quantiles {2,10,50,90,98} (type 7) of every training value within +/-7 days of d
     rate band for d             = p95 of |24 h change| in the same window over training years
     score the held-out year's days: inside [p10,p90]; outside [p02,p98]; |24 h change| > rate p95
PRE-REGISTERED acceptance (fixed before running; thresholds are not tuned to results):
  V1 band calibration  - per lake: mean coverage of [p10,p90] in [0.70,0.90]  AND  of [p02,p98] in [0.92,0.99]
  V2 tail rate         - per lake: share of days outside [p02,p98] <= 0.08   (nominal 0.04)
  V3 rapid-change rate - per lake: share of days with |24 h change| > p95 in [0.02,0.09]   (nominal 0.05)
  Fleet verdict        - ELIGIBLE_FOR_PARTIAL if, over >= 100 lakes trained on >= 10 years, >= 70 % pass V1 and V2 and >= 70 % pass V3.
Stationarity is not assumed away: lakes whose operations changed will fail, and that is a finding, not noise.
usage: holdout_validation.py [--min-train 10] [--test-years 5] [--out DIR]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import json
import os
import statistics

import numpy as np

DATA = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain")
HIST = os.path.join(DATA, "binding", "history")
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WINDOW = 7
QS = (2, 10, 50, 90, 98)


def series_path(series: str) -> str | None:
    """'cwms:SPA:Abiquiu.Elev.Inst.~1Day.0.MRS' -> history/cwms_SPA_Abiquiu....csv.gz ; 'usgs:0106:62614' ; 'rise:106'."""
    base = series.replace(":", "_").replace("/", "_")
    for cand in (os.path.join(HIST, base + ".csv.gz"),):
        if os.path.exists(cand):
            return cand
    g = glob.glob(os.path.join(HIST, glob.escape(base) + "*.csv.gz"))
    return g[0] if g else None


def read_daily(path: str) -> dict[dt.date, float]:
    out = {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 2 or not parts[1]:
                continue
            try:
                d, v = dt.date.fromisoformat(parts[0][:10]), float(parts[1])
            except ValueError:
                continue
            if v > 1.0:                                # RISE placeholders are 0.0; no reservoir surface is < 1 ft or m here
                out[d] = v
    return out


def doy(d: dt.date) -> int:
    t = d.timetuple().tm_yday
    return t - 1 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) and t > 59 else t      # 1..365 ; Feb 29 folds onto Mar 1


def year_arrays(daily: dict[dt.date, float]):
    by = collections.defaultdict(dict)
    for d, v in daily.items():
        by[d.year][d] = v
    return by


def complete_years(by, today_year: int) -> list[int]:
    return sorted(y for y, m in by.items() if len(m) >= 329 and y < today_year)


def to_grid(m: dict[dt.date, float]) -> np.ndarray:
    a = np.full(366, np.nan)
    for d, v in m.items():
        a[doy(d)] = v
    return a[1:366]


def window_idx(i: int) -> np.ndarray:
    return np.array([(i + k) % 365 for k in range(-WINDOW, WINDOW + 1)])


def baseline(train_grids: list[np.ndarray]):
    L = np.vstack(train_grids)                                              # years x 365
    R = np.abs(np.diff(L, axis=1, prepend=np.nan))                         # |24 h change| ; first column NaN (year wrap not bridged)
    q = np.full((365, len(QS)), np.nan)
    r95 = np.full(365, np.nan)
    for i in range(365):
        idx = window_idx(i)
        vals = L[:, idx].ravel(); vals = vals[~np.isnan(vals)]
        if vals.size >= 30:
            q[i] = np.percentile(vals, QS)                                  # numpy default = type 7
        rv = R[:, idx].ravel(); rv = rv[~np.isnan(rv)]
        if rv.size >= 20:
            r95[i] = np.percentile(rv, 95)
    return q, r95


def evaluate_lake(daily: dict[dt.date, float], min_train: int, test_years: int, today_year: int):
    by = year_arrays(daily)
    cy = complete_years(by, today_year)
    tests = [y for y in cy[-test_years:] if sum(1 for t in cy if t < y) >= min_train]
    rows = []
    for Y in tests:
        train = [t for t in cy if t < Y][-30:]
        if len(train) < min_train:
            continue
        q, r95 = baseline([to_grid(by[t]) for t in train])
        g = to_grid(by[Y])
        valid = ~np.isnan(g) & ~np.isnan(q[:, 0])
        if valid.sum() < 200:
            continue
        in8 = ((g >= q[:, 1]) & (g <= q[:, 3]))[valid].mean()
        in96 = ((g >= q[:, 0]) & (g <= q[:, 4]))[valid].mean()
        dlt = np.abs(np.diff(g, prepend=np.nan))
        rv = valid & ~np.isnan(dlt) & ~np.isnan(r95)
        rapid = (dlt[rv] > r95[rv]).mean() if rv.sum() > 100 else float("nan")
        rows.append({"year": Y, "train": len(train), "in80": float(in8), "in96": float(in96), "tail": float(1 - in96), "rapid": float(rapid), "days": int(valid.sum())})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-train", type=int, default=10)
    ap.add_argument("--test-years", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(DATA, "history", "holdout"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    res = json.load(open(os.path.join(DATA, "binding", "history_results.json")))
    ver = {r["lakeId"]: r for r in csv.DictReader(open(os.path.join(DATA, "binding", "verified.csv")))}
    feats = {r["lakeId"]: r for r in csv.DictReader(open(os.path.join(REPO, "docs", "research", "lake-brain", "data", "lake_features.csv")))} \
        if os.path.exists(os.path.join(REPO, "docs", "research", "lake-brain", "data", "lake_features.csv")) else {}
    today_year = dt.date.today().year
    lakes = {}
    for key, v in res.items():
        lake = key.split("|")[0] + "|" + key.split("|")[1]
        b = (v or {}).get("best")
        if not b or ver.get(lake, {}).get("bindingStatus") not in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG"):
            continue
        if lake not in lakes or b.get("completeYears", 0) > lakes[lake]["completeYears"]:
            lakes[lake] = {"series": b["series"], "completeYears": b.get("completeYears", 0)}
    per = []
    for lake, info in sorted(lakes.items()):
        p = series_path(info["series"])
        if not p:
            continue
        rows = evaluate_lake(read_daily(p), a.min_train, a.test_years, today_year)
        if not rows:
            continue
        m = lambda k: float(np.nanmean([r[k] for r in rows]))  # noqa: E731
        cls = (feats.get(lake) or {}).get("class") or (feats.get(lake) or {}).get("regime") or ""
        rec = {"lakeId": lake, "series": info["series"], "testYears": len(rows), "train": rows[-1]["train"], "in80": m("in80"), "in96": m("in96"),
               "tail": m("tail"), "rapid": m("rapid"), "class": cls, "provider": ver[lake]["provider"], "capability": ver[lake]["capability"]}
        rec["V1"] = 0.70 <= rec["in80"] <= 0.90 and 0.92 <= rec["in96"] <= 0.99
        rec["V2"] = rec["tail"] <= 0.08
        rec["V3"] = 0.02 <= rec["rapid"] <= 0.09 if rec["rapid"] == rec["rapid"] else False
        per.append(rec)
    n = len(per)
    ok12 = [r for r in per if r["V1"] and r["V2"]]
    ok3 = [r for r in per if r["V3"]]
    summary = {"minTrain": a.min_train, "testYears": a.test_years, "lakesTested": n,
               "passV1V2": len(ok12), "passV1V2Pct": round(100 * len(ok12) / n, 1) if n else None,
               "passV3": len(ok3), "passV3Pct": round(100 * len(ok3) / n, 1) if n else None,
               "median": {k: round(statistics.median(r[k] for r in per), 3) for k in ("in80", "in96", "tail", "rapid")} if n else {},
               "nominal": {"in80": 0.80, "in96": 0.96, "tail": 0.04, "rapid": 0.05},
               "verdict": "ELIGIBLE_FOR_PARTIAL" if (n >= 100 and len(ok12) / max(n, 1) >= 0.70 and len(ok3) / max(n, 1) >= 0.70) else "NOT_ELIGIBLE",
               "byProvider": {}, "byClass": {}, "failuresByMode": {"in80_low": sum(r["in80"] < 0.70 for r in per), "in80_high": sum(r["in80"] > 0.90 for r in per),
                                                             "tail_high": sum(r["tail"] > 0.08 for r in per), "rapid_low": sum(r["rapid"] < 0.02 for r in per if r["rapid"] == r["rapid"]),
                                                             "rapid_high": sum(r["rapid"] > 0.09 for r in per if r["rapid"] == r["rapid"])}}
    for field, key in (("provider", "byProvider"), ("class", "byClass")):
        g = collections.defaultdict(list)
        for r in per:
            g[r[field] or "?"].append(r)
        summary[key] = {k: {"n": len(v), "passV1V2Pct": round(100 * sum(1 for r in v if r["V1"] and r["V2"]) / len(v)), "passV3Pct": round(100 * sum(1 for r in v if r["V3"]) / len(v))} for k, v in sorted(g.items())}
    tag = f"mt{a.min_train}"
    json.dump({"summary": summary, "lakes": per}, open(os.path.join(a.out, f"holdout_{tag}.json"), "w"), indent=1)
    cdir = os.path.join(REPO, "docs", "research", "lake-brain", "data")
    json.dump(summary, open(os.path.join(cdir, f"holdout_validation_{tag}.json"), "w"), indent=1)
    with open(os.path.join(cdir, f"holdout_validation_{tag}_lakes.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lakeId", "provider", "class", "trainYears", "testYears", "cov_p10_p90", "cov_p02_p98", "tailRate", "rapidRate", "V1", "V2", "V3"])
        for r in per:
            w.writerow([r["lakeId"], r["provider"], r["class"], r["train"], r["testYears"], round(r["in80"], 3), round(r["in96"], 3), round(r["tail"], 3), round(r["rapid"], 3), int(r["V1"]), int(r["V2"]), int(r["V3"])])
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
