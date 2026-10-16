#!/usr/bin/env python3
"""Lake Brain: one-time deep history backfill for the four TVA pilot lakes.

WHAT IT DOES
  For Guntersville, Wheeler, Wilson and Pickwick it builds a merged daily pool-elevation series
      deep composite  (NWS Huntsville RVDHUN text 2003/2005-2021, 6-7 AM local, 0.1 ft;
                       NWS/TVA HADS 'HP' hourly -> lake-local MIDNIGHT, 2022-10-27 ->, 0.01 ft;
                       Pickwick only: CWMS LRD 'Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA' -> local midnight, 2019-10 ->)
    UNION  the existing gs://sector-lake-brain/history/<key>/daily.csv (TVA operating-guide midnight, 2025-01-01 ->)
  using EXACTLY the Swift collision rule (LakeDailyHistory.merge(existing:new:) = dedupe(existing + new): on the
  same date the LATER entry wins). The existing authoritative rows are therefore passed as `new`, so they win over any
  composite value on the same date. Within the composite the precedence is HADS midnight > CWMS midnight > RVDHUN.

  The output file format is byte-compatible with LakeDailyHistory.encode/decode:
      header 'date,elevationFt,sourceId', one row per lake-local day (America/Chicago), ascending date,
      elevation '%.2f', LF line endings, trailing LF, no commas inside sourceId.

SAFETY
  * dry-run by default: nothing is written to GCS (the merged files, a JSON report and the mirrored baselines are
    written under --out-dir on local disk).
  * --write: for each lake (a) the live object's generation G is read, (b) generation G is copied to
    gs://<bucket>/history_backup/<key>/daily.<UTC timestamp>.csv, (c) the merged file is uploaded with
    --if-generation-match=G (so a concurrent write by the job aborts the upload instead of being overwritten), (d) the
    object is read back and its md5 and row count are verified. A BACKFILL_LOG.md entry is appended.
  * it never runs the lake-brain job and never touches Cloud Run, Scheduler or the RTDB.

INPUTS (research data, outside Git; see Sector_Engine docs/research/lake-brain/LAKE_BRAIN_BASELINE_RESEARCH.md s.1)
  <hist>/hads/<LOC>_*.csv                      IEM hads.py pulls (columns utc_valid, HPIRZZZ)
  <hist>/nws_rvdhun/rvdhun_pool_parsed.csv     research/lake-brain/parse_rvdhun.py output
  <hist>/nws_rvdmeg/rvdmeg_*.txt               NWS Memphis product (Pickwick headwater 2013, 2020-21)
  <hist>/cwms/pickwick_lake_hourly.csv         research/lake-brain/baseline_fetch.py cwms
  <hist>/tva_pilots/<LOC>_daily.csv            research composite (used only as a cross-check of this script's composite)

USAGE
  python backfill_tva_deep.py                          # dry run, all four lakes
  python backfill_tva_deep.py --lakes GVDA1 --write
  python backfill_tva_deep.py mirror-check --history <daily.csv> --baseline <swift baseline.json> --today YYYY-MM-DD
"""
import argparse, base64, datetime as dt, glob, hashlib, json, math, os, re, subprocess, sys
import numpy as np
import pandas as pd

BUCKET = "sector-lake-brain"
TZ = "America/Chicago"                       # TVA lake time zone in LakeSourceBindings.tvaPilot
METHOD = "doy15-percentile-v1"               # LakeBrainSpec.baselineMethod
DEFAULT_HIST = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/history")

# loc -> lake id, gcs key, RVDHUN name regex, plausible range [lo, hi] ft, directory fullPoolFt, topOfGatesFt
# lo = fullPool - seasonal drawdown tolerance; hi = LakeSourceBindings topOfGates + 0.6 ft (0.1-ft rounding + wave/seiche slack)
PILOTS = {
    "GVDA1": dict(lake_id="Guntersville|AL", key="Guntersville_AL", rx=r"^GUNTERSVILLE( HW)?$",
                  full_pool=595.0, top_of_gates=595.44, lo=590.0, hi=596.04),
    "WHLA1": dict(lake_id="Wheeler|AL", key="Wheeler_AL", rx=r"^WHEELER( HW| DAM)?$",
                  full_pool=556.0, top_of_gates=556.28, lo=548.0, hi=556.88),
    "WLSA1": dict(lake_id="Wilson|AL", key="Wilson_AL", rx=r"^WILSON HW$",
                  full_pool=507.7, top_of_gates=507.88, lo=502.7, hi=508.48),
    "PICT1": dict(lake_id="Pickwick Lake|TN", key="Pickwick_Lake_TN", rx=r"^PICKWICK( HW| DAM)?$",
                  full_pool=414.0, top_of_gates=418.0, lo=405.5, hi=418.6),
}
# recount expected from the research composite (complete years >= 329 days, years before 2026)
EXPECTED_COMPLETE_YEARS = {"GVDA1": 17, "WHLA1": 18, "WLSA1": 18, "PICT1": 16}
COMPLETE_YEAR_DAYS = 329

