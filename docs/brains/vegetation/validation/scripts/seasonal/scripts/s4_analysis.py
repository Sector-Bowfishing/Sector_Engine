"""Seasonal back-test analysis: observability, cloud-gap, climatology, states, LOYO vs baselines, gate, peak timing. Writes out/analysis.json + out/tables/*.csv"""
import json, math, datetime as dt, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from common import *
RNG = np.random.default_rng(20260713)
ORDER = ["DORMANT", "EMERGING", "GROWING", "PEAK", "DECLINING"]; IDX = {s: i for i, s in enumerate(ORDER)}
LVL = {"DORMANT": "low", "PEAK": "high", "EMERGING": "mid", "GROWING": "mid", "DECLINING": "mid"}
NB = 23; BW = 16.0                      # climatology: 16-day DOY bins
U_LO, U_HI = 0.2, 0.8; U_MID = 0.5      # state thresholds on the lake-relative position u
DIR_WIN = 40; DIR_MIN = 0.10            # observed-direction neighbourhood (days) and flat threshold (fraction of lake amplitude)
MIN_OBS_YEAR = 6; MIN_YEARS = 4; MIN_EVAL = 40; SIGNAL_MIN = 0.02
CAL = {12: "DORMANT", 1: "DORMANT", 2: "DORMANT", 3: "EMERGING", 4: "EMERGING", 5: "GROWING", 6: "GROWING", 7: "PEAK", 8: "PEAK", 9: "DECLINING", 10: "DECLINING", 11: "DECLINING"}
def cdist(a, b): d = abs(IDX[a]-IDX[b]); return min(d, 5-d)

def load(lk):
    df = pd.DataFrame([json.loads(l) for l in open(H/f"out/scenes_{lk}.jsonl")]); df["date"] = pd.to_datetime(df.date)
    df["year"] = df.date.dt.year; df["month"] = df.date.dt.month; df["doy"] = df.date.dt.dayofyear
    for c in ("cov", "belt_share", "lake_share"):
        if c not in df: df[c] = np.nan
    try: B = json.load(open(H/f"out/baselines_{lk}.json"))
    except Exception: B = {}
    def base(d, s):
        if not isinstance(s, list): return None
        e = B.get(d, {}); k = "c1" if "c1" in s else "l2a"; v = e.get(k) or [None]
        return v[0]
    df["base"] = [base(d, s) for d, s in zip(df.date.dt.strftime("%Y-%m-%d"), df.get("src", [None]*len(df)))]
    df["legacy"] = [(isinstance(b, str) and b < "04.00") for b in df.base]
    return df.sort_values("date").reset_index(drop=True)

