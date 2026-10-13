#!/usr/bin/env python3
"""Fleet-level coverage / match-quality / Dmax-distribution summary -> merged into globathy_eval_summary.json['fleet']"""
import json, numpy as np, pandas as pd
O = "/Users/mcather/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/"
m = pd.read_csv(O + "globathy_fleet_match.csv")
F = {"n_fleet": len(m), "n_hl_matched": int(m.hl_id.notna().sum()), "n_glob_row": int(m.glob_dmax_m.notna().sum()), "n_no_polygon": int(m.poly_area_km2.isna().sum()),
     "tier": m.match_tier.value_counts().to_dict(), "match_mode": m.hl_match.value_counts().to_dict(), "dmax_source": m.glob_dmax_source.value_counts().to_dict(),
     "flags": m.match_flags.fillna("").str.split(";").explode().replace("", np.nan).value_counts().to_dict()}
g = m[m.glob_dmax_m.notna()].copy()
g["size"] = pd.cut(g.area_ref_km2, [0, 5, 20, 100, 500, 1e9], labels=["<5", "5-20", "20-100", "100-500", ">500"])
def q(s): return dict(n=int(len(s)), p10=round(s.quantile(.1), 1), p25=round(s.quantile(.25), 1), median=round(s.median(), 1), p75=round(s.quantile(.75), 1), p90=round(s.quantile(.9), 1))
F["dmax_by_hl_type"] = {str(int(k)): q(v.glob_dmax_m) for k, v in g.groupby("hl_type")}
F["dmax_by_hl_type_and_source"] = {f"{int(k[0])}/{k[1]}": q(v.glob_dmax_m) for k, v in g.groupby(["hl_type", "glob_dmax_source"]) if len(v) > 2}
F["dmax_by_size_km2"] = {str(k): q(v.glob_dmax_m) for k, v in g.groupby("size", observed=True)}
F["dmax_by_regime"] = {k: q(v.glob_dmax_m) for k, v in g.groupby("regime")}
F["dmax_by_lake_class"] = {k: q(v.glob_dmax_m) for k, v in g.groupby("lake_class")}
F["shallow_frac_1p2m_by_regime"] = {k: q(v.glob_shallow_frac_1p2m * 100) for k, v in g.groupby("regime")}
F["glob_shallow_frac_1p2m_overall"] = q(g.glob_shallow_frac_1p2m * 100)
F["glob_b_overall"] = q(g.glob_b * 10)
F["dmax_estimate_range_among_modeled"] = q(g[g.glob_dmax_source == "modeled_estimate"].glob_dmax_m)
F["frac_modeled_dmax_between_10_and_50m"] = float(g[g.glob_dmax_source == "modeled_estimate"].glob_dmax_m.between(10, 50).mean())
F["suspect_matches"] = m[m.match_tier == "suspect"][["id", "hl_name", "hl_over_poly", "poly_hl_n", "poly_hl_iou", "n_sector_per_hl", "match_flags"]].round(2).to_dict("records")
F["shared_hl_ids"] = m[m.n_sector_per_hl > 1][["id", "hl_id", "hl_name"]].to_dict("records")
F["area_ratio_dist"] = q(m.hl_over_poly.dropna() * 10)
F["pilots"] = m[m.id.isin(["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"])][["id", "hl_name", "hl_over_poly", "poly_hl_n", "match_tier", "glob_dmax_m", "glob_mean_depth_m", "glob_shallow_frac_1p2m", "glob_dmax_source"]].round(3).to_dict("records")
S = json.load(open(O + "globathy_eval_summary.json")); S["fleet"] = F; json.dump(S, open(O + "globathy_eval_summary.json", "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in F.items() if k not in ("suspect_matches", "shared_hl_ids")}, indent=0)[:6000]); print(F["pilots"]); print(F["suspect_matches"][:40])
