#!/usr/bin/env python3
"""Depth Brain / effective depth (Question B): per-lake operating range of the published lake level, from the Lake Brain bound sources.
Pull 10 years (2016-2025 + 2026 YTD) of level for bound lakes whose source is a plain public API (CWMS timeseries incl. Access2Water-locations that
resolve to a CWMS series, USGS NWIS dv 62614/62615/00062), plus locally cached long series (TVA pilots, plan-thread composites/HADS).
Reduce to daily means.  Stats per lake: p05/p50/p95, p05-p95 range, mean annual max-min (swing), share of days below fullPoolFt by >1/2/5/10 ft,
drawdown_p50/p95 (fullPool - level), median-vs-fullPool datum consistency flag.
Output: docs/research/depth-brain/data/operating_range_by_lake.csv, <RAW>/levels/<safe>.csv.gz (never git).  Polite, 4 threads."""
import csv, gzip, io, json, re, sys, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain/levels"); RAW.mkdir(parents=True, exist_ok=True)
LB = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data")
FP = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/data/full_pool.csv")
PLANH = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/plan/history")
H = {"Accept": "application/json;version=2", "User-Agent": "SectorResearch/1.0 (depth-brain terrain research)"}
CW = "https://cwms-data.usace.army.mil/cwms-data"
Y0, Y1 = 2016, 2026


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def get(url, params=None, hdr=H, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=hdr, timeout=240)
            if r.status_code == 200: return r
            if r.status_code in (400, 404): return None
        except Exception: pass
        time.sleep(2 * (i + 1))
    return None


def cwms_series(office, tsid):
    acc = {}
    for ys in range(Y0, Y1 + 1, 5):
        r = get(f"{CW}/timeseries", dict(name=tsid, office=office, begin=f"{ys}-01-01T00:00:00Z", end=f"{min(ys + 4, Y1)}-12-31T23:59:59Z", unit="EN", **{"page-size": 200000}))
        if r is None: continue
        for t, v, *_ in r.json().get("values", []):
            if v is not None: acc.setdefault(dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date().isoformat(), []).append(v)
    return {d: float(np.mean(v)) for d, v in acc.items()}


_A2W = {}
def a2w_tsid(office, loc):
    """pool-elevation tsid from the Access2Water location files cached by the binding thread"""
    if not _A2W:
        import glob
        for f in glob.glob("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding/raw/a2w/locations_*.json"):
            for it in json.load(open(f)): _A2W[(it.get("provider"), it.get("code"))] = it.get("timeseries", [])
    best = None
    for t in _A2W.get((office, loc), []):
        if t.get("base_parameter") != "Elev": continue
        n, lab = t["tsid"], t.get("label", "")
        if re.search(r"Tailwater|Downstream|Tail|Forecast|Guide|Top|Bottom|Stage", n + lab, re.I): continue
        sc = (bool(re.search(r"Pool|Forebay|Headwater|Lake", n + lab, re.I)), "1Hour" in n or "1Day" in n, -len(n))
        if best is None or sc > best[0]: best = (sc, n)
    return best[1] if best else None


def cwms_find_ts(office, loc):
    base = loc.split("-")[0] if False else loc
    r = get(f"{CW}/catalog/TIMESERIES", dict(office=office, like=re.escape(loc) + r"\.Elev.*", **{"page-size": 200}))
    if r is None: return None
    best = None
    for e in r.json().get("entries", []):
        n = e["name"]
        if re.search(r"Forecast|Guide|Rule|Top|Bottom|Pool-Dep", n, re.I): continue
        ex = (e.get("extents") or [{}])[0]; a, b = ex.get("earliest-time"), ex.get("latest-time")
        if not a or not b or b < "2026-01-01" or a > "2019-01-01": continue
        score = (a < "2016-01-01", "1Hour" in n or "1Day" in n or "Day" in n, -len(n))
        if best is None or score > best[0]: best = (score, n)
    return best[1] if best else None


def usgs_dv(site, param):
    r = get("https://waterservices.usgs.gov/nwis/dv/", dict(format="json", sites=site, parameterCd=param, statCd="00003", startDT=f"{Y0}-01-01", endDT=f"{Y1}-12-31"), hdr={"User-Agent": H["User-Agent"]})
    if r is None: return {}
    out = {}
    for ts in r.json()["value"]["timeSeries"]:
        for v in ts["values"][0]["value"]:
            try:
                x = float(v["value"])
                if x > -999: out[v["dateTime"][:10]] = x
            except Exception: pass
    return out


def load_local(lake):
    """long local series, if any: plan composite, TVA pilots"""
    p = PLANH / "composite" / (safe(lake.replace("|", "_")) + ".csv.gz")
    for cand in [p] + list((PLANH / "composite").glob(safe(lake.split("|")[0]) + "*")):
        if cand.exists():
            d = pd.read_csv(cand); return dict(zip(d["date"], d["value"]))
    return {}