SRC_HADS = "nws:hads:{loc}:HP"
SRC_CWMS = "cwms:LRD:Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA"
SRC_RVD = "nws:rvdhun:{loc}"
SRC_RVDMEG = "nws:rvdmeg:PICT1"

# ----------------------------------------------------------------------------------------------------------------
# Mirror of Swift LakeBrainArchive.swift (LakeDailyHistory) and LakeLevelBaseline.swift (LakeBaselineBuilder)
# ----------------------------------------------------------------------------------------------------------------

def _ints(day):                       # Swift: day.split(separator:"-").compactMap { Int($0) }
    out = []
    for s in day.split("-"):
        if s == "":
            continue
        try:
            out.append(int(s))
        except ValueError:
            pass
    return out

def doy365(day):
    """LakeLevelCalendar.doy365: 365-day index, Feb 29 shares Feb 28's index."""
    p = _ints(day)
    if len(p) != 3 or not (1 <= p[1] <= 12) or not (1 <= p[2] <= 31):
        return None
    cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    d = 28 if (p[1] == 2 and p[2] == 29) else p[2]
    return cum[p[1] - 1] + d

def is_day_string(s):
    return len(s) == 10 and doy365(s) is not None

def previous_day(day):
    p = _ints(day)
    if len(p) != 3:
        return None
    return (dt.date(p[0], p[1], p[2]) - dt.timedelta(days=1)).isoformat()

def dedupe(rows):
    """LakeDailyHistory.dedupe: one value per date, the LATER entry wins; sorted by date."""
    by = {}
    for r in rows:
        by[r[0]] = r
    return [by[d] for d in sorted(by)]

def encode(rows):
    s = "date,elevationFt,sourceId\n"
    for d, ft, src in dedupe(rows):
        s += "%s,%.2f,%s\n" % (d, ft, src)
    return s.encode("utf-8")

def decode(data):
    """LakeDailyHistory.decode: split on LF (omitting empty lines), drop the first line, split(',', maxSplits=2)."""
    lines = [l for l in data.decode("utf-8", errors="replace").split("\n") if l != ""]
    out = []
    for line in lines[1:]:
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        try:
            ft = float(parts[1])
        except ValueError:
            continue
        if not is_day_string(parts[0]):
            continue
        out.append((parts[0], ft, parts[2]))
    return out

def merge(existing, new):
    """LakeDailyHistory.merge(existing:new:): existing U new, NEW wins on the same date."""
    return dedupe(list(existing) + list(new))

GRID = [0, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100]

def _round_half_away(x):
    f = math.floor(x)
    return f + 1 if x - f >= 0.5 else f

def quantile(xs, p):
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    h = (len(xs) - 1.0) * p / 100
    lo = int(math.floor(h))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])

def grid_of(samples):
    s = sorted(samples)
    return [_round_half_away(quantile(s, p) * 1000) / 1000 for p in GRID]

def fingerprint(s):
    h = 0xcbf29ce484222325
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return "%016x" % h

def lake_key(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s)

