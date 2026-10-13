#!/usr/bin/env python3
"""Lake Brain baselines thread: methodology evaluation for `doy15-percentile-v1` / `lake-level-rules-v1`.

Reproduce:  <venv>/bin/python research/lake-brain/baseline_eval.py [--quick]
Inputs (never in Git): ~/Desktop/Development/Sector_Research_Data/lake-brain/history/ (see tva_pilot_history.py,
baseline_fetch.py, guide_availability.py for how each file is acquired). Output: docs/research/lake-brain/data/baseline_summary.json
and a markdown dump of every table on stdout.

Everything here is research tooling; it re-implements the Engine's baseline (LakeLevelBaseline.swift) in numpy and
checks it against the Hartwell numbers recorded in docs/brains/LAKE_BRAIN_INTEGRATION.md §6.
"""
import os, sys, json, math, itertools, random, glob, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

ROOT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain")
HIST = f"{ROOT}/history"
REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine")
OUTJSON = f"{REPO}/docs/research/lake-brain/data/baseline_summary.json"
QUICK = "--quick" in sys.argv
RNG = np.random.default_rng(20261013)
GRID = np.array([0, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100], float)

# ----------------------------------------------------------------------------- loading
def _cwms(path):
    d = pd.read_csv(path)
    d["t"] = pd.to_datetime(d.epoch_ms, unit="ms", utc=True)
    return d.dropna(subset=["value"]).set_index("t").value

def daily_near(s, hour_utc, tol_h):
    """sub-daily UTC series -> one value/day: the reading nearest to `hour_utc` o'clock UTC (within +-tol_h)."""
    u = s.index - pd.Timedelta(hours=hour_utc)
    day = (u + pd.Timedelta(hours=12)).floor("D")
    d = pd.DataFrame({"v": s.values, "day": day.tz_localize(None), "dist": np.abs((u - day).total_seconds().values) / 3600.0})
    d = d[d.dist <= tol_h].sort_values("dist").drop_duplicates("day")
    return d.set_index("day").v.sort_index()

def qc_spikes(s, ft=12.0):
    m = s.rolling(15, center=True, min_periods=5).median()
    return s[(s - m).abs() <= ft]

def load_all():
    S = {}
    # --- Hartwell: CWMS SAS daily (00:00Z stamps)
    h = _cwms(f"{HIST}/cwms/hartwell_daily.csv"); h.index = h.index.tz_localize(None).normalize() - pd.Timedelta(days=1)  # CWMS stamps 00:00Z = prior US/Central day (matches Engine's stored history)
    S["Hartwell (USACE SAS, storage/hydro)"] = h[~h.index.duplicated()]
    # --- Kentucky Lake (TVA, big drawdown), hourly/6-hourly, midnight CST = 06Z
    k = _cwms(f"{HIST}/cwms/kentucky_lake_hourly.csv"); S["Kentucky Lake (TVA)"] = qc_spikes(daily_near(k, 6, 3.5))
    # --- Cave Run (USACE LRL flood-control), US/Eastern
    c = _cwms(f"{HIST}/cwms/caverun_hourly.csv"); S["Cave Run (USACE LRL flood control)"] = qc_spikes(daily_near(c, 5, 1.5))
    # --- Allatoona (USACE SAM, 2007+)
    a = _cwms(f"{HIST}/cwms/allatoona_hourly.csv"); S["Allatoona (USACE SAM)"] = qc_spikes(daily_near(a, 6, 1.5))
    # --- Pueblo (USACE SPA/USBR storage, west), US/Mountain
    p = _cwms(f"{HIST}/cwms/pueblo_15min.csv"); S["Pueblo Res. (USACE SPA, arid storage)"] = qc_spikes(daily_near(p, 7, 0.5))
    # --- Shasta (USBR via CWMS SPK, 2013+)
    sh = _cwms(f"{HIST}/cwms/shasta_daily.csv"); sh.index = sh.index.tz_localize(None).normalize(); S["Shasta (USBR via CWMS)"] = qc_spikes(sh[~sh.index.duplicated()])
    # --- TVA pilots composites (RVDHUN 0.1 ft + HADS/CWMS 0.01 ft)
    for loc, nm in [("GVDA1", "Guntersville"), ("WHLA1", "Wheeler"), ("WLSA1", "Wilson"), ("PICT1", "Pickwick")]:
        df = pd.read_csv(f"{HIST}/tva_pilots/{loc}_daily.csv", parse_dates=["date"]).set_index("date")
        S[f"{nm} (TVA pilot, composite)"] = df.elevationFt
    # --- natural: Lake Erie (NOAA CO-OPS Cleveland daily mean), Lake Champlain (USGS 62614)
    e = pd.concat([pd.read_csv(f, skipinitialspace=True) for f in sorted(glob.glob(f"{HIST}/noaa/erie_*.csv"))])
    e.columns = [c.strip() for c in e.columns]; e["d"] = pd.to_datetime(e["Date Time"]).dt.normalize()
    S["Lake Erie (NOAA, natural Great Lake)"] = e.drop_duplicates("d").set_index("d")["Water Level"].dropna().astype(float)
    ch = pd.read_csv(f"{HIST}/usgs/champlain_62614.csv", parse_dates=["date"]).set_index("date").value.astype(float)
    S["Lake Champlain (USGS, natural)"] = ch
    for k_ in list(S):
        s = S[k_].copy(); s.index = pd.DatetimeIndex(s.index).tz_localize(None) if getattr(s.index, "tz", None) else pd.DatetimeIndex(s.index)
        s = s[~s.index.duplicated()].sort_index(); S[k_] = s.dropna()
    return S

