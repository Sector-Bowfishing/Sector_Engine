#!/usr/bin/env python3
"""Fleet coverage and match quality of GLOBathy for the 621 Sector lakes.
Inputs: lake-brain external_join.json (HydroLAKES id per lake), hydrolakes_metrics.json (polygon IoU/area ratio),
lake_features.csv, GLOBathy basic parameters CSV + hAV nc.  Output: docs/research/depth-brain/data/globathy_fleet_match.csv"""
import json, numpy as np, pandas as pd, netCDF4 as nc
D = "/Users/mcather/Desktop/Development/"
LB = D + "Sector_Research_Data/lake-brain/"
OUT = D + "Sector_Engine-depth-research/docs/research/depth-brain/data/globathy_fleet_match.csv"
f = pd.read_csv(D + "Sector_Engine/docs/research/lake-brain/data/lake_features.csv").set_index("id")
j = json.load(open(LB + "context/external_join.json"))
gm = json.load(open(LB + "geometry/hydrolakes_metrics.json"))
bp = pd.read_csv(LB + "context/globathy/basic/GLOBathy_basic_parameters/GLOBathy_basic_parameters(ALL_LAKES).csv").set_index("Hylak_id")
_est = ["Dmax_box_m","Dmax_cone_m","Dmax_prism_m","Dmax_ellip_m","Dmax_est_PA_m","Dmax_est_PAVEW_m"]
bp["dmax_is_estimate"] = np.any([np.isclose(bp.Dmax_use_m, bp[c], rtol=1e-3) for c in _est], axis=0)   # False = literature/observed Dmax supplied to GLOBathy (1,468 lakes worldwide)
ds = nc.Dataset(LB + "context/globathy/GLOBathy_hAV_relationships.nc")
ids = ds["lake_id"][:]; pos = {int(v): i for i, v in enumerate(ids)}
rows = []
for lid in f.index:
    r = f.loc[lid]; m = j.get(lid, {}); g = gm.get(lid, {})
    hid = m.get("hl_id")
    o = dict(id=lid, name=r["name"], state=r.state1, regime=r.regime, lake_class=r.lake_class, hyd=r.hyd, hl_id=hid, hl_match=m.get("hl_match"),
             hl_name=m.get("hl_name"), hl_type=m.get("hl_type"), poly_area_km2=r.area_km2, area_ref_km2=r.area_ref_km2, hl_area_km2=m.get("hl_area_km2"),
             hl_over_poly=m.get("hl_ratio"), poly_hl_n=g.get("hl_n"), poly_hl_iou=g.get("hl_iou"), hasDam=r.hasDam, storage_mcm=r.storage_mcm, storage_src=r.storage_src)
    if hid is not None and int(hid) in pos:
        i = pos[int(hid)]; b = bp.loc[int(hid)]
        att = ds["lake_attributes"][i]; fh = ds["f_hA"][i]; h = ds["h"][i]; A = ds["A"][i]; V = ds["V"][i]
        dmax = float(att[0]); bexp = float(fh[1])
        o.update(glob_dmax_m=dmax, glob_dmax_box=b.Dmax_box_m, glob_dmax_cone=b.Dmax_cone_m, glob_dmax_prism=b.Dmax_prism_m, glob_dmax_ellip=b.Dmax_ellip_m,
                 glob_area_km2=float(att[2]), glob_vol_km3=float(att[3]), glob_mean_depth_m=float(att[3]) / float(att[2]) * 1000 if att[2] > 0 else np.nan,
                 glob_b=bexp, glob_dmax_source="modeled_estimate" if b.dmax_is_estimate else "supplied_observed")
        for d in (1.2, 1.8, 3.0):
            o[f"glob_shallow_frac_{str(d).replace('.','p')}m"] = 1 - max(0.0, 1 - d / dmax) ** bexp if dmax > 0 and bexp > 0 else np.nan
    rows.append(o)
df = pd.DataFrame(rows)
# --- flags
df["n_sector_per_hl"] = df.groupby("hl_id").id.transform("count")
fl = []
for _, r in df.iterrows():
    x = []
    if pd.isna(r.hl_id): x.append("no_match")
    else:
        if pd.isna(r.glob_dmax_m): x.append("no_globathy_row")
        if r.hl_match == "geo": x.append("geo_only_match")
        if pd.isna(r.poly_area_km2): x.append("no_polygon")
        else:
            q = r.hl_over_poly
            if pd.notna(q) and (q < 0.67 or q > 1.5): x.append("area_ratio_off")
            if pd.notna(q) and (q < 0.5 or q > 2): x.append("area_ratio_bad")
        if pd.notna(r.poly_hl_n) and r.poly_hl_n > 1: x.append("poly_spans_multi_HL")
        if pd.notna(r.poly_hl_iou) and r.poly_hl_iou < 0.5: x.append("low_iou")
        if r.n_sector_per_hl > 1: x.append("shared_HL_id")
        if r.poly_area_km2 and r.poly_area_km2 > 1500: x.append("mega")
    fl.append(";".join(x))
df["match_flags"] = fl
def tier(r):
    fs = set(r.match_flags.split(";")) - {""}
    if "no_match" in fs or "no_globathy_row" in fs: return "none"
    if fs & {"area_ratio_bad", "shared_HL_id", "low_iou", "mega"}: return "suspect"
    if fs & {"geo_only_match", "area_ratio_off", "poly_spans_multi_HL", "no_polygon"}: return "weak"
    return "verified"
df["match_tier"] = df.apply(tier, axis=1)
df.round(5).to_csv(OUT, index=False)
print(df.match_tier.value_counts())
print(df.match_flags.str.split(";").explode().value_counts())