def build_baseline(lake_id, raw, today):
    """LakeBaselineBuilder.build (doy15-percentile-v1). `raw` = list of (date, ft, sourceId)."""
    daily = [r for r in dedupe(raw) if r[0] <= today]
    cur_year = int(today[:4])
    per_year = {}
    for d, _, _ in daily:
        y = int(d[:4])
        per_year[y] = per_year.get(y, 0) + 1
    complete = sorted(y for y, n in per_year.items() if y < cur_year and n >= COMPLETE_YEAR_DAYS)
    basis = complete[-30:]
    if len(basis) >= 5:
        status = "SUFFICIENT"
    elif len(basis) >= 2:
        status = "LIMITED"
    else:
        status = "NONE" if not daily else "INSUFFICIENT"
    basis_set = set(basis)
    level_by_doy = {}
    if len(basis) >= 2:
        for d, ft, _ in daily:
            if int(d[:4]) in basis_set:
                k = doy365(d)
                if k is not None:
                    level_by_doy.setdefault(k, []).append(ft)
    by_date = {d: ft for d, ft, _ in daily}
    rate_by_doy = {}
    for d, ft, _ in daily:
        if int(d[:4]) <= cur_year - 30:
            continue
        pv = by_date.get(previous_day(d))
        k = doy365(d)
        if pv is None or k is None:
            continue
        rate_by_doy.setdefault(k, []).append(abs(ft - pv))
    days = []
    for doy in range(1, 366):
        lv, rv = [], []
        for off in range(-7, 8):
            k = ((doy - 1 + off) % 365 + 365) % 365 + 1
            lv += level_by_doy.get(k, [])
            rv += rate_by_doy.get(k, [])
        days.append(dict(doy=doy, n=len(lv), levelQ=grid_of(lv) if lv else None,
                         rateN=len(rv), rateQ=grid_of(rv) if len(rv) >= 20 else None))
    coverage = None
    if daily:
        s = dt.date.fromisoformat(daily[0][0]); e = dt.date.fromisoformat(daily[-1][0])
        span = (e - s).days + 1
        coverage = _round_half_away(len(daily) / span * 1000) / 10
    csv = encode(daily).decode("utf-8")
    version = "%s@%s#%s" % (METHOD, daily[-1][0] if daily else "none", fingerprint(csv)[:8])
    return dict(lakeId=lake_id, method=METHOD, baselineVersion=version,
                historyStart=daily[0][0] if daily else None, historyEnd=daily[-1][0] if daily else None,
                observationCount=len(daily), coveragePct=coverage, completeYears=complete, basisYears=basis,
                status=status, windowDays=7, days=days)

def baseline_path(b):
    return "baselines/%s/%s.json" % (lake_key(b["lakeId"]), lake_key(b["baselineVersion"]))

def band(b, doy):
    q = b["days"][doy - 1]["levelQ"]
    if not q:
        return None
    return {p: q[GRID.index(p)] for p in (2, 10, 50, 90, 98)}

def doy_label(doy):
    d = dt.date(2025, 1, 1) + dt.timedelta(days=doy - 1)
    return d.strftime("%b %d")

# ----------------------------------------------------------------------------------------------------------------
# Deep composite (same inputs and precedence as research/lake-brain/tva_pilot_history.py)
# ----------------------------------------------------------------------------------------------------------------

def rvd_series(hist, loc, cfg):
    d = pd.read_csv(f"{hist}/nws_rvdhun/rvdhun_pool_parsed.csv", dtype={"issue_hhmm": str})
    d["nm"] = d["name"].str.upper().str.strip()
    ids = [loc] + (["PKDT1"] if loc == "PICT1" else [])
    s = d[d.station.isin(ids) & d.nm.str.match(cfg["rx"]) & d.value_ft.notna()].copy()
    s["date"] = pd.to_datetime(s.date)
    # 'WHEELER DAM' in 2005-07 also carried Wilson values -> range QC (cfg lo/hi) removes them
    n0 = len(s)
    s = s[(s.value_ft >= cfg["lo"]) & (s.value_ft <= cfg["hi"])]
    rvd = s.groupby("date").value_ft.median().rename("v")
    qc = {"rvd_rows": int(n0), "rvd_out_of_range_dropped": int(n0 - len(s))}
    meg = pd.Series(dtype=float)
    if loc == "PICT1":
        meg = rvdmeg_pickwick(hist, cfg)
        meg = meg[~meg.index.isin(rvd.index)]
    return rvd, meg, qc