# ----------------------------------------------------------------------------- Engine-equivalent baseline
def to_matrix(s, complete_days=329, last_year=None):
    """Return (years list of complete years, matrix [nyears x 365]) dropping Feb 29 (doy365 mapping)."""
    s = s[~((s.index.month == 2) & (s.index.day == 29))]
    doy = s.index.dayofyear.values - ((s.index.is_leap_year) & (s.index.month > 2)).astype(int)
    yr = s.index.year.values
    cnt = pd.Series(yr).value_counts()
    cur = last_year or pd.Timestamp("2026-10-13").year
    comp = sorted(int(y) for y, n in cnt.items() if n >= complete_days and y < cur)
    M = np.full((len(comp), 365), np.nan)
    ix = {y: i for i, y in enumerate(comp)}
    for y, d, v in zip(yr, doy, s.values):
        if y in ix and 1 <= d <= 365: M[ix[y], d - 1] = v
    return comp, M

def window_vals(M, rows, doy, w):
    idx = [(doy - 1 + o) % 365 for o in range(-w, w + 1)]
    return M[np.ix_(rows, idx)].ravel()

def grid_q(vals):
    v = vals[~np.isnan(vals)]
    return np.percentile(v, GRID, method="linear") if v.size else None

def pct_of(x, q):  # percentile of x vs quantile grid (Engine: linear interpolation between grid points)
    if x <= q[0]: return 0.0
    if x >= q[-1]: return 100.0
    return float(np.interp(x, q, GRID)) if len(set(q)) == len(q) else float(np.interp(x, q + np.arange(len(q)) * 1e-9, GRID))

def hist_state(x, q):
    p10, p90, p02, p98 = q[3], q[19], q[1], q[21]
    if x < p02 or x > p98: return 2
    if x < p10 or x > p90: return 1
    return 0

def wquantiles(vals, weights, qs):
    o = np.argsort(vals); v = vals[o]; w = weights[o]; cw = (np.cumsum(w) - 0.5 * w) / w.sum()
    return np.interp(qs / 100.0, cw, v)

# ----------------------------------------------------------------------------- analyses
def inventory(S):
    rows = []
    for nm, s in S.items():
        comp, M = to_matrix(s)
        d1 = s.diff()[s.index.to_series().diff() == pd.Timedelta(days=1)].abs()
        res = np.nan
        sv = s.dropna().values[-3000:]
        for r in (0.01, 0.1, 1.0):
            if np.mean(np.abs(sv / r - np.round(sv / r)) < 1e-6) > 0.97: res = r; break
        rows.append(dict(series=nm, first=str(s.index.min().date()), last=str(s.index.max().date()), days=int(len(s)),
                         complete_years=len(comp), complete_range=f"{comp[0]}-{comp[-1]}" if comp else "-",
                         range_ft=round(float(s.max() - s.min()), 1), p05_p95_ft=round(float(s.quantile(.95) - s.quantile(.05)), 1),
                         daily_abs_change_p50=round(float(d1.median()), 3), p95=round(float(d1.quantile(.95)), 3), resolution_ft=res))
    return rows

def reproduce_hartwell(S):
    s = S["Hartwell (USACE SAS, storage/hydro)"]; s = s[s.index <= "2026-10-06"]
    comp, M = to_matrix(s, last_year=2026); basis = comp[-30:]
    rows = list(range(len(comp) - len(basis), len(comp)))
    doy = pd.Timestamp("2026-10-12").dayofyear  # 285 (2026 is not a leap year)
    q = grid_q(window_vals(M, rows, doy, 7))
    return {"basis_years": f"{basis[0]}-{basis[-1]}", "n_basis": len(basis), "p10": round(q[3], 2), "p50": round(q[11], 2), "p90": round(q[19], 2),
            "engine_doc": {"p10": 649.89, "p50": 655.58, "p90": 660.54}, "p02": round(q[1], 2), "p98": round(q[21], 2)}

def choose_targets(step=15): return list(range(8, 366, step))

