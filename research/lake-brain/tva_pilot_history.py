#!/usr/bin/env python3
"""Assemble candidate deep daily pool-elevation histories for the four TVA pilots and validate them
against TVA's own live values. Reads only files under HIST (never Git). Writes
HIST/tva_pilots/<LOC>_daily.csv and prints/saves a validation summary JSON.

Sources (all read-only, public):
  A  NWS Huntsville RVDHUN 'Daily River and Lake Summary' text product via the Iowa Environmental Mesonet AFOS
     archive (TVA mainstem pool elevation headwater at 6-7 AM local, 0.1 ft resolution, 2005-2021-09-30)
  B  NWS/TVA HADS DCP 'HP' (pool elevation) via IEM hads.py (hourly, 0.01 ft, 2022-10-27 -> today)
  C  CWMS LRD 'Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA' (hourly, 2019-10 -> today; needs QC)
  T  Truth: TVA operating-guide midnight series as stored by Lake Brain (gs://sector-lake-brain/history, 2025-01-01 ->)
"""
import glob, json, os, re, sys
import numpy as np, pandas as pd

HIST = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/history")
OUT = f"{HIST}/tva_pilots"; os.makedirs(OUT, exist_ok=True)
PILOTS = {  # loc -> (lake key, name regex in RVDHUN, plausible pool range ft)
    "GVDA1": ("Guntersville_AL", r"^GUNTERSVILLE( HW)?$", (592.0, 596.5)),
    "WHLA1": ("Wheeler_AL", r"^WHEELER( HW| DAM)?$", (549.0, 557.8)),
    "WLSA1": ("Wilson_AL", r"^WILSON HW$", (503.5, 508.5)),
    "PICT1": ("Pickwick_Lake_TN", r"^PICKWICK( HW| DAM)?$", (406.5, 419.5)),
}

def rvd():
    d = pd.read_csv(f"{HIST}/nws_rvdhun/rvdhun_pool_parsed.csv", dtype={"issue_hhmm": str})
    d["nm"] = d["name"].str.upper().str.strip()
    out = {}
    for loc, (_, rx, (lo, hi)) in PILOTS.items():
        ids = [loc] + (["PKDT1"] if loc == "PICT1" else [])
        s = d[d.station.isin(ids) & d.nm.str.match(rx) & d.value_ft.notna()].copy()
        # Wheeler 'WHEELER DAM' in 2005-07 also carried Wilson values -> range QC handles it
        s = s[(s.value_ft >= lo) & (s.value_ft <= hi)]
        s["date"] = pd.to_datetime(s.date)
        out[loc] = s.groupby("date").value_ft.median().rename("rvd")
    mg = rvdmeg_pickwick()
    new = mg[~mg.index.isin(out["PICT1"].index)]
    out["PICT1"] = pd.concat([out["PICT1"], new]).sort_index().rename("rvd")
    return out

def rvdmeg_pickwick():
    """NWS Memphis RVDMEG carries 'PICKWICK DAM HEADWATER' (PICT1/PKDT1); observed 7 AM value present 2013 and 2020-21 only."""
    rows = []
    for f in sorted(glob.glob(f"{HIST}/nws_rvdmeg/rvdmeg_*.txt")):
        for prod in re.split(r"(?m)^RVDMEG\s*$", open(f, errors="replace").read())[1:]:
            m = re.search(r"DC(\d{4})(\d{2})(\d{2})", prod)
            if not m: continue
            ls = prod.splitlines()
            for i, l in enumerate(ls):
                if "PICKWICK DAM HEADWATER" in l.upper() and i + 1 < len(ls):
                    mm = re.search(r":\s*(M|\d{3}\.\d)/", ls[i + 1].split(":", 1)[1] if ":" in ls[i + 1] else "")
                    if mm and mm.group(1) != "M":
                        rows.append((pd.Timestamp(f"{m[1]}-{m[2]}-{m[3]}"), float(mm.group(1))))
    s = pd.Series(dict(rows)).sort_index() if rows else pd.Series(dtype=float)
    return s[(s >= 406.5) & (s <= 419.5)]

def hads():
    out = {}
    for loc in PILOTS:
        fs = sorted(glob.glob(f"{HIST}/hads/{loc}_*.csv"))
        if not fs: continue
        x = pd.concat([pd.read_csv(f, usecols=["utc_valid", "HPIRZZZ"]) for f in fs]).dropna()
        x["t"] = pd.to_datetime(x.utc_valid, utc=True)
        x = x[x.HPIRZZZ > 100].drop_duplicates("t").set_index("t").HPIRZZZ
        out[loc] = x
    return out

def local_midnight(h):
    """hourly utc series -> value at 00:00 America/Chicago (same convention as TVA operating guide)."""
    lt = h.copy(); lt.index = lt.index.tz_convert("America/Chicago")
    m = lt[(lt.index.hour == 0)]
    m.index = m.index.tz_localize(None).normalize()
    return m[~m.index.duplicated()]

def local_hour(h, hour):
    lt = h.copy(); lt.index = lt.index.tz_convert("America/Chicago")
    m = lt[(lt.index.hour == hour)]
    m.index = m.index.tz_localize(None).normalize()
    return m[~m.index.duplicated()]

def cwms_pickwick():
    d = pd.read_csv(f"{HIST}/cwms/pickwick_lake_hourly.csv")
    d["t"] = pd.to_datetime(d.epoch_ms, unit="ms", utc=True)
    d = d.dropna(subset=["value"]); d = d[(d.value > 406) & (d.value < 420)]
    return d.set_index("t").value