def rvdmeg_pickwick(hist, cfg):
    """NWS Memphis RVDMEG 'PICKWICK DAM HEADWATER' observed 7 AM value (present 2013 and 2020-21 only)."""
    rows = {}
    for f in sorted(glob.glob(f"{hist}/nws_rvdmeg/rvdmeg_*.txt")):
        for prod in re.split(r"(?m)^RVDMEG\s*$", open(f, errors="replace").read())[1:]:
            m = re.search(r"DC(\d{4})(\d{2})(\d{2})", prod)
            if not m:
                continue
            ls = prod.splitlines()
            for i, l in enumerate(ls):
                if "PICKWICK DAM HEADWATER" in l.upper() and i + 1 < len(ls):
                    mm = re.search(r":\s*(M|\d{3}\.\d)/", ls[i + 1].split(":", 1)[1] if ":" in ls[i + 1] else "")
                    if mm and mm.group(1) != "M":
                        rows[pd.Timestamp(f"{m[1]}-{m[2]}-{m[3]}")] = float(mm.group(1))
    s = pd.Series(rows, dtype=float).sort_index() if rows else pd.Series(dtype=float)
    return s[(s >= cfg["lo"]) & (s <= cfg["hi"])]

def hads_hourly(hist, loc):
    fs = sorted(glob.glob(f"{hist}/hads/{loc}_*.csv"))
    x = pd.concat([pd.read_csv(f, usecols=["utc_valid", "HPIRZZZ"]) for f in fs]).dropna()
    x["t"] = pd.to_datetime(x.utc_valid, utc=True)
    return x[x.HPIRZZZ > 100].drop_duplicates("t").set_index("t").HPIRZZZ.sort_index()

def cwms_pickwick_hourly(hist):
    d = pd.read_csv(f"{hist}/cwms/pickwick_lake_hourly.csv")
    d["t"] = pd.to_datetime(d.epoch_ms, unit="ms", utc=True)
    d = d.dropna(subset=["value"])
    d = d[(d.value > 406) & (d.value < 420)]          # research QC: 2019-20 hold tailwater/Normandy-scale values
    return d.set_index("t").value.sort_index()

def local_hour(h, hour):
    """hourly UTC series -> first reading in the given America/Chicago clock hour of each local day (index = local date)."""
    lt = h.copy()
    lt.index = lt.index.tz_convert(TZ)
    m = lt[lt.index.hour == hour]
    m.index = m.index.tz_localize(None).normalize()
    return m[~m.index.duplicated()]

def composite(hist, loc, cfg):
    """Return (comp DataFrame[value, src] indexed by date, parts dict, qc dict)."""
    qc = {}
    parts = {}
    h = hads_hourly(hist, loc)
    hm = local_hour(h, 0)
    n0 = len(hm)
    hm = hm[(hm >= cfg["lo"]) & (hm <= cfg["hi"])]
    qc["hads_midnight_days"] = int(n0); qc["hads_out_of_range_dropped"] = int(n0 - len(hm))
    parts["hads"] = (hm, SRC_HADS.format(loc=loc))
    order = [("hads", hm, SRC_HADS.format(loc=loc))]
    if loc == "PICT1":
        c = cwms_pickwick_hourly(hist)
        cm = local_hour(c, 0)
        n0 = len(cm)
        cm = cm[(cm >= cfg["lo"]) & (cm <= cfg["hi"])]
        qc["cwms_midnight_days"] = int(n0); qc["cwms_out_of_range_dropped"] = int(n0 - len(cm))
        parts["cwms"] = (cm, SRC_CWMS)
        parts["cwms_7am"] = (local_hour(c, 7), None)
        order.append(("cwms", cm, SRC_CWMS))
    rvd, meg, q = rvd_series(hist, loc, cfg)
    qc.update(q)
    parts["rvd"] = (rvd, SRC_RVD.format(loc=loc))
    order.append(("rvd", rvd, SRC_RVD.format(loc=loc)))
    if len(meg):
        parts["rvdmeg"] = (meg, SRC_RVDMEG)
        order.append(("rvdmeg", meg, SRC_RVDMEG))
    comp = pd.Series(dtype=float); src = pd.Series(dtype=object)
    for _, s, tag in order:
        new = s[~s.index.isin(comp.index)]
        comp = pd.concat([comp, new])
        src = pd.concat([src, pd.Series(tag, index=new.index, dtype=object)])
    comp = comp.sort_index(); src = src.reindex(comp.index)
    return pd.DataFrame({"value": comp, "src": src}), parts, qc

# ----------------------------------------------------------------------------------------------------------------
# GCS helpers (gcloud storage)
# ----------------------------------------------------------------------------------------------------------------