def min_years(S, ks=(2, 3, 4, 5, 7, 10, 15, 20), draws=120):
    """Subsample stability: for k random complete years vs reference = the other complete years (LOYO-style)."""
    out = {}
    tg = choose_targets()
    for nm, s in S.items():
        comp, M = to_matrix(s); n = len(comp)
        if n < 7: continue
        res = {}
        for k in ks:
            if k > n - 3: continue
            err10, err90, err50, agree, unus_rate, vunus_rate, ref_unus = [], [], [], [], [], [], []
            width = []
            for _ in range(draws):
                held = int(RNG.integers(n))            # held-out year
                pool = [i for i in range(n) if i != held]
                sub = list(RNG.choice(pool, size=k, replace=False))
                for d in tg[::3] if QUICK else tg:
                    ref = grid_q(window_vals(M, pool, d, 7)); cand = grid_q(window_vals(M, sub, d, 7))
                    if ref is None or cand is None: continue
                    w_ = ref[19] - ref[3]
                    if w_ <= 0: continue
                    err10.append((cand[3] - ref[3]) / w_); err90.append((cand[19] - ref[19]) / w_); err50.append((cand[11] - ref[11]) / w_)
                    width.append(w_)
                    # classification of the held-out year's days in the window around d
                    xs = M[held, [(d - 1 + o) % 365 for o in range(-3, 4)]]
                    for x in xs[~np.isnan(xs)]:
                        a, b = hist_state(x, ref), hist_state(x, cand)
                        agree.append(a == b); unus_rate.append(b >= 1); vunus_rate.append(b == 2); ref_unus.append(a >= 1)
            res[k] = dict(edge_rmse_p10_pct_of_width=round(100 * float(np.sqrt(np.mean(np.square(err10)))), 1),
                          edge_rmse_p90_pct_of_width=round(100 * float(np.sqrt(np.mean(np.square(err90)))), 1),
                          p50_rmse_pct_of_width=round(100 * float(np.sqrt(np.mean(np.square(err50)))), 1),
                          median_width_ft=round(float(np.median(width)), 2),
                          class_agree_pct=round(100 * float(np.mean(agree)), 1),
                          unusual_rate_pct=round(100 * float(np.mean(unus_rate)), 1), ref_unusual_rate_pct=round(100 * float(np.mean(ref_unus)), 1),
                          very_unusual_rate_pct=round(100 * float(np.mean(vunus_rate)), 1))
        out[nm] = dict(n_complete_years=n, by_k=res)
    return out

def rolling_origin(S, windows=(5, 10, 20, 30, 999), halfl=(5, 10), wdays=(3, 7, 10, 14), last_n=10, step=9):
    """For each of the last `last_n` complete years Y: build baseline only from years < Y, score Y's days.
    Metrics: coverage of p10-p90 (nominal 80), p02-p98 (nominal 96), mean pinball loss over the quantile grid, mean width."""
    out = {}
    for nm, s in S.items():
        comp, M = to_matrix(s); n = len(comp)
        if n < 12: continue
        targets = list(range(n - last_n, n)) if n - last_n >= 6 else list(range(6, n))
        ev = {}
        def score(rows_fn, w, weights_fn=None):
            c80 = c96 = loss = width = cnt = 0
            for yi in targets:
                rows = rows_fn(yi)
                if len(rows) < 2: continue
                for d in range(5, 366, step):
                    xs = M[yi, d - 1]
                    if np.isnan(xs): continue
                    vals = window_vals(M, rows, d, w)
                    if weights_fn is None:
                        ok = ~np.isnan(vals)
                        if ok.sum() < 8: continue
                        q = np.percentile(vals[ok], GRID)
                    else:
                        wt = np.repeat(weights_fn(rows)[:, None], 2 * w + 1, axis=1).ravel()
                        ok = ~np.isnan(vals)
                        if ok.sum() < 8: continue
                        q = wquantiles(vals[ok], wt[ok], GRID)
                    cnt += 1
                    c80 += q[3] <= xs <= q[19]; c96 += q[1] <= xs <= q[21]
                    tau = GRID / 100.0; e = xs - q
                    loss += np.mean(np.maximum(tau * e, (tau - 1) * e)); width += q[19] - q[3]
            if cnt == 0: return None
            return dict(cov80=round(100 * c80 / cnt, 1), cov96=round(100 * c96 / cnt, 1), pinball=round(loss / cnt, 4), width80_ft=round(width / cnt, 2), n=cnt)
        r = {}
        for W in windows:
            r[f"last{W if W < 999 else 'all'}y_w7"] = score(lambda yi, W=W: list(range(max(0, yi - W), yi)), 7)
        for hl in halfl:
            r[f"all_halflife{hl}y_w7"] = score(lambda yi: list(range(0, yi)), 7, lambda rows, hl=hl: 0.5 ** ((rows[-1] - np.array(rows)) / hl))
        for w in wdays:
            r[f"last30y_w{w}"] = score(lambda yi: list(range(max(0, yi - 30), yi)), w)
        out[nm] = dict(n_complete_years=n, target_years=[comp[i] for i in targets], results=r)
    return out