def work(row):
    lake, prov, st, sp = row["lake_id"], row["provider"], row["station"], row["series_or_param"]
    fn = RAW / (safe(lake) + ".csv.gz")
    if fn.exists():
        d = pd.read_csv(fn); return lake, dict(zip(d["date"], d["value"])), "cached"
    s, how = {}, ""
    try:
        if prov == "cwms" or prov.startswith("cwms-"):
            office = st.split(":")[0] if ":" in st else (prov.split("-")[1].upper() if "-" in prov else st)
            s = cwms_series(office, sp); how = f"cwms:{office}"
        elif prov == "a2w":
            office, loc = st.split(":")
            ts = a2w_tsid(office, loc) or cwms_find_ts(office, loc)
            if ts: s = cwms_series(office, ts); how = f"cwms-via-a2w:{office}:{ts}"
            else: how = "a2w-no-cwms-series"
        elif prov in ("usgs", "usgs-d") and sp.split("+")[0] in ("62614", "62615", "62616", "00062"):
            s = usgs_dv(st, sp.split("+")[0]); how = f"usgs:{st}:{sp}"
    except Exception as e:
        how = "error:" + repr(e)[:60]
    if s:
        pd.DataFrame(sorted(s.items()), columns=["date", "value"]).to_csv(fn, index=False, compression="gzip")
    return lake, s, how


def stats(lake, s, fullpool):
    ser = pd.Series(s); ser.index = pd.to_datetime(ser.index); ser = ser.sort_index()
    ser = ser[ser.index >= "2016-01-01"]
    ser = ser[(ser > -500) & (ser < 30000)]                               # sentinels / unit errors
    if len(ser) >= 365:
        med = ser.median(); iqr = ser.quantile(.99) - ser.quantile(.01)
        ser = ser[(ser - med).abs() <= max(80.0, 2.5 * iqr)]            # isolated spikes
    if len(ser) < 365: return None
    yrs = ser.groupby(ser.index.year)
    full = [y for y, g in yrs if len(g) >= 300 and y <= 2025]
    r = dict(lake=lake, days=len(ser), first=ser.index[0].date().isoformat(), last=ser.index[-1].date().isoformat(), full_years=len(full),
             p05=ser.quantile(.05), p50=ser.median(), p95=ser.quantile(.95), p05_p95_range_ft=ser.quantile(.95) - ser.quantile(.05), max_min_ft=ser.max() - ser.min(), p99=ser.quantile(.99), p_max=ser.max())
    sw = [yrs.get_group(y).quantile(.99) - yrs.get_group(y).quantile(.01) for y in full]
    r["annual_swing_p99_p01_ft"] = float(np.mean(sw)) if sw else np.nan
    if fullpool is not None and np.isfinite(fullpool):
        dd = fullpool - ser
        # gross datum / unit mismatch only: median more than 200 ft from the stated full pool (Indian Lake OH: 1645 ft series vs 996 ft pool).
        r["datum_flag"] = "median-differs-from-fullpool(>200ft)" if abs(ser.median() - fullpool) > 200 else ""
        # regime notes (legitimate behaviour, not errors): flood-control lakes whose p99 sits far above the conservation pool, and drought-drawn lakes that rarely refill
        q99 = ser.quantile(.99)
        r["regime_note"] = "flood-pool-excursions(p99>15ft above fullPool)" if q99 - fullpool > 15 else ("rarely-full(p99>15ft below fullPool)" if fullpool - q99 > 15 else "")
        r.update(fullPoolFt=fullpool, median_minus_fullpool=ser.median() - fullpool, draw_p50=dd.quantile(.5), draw_p95=dd.quantile(.95), draw_p05=dd.quantile(.05),
                 frac_below_1=(dd > 1).mean(), frac_below_2=(dd > 2).mean(), frac_below_5=(dd > 5).mean(), frac_below_10=(dd > 10).mean(), frac_above_1=(dd < -1).mean())
    return r


def main():
    v1 = pd.read_csv(LB / "verified_bindings.csv"); v2 = pd.read_csv(LB / "verified_bindings_v2.csv")
    vb = pd.concat([v2, v1[~v1.lake_id.isin(v2.lake_id)]])           # v2 (wave 1+2) first, then any v1-only lake
    vb = vb[vb["binding_status"].str.startswith("VERIFIED")].drop_duplicates("lake_id")      # 417 bound lakes (not STAGE_ONLY)
    fp = pd.read_csv(FP).set_index("id")
    rows = vb.to_dict("records")
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(work, rows))
    out, cov = [], []
    for lake, s, how in res:
        if not s:
            s = load_local(lake)
            if s: how = (how + "|") + "local-composite"
        fpv = float(fp.loc[lake, "fullPoolFt"]) if lake in fp.index and pd.notna(fp.loc[lake, "fullPoolFt"]) and fp.loc[lake, "basis"] == "fullPool" else None
        st = stats(lake, s, fpv) if s else None
        cov.append((lake, how, bool(st)))
        if st: st["source"] = how; st["fp_conf"] = fp.loc[lake, "conf"] if lake in fp.index else ""; out.append(st)
        print(lake, how, "OK" if st else "no-stats", flush=True)
    df = pd.DataFrame(out).round(3)
    df.to_csv(REPO / "docs/research/depth-brain/data/operating_range_by_lake.csv", index=False)
    print(len(df), "lakes with stats of", len(res))


if __name__ == "__main__":
    main()