# ---------- climatology ----------
def build_curve(doys, vals, years):
    per = {}
    for d, v, y in zip(doys, vals, years): per.setdefault((y, min(int((d-1)//BW), NB-1)), []).append(v)
    bm = [[] for _ in range(NB)]
    for (y, b), v in per.items(): bm[b].append(np.median(v))
    c = np.array([np.median(x) if len(x) >= 2 else np.nan for x in bm])
    if np.isnan(c).all(): return None
    ok = ~np.isnan(c); xs = np.arange(NB)
    xx = np.concatenate([xs[ok]-NB, xs[ok], xs[ok]+NB]); yy = np.tile(c[ok], 3)
    c = np.interp(xs, xx, yy)
    cs = np.array([(c[(i-1) % NB]+c[i]+c[(i+1) % NB])/3 for i in range(NB)])
    return cs
def curve_at(cs, doy):
    pos = (np.asarray(doy)-1)/BW - 0.5; i0 = np.floor(pos).astype(int); f = pos-i0
    return cs[i0 % NB]*(1-f)+cs[(i0+1) % NB]*f
def phase_rising(cs, doy):
    p = int(np.argmax(cs)); q = int(np.argmin(cs)); b = ((np.asarray(doy)-1)/BW) % NB
    span = (p-q) % NB; off = (b-q) % NB
    return off < span
def label(u, dirn):
    if u < U_LO: return "DORMANT"
    if u >= U_HI: return "PEAK"
    if dirn is None or dirn == 0: return None
    if dirn < 0: return "DECLINING"
    return "EMERGING" if u < U_MID else "GROWING"
def obs_dir(t, v, i, amp, causal=False):
    ti = t[i]; prior = [v[j] for j in range(len(t)) if 0 < (ti-t[j]) <= DIR_WIN]
    later = [] if causal else [v[j] for j in range(len(t)) if 0 < (t[j]-ti) <= DIR_WIN]
    if prior and later: d = np.mean(later)-np.mean(prior)
    elif prior: d = v[i]-np.mean(prior)
    elif later: d = np.mean(later)-v[i]
    else: return None
    return 0 if abs(d)/amp < DIR_MIN else int(np.sign(d))

# ---------- GDD proxy ----------
def d100(lk):
    a = json.load(open(H/f"out/airtemp_{lk}.json")); s = pd.Series(a["t"], index=pd.to_datetime(a["time"])).astype(float)
    out = {}
    for y in range(2016, 2026):
        x = s[str(y)].clip(lower=10)-10; c = x.fillna(0).cumsum(); hit = np.where(c.values >= 100)[0]
        out[y] = int(hit[0])+1 if len(hit) else 366
    return out

def loyo(df, lk, col="belt_share", gdd=False, modern=False):
    a = df[(df.status == "ACCEPTED") & df[col].notna() & (~df.legacy if modern else True)].copy()
    t = (a.date - pd.Timestamp("2017-01-01")).dt.days.values.astype(float); v = a[col].values; yrs = a.year.values; doy = a.doy.values; dates = a.date.values
    cnt = pd.Series(yrs).value_counts(); ty = sorted(y for y, n in cnt.items() if n >= MIN_OBS_YEAR)
    info = dict(lake=lk, series=col, n_acc=len(a), years_with_obs=sorted(int(y) for y in cnt.index), testable_years=[int(y) for y in ty])
    if len(ty) < MIN_YEARS: info["verdict_reason"] = f"only {len(ty)} years with >= {MIN_OBS_YEAR} accepted scenes"; return info, []
    dd = d100(lk) if gdd else None
    rows = []
    for yh in ty:
        tr = [y for y in ty if y != yh]; mtr = np.isin(yrs, tr)
        if gdd:
            med = np.median([dd[y] for y in tr]); shift = {y: dd[y]-med for y in set(ty)}
            wd = np.array([((d-1-shift[y]) % 365)+1 for d, y in zip(doy, yrs)])   # thermal-time-warped DOY
        else: wd = doy.astype(float)
        cs = build_curve(wd[mtr], v[mtr], yrs[mtr])
        if cs is None: continue
        lo, hi = float(cs.min()), float(cs.max()); amp = hi-lo
        if hi < SIGNAL_MIN or amp <= 0: info["no_signal_fold"] = True; continue
        for i in np.where(yrs == yh)[0]:
            u = float(np.clip((v[i]-lo)/amp, 0, 1)); dr = obs_dir(t, v, i, amp)
            ol = label(u, dr)
            if ol is None: continue
            uc = float((curve_at(cs, wd[i])-lo)/amp); uc = min(max(uc, 0), 1)
            cl = label(uc, 1 if phase_rising(cs, wd[i]) else -1)
            pl = None; age = None
            if i > 0:
                pdr = obs_dir(t, v, i-1, amp, causal=True); pu = float(np.clip((v[i-1]-lo)/amp, 0, 1)); pl = label(pu, pdr); age = float(t[i]-t[i-1])
            rows.append(dict(lake=lk, date=str(dates[i])[:10], year=int(yh), month=int(pd.Timestamp(dates[i]).month), obs=ol, clim=cl, cal=CAL[int(pd.Timestamp(dates[i]).month)], pers=pl, age=age, u=u, uc=uc))
    return info, rows

def agree(rows, a, b):
    r = [x for x in rows if x[a] is not None and x[b] is not None]
    if not r: return dict(n=0, exact=np.nan, w1=np.nan)
    ex = np.mean([x[a] == x[b] for x in r]); w1 = np.mean([cdist(x[a], x[b]) <= 1 for x in r])
    return dict(n=len(r), exact=float(ex), w1=float(w1))
def lvl_agree(rows, a, b):
    r = [x for x in rows if x[a] is not None and x[b] is not None]
    return float(np.mean([LVL[x[a]] == LVL[x[b]] for x in r])) if r else np.nan

if __name__ == "__main__":
    out = dict(lakes={}); allrows = {}; tabs = {}
    for lk, cls, lab in LAKES:
        df = load(lk); W = json.load(open(H/"out/windows.json"))[lk]; plan = json.load(open(H/f"out/fetchplan_{lk}.json"))
        L = dict(label=lab, cls=cls, n_dates=len(df), status=df.status.value_counts().to_dict(), bin=plan["bin"], window_km=W["windowKm"])
        # ---- observability by month (STAC dates, tile cloud<85) ----
        mo = df.groupby("month").status.value_counts().unstack(fill_value=0).reindex(range(1, 13), fill_value=0)
        for c in ["NODATA", "ICE", "CLOUD", "REFUSED", "FALLBACK", "ACCEPTED", "SKIPPED_SUBSAMPLE", "ERR"]:
            if c not in mo: mo[c] = 0
        read = mo.ACCEPTED+mo.FALLBACK+mo.REFUSED; pacc = (mo.ACCEPTED/read.replace(0, np.nan)).fillna(0)
        nyrs = df.year.nunique()
        mo["acc_est"] = mo.ACCEPTED+mo.SKIPPED_SUBSAMPLE*pacc
        mo["acc_per_year_est"] = mo.acc_est/9.0; mo["acc_per_year_raw"] = mo.ACCEPTED/9.0
        mo["tot"] = mo[["NODATA", "ICE", "CLOUD", "REFUSED", "FALLBACK", "ACCEPTED", "SKIPPED_SUBSAMPLE"]].sum(axis=1)
        tabs[lk] = mo; L["monthly"] = mo.round(3).reset_index().to_dict("records")
        # ---- observation age / gaps ----
        acc = df[df.status == "ACCEPTED"].date.values
        days = pd.date_range(pd.Timestamp(acc[0]), "2025-12-31") if len(acc) else []
        def ages(accdates):
            ad = np.sort(np.array(accdates, dtype="datetime64[D]")); dd_ = np.array(days, dtype="datetime64[D]")
            j = np.searchsorted(ad, dd_, side="right")-1; return (dd_-ad[j]).astype(int)
        ag_raw = ages(acc); dfm = pd.DatetimeIndex(days).month.values
        # imputed: skipped dates accepted w.p. pacc(month)
        skip = df[df.status == "SKIPPED_SUBSAMPLE"]; ags = []
        for _ in range(20):
            keep = [d for d, m in zip(skip.date.values, skip.month.values) if RNG.random() < pacc.loc[m]]
            ags.append(ages(np.concatenate([acc, np.array(keep, dtype="datetime64[ns]")])))
        ag_imp = np.mean(ags, axis=0) if False else np.concatenate([a[None] for a in ags], 0)
        def amstats(ag, m):
            x = ag[dfm == m]; return dict(med=float(np.median(x)), p90=float(np.percentile(x, 90)), p95=float(np.percentile(x, 95)), mx=int(x.max()), gt14=float((x > 14).mean()), gt30=float((x > 30).mean()))
        L["age_raw"] = {m: amstats(ag_raw, m) for m in range(1, 13)}
        L["age_imp"] = {m: {k: float(np.mean([amstats(a, m)[k] for a in ags])) for k in ("med", "p90", "p95", "mx", "gt14", "gt30")} for m in range(1, 13)}
        gaps = np.diff(np.sort(acc).astype("datetime64[D]")).astype(int); L["gap_all"] = dict(n=len(gaps), med=float(np.median(gaps)) if len(gaps) else None, p90=float(np.percentile(gaps, 90)) if len(gaps) else None, mx=int(gaps.max()) if len(gaps) else None)
        rd = df[df["cov"].notna()]
        L["acc_by_baseline"] = {("legacy(<04.00)" if lg else "modern(>=04.00)"): dict(n=int(len(g)), acc=float((g.status == "ACCEPTED").mean())) for lg, g in rd.groupby("legacy")}
        # ---- belt/lake series stats ----
        a = df[(df.status == "ACCEPTED")]
        L["n_accepted"] = int(len(a)); L["n_belt_ok"] = int(a.belt_share.notna().sum()); L["n_lake_ok"] = int(a.lake_share.notna().sum())
        L["acc_years"] = a.year.value_counts().sort_index().to_dict()
        L["belt_summary"] = dict(median=float(a.belt_share.median()), p10=float(a.belt_share.quantile(.1)), p90=float(a.belt_share.quantile(.9)), mean_lake=float(a.lake_share.mean()))
        # ---- LOYO ----
        for col in ("belt_share", "lake_share"):
            for gdd, modern in ((False, False), (True, False), (False, True)):
                if col == "lake_share" and (gdd or modern): continue
                info, rows = loyo(df, lk, col, gdd, modern); key = f"{col}{'_gdd' if gdd else ''}{'_modern' if modern else ''}"
                L.setdefault("loyo", {})[key] = info; allrows[(lk, key)] = rows
                if rows:
                    info["n_eval"] = len(rows); info["clim_vs_obs"] = agree(rows, "clim", "obs"); info["cal_vs_obs"] = agree(rows, "cal", "obs")
                    cm = [r for r in rows if r["pers"] is not None]
                    info["common_n"] = len(cm)
                    for m in ("clim", "cal", "pers"): info[f"common_{m}"] = agree(cm, m, "obs")
                    info["level_clim"] = lvl_agree(rows, "clim", "obs"); info["level_cal"] = lvl_agree(rows, "cal", "obs")
                    info["obs_dist"] = pd.Series([r["obs"] for r in rows]).value_counts().to_dict()
                    info["by_age"] = {}
                    for nm, (lo_, hi_) in {"<=14d": (0, 14), "15-30d": (15, 30), "31-60d": (31, 60), ">60d": (61, 99999)}.items():
                        sub = [r for r in cm if r["age"] is not None and lo_ <= r["age"] <= hi_]
                        info["by_age"][nm] = dict(n=len(sub), pers=agree(sub, "pers", "obs")["exact"] if sub else None, clim=agree(sub, "clim", "obs")["exact"] if sub else None, cal=agree(sub, "cal", "obs")["exact"] if sub else None)
        # ---- full-data climatology & timing ----
        aa = a[a.belt_share.notna()]
        if len(aa) > 20:
            cs = build_curve(aa.doy.values, aa.belt_share.values, aa.year.values)
            L["curve"] = [round(float(x), 4) for x in cs]
            lo, hi = cs.min(), cs.max(); L["clim_amp"] = [float(lo), float(hi)]
            pk = int(np.argmax(cs)); L["clim_peak_doy"] = float(pk*BW+BW/2+0.5); L["clim_trough_doy"] = float(int(np.argmin(cs))*BW+BW/2+0.5)
            hiw = [i for i in range(NB) if (cs[i]-lo)/max(hi-lo, 1e-9) >= 0.8]; L["peak_window_doy"] = [float(min(hiw)*BW+1), float(max(hiw)*BW+BW)]
            # local maxima with prominence
            prom = []
            for i in range(NB):
                if cs[i] > cs[(i-1) % NB] and cs[i] >= cs[(i+1) % NB]:
                    # prominence: min drop on both sides before higher point
                    def drop(step):
                        m_ = cs[i]; j = i
                        for k in range(1, NB):
                            jj = (i+step*k) % NB
                            if cs[jj] > cs[i]: break
                            m_ = min(m_, cs[jj])
                        return cs[i]-m_
                    prom.append((i, min(drop(1), drop(-1))))
            L["n_peaks_prom25"] = int(sum(1 for _, p in prom if p >= 0.25*(hi-lo))) if hi > lo else 0
            wint = aa[aa.month.isin([12, 1, 2])].belt_share; L["winter"] = dict(n=int(len(wint)), median=float(wint.median()) if len(wint) else None, ratio_to_peak=float(wint.median()/hi) if len(wint) and hi > 0 else None)
            # per-year peak (rolling 3-obs median within Apr-Nov)
            pys = []
            for y, g in aa[(aa.month >= 4) & (aa.month <= 11)].groupby("year"):
                if len(g) < 8: continue
                s = g.set_index("date").belt_share.rolling(3, center=True, min_periods=2).median(); pys.append(int(s.idxmax().dayofyear))
            L["peak_doy_by_year"] = pys
            # shoreline-ring diagnostic (summer accepted scenes)
            z = np.load(H/f"out/cells_{lk}.npz", allow_pickle=True); dates_c = [str(d) for d in z["dates"]]; V, SN, dist, an_ = z["V"], z["SN"], z["dist"], z["an"]
            sel = [i for i, d in enumerate(dates_c) if d in set(a[a.month.isin([6, 7, 8, 9])].date.dt.strftime("%Y-%m-%d"))]
            rings = {}
            for lo_, hi_ in [(35, 50), (50, 70), (70, 90), (90, 150), (150, 300), (300, 1e9)]:
                m = an_ & (dist >= lo_) & (dist < hi_); rings[f"{lo_}-{int(hi_) if hi_ < 1e8 else 'inf'}"] = dict(cells=int(m.sum()), share=float(np.mean([V[i][m].sum()/max(1, SN[i][m].sum()) for i in sel])) if sel and m.sum() else None)
            L["rings_summer"] = rings
        out["lakes"][lk] = L
    json.dump(out, open(H/"out/analysis.json", "w"), indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    pd.to_pickle(allrows, H/"out/loyo_rows.pkl")
    print("ok")