def truth(loc):
    k = PILOTS[loc][0]
    t = pd.read_csv(f"{HIST}/lakebrain_gcs/{k}.csv", parse_dates=["date"]).set_index("date").elevationFt
    return t

def completeness(s):
    s = s.dropna(); y = s.groupby(s.index.year).size()
    return {int(k): int(v) for k, v in y.items()}

def main():
    R, H = rvd(), hads()
    summary = {}
    for loc in PILOTS:
        T = truth(loc)
        r = R.get(loc, pd.Series(dtype=float))
        h = H.get(loc)
        entry = {"rvdhun_days": int(r.size), "rvdhun_first": str(r.index.min().date()), "rvdhun_last": str(r.index.max().date()),
                 "rvdhun_per_year": completeness(r)}
        if h is not None:
            hm = local_midnight(h)
            h7 = local_hour(h, 7)
            entry["hads_first"] = str(h.index.min().date()); entry["hads_last"] = str(h.index.max().date())
            j = pd.concat([hm.rename("hads"), T.rename("truth")], axis=1).dropna()
            dlt = j.hads - j.truth
            entry["hads_vs_tva_guide"] = {"n": int(len(j)), "bias_ft": round(float(dlt.mean()), 3), "mae_ft": round(float(dlt.abs().mean()), 3),
                                          "p95_abs_ft": round(float(dlt.abs().quantile(.95)), 3), "max_abs_ft": round(float(dlt.abs().max()), 3),
                                          "corr": round(float(j.hads.corr(j.truth)), 5)}
            hd = pd.concat([hm.rename("v")], axis=1).v
            entry["hads_midnight_per_year"] = completeness(hd)
            daily = hm.copy()
        else:
            daily = pd.Series(dtype=float)
        if loc == "PICT1":
            c = cwms_pickwick(); cm = local_midnight(c)
            c7 = local_hour(c, 7)
            j = pd.concat([cm.rename("cwms"), T.rename("truth")], axis=1).dropna()
            dlt = j.cwms - j.truth
            entry["cwms_vs_tva_guide"] = {"n": int(len(j)), "bias_ft": round(float(dlt.mean()), 3), "mae_ft": round(float(dlt.abs().mean()), 3),
                                          "p95_abs_ft": round(float(dlt.abs().quantile(.95)), 3), "max_abs_ft": round(float(dlt.abs().max()), 3)}
            entry["cwms_first"] = str(c.index.min().date()); entry["cwms_per_year"] = completeness(cm)
            # RVDHUN (~6-7AM, 0.1 ft) vs CWMS hourly at 7 AM local over 2019-2021
            j2 = pd.concat([r.rename("rvd"), c7.rename("cwms7")], axis=1).dropna()
            d2 = j2.rvd - j2.cwms7
            entry["rvdhun_vs_cwms_7am"] = {"n": int(len(j2)), "bias_ft": round(float(d2.mean()), 3), "mae_ft": round(float(d2.abs().mean()), 3),
                                           "p95_abs_ft": round(float(d2.abs().quantile(.95)), 3), "max_abs_ft": round(float(d2.abs().max()), 3)}
            c6 = local_hour(c, 6)
            j3 = pd.concat([r.rename("rvd"), c6.rename("cwms6")], axis=1).dropna(); d3 = j3.rvd - j3.cwms6
            entry["rvdhun_vs_cwms_6am"] = {"n": int(len(j3)), "mae_ft": round(float(d3.abs().mean()), 3), "bias_ft": round(float(d3.mean()), 3)}
        # composite: prefer HADS midnight, then RVDHUN; for Pickwick also CWMS midnight between
        parts = []
        if h is not None: parts.append(("hads", daily))
        if loc == "PICT1": parts.append(("cwms", cm))
        parts.append(("rvdhun", r))
        comp = pd.Series(dtype=float); src = pd.Series(dtype=object)
        for name, s in parts:
            new = s[~s.index.isin(comp.index)]
            comp = pd.concat([comp, new]); src = pd.concat([src, pd.Series(name, index=new.index)])
        comp = comp.sort_index(); src = src.reindex(comp.index)
        # fill with TVA guide for dates TVA guide covers but nothing else does (2025+ is covered by HADS anyway)
        df = pd.DataFrame({"date": comp.index.strftime("%Y-%m-%d"), "elevationFt": comp.round(2).values, "source": src.values})
        df.to_csv(f"{OUT}/{loc}_daily.csv", index=False)
        pyc = completeness(comp)
        entry["composite_first"] = df.date.iloc[0]; entry["composite_last"] = df.date.iloc[-1]; entry["composite_days"] = int(len(df))
        cy = [y for y, n in pyc.items() if y < 2026 and n >= 329]
        entry["composite_per_year"] = pyc; entry["complete_years_ge329"] = cy
        # yearly 0.1-ft rounding fingerprint of RVDHUN
        entry["rvdhun_share_on_0.1_grid"] = round(float((np.abs(r * 10 - np.round(r * 10)) < 1e-6).mean()), 3)
        summary[loc] = entry
    json.dump(summary, open(f"{OUT}/validation_summary.json", "w"), indent=1)
    print(json.dumps(summary, indent=1)[:9000])

if __name__ == "__main__":
    main()