def bands_and_extremes(S):
    """(a) Realised UNUSUAL / VERY_UNUSUAL frequency under rolling origin (all prior years), band choices.
       (b) extreme-year sensitivity: drop the 2 most extreme years (by annual mean z) from the basis."""
    out = {}
    for nm, s in S.items():
        comp, M = to_matrix(s); n = len(comp)
        if n < 12: continue
        ann = np.nanmean(M, axis=1); z = (ann - np.nanmean(ann)) / (np.nanstd(ann) + 1e-9)
        bands = {"p10-p90": (3, 19), "p05-p95": (2, 20), "p02-p98": (1, 21)}
        freq = {k: 0 for k in bands}; cnt = 0
        shift10, shift90, shift50, wid = [], [], [], []
        for yi in range(max(6, n - 10), n):
            rows = list(range(max(0, yi - 30), yi))
            for d in range(5, 366, 9):
                x = M[yi, d - 1]
                if np.isnan(x): continue
                q = grid_q(window_vals(M, rows, d, 7))
                if q is None: continue
                cnt += 1
                for k, (a, b) in bands.items(): freq[k] += (x < q[a]) or (x > q[b])
        # extreme-year sensitivity on the full 30-year basis
        basis = list(range(max(0, n - 30), n)); ext = sorted(basis, key=lambda i: -abs(z[i]))[:2]
        keep = [i for i in basis if i not in ext]
        for d in range(5, 366, 9):
            q1 = grid_q(window_vals(M, basis, d, 7)); q2 = grid_q(window_vals(M, keep, d, 7))
            if q1 is None or q2 is None: continue
            shift10.append(q2[3] - q1[3]); shift90.append(q2[19] - q1[19]); shift50.append(q2[11] - q1[11]); wid.append(q1[19] - q1[3])
        out[nm] = dict(realised_outside_band_pct={k: round(100 * v / cnt, 1) for k, v in freq.items()},
                       nominal_pct={"p10-p90": 20, "p05-p95": 10, "p02-p98": 4},
                       extreme_years_dropped=[comp[i] for i in ext],
                       drop2_extreme_median_shift_p10_ft=round(float(np.median(shift10)), 3), drop2_median_shift_p90_ft=round(float(np.median(shift90)), 3),
                       drop2_median_shift_p50_ft=round(float(np.median(shift50)), 3), drop2_max_abs_shift_ft=round(float(np.max(np.abs(shift10 + shift90))), 2),
                       median_band_width_ft=round(float(np.median(wid)), 2))
    return out

def structural_change(S):
    """Does the seasonal baseline move? compare the first and last decades of the record (median |p50 shift|, band shift)."""
    out = {}
    for nm, s in S.items():
        comp, M = to_matrix(s); n = len(comp)
        if n < 20: continue
        early, late = list(range(0, 10)), list(range(n - 10, n))
        d50, d10, d90, wd = [], [], [], []
        for d in range(5, 366, 9):
            a, b = grid_q(window_vals(M, early, d, 7)), grid_q(window_vals(M, late, d, 7))
            if a is None or b is None: continue
            d50.append(b[11] - a[11]); d10.append(b[3] - a[3]); d90.append(b[19] - a[19]); wd.append(a[19] - a[3])
        out[nm] = dict(first10=f"{comp[0]}-{comp[9]}", last10=f"{comp[n-10]}-{comp[-1]}", median_p50_shift_ft=round(float(np.median(d50)), 2),
                       median_abs_p50_shift_ft=round(float(np.median(np.abs(d50))), 2), max_abs_p50_shift_ft=round(float(np.max(np.abs(d50))), 2),
                       shift_as_pct_of_band_width=round(100 * float(np.median(np.abs(d50)) / np.median(wd)), 1))
    return out

