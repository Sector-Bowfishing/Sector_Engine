#!/usr/bin/env python3
"""Post-process contour_method_check outputs: split the fleet decimation test by lake depth (a 5-ft ladder on a lake whose maximum depth is <= 15 ft is not a representative tier-A case)
and by TWDB lake depth.  Adds keys to data/contour_method_check.json."""
import json
from pathlib import Path
import numpy as np, pandas as pd
D = Path(__file__).resolve().parents[2] / "docs/research/depth-brain/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
f = pd.read_csv(D / "contour_method_check_fleet.csv")
p = pd.read_csv(RAW / "depth-brain/contour/truth_pairs_flagged.csv")[["lakeId", "src", "max_contour_ft"]]
f = f.merge(p, on=["lakeId", "src"], how="left")
res = json.load(open(D / "contour_method_check.json"))
def st(df, a, b):
    e = df[a] - df[b]
    return dict(n=int(len(e)), bias=float(e.mean()), mae=float(e.abs().mean()), p90_abs=float(e.abs().quantile(.9)), max_abs=float(e.abs().max()))
for lab, sel in (("max_depth_ge_25ft", f.max_contour_ft >= 25), ("max_depth_lt_25ft", f.max_contour_ft < 25)):
    g = f[sel & f.d5_s3.notna()]
    res[f"fleet_d5_vs_native_{lab}"] = {s: st(g, f"d5_{s}", f"native_{s}") for s in ("s3", "s6", "s10")}
    g = f[sel & f.d10_s3.notna()]
    res[f"fleet_d10_vs_native_{lab}"] = {s: st(g, f"d10_{s}", f"native_{s}") for s in ("s3", "s6", "s10")}
t = pd.read_csv(D / "contour_method_check_twdb.csv")
t = t[t.native_s3.notna()]
for tag in ("native", "d5", "d10"):
    g = t[t[f"{tag}_s3"].notna()]
    res[f"twdb_{tag}_signed_error_quantiles_s6"] = np.quantile(g[f"{tag}_s6"] - g.S6, [0, .25, .5, .75, 1]).round(4).tolist()
json.dump(res, open(D / "contour_method_check.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if "ge_25" in k or "lt_25" in k}, indent=1))