def sh(cmd, check=True, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("command failed: %s\n%s" % (" ".join(cmd), (r.stderr or "")[-2000:]))
    return r

def gcs_describe(uri):
    r = sh(["gcloud", "storage", "objects", "describe", uri, "--format=json"])
    return json.loads(r.stdout)

def gcs_cat(uri):
    return sh(["gcloud", "storage", "cat", uri], capture=True).stdout.encode("utf-8")

def md5_b64(data):
    return base64.b64encode(hashlib.md5(data).digest()).decode()

# ----------------------------------------------------------------------------------------------------------------
# Per-lake build + validation
# ----------------------------------------------------------------------------------------------------------------

def stats(a, b):
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if j.empty:
        return None
    d = (j.a - j.b).abs()
    return dict(n=int(len(j)), mean_abs=round(float(d.mean()), 4), median_abs=round(float(d.median()), 4),
                p95_abs=round(float(d.quantile(.95)), 4), max_abs=round(float(d.max()), 3),
                bias=round(float((j.a - j.b).mean()), 4))

def build_lake(loc, cfg, hist, existing_bytes, today):
    existing = decode(existing_bytes)
    ex_dates = [r[0] for r in existing]
    ex_min, ex_max = (ex_dates[0], ex_dates[-1]) if existing else (None, None)
    comp, parts, qc = composite(hist, loc, cfg)
    comp_rows = [(d.strftime("%Y-%m-%d"), float("%.2f" % v), s)
                 for d, v, s in zip(comp.index, comp.value.values, comp.src.values)]
    # composite rows are only ever BEFORE / BETWEEN the guide-derived rows, never after the last existing day
    limit = min(today, ex_max) if ex_max else today
    comp_rows = [r for r in comp_rows if r[0] <= limit]
    merged = merge(comp_rows, existing)                   # existing passed as `new` -> existing wins on collisions
    data = encode(merged)
    round_trip = decode(data)
    assert round_trip == merged, "encode/decode round trip changed the rows"
    rep = dict(loc=loc, lake_id=cfg["lake_id"], key=cfg["key"], qc=qc)
    rep["existing"] = dict(rows=len(existing), first=ex_min, last=ex_max,
                           source_ids=sorted({r[2] for r in existing}))
    # collisions: composite dates that also exist in `existing` (existing wins)
    ex_set = {r[0]: r for r in existing}
    coll = [r for r in comp_rows if r[0] in ex_set]
    mm = {r[0]: r for r in merged}
    rep["collisions"] = dict(n=len(coll), existing_wins=all(mm[r[0]] == ex_set[r[0]] for r in coll))
    # overlap agreement: composite sources vs existing (the authoritative TVA guide midnight values)
    tr = pd.Series({pd.Timestamp(d): ft for d, ft, _ in existing})
    ov = {}
    hm = parts["hads"][0]
    ov["hads_midnight_vs_existing"] = stats(hm[hm.index.isin(tr.index)], tr)
    if "cwms" in parts:
        cm = parts["cwms"][0]
        ov["cwms_midnight_vs_existing"] = stats(cm[cm.index.isin(tr.index)], tr)
        rv = parts["rvd"][0]; c7 = parts["cwms_7am"][0]
        if "rvdmeg" in parts:
            rv = pd.concat([rv, parts["rvdmeg"][0]])
        ov["rvd_(hun+meg)_vs_cwms_07h"] = stats(rv, c7)
    rep["overlap"] = ov
    # in-sample precedence check: where the composite had a HADS midnight value AND existing has the date, how often do they differ > 0.02 ft
    j = pd.concat([hm.rename("h"), tr.rename("t")], axis=1).dropna()
    rep["overlap"]["hads_days_differing_gt_0.02ft"] = int(((j.h - j.t).abs() > 0.02).sum())
    rep["overlap"]["hads_days_differing_gt_0.05ft"] = int(((j.h - j.t).abs() > 0.05).sum())
    # ---- validation
    dates = [r[0] for r in merged]
    checks = {}
    checks["no_duplicate_dates"] = len(dates) == len(set(dates))
    checks["strictly_ascending"] = all(dates[i] < dates[i + 1] for i in range(len(dates) - 1))
    checks["all_valid_day_strings"] = all(is_day_string(d) for d in dates)
    vals = np.array([r[1] for r in merged])
    checks["in_plausible_range"] = bool(((vals >= cfg["lo"]) & (vals <= cfg["hi"])).all())
    rep["range"] = dict(plausible=[cfg["lo"], cfg["hi"]], observed_min=float(vals.min()), observed_max=float(vals.max()),
                        full_pool_ft=cfg["full_pool"], top_of_gates_ft=cfg["top_of_gates"])
    checks["existing_rows_unchanged"] = all(dict((r[0], r) for r in merged).get(e[0]) == e for e in existing)
    checks["lf_only_no_cr"] = b"\r" not in data
    checks["no_comma_in_source_id"] = all("," not in r[2] for r in merged)
    steps = np.abs(np.diff(vals))
    rep["largest_day_to_day_steps_ft"] = sorted([(round(float(s), 2), dates[i + 1]) for i, s in enumerate(steps)], reverse=True)[:3]
    checks["max_day_step_le_5ft"] = bool(steps.max() <= 5.0)          # pool floods move 3-4 ft/day (Pickwick Feb 2004); >5 ft is a data error
    rep["day_steps_gt_3ft_warning"] = [(round(float(s), 2), dates[i + 1]) for i, s in enumerate(steps) if s > 3.0]
    by_src = {}
    for r in merged:
        by_src[r[2]] = by_src.get(r[2], 0) + 1
    rep["rows_by_source"] = by_src
    gaps = []
    for i in range(len(dates) - 1):
        a = dt.date.fromisoformat(dates[i]); b = dt.date.fromisoformat(dates[i + 1])
        if (b - a).days > 1:
            gaps.append((dates[i], dates[i + 1], (b - a).days - 1))
    rep["gaps"] = [dict(after=g[0], before=g[1], missing_days=g[2]) for g in gaps if g[2] >= 30]
    rep["gap_count_total"] = len(gaps)
    # ---- baseline mirror: BEFORE (existing only) vs AFTER (merged)
    b_before = build_baseline(cfg["lake_id"], existing, today)
    b_after = build_baseline(cfg["lake_id"], decode(data), today)
    rep["baseline_before"] = dict(status=b_before["status"], completeYears=b_before["completeYears"], version=b_before["baselineVersion"])
    rep["baseline_after"] = dict(status=b_after["status"], completeYears=b_after["completeYears"], basisYears=b_after["basisYears"],
                                 version=b_after["baselineVersion"], observationCount=b_after["observationCount"],
                                 coveragePct=b_after["coveragePct"], historyStart=b_after["historyStart"], historyEnd=b_after["historyEnd"],
                                 path=baseline_path(b_after))
    cy = len(b_after["completeYears"])
    rep["complete_years_recount"] = cy
    rep["complete_years_expected"] = EXPECTED_COMPLETE_YEARS[loc]
    checks["baseline_status_sufficient"] = b_after["status"] == "SUFFICIENT"
    checks["complete_years_ge_expected_minus1"] = cy >= EXPECTED_COMPLETE_YEARS[loc] - 1
    # sanity bands (p10/p50/p90 at three days of year) + independent numpy check
    day_samples = {}
    for doy in (15, 166, 286):
        bd = band(b_after, doy)
        # independent recompute of the window with numpy (type-7 == numpy 'linear')
        basis = set(b_after["basisYears"])
        win = {((doy - 1 + off) % 365) + 1 for off in range(-7, 8)}
        s = [ft for d, ft, _ in decode(data) if int(d[:4]) in basis and doy365(d) in win]
        npq = {p: round(float(np.percentile(s, p)), 3) for p in (2, 10, 50, 90, 98)}
        ok = all(abs(npq[p] - bd[p]) <= 0.0006 for p in bd)
        checks[f"numpy_cross_check_doy{doy}"] = ok
        day_samples[doy_label(doy)] = dict(doy=doy, n=b_after["days"][doy - 1]["n"], band=bd,
                                           band_before=band(b_before, doy))
    rep["baseline_sanity"] = day_samples
    # rate climatology contamination: build once WITHOUT the 0.1-ft RVD rows to quantify the effect
    no_rvd = [r for r in merged if not r[2].startswith("nws:rvd")]
    b_nr = build_baseline(cfg["lake_id"], no_rvd, today)
    rate_note = {}
    for doy in (15, 166, 286):
        a = b_after["days"][doy - 1]; n = b_nr["days"][doy - 1]
        pick = lambda d: None if not d["rateQ"] else dict(rateN=d["rateN"], p50=d["rateQ"][GRID.index(50)], p95=d["rateQ"][GRID.index(95)])
        rate_note[doy_label(doy)] = dict(with_rvd_rows=pick(a), hads_cwms_era_only=pick(n))
    rep["rate_climatology_effect_of_0.1ft_rvd_rows"] = rate_note
    rep["checks"] = checks
    rep["pass"] = all(checks.values())
    return data, merged, b_after, rep

# ----------------------------------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------------------------------

def cmd_mirror_check(a):
    daily = decode(open(a.history, "rb").read())
    b = build_baseline(a.lake_id, daily, a.today)
    sw = json.load(open(a.baseline))
    bad = []
    for k in ("baselineVersion", "historyStart", "historyEnd", "observationCount", "coveragePct", "completeYears", "basisYears", "status", "method", "windowDays"):
        if b[k] != sw[k]:
            bad.append((k, b[k], sw[k]))
    worst = 0.0
    for x, y in zip(b["days"], sw["days"]):
        for f in ("n", "rateN"):
            if x[f] != y[f]:
                bad.append(("day%d.%s" % (x["doy"], f), x[f], y[f]))
        for f in ("levelQ", "rateQ"):
            xv, yv = x[f], y.get(f)
            if (xv is None) != (yv is None):
                bad.append(("day%d.%s presence" % (x["doy"], f), xv is None, yv is None))
            elif xv is not None:
                worst = max(worst, max(abs(p - q) for p, q in zip(xv, yv)))
    print(json.dumps(dict(mirror_version=b["baselineVersion"], swift_version=sw["baselineVersion"], mismatches=bad[:10],
                          mismatch_count=len(bad), max_abs_quantile_diff=worst, status=b["status"]), indent=1))
    return 0 if not bad and worst < 1e-9 else 1

def append_log(path, text):
    with open(path, "a") as f:
        f.write(text)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    mc = sub.add_parser("mirror-check", help="verify the Python baseline mirror against a Swift-written baseline JSON")
    mc.add_argument("--history", required=True); mc.add_argument("--baseline", required=True)
    mc.add_argument("--lake-id", required=True); mc.add_argument("--today", required=True)
    ap.add_argument("--lakes", default="GVDA1,WHLA1,WLSA1,PICT1")
    ap.add_argument("--hist-dir", default=os.environ.get("LAKE_BRAIN_HIST", DEFAULT_HIST))
    ap.add_argument("--bucket", default=BUCKET)
    ap.add_argument("--out-dir", default=None, help="dry-run outputs (default <hist-dir>/tva_pilots/backfill_dryrun)")
    ap.add_argument("--existing-dir", default=None, help="use <dir>/<key>.daily.csv instead of reading gs:// (dry run only)")
    ap.add_argument("--today", default=None, help="lake-local day, default today in America/Chicago")
    ap.add_argument("--write", action="store_true", help="back up + upload + verify (default is a dry run)")
    ap.add_argument("--log", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "BACKFILL_LOG.md"))
    a = ap.parse_args()
    if a.cmd == "mirror-check":
        sys.exit(cmd_mirror_check(a))
    if a.write and a.existing_dir:
        sys.exit("--write reads the live objects; do not combine with --existing-dir")
    today = a.today or dt.datetime.now(dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo(TZ)).strftime("%Y-%m-%d")
    out_dir = a.out_dir or f"{a.hist_dir}/tva_pilots/backfill_dryrun"
    os.makedirs(out_dir, exist_ok=True)
    locs = [l.strip() for l in a.lakes.split(",") if l.strip()]
    results = {}
    ok_all = True
    for loc in locs:
        cfg = PILOTS[loc]
        uri = f"gs://{a.bucket}/history/{cfg['key']}/daily.csv"
        gen = None
        if a.existing_dir:
            existing_bytes = open(f"{a.existing_dir}/{cfg['key']}.daily.csv", "rb").read()
        else:
            meta = gcs_describe(uri)
            gen = str(meta["generation"])
            existing_bytes = gcs_cat(f"{uri}#{gen}")
            assert md5_b64(existing_bytes) == meta["md5_hash"], "downloaded bytes do not match generation %s" % gen
        data, merged, base, rep = build_lake(loc, cfg, a.hist_dir, existing_bytes, today)
        # cross-check against the research composite CSV (tva_pilot_history.py output), when present
        ref_path = f"{a.hist_dir}/tva_pilots/{loc}_daily.csv"
        if os.path.exists(ref_path):
            ref = pd.read_csv(ref_path)
            mine = {r[0]: r for r in merged}
            diff = [(r.date, r.elevationFt, mine[r.date][1]) for r in ref.itertuples() if r.date in mine and abs(r.elevationFt - mine[r.date][1]) > 0.0051]
            missing = [r.date for r in ref.itertuples() if r.date not in mine and r.date <= (rep["existing"]["last"] or today)]
            first_ex = rep["existing"]["first"]
            rep["research_composite_crosscheck"] = dict(
                ref_rows=int(len(ref)), value_diffs_gt_0p005=len(diff), first_diffs=diff[:3],
                all_diffs_on_dates_where_existing_wins=all(d[0] >= first_ex for d in diff),
                ref_dates_missing_from_merge=len(missing), missing_dates=missing[:5])
            rep["checks"]["research_composite_diffs_only_where_existing_wins"] = rep["research_composite_crosscheck"]["all_diffs_on_dates_where_existing_wins"]
            rep["pass"] = all(rep["checks"].values())
        rep["merged_file"] = dict(rows=len(merged), bytes=len(data), md5_b64=md5_b64(data), sha256=hashlib.sha256(data).hexdigest(),
                                  first=merged[0][0], last=merged[-1][0])
        rep["live_generation_read"] = gen
        open(f"{out_dir}/{cfg['key']}.merged.csv", "wb").write(data)
        json.dump(base, open(f"{out_dir}/{cfg['key']}.baseline.{lake_key(base['baselineVersion'])}.json", "w"))
        ok_all &= rep["pass"]
        if a.write and rep["pass"]:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = f"gs://{a.bucket}/history_backup/{cfg['key']}/daily.{ts}.csv"
            sh(["gcloud", "storage", "cp", f"{uri}#{gen}", backup])                    # exact generation that was merged
            bmeta = gcs_describe(backup)
            assert bmeta["md5_hash"] == md5_b64(existing_bytes), "backup md5 mismatch"
            tmp = f"{out_dir}/{cfg['key']}.merged.csv"
            sh(["gcloud", "storage", "cp", tmp, uri, "--content-type=text/csv", f"--if-generation-match={gen}"])
            new = gcs_describe(uri)
            back = gcs_cat(f"{uri}#{new['generation']}")
            rows_back = len(decode(back))
            verify = dict(md5_ok=new["md5_hash"] == md5_b64(data) and md5_b64(back) == md5_b64(data), rows_ok=rows_back == len(merged),
                          rows=rows_back, size=int(new["size"]))
            rep["written"] = dict(object=uri, backup=backup, backup_generation=str(bmeta["generation"]), backup_size=int(bmeta["size"]),
                                  generation_before=gen, generation_after=str(new["generation"]), size_after=int(new["size"]),
                                  size_before=len(existing_bytes), md5_b64=new["md5_hash"], crc32c=new.get("crc32c_hash"), verify=verify, utc=ts)
            ok_all &= verify["md5_ok"] and verify["rows_ok"]
            append_log(a.log, "\n### %s (%s) written %s\n\n```json\n%s\n```\n" % (cfg["lake_id"], loc, ts, json.dumps(
                dict(merged_file=rep["merged_file"], written=rep["written"], rows_by_source=rep["rows_by_source"],
                     complete_years_before=rep["baseline_before"]["completeYears"], status_before=rep["baseline_before"]["status"],
                     complete_years_after=rep["baseline_after"]["completeYears"], status_after=rep["baseline_after"]["status"]), indent=1)))
        results[loc] = rep
    json.dump(dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(), today=today, write=a.write, results=results),
              open(f"{out_dir}/report.json", "w"), indent=1, default=str)
    print(json.dumps(results, indent=1, default=str))
    print("\nMODE: %s   ALL CHECKS PASS: %s   report: %s/report.json" % ("WRITE" if a.write else "DRY RUN", ok_all, out_dir))
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