# ----------------------------------------------------------------------------- guide-relative vs history
def guide_vs_history(S):
    """Is the operator guide more informative than the historical percentile? (managed lakes)
    guide sources: Hartwell CWMS Elev-GC daily archive; Allatoona CWMS guide curve (2017+); TVA operating guide template
    (GuideCurve; Wilson has none -> zone only). Metrics use leave-one-year-out historical baselines (<=30 other years)."""
    from scipy.stats import spearmanr
    out = {}
    g, zone = {}, {}
    gh = pd.read_csv(f"{HIST}/cwms/hartwell_gc_daily.csv").dropna(subset=["value"])
    gh["d"] = pd.to_datetime(gh.epoch_ms, unit="ms").dt.normalize() - pd.Timedelta(days=1); g["Hartwell (USACE SAS, storage/hydro)"] = gh.drop_duplicates("d").set_index("d").value
    ga = pd.read_csv(f"{HIST}/cwms/allatoona_gc_daily.csv").dropna(subset=["value"])
    ga["d"] = pd.to_datetime(ga.epoch_ms, unit="ms", utc=True).dt.tz_convert("Etc/GMT+6").dt.tz_localize(None).dt.normalize(); g["Allatoona (USACE SAM)"] = ga.drop_duplicates("d").set_index("d").value
    for nm, loc in [("Guntersville (TVA pilot, composite)", "GVDA1"), ("Wheeler (TVA pilot, composite)", "WHLA1"), ("Wilson (TVA pilot, composite)", "WLSA1"), ("Pickwick (TVA pilot, composite)", "PICT1")]:
        fp = f"{HIST}/tva_guides/{loc}.json"
        if not os.path.exists(fp): continue
        t = pd.DataFrame(json.load(open(fp))["items"]); t["md"] = pd.to_datetime("2001/" + t.Day.str[:5], format="%Y/%m/%d", errors="coerce")
        t = t.dropna(subset=["md"]); t["doy365"] = t.md.dt.dayofyear; t = t.drop_duplicates("doy365").set_index("doy365")
        sx = S[nm]; doy = sx.index.dayofyear - ((sx.index.is_leap_year) & (sx.index.month > 2)).astype(int)
        if "GuideCurve" in t.columns and (t.GuideCurve > 0).any():
            g[nm] = pd.Series(t.GuideCurve.reindex(doy).values, index=sx.index).dropna()
        zone[nm] = (pd.Series(t.BtmOpZone.reindex(doy).values, index=sx.index), pd.Series(t.TopOpZone.reindex(doy).values, index=sx.index))
    for nm in sorted(set(g) | set(zone)):
        s = S[nm]; comp, M = to_matrix(s); n = len(comp)
        gc = g.get(nm); bz, tz = zone.get(nm, (None, None))
        rows_out = []
        for t, x in s.items():
            y = t.year
            if y not in comp or (t.month == 2 and t.day == 29): continue
            if gc is not None and t not in gc.index and bz is None: continue
            yi = comp.index(y); rows = [i for i in range(n) if i != yi][-30:]
            if len(rows) < 4: continue
            doy = t.dayofyear - (1 if (t.is_leap_year and t.month > 2) else 0)
            q = grid_q(window_vals(M, rows, doy, 7))
            if q is None: continue
            rows_out.append((t, x, pct_of(x, q), q[11], gc.get(t, np.nan) if gc is not None else np.nan,
                             bz.get(t, np.nan) if bz is not None else np.nan, tz.get(t, np.nan) if tz is not None else np.nan))
        df = pd.DataFrame(rows_out, columns=["t", "x", "pct", "p50", "gc", "bz", "tz"]).dropna(subset=["x"])
        r = dict(years=f"{df.t.dt.year.min()}-{df.t.dt.year.max()}", n_days=int(len(df)))
        if df.gc.notna().sum() > 100:
            d = df.dropna(subset=["gc"]); an = d.x - d.gc
            wid = d.p50 * 0  # placeholder to keep alignment
            r.update(guide_n_days=int(len(d)), guide_minus_p50_median_abs_ft=round(float((d.gc - d.p50).abs().median()), 2), spearman_pct_vs_guide_anomaly=round(float(spearmanr(d.pct, an).correlation), 3),
                     rmse_vs_guide_ft=round(float(np.sqrt(np.mean(an ** 2))), 2), rmse_vs_hist_p50_ft=round(float(np.sqrt(np.mean((d.x - d.p50) ** 2))), 2),
                     guide_anom_p10_p50_p90_ft=[round(float(np.percentile(an, q_)), 2) for q_ in (10, 50, 90)])
        if df.bz.notna().sum() > 100:
            d = df.dropna(subset=["bz", "tz"]); d = d[(d.bz > 0) & (d.tz > 0)]
            below, above = d.x < d.bz - 1e-9, d.x > d.tz + 1e-9; inz = ~(below | above)
            hl, hh = d.pct < 10, d.pct > 90; hn = ~(hl | hh)
            r.update(zone_n_days=int(len(d)), pct_in_zone=round(100 * float(inz.mean()), 1), pct_hist_normal=round(100 * float(hn.mean()), 1),
                     zone_vs_hist_agreement_pct=round(100 * float(((inz & hn) | (below & hl) | (above & hh)).mean()), 1),
                     in_zone_but_hist_unusual_pct=round(100 * float((inz & ~hn).sum() / max(1, (inz).sum())), 1),
                     out_of_zone_but_hist_normal_pct=round(100 * float(((~inz) & hn).sum() / max(1, (~inz).sum())), 1),
                     below_zone_hist_low_pct=round(100 * float((below & hl).sum() / max(1, below.sum())), 1),
                     above_zone_hist_high_pct=round(100 * float((above & hh).sum() / max(1, above.sum())), 1),
                     spearman_pct_vs_zone_position=round(float(spearmanr(d.pct, (d.x - (d.bz + d.tz) / 2)).correlation), 3))
        out[nm] = r
    return out

# ----------------------------------------------------------------------------- STABLE rule
def hourly_sets():
    H = {}
    H["Pickwick (TVA, CWMS hourly)"] = (_cwms(f"{HIST}/cwms/pickwick_lake_hourly.csv"), (406, 420), "2020-01-01")
    H["Kentucky Lake (TVA, hourly)"] = (_cwms(f"{HIST}/cwms/kentucky_lake_hourly.csv"), (350, 380), "2012-06-01")
    H["Cave Run (USACE LRL, hourly)"] = (_cwms(f"{HIST}/cwms/caverun_hourly.csv"), (700, 800), "2010-01-01")
    H["Allatoona (USACE SAM, hourly)"] = (_cwms(f"{HIST}/cwms/allatoona_hourly.csv"), (800, 900), "2010-01-01")
    H["Pueblo (15-min)"] = (_cwms(f"{HIST}/cwms/pueblo_15min.csv"), (4600, 5000), "2010-01-01")
    for loc, nm in [("GVDA1", "Guntersville"), ("WHLA1", "Wheeler"), ("WLSA1", "Wilson")]:
        fs = sorted(glob.glob(f"{HIST}/hads/{loc}_*.csv"))
        x = pd.concat([pd.read_csv(f, usecols=["utc_valid", "HPIRZZZ"]) for f in fs]).dropna()
        x["t"] = pd.to_datetime(x.utc_valid, utc=True); x = x[x.HPIRZZZ > 100].drop_duplicates("t").set_index("t").HPIRZZZ
        H[f"{nm} (TVA, HADS hourly)"] = (x, (400, 700), "2022-11-01")
    return H

