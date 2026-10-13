#!/usr/bin/env python3
"""Track 7 evaluation: can cheap proxies predict the real fractional surface-area change per foot of pool change (rel_per_ft, from CWMS Stor/Elev)?
Predictors (all computable without bathymetry):
  P_shape : shoreline length per area  (perimeter_km / area_km2)                       -- geometry only
  P_dem   : perimeter x mean(horizontal run per vertical ft, capped) / area            -- geometry + 3DEP shoreline slope  (run = 1/tan(slope 10->60 m))
  P_glob  : GLOBathy power-law  b / Dmax_ft  (A = a h^b, h above the bottom)           -- modeled bathymetry
  P_slope : median shoreline slope alone
Truth: context/hypso_truth.json; DEM: context/shore_dem*.json; GLOBathy via HydroLAKES id in context/external_join.json.
Outputs docs/research/lake-brain/data/hypso_validation.json (+ a compact per-lake table)."""
import json, glob
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
CTX = DATA / "context"


def spearman(a, b):
    x = pd.concat([pd.Series(a), pd.Series(b)], axis=1).dropna()
    return float(x.rank().corr().iloc[0, 1]), len(x)


def pearson_log(a, b):
    x = pd.concat([np.log(pd.Series(a)), np.log(pd.Series(b))], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    return float(x.corr().iloc[0, 1]), len(x)


def main():
    truth = json.load(open(CTX / "hypso_truth.json"))
    shore = {}
    for f in glob.glob(str(CTX / "shore_dem*.json")): shore.update(json.load(open(f)))
    feats = pd.read_csv(REPO / "docs/research/lake-brain/data/lake_features.csv").set_index("id")
    join = json.load(open(CTX / "external_join.json"))
    import xarray as xr
    ds = xr.open_dataset(CTX / "globathy/GLOBathy_hAV_relationships.nc"); ids = ds["lake_id"].values; idpos = {int(v): i for i, v in enumerate(ids)}
    rows = []
    for key, rec in truth.items():
        lake = key.split("#")[0]; fit = rec.get("fit")
        if not fit or lake not in shore or lake not in feats.index: continue
        # one row per lake: keep the pair with most days
        s = shore[lake]; f = feats.loc[lake]
        perim_ft = s["perim_km"] * 1000 * 3.28084; area_ft2 = f.area_km2 * 1e6 * 10.7639
        r = dict(lake=lake, loc=rec["loc"], office=rec["office"], n_days=fit["n_days"], A_ref_ac=fit["A_ref_ac"], truth_rel_per_ft=fit["rel_per_ft"], truth_dA_dz=fit["dA_dz_ac_per_ft"], r2=fit["r2"],
                 area_km2=f.area_km2, truth_area_ratio=fit["A_ref_ac"] * 0.00404686 / f.area_km2 if f.area_km2 else np.nan, slope_med=s["slope_med"], run_med=s["run_per_ft_med"], run_mean=s["run_per_ft_mean"])
        r["P_shape"] = s["perim_km"] / f.area_km2
        for cap in (25, 50, 100):
            pass
        r["P_dem_med"] = perim_ft * s["run_per_ft_med"] / area_ft2
        r["P_dem_mean"] = perim_ft * s["run_per_ft_mean"] / area_ft2
        r["P_dem_gm"] = perim_ft * np.sqrt(s["run_per_ft_med"] * s["run_per_ft_mean"]) / area_ft2
        r["P_slope"] = -s["slope_med"]            # steeper -> smaller rel change (sign flipped so higher = larger predicted change)
        hl = join.get(lake, {}).get("hl_id")
        if hl and int(hl) in idpos:
            i = idpos[int(hl)]; a_, b_ = ds["f_hA"][i].values[:2]; dmax = ds["lake_attributes"][i].values[0]
            r["P_glob"] = float(b_ / (dmax * 3.28084)); r["glob_dmax_m"] = float(dmax)
        rows.append(r)
    d = pd.DataFrame(rows)
    d = d.sort_values("n_days", ascending=False).drop_duplicates("lake")
    d = d[(d.truth_rel_per_ft > 0) & (d.r2 > 0.9) & d.truth_area_ratio.between(0.2, 5)]   # r2/units gate: drops Alamo (poor fit) and Tahoe (storage units differ)
    res = {"n_lakes": int(len(d))}
    for p in ["P_shape", "P_dem_med", "P_dem_mean", "P_dem_gm", "P_slope", "P_glob"]:
        sp, n = spearman(d[p], d.truth_rel_per_ft)
        res[p] = {"spearman": round(sp, 2), "n": n}
        if p == "P_shape":
            res[p]["pearson_log"] = round(pearson_log(d[p], d.truth_rel_per_ft)[0], 2)
        if p in ("P_dem_med", "P_dem_mean", "P_dem_gm", "P_glob"):
            lp, n2 = pearson_log(d[p], d.truth_rel_per_ft); res[p]["pearson_log"] = round(lp, 2)
            ratio = (d[p] / d.truth_rel_per_ft).replace([np.inf, -np.inf], np.nan).dropna()
            res[p]["log10_rmse"] = round(float(np.sqrt(np.mean(np.log10(ratio) ** 2))), 2)
            res[p]["median_ratio_pred_to_truth"] = round(float(ratio.median()), 2); res[p]["within_x2"] = round(float(((ratio > 0.5) & (ratio < 2)).mean()), 2)
    c = d.truth_rel_per_ft.median(); rc = (c / d.truth_rel_per_ft)
    res["constant_median_baseline"] = {"value": round(float(c), 4), "within_x2": round(float(((rc > .5) & (rc < 2)).mean()), 2), "log10_rmse": round(float(np.sqrt(np.mean(np.log10(rc) ** 2))), 2)}
    # partial: does slope add to shape?  rank-regress truth on P_shape and slope
    x = d[["truth_rel_per_ft", "P_shape", "slope_med"]].rank().dropna()
    if len(x) > 8:
        A = np.column_stack([np.ones(len(x)), x.P_shape, x.slope_med]); coef, *_ = np.linalg.lstsq(A, x.truth_rel_per_ft, rcond=None)
        pred = A @ coef; r2_both = 1 - ((x.truth_rel_per_ft - pred) ** 2).sum() / ((x.truth_rel_per_ft - x.truth_rel_per_ft.mean()) ** 2).sum()
        A1 = A[:, :2]; c1, *_ = np.linalg.lstsq(A1, x.truth_rel_per_ft, rcond=None); p1 = A1 @ c1
        r2_shape = 1 - ((x.truth_rel_per_ft - p1) ** 2).sum() / ((x.truth_rel_per_ft - x.truth_rel_per_ft.mean()) ** 2).sum()
        res["rank_regression_r2"] = {"shape_only": round(float(r2_shape), 2), "shape_plus_slope": round(float(r2_both), 2)}
    res["truth_rel_per_ft_quantiles"] = {k: round(float(v), 4) for k, v in d.truth_rel_per_ft.quantile([.1, .25, .5, .75, .9]).items()}
    res["truth_area_ratio_median"] = round(float(d.truth_area_ratio.median()), 2)
    out = d[["lake", "office", "n_days", "A_ref_ac", "truth_rel_per_ft", "slope_med", "run_med", "P_shape", "P_dem_med", "P_dem_gm", "P_glob"]].round(4)
    res["table"] = out.to_dict("records")
    (REPO / "docs/research/lake-brain/data/hypso_validation.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "table"}, indent=1))
    print(out.to_string())


if __name__ == "__main__":
    main()
