#!/usr/bin/env python3
"""Track 6: does the lightweight class scheme explain anything independent of the features that define it?
Independent outcomes available fleet-wide: the production Water Clarity index (read-only copy of gs://sector-lake-surface/index.json, latest pass per lake,
2026-10-12): fnuP50 (turbidity, FNU) and grassPct (share of read water classified grass/vegetation).  Variance explained (adjusted R2 of OLS on rank-transformed outcome
with one-hot dummies): class, region, operator family, class+region.  Also: one-way Kruskal-style eta2 for single numeric features (Spearman rho).
Output docs/research/lake-brain/data/class_eval.json"""
import json
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")


def adj_r2(y, cols, df):
    X = pd.get_dummies(df[cols].astype(str), drop_first=True).astype(float).values
    X = np.column_stack([np.ones(len(df)), X]); n, p = X.shape
    b, *_ = np.linalg.lstsq(X, y, rcond=None); res = y - X @ b
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return float(1 - (1 - r2) * (n - 1) / (n - p)), int(p - 1)


def main():
    idx = json.load(open(DATA / "context/clarity_read/index.json"))["lakes"]
    g = pd.DataFrame(idx).T
    for c in ("grassPct", "fnuP50", "measuredPct"): g[c] = pd.to_numeric(g[c])
    f = pd.read_csv(REPO / "docs/research/lake-brain/data/lake_features.csv").set_index("id")
    d = f.join(g[["grassPct", "fnuP50", "measuredPct"]], how="inner")
    d = d[~d.lake_class.isin(["X_mega", "Z_nodata"])]
    out = {"n": int(len(d))}
    for y in ("fnuP50", "grassPct"):
        r = d[y].rank().values
        out[y] = {name: dict(zip(("adj_r2", "n_params"), adj_r2(r, cols, d))) for name, cols in
                  {"class": ["lake_class"], "region": ["region"], "operator_family": ["operator_family"], "regime": ["regime"], "class+region": ["lake_class", "region"], "region+operator": ["region", "operator_family"]}.items()}
        out[y]["spearman"] = {c: round(float(pd.concat([d[c], d[y]], axis=1).dropna().rank().corr().iloc[0, 1]), 2) for c in
                              ["mean_depth_m", "area_ref_km2", "sdi_ext", "res_time_d", "frac_within_100m", "frac_narrow_300m", "lat", "lon"]}
    out["median_by_class"] = d.groupby("lake_class")[["fnuP50", "grassPct"]].median().round(1).to_dict("index")
    out["median_by_region"] = d.groupby("region")[["fnuP50", "grassPct"]].median().round(1).to_dict("index")
    (REPO / "docs/research/lake-brain/data/class_eval.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n", "fnuP50", "grassPct")}, indent=1))


if __name__ == "__main__":
    main()