def stable_rule(minpts=20):
    H = hourly_sets()
    res = {}
    for nm, (s, (lo, hi), start) in H.items():
        s = s[(s > lo) & (s < hi)]
        s = s[s.index >= pd.Timestamp(start, tz="UTC")]
        h = s.resample("1h").mean() if s.index.to_series().diff().median() < pd.Timedelta(hours=1) else s
        h = h.dropna()
        # 24h change at each hour using exact 24h lag (+-30 min)
        hh = h.resample("1h").nearest(limit=1) if False else h.reindex(pd.date_range(h.index.min().floor("h"), h.index.max(), freq="1h", tz="UTC"))
        d24 = (hh - hh.shift(24)).dropna()
        a = d24.abs()
        # noise: robust sigma of hour-to-hour second differences (removes slow trend), converted to sigma of a 24h difference
        d1 = hh.diff(); d2 = d1.diff().dropna()
        sig_noise = 1.4826 * np.median(np.abs(d2 - np.median(d2))) / math.sqrt(6)    # var(second diff of white noise)=6 sigma^2
        # one reading per day at 00:00 local-ish (06 UTC) for the day-level classification tests
        dayv = a[a.index.hour == 6]
        month = dayv.index.month
        seas = dayv.groupby(((dayv.index.dayofyear - 1) // 15)).transform("median")  # crude seasonal p50 (15-day bins) for current rule
        cur_thr = np.maximum(0.10, seas)
        row = dict(n_days=int(len(dayv)), abs_d24_p50=round(float(dayv.median()), 3), p75=round(float(dayv.quantile(.75)), 3), p90=round(float(dayv.quantile(.90)), 3),
                   p95=round(float(dayv.quantile(.95)), 3), noise_sigma_hourly_ft=round(float(sig_noise), 4),
                   sigma_of_24h_diff_from_noise_ft=round(float(sig_noise * math.sqrt(2)), 4),
                   median_seasonal_p50=round(float(seas.median()), 3),
                   current_rule_share_stable_pct=round(100 * float((dayv <= cur_thr).mean()), 1),
                   share_le_0p05=round(100 * float((dayv <= .05).mean()), 1), share_le_0p10=round(100 * float((dayv <= .10).mean()), 1),
                   share_le_0p15=round(100 * float((dayv <= .15).mean()), 1), share_le_0p25=round(100 * float((dayv <= .25).mean()), 1),
                   # of days that the current rule calls STABLE, how many have |d24| above 0.25 / 0.5 ft (i.e. would be a visible 3-6 inch/day move)
                   stable_but_gt_0p25=round(100 * float(((dayv <= cur_thr) & (dayv > .25)).sum() / max(1, (dayv <= cur_thr).sum())), 1),
                   stable_but_gt_0p50=round(100 * float(((dayv <= cur_thr) & (dayv > .50)).sum() / max(1, (dayv <= cur_thr).sum())), 1),
                   seasonal_p50_gt_0p10_share_days=round(100 * float((seas > .10).mean()), 1),
                   # persistence: 3-day net / sign agreement for the same day (is a 'STABLE' day part of a sustained move?)
                   )
        d3 = (hh - hh.shift(72)).reindex(dayv.index).abs()
        row["stable_by_current_but_3day_net_gt_0p5ft_pct"] = round(100 * float(((dayv <= cur_thr) & (d3 > 0.5)).sum() / max(1, (dayv <= cur_thr).sum())), 1)
        # month-wise share of days with seasonal p50 > 0.10 (when the p50 term dominates the floor)
        row["months_where_seasonal_p50_exceeds_floor"] = sorted(set(int(m) for m in month[(seas > .10).values]))
        res[nm] = row
    return res

def _seasonal_stat(dayv, fn):
    """per-calendar-day statistic of |d24| over a +-7 day window (all years in the sample)"""
    doy = dayv.index.dayofyear.values - ((dayv.index.is_leap_year) & (dayv.index.month > 2)).astype(int)
    vals = dayv.values; out = np.full(365, np.nan)
    byd = [[] for _ in range(365)]
    for d, v in zip(doy, vals):
        if 1 <= d <= 365: byd[d - 1].append(v)
    for d in range(365):
        w = [v for o in range(-7, 8) for v in byd[(d + o) % 365]]
        if len(w) >= 20: out[d] = fn(np.array(w))
    return pd.Series(out[doy - 1], index=dayv.index)

def stable_alternatives():
    """Compare trendState rules on the instrument-resolution series (hourly for reservoirs, daily mean for natural lakes)."""
    H = hourly_sets(); D = {}
    for nm, (s, (lo, hi), start) in H.items():
        s = s[(s > lo) & (s < hi)]; s = s[s.index >= pd.Timestamp(start, tz="UTC")]
        hh = s.resample("1h").mean().reindex(pd.date_range(s.index.min().floor("h"), s.index.max(), freq="1h", tz="UTC"))
        d24 = (hh - hh.shift(24)); d72 = (hh - hh.shift(72))
        pick = d24[d24.index.hour == 6].dropna()
        D[nm] = (pick, d72.reindex(pick.index))
    S = load_all()
    for nm in ("Lake Erie (NOAA, natural Great Lake)", "Lake Champlain (USGS, natural)"):
        x = S[nm]; x = x[x.index >= "2012-01-01"]; x = x.asfreq("D")
        D[nm + " [daily mean]"] = ((x - x.shift(1)).dropna(), (x - x.shift(3)).reindex((x - x.shift(1)).dropna().index))
    res = {}
    for nm, (d, d3) in D.items():
        a = d.abs()
        if len(a) < 200: continue
        p50 = _seasonal_stat(a, np.median); p95 = _seasonal_stat(a, lambda v: np.percentile(v, 95))
        rules = {"R0 current: max(0.10, seasonal p50)": np.maximum(0.10, p50),
                 "A 0.05 ft": pd.Series(0.05, index=a.index), "A 0.10 ft": pd.Series(0.10, index=a.index),
                 "A 0.15 ft": pd.Series(0.15, index=a.index), "A 0.25 ft": pd.Series(0.25, index=a.index),
                 "R5 max(0.05, 0.5*seasonal p50)": np.maximum(0.05, 0.5 * p50)}
        a3 = (d3.abs() / 3.0).reindex(a.index)   # mean daily rate over the last 72 h
        rapid_cur = a > p95; rapid_new = a > np.maximum(p95, 0.25)
        rr = {}
        for k, thr in rules.items():
            st = a <= thr
            flips = float((st.astype(int).diff().abs() > 0).mean())
            rr[k] = dict(stable_pct=round(100 * float(st.mean()), 1),
                         false_stable_3d_net_ge_0p3ft_pct=round(100 * float((st & (d3.abs() >= 0.3)).sum() / max(1, st.sum())), 1),
                         stable_but_d24_gt_0p25_pct=round(100 * float((st & (a > 0.25)).sum() / max(1, st.sum())), 1),
                         label_flip_rate_pct=round(100 * flips, 1))
        for k, thr in {"T72 |72h net|/3 <= 0.10 ft/day": 0.10, "T72 |72h net|/3 <= 0.15 ft/day": 0.15}.items():
            ok = a3.notna(); st = (a3 <= thr)[ok]
            rr[k] = dict(stable_pct=round(100 * float(st.mean()), 1), false_stable_3d_net_ge_0p3ft_pct=round(100 * float((st & (d3.abs()[ok] >= 0.3)).sum() / max(1, st.sum())), 1),
                         stable_but_d24_gt_0p25_pct=round(100 * float((st & (a[ok] > 0.25)).sum() / max(1, st.sum())), 1),
                         label_flip_rate_pct=round(100 * float((st.astype(int).diff().abs() > 0).mean()), 1))
        res[nm] = dict(n_days=int(len(a)), abs_d24_p50=round(float(a.median()), 3), p90=round(float(a.quantile(.9)), 3), p95=round(float(a.quantile(.95)), 3),
                       rapid_share_current_pct=round(100 * float(rapid_cur.mean()), 1), rapid_share_with_0p25_min_pct=round(100 * float(rapid_new.mean()), 1),
                       median_seasonal_p95=round(float(p95.median()), 3), rules=rr)
    return res

def time_basis():
    """Effect of the daily-value time-of-day (00:00 vs 07:00 local) on level and on STABLE/percentile outcomes (TVA HADS hourly)."""
    out = {}
    for loc, nm in [("GVDA1", "Guntersville"), ("WHLA1", "Wheeler"), ("WLSA1", "Wilson"), ("PICT1", "Pickwick")]:
        fs = sorted(glob.glob(f"{HIST}/hads/{loc}_*.csv"))
        x = pd.concat([pd.read_csv(f, usecols=["utc_valid", "HPIRZZZ"]) for f in fs]).dropna()
        x["t"] = pd.to_datetime(x.utc_valid, utc=True); x = x[x.HPIRZZZ > 100].drop_duplicates("t").set_index("t").HPIRZZZ
        lt = x.copy(); lt.index = lt.index.tz_convert("America/Chicago")
        m0 = lt[lt.index.hour == 0]; m7 = lt[lt.index.hour == 7]
        m0.index = m0.index.tz_localize(None).normalize(); m7.index = m7.index.tz_localize(None).normalize()
        j = pd.concat([m0.rename("a"), m7.rename("b")], axis=1, sort=True).dropna(); dd = (j.b - j.a)
        # band-edge effect: p10/p50/p90 (+-7d window, 2023-2025) from 00:00 vs 07:00 values
        edges = {}
        for lab, ser in (("00", j.a), ("07", j.b)):
            sdf = ser[(ser.index.year >= 2023) & (ser.index.year <= 2025)]
            comp, M = to_matrix(sdf, complete_days=300, last_year=2026)
            edges[lab] = np.array([grid_q(window_vals(M, list(range(len(comp))), d, 7))[[3, 11, 19]] for d in range(8, 366, 15) if grid_q(window_vals(M, list(range(len(comp))), d, 7)) is not None])
        sh = np.abs(edges["07"] - edges["00"])
        out[nm] = dict(n=int(len(j)), mean_abs_diff_00_vs_07_ft=round(float(dd.abs().mean()), 3), p95_abs_ft=round(float(dd.abs().quantile(.95)), 3),
                       bias_ft=round(float(dd.mean()), 3), baseline_p10_p50_p90_median_abs_shift_ft=[round(float(np.median(sh[:, i])), 3) for i in range(3)],
                       baseline_max_abs_shift_ft=round(float(sh.max()), 2))
    return out

def pilot_state_now(S):
    """What Lake Brain would publish today (2026-10-13) for the pilots if the composite deep history were adopted."""
    out = {}
    for nm, k in [("Guntersville (TVA pilot, composite)", "Guntersville_AL"), ("Wheeler (TVA pilot, composite)", "Wheeler_AL"),
                  ("Wilson (TVA pilot, composite)", "Wilson_AL"), ("Pickwick (TVA pilot, composite)", "Pickwick_Lake_TN")]:
        live = pd.read_csv(f"{HIST}/lakebrain_gcs/{k}.csv", parse_dates=["date"]).set_index("date").elevationFt
        x = float(live.iloc[-1]); day = live.index[-1]
        comp, M = to_matrix(S[nm], last_year=2026); rows = list(range(max(0, len(comp) - 30), len(comp)))
        doy = day.dayofyear - (1 if day.is_leap_year and day.month > 2 else 0)
        q = grid_q(window_vals(M, rows, doy, 7))
        st = ["NORMAL", "UNUSUAL", "VERY_UNUSUAL"][hist_state(x, q)]
        out[nm.split(" (")[0]] = dict(date=str(day.date()), level_ft=x, basis_years=f"{comp[rows[0]]}-{comp[rows[-1]]}", n_basis_years=len(rows),
                                      p02=round(q[1], 2), p10=round(q[3], 2), p50=round(q[11], 2), p90=round(q[19], 2), p98=round(q[21], 2),
                                      percentile=round(pct_of(x, q), 1), historicalState=st,
                                      current_history_days=int(len(live)), current_complete_years=int(sum(1 for y, n in live.groupby(live.index.year).size().items() if n >= 329 and y < 2026)))
    return out

# ----------------------------------------------------------------------------- run
def main():
    S = load_all()
    summary = {"generated": pd.Timestamp.now(tz="UTC").isoformat(), "series_inventory": inventory(S)}
    summary["engine_reproduction_hartwell"] = reproduce_hartwell(S)
    print(json.dumps(summary["engine_reproduction_hartwell"], indent=1))
    summary["min_years"] = min_years(S, draws=40 if QUICK else 150)
    summary["rolling_origin"] = rolling_origin(S, last_n=6 if QUICK else 10, step=18 if QUICK else 9)
    summary["bands_extremes"] = bands_and_extremes(S)
    summary["structural_change"] = structural_change(S)
    try: summary["guide_vs_history"] = guide_vs_history(S)
    except Exception as ex: summary["guide_vs_history"] = {"error": repr(ex)}
    summary["stable_rule"] = stable_rule()
    summary["stable_alternatives"] = stable_alternatives()
    summary["time_basis_00_vs_07_local"] = time_basis()
    summary["pilot_state_now"] = pilot_state_now(S)
    vp = f"{HIST}/tva_pilots/validation_summary.json"
    if os.path.exists(vp):  # written by tva_pilot_history.py
        v = json.load(open(vp))
        summary["tva_pilot_history"] = {k: {x: y[x] for x in ("rvdhun_first", "rvdhun_last", "rvdhun_days", "hads_first", "hads_last", "hads_vs_tva_guide", "cwms_vs_tva_guide",
                                                             "rvdhun_vs_cwms_7am", "composite_first", "composite_last", "composite_days", "complete_years_ge329", "composite_per_year") if x in y} for k, y in v.items()}
    gp = f"{HIST}/guide_availability_cwms.json"
    if os.path.exists(gp):  # written by guide_availability.py
        summary["guide_availability_totals"] = json.load(open(gp))["totals"]
    os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
    json.dump(summary, open(OUTJSON, "w"), indent=1, default=str)
    print("wrote", OUTJSON)

if __name__ == "__main__":
    main()
