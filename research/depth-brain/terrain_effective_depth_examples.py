#!/usr/bin/env python3
"""Depth Brain / effective depth (Question B): worked examples on REAL level history.
effective depth of a point = reference depth at full pool + (level - fullPoolFt).   shift = level - fullPoolFt.
 1. Guntersville (TVA, GVDA1 daily 2005-2026; fullPool 595, TVA summer pool, winter guide ~593.3): a hypothetical 4.0 ft flat.
 2. Hartwell (USACE SAS, CWMS daily; fullPool 660): same 4.0 ft flat, 2016-2025.
 3. Lake Fork (TWDB truth): the REAL set of cells that are 3.5-4.5 ft deep at pool (from the survey contours), effective depth over the TWDB daily level
    series, plus area-weighted share of the lake in 0-3 ft by month.
Also: exposed/flooded acres per foot of pool change from a lake's A(z) (TWDB table) and from the 3DEP proxy.
Output docs/research/depth-brain/data/effective_depth_examples.json, effective_depth_monthly.csv.  venv python."""
import io, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd, requests

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
LBH = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/history")
OUT = REPO / "docs/research/depth-brain/data"


def summarize(name, level, fp, d0=4.0, start=None, end=None, extra=None):
    s = level.copy(); s.index = pd.to_datetime(s.index)
    if start: s = s[s.index >= start]
    if end: s = s[s.index <= end]
    eff = d0 + (s - fp)
    shift = s - fp
    r = dict(name=name, fullPoolFt=fp, ref_depth_ft=d0, period=[str(s.index[0].date()), str(s.index[-1].date())], days=int(len(s)),
             shift_p05=float(shift.quantile(.05)), shift_p50=float(shift.median()), shift_p95=float(shift.quantile(.95)), shift_min=float(shift.min()), shift_max=float(shift.max()),
             eff_p05=float(eff.quantile(.05)), eff_p50=float(eff.median()), eff_p95=float(eff.quantile(.95)),
             frac_days_eff_lt_3=float((eff < 3).mean()), frac_days_eff_lt_2=float((eff < 2).mean()), frac_days_eff_lt_1=float((eff < 1).mean()), frac_days_dry=float((eff <= 0).mean()), frac_days_eff_ge_4=float((eff >= 4).mean()), frac_days_eff_gt_5=float((eff > 5).mean()))
    mo = pd.DataFrame(dict(shift=shift)).groupby(shift.index.month)["shift"].agg(["min", lambda x: x.quantile(.1), "median", lambda x: x.quantile(.9), "max"]); mo.columns = ["min", "p10", "median", "p90", "max"]
    r["monthly_shift_ft"] = {int(m): {k: round(float(v), 2) for k, v in row.items()} for m, row in mo.iterrows()}
    yr = shift.groupby(shift.index.year).agg(lambda x: x.quantile(.99) - x.quantile(.01))
    r["annual_swing_p99_p01_ft_by_year"] = {int(y): round(float(v), 2) for y, v in yr.items() if (s.index.year == y).sum() > 300}
    if extra: r.update(extra)
    return r, mo


def main():
    out = {}; monthly = []
    # 1 Guntersville
    g = pd.read_csv(LBH / "tva_pilots/GVDA1_daily.csv", parse_dates=["date"]).set_index("date")["elevationFt"]
    r, mo = summarize("Guntersville|AL (TVA GVDA1)", g, 595.0, extra=dict(note="TVA summer pool 595 (Sector fullPoolFt); winter guide curve 593.3 per TVA operating guide; 0.1 ft RVDHUN resolution to 2021, 0.01 ft HADS after"))
    out["guntersville"] = r; mo["lake"] = "Guntersville"; monthly.append(mo)
    gs = g[g.index >= "2012-01-01"]
    r2, _ = summarize("Guntersville 2012-2026", gs, 595.0); out["guntersville_2012_2026"] = r2
    # 2 Hartwell
    h = pd.read_csv(LBH / "cwms/hartwell_daily.csv"); h = h[h.value.notna() & (h.value > 400)]
    h["date"] = pd.to_datetime(h.epoch_ms, unit="ms").dt.normalize(); hs = h.groupby("date")["value"].mean()
    r, mo = summarize("Lake Hartwell|SC (USACE CWMS)", hs, 660.0, start="2016-01-01"); out["hartwell_2016_2025"] = r; mo["lake"] = "Hartwell"; monthly.append(mo)
    r, mo = summarize("Lake Hartwell|SC full record", hs, 660.0, start="1990-01-01"); out["hartwell_1990_2026"] = r
    # 3 Fork (needs the contour depth grid)
    t = requests.get("https://www.waterdatafortexas.org/reservoirs/individual/fork.csv", timeout=120).text
    f = pd.read_csv(io.StringIO("\n".join(l for l in t.splitlines() if not l.startswith("#"))), parse_dates=["date"]).dropna(subset=["water_level"]).set_index("date")["water_level"]
    r, mo = summarize("Lake Fork|TX (TWDB daily)", f, 403.0, start="2008-01-01"); out["fork_2008_2026"] = r; mo["lake"] = "Fork"; monthly.append(mo)
    gp = RAW / "depthgrid/Fork_2009-10.npz"
    if gp.exists():
        z = np.load(gp); dep = z["depth_ft"]; dep = dep[np.isfinite(dep)]
        cell_ac = 15.0 * 15.0 / 4046.856
        flat = (dep >= 3.5) & (dep <= 4.5); sh = (dep <= 3)
        ff = f[f.index >= "2008-01-01"]; shift = ff - 403.0
        d_eff = lambda dd: dd[:, None] + shift.values[None, :]
        fd = dep[flat]
        eff = fd[:, None] + shift.values[None, :]             # cells x days
        out["fork_real_flat"] = dict(cells=int(flat.sum()), acres_at_pool=round(float(flat.sum() * cell_ac), 1), lake_acres=round(float(len(dep) * cell_ac), 1),
                                     share_of_lake_in_0_3ft_at_pool=round(float(sh.mean()), 4),
                                     median_flat_eff_depth_ft=round(float(np.median(eff)), 2), frac_flat_area_days_below_2ft=round(float((eff < 2).mean()), 3),
                                     frac_flat_area_days_dry=round(float((eff <= 0).mean()), 3),
                                     lowest_day=str(shift.idxmin().date()), lowest_shift_ft=round(float(shift.min()), 2),
                                     acres_of_the_4ft_flat_dry_on_lowest_day=round(float((fd + shift.min() <= 0).sum() * cell_ac), 1),
                                     wet_share_0_3ft_on_lowest_day=round(float(((dep > -shift.min()) & (dep <= 3 - shift.min())).sum() / max((dep > -shift.min()).sum(), 1)), 4),
                                     pool_area_share_wet_0_3ft_on_lowest_day=round(float(((dep > -shift.min()) & (dep <= 3 - shift.min())).mean()), 4),
                                     wet_surface_share_on_lowest_day=round(float((dep > -shift.min()).mean()), 4))
        # lake-wide share of surface 0-3 ft by day -> monthly median (shift moves the 3 ft line)
        sv = shift.values[::10]
        wet_sh = np.array([((dep > -s_) & (dep <= 3 - s_)).sum() / max((dep > -s_).sum(), 1) for s_ in sv])        # share of the CURRENTLY WET surface that is 0-3 ft deep
        pool_sh = np.array([((dep > -s_) & (dep <= 3 - s_)).mean() for s_ in sv])                                # acres of 0-3 ft water as a share of the pool-level surface
        out["fork_real_flat"]["wet_surface_share_0_3ft_p10_p50_p90"] = [round(float(np.quantile(wet_sh, q)), 4) for q in (.1, .5, .9)]
        out["fork_real_flat"]["pool_area_share_wet_0_3ft_p10_p50_p90"] = [round(float(np.quantile(pool_sh, q)), 4) for q in (.1, .5, .9)]
    (OUT / "effective_depth_examples.json").write_text(json.dumps(out, indent=1, default=float))
    pd.concat(monthly).reset_index().rename(columns={"index": "month"}).round(2).to_csv(OUT / "effective_depth_monthly.csv", index=False)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("monthly_shift_ft", "annual_swing_p99_p01_ft_by_year")} for k, v in out.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
