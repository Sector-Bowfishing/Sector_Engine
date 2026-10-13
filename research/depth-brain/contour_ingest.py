#!/usr/bin/env python3
"""Depth Brain / contour truth, step 1: NORMALIZE every downloaded contour source into one schema.

Output (outside git): ~/Desktop/Development/Sector_Research_Data/depth-brain/contour/norm/<src>.gpkg  (lines, EPSG:4326)
  columns: src, grp, grp_name, depth_ft (positive = below water surface; 0 = shoreline/island ring),
           kind (contour|shore|band), band_lo, band_hi, parse_note
and  .../contour/groups.csv  (one row per source group: bounds, n_lines, depth range, interval, parse rule).

PARSING RULES (documented here and in the report):
  depth_ft is always positive-down, in feet, relative to the surveyed water surface (NOT elevation) unless noted.
  CT   DEPTH_FT (ft, positive). BATHY_ARC Contour->contour, Shore/Island->shore (0). Marsh dropped.
  FL   -DEPTHF (ft, stored negative; 1-ft hydroacoustic). 0 -> shore. No names -> spatial cluster.
  IL   CONTOUR is depth ft for most lakes but elevation-like (up to 620) for some; resolved per spatial cluster against il_lakes_surveyed
       (max_dpth, norm_pool). Unresolvable clusters are dropped (parse_note=il_unresolved).
  IN   abs(contour) ft (some negative). Named by lake_name; blank names -> spatial cluster.
  KS   CONTOUR ft (assumed depth, positive, no unit field; max 70). No names -> spatial cluster.
  MA   DEPTH ft; SHORE==1 -> shore.
  MI   MinDepth==MaxDepth -> contour at that depth (ft). MinDepth<MaxDepth rows are closed band rings: kept as kind=band
       with band_lo/band_hi, depth_ft=NaN (interpretation resolved in contour_truth.py).
  MN   abs(depth) ft (stored negative); depth>=0 -> shore.
  MT   CONTOUR ft; TYPE S/I (shore/island) -> shore.
  ND   abs(CONTOUR) ft (stored negative); 0 -> shore.
  NE   Depth ft; 0 -> shore.
  NH   DEPTH ft; DESCRIP SHORELINE -> shore. (Other descriptors dropped.)
  NJ   VAL2NUM metres -> ft (x3.28084).
  OH   abs(DEPTH) ft.
  OK   abs(depth) ft (stored negative); vert datum noted but depth is below normal pool already.
  TN   depth parsed from Name ('10ft').
  WA   Depth ft (0 -> shore). Legacy USGS-map digitization.
  WV   Contour ft (min 1; no shoreline rows).
  UT   Utah Lake: Contour is ELEVATION ft; depth = 4489.045 - elev (compromise level). Low confidence.
  PA/WI misc: Depth_Ft / Feet (ft).
No lake-level datum shifts applied (TWDB sources are handled by the terrain thread's depth grids instead)."""
import json, re, sys, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box

SRC = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/sources")
OUT = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/contour")
NORM = OUT / "norm"
NORM.mkdir(parents=True, exist_ok=True)
FT = 3.28084


def rd(rel, **kw):
    g = gpd.read_file(SRC / rel, **kw)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g.to_crs(4326) if g.crs is not None else g.set_crs(4326)


def cluster_lines(g, dist_m=250):
    """connected components of lines within dist_m (EPSG:5070)."""
    p = g.to_crs(5070)
    b = gpd.GeoDataFrame(geometry=p.geometry.buffer(dist_m / 2), crs=5070)
    u = b.union_all()
    parts = gpd.GeoDataFrame(geometry=list(u.geoms) if hasattr(u, "geoms") else [u], crs=5070)
    parts["cid"] = np.arange(len(parts))
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=p.geometry.representative_point(), crs=5070), parts, predicate="within", how="left")
    j = j[~j.index.duplicated()]
    return j["cid"].reindex(g.index).fillna(-1).astype(int).values


def finish(g, src, grp, name, depth, kind, **extra):
    o = gpd.GeoDataFrame({"src": src, "grp": grp, "grp_name": name, "depth_ft": depth, "kind": kind}, geometry=g.geometry.values, crs=4326)
    for k, v in extra.items(): o[k] = v
    for c in ["band_lo", "band_hi", "parse_note"]:
        if c not in o: o[c] = np.nan if c != "parse_note" else ""
    return o[["src", "grp", "grp_name", "depth_ft", "kind", "band_lo", "band_hi", "parse_note", "geometry"]].reset_index(drop=True)


def s_ct():
    g = rd("ct_deep/ct_lake_bathy_lines.geojson"); g = g[g.BATHY_ARC.isin(["Contour", "Shore", "Island"])]
    kind = np.where(g.BATHY_ARC == "Contour", "contour", "shore")
    return finish(g, "CT", g.WB_NO.astype(str) + "|" + g.BAY_NO.astype(str), g.WBNAME + " (" + g.WBTOWN.fillna("") + ")", np.where(kind == "shore", 0.0, g.DEPTH_FT.astype(float)), kind)


def s_fl():
    g = rd("fl_fwc/fl_fwc_select_lakes_bathy.geojson"); cid = cluster_lines(g)
    d = (-g.DEPTHF).astype(float)
    return finish(g, "FL", "FLc" + pd.Series(cid, index=g.index).astype(str), "", d.clip(lower=0), np.where(d <= 0, "shore", "contour"))


def s_il():
    g = rd("il_idnr/il_contours.geojson"); cid = cluster_lines(g)
    lk = rd("il_idnr/il_lakes_surveyed.geojson")
    g["cid"] = cid
    keep = []
    cen = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=4326)
    j = gpd.sjoin(cen, lk[["name", "max_dpth", "norm_pool", "geometry"]], predicate="within", how="left"); j = j[~j.index.duplicated()]
    g[["lk", "mx", "pool"]] = j[["name", "max_dpth", "norm_pool"]].reindex(g.index).values
    depth = g.CONTOUR.astype(float).copy(); note = pd.Series("", index=g.index)
    for c, sub in g.groupby("cid"):
        mx, pool = sub.mx.dropna().max() if sub.mx.notna().any() else np.nan, sub.pool.dropna().median() if sub.pool.notna().any() else np.nan
        cmax = sub.CONTOUR.max()
        if np.isfinite(mx) and cmax <= 1.3 * mx + 3: note[sub.index] = "il_depth"
        elif np.isfinite(mx) and np.isfinite(pool) and cmax > 1.3 * mx + 3 and 0 <= pool - cmax <= pool:
            depth[sub.index] = pool - sub.CONTOUR; note[sub.index] = "il_elev_to_depth"
        elif not np.isfinite(mx) and cmax <= 60: note[sub.index] = "il_depth_noanchor"
        else: note[sub.index] = "il_unresolved"
    ok = ~note.eq("il_unresolved") & (depth >= 0)
    g = g[ok]
    return finish(g, "IL", "ILc" + g.cid.astype(str), g.lk.fillna(""), depth[ok].clip(lower=0), np.where(depth[ok] <= 0, "shore", "contour"), parse_note=note[ok].values)


def s_in():
    g = rd("in_dnr/in_lake_bathy_contours.geojson"); d = g.contour.abs().astype(float)
    nm = g.lake_name.fillna("").str.strip(); un = nm == ""
    grp = nm.copy()
    if un.any():
        cid = cluster_lines(g[un]); grp[un] = "INc" + pd.Series(cid, index=g[un].index).astype(str)
    return finish(g, "IN", grp, nm, d, np.where(d <= 0, "shore", "contour"))


def s_ks():
    g = rd("ks_kbs/ks_bathy_contours.geojson"); cid = cluster_lines(g)
    return finish(g, "KS", "KSc" + pd.Series(cid, index=g.index).astype(str), "", g.CONTOUR.astype(float), "contour")


def s_ma():
    g = rd("ma_masswildlife/ma_inland_bathy.geojson"); sh = g.SHORE == 1
    return finish(g, "MA", g.PALIS_ID.astype(str), g.NAME, np.where(sh, 0.0, g.DEPTH.astype(float)), np.where(sh, "shore", "contour"))


def s_mi():
    g = rd("mi_dnr_contours/mi_inland_lake_contours.geojson"); eq = g.MinDepth == g.MaxDepth
    d = np.where(eq, g.MaxDepth.astype(float), np.nan)
    kind = np.where(eq, np.where(g.MaxDepth == 0, "shore", "contour"), "band")
    return finish(g, "MI", g.NewKey.astype(str), g.Name, d, kind, band_lo=np.where(eq, np.nan, g.MinDepth), band_hi=np.where(eq, np.nan, g.MaxDepth))


def s_mn():
    g = rd("mn_dnr/mn_bathy_contours.geojson"); d = g.depth.abs().astype(float).where(g.depth < 0, 0.0)
    return finish(g, "MN", g.dowlknum, g.lake_name, d, np.where(d <= 0, "shore", "contour"))


def s_mt():
    g = rd("mt_fwp/mt_lakes_bathymetry.geojson"); sh = g.TYPE.str.upper().isin(["S", "I"])
    return finish(g, "MT", g.LAKENAME.fillna("") + "|" + g.LLID.fillna(""), g.LAKENAME, np.where(sh, 0.0, g.CONTOUR.astype(float)), np.where(sh, "shore", "contour"))


def s_nd():
    g = rd("nd_gnf/nd_gnf_lake_contours.geojson"); d = g.CONTOUR.abs().astype(float)
    return finish(g, "ND", g.LAKE.astype(str), g.LAKE_NAME, d, np.where(d <= 0, "shore", "contour"))


def s_ne():
    g = rd("ne_ngpc/ne_lake_contours.geojson"); d = g.Depth.astype(float)
    return finish(g, "NE", g.Name, g.Name, d, np.where(d <= 0, "shore", "contour"))


def s_nh():
    g = rd("nh_des/nh_bathy_lines.geojson"); desc = g.DESCRIP.fillna("").str.upper().str.strip()
    sh = desc.isin(["SHORELINE", "SHORLINE"]); bt = desc.isin(["BATHYMETRY", "BATHMETRY"])
    g = g[sh | bt]; sh = sh[g.index]
    return finish(g, "NH", g.AU_ID.fillna("") + "|" + g.LAKE.fillna(""), g.LAKE, np.where(sh, 0.0, g.DEPTH.astype(float)), np.where(sh, "shore", "contour"))


def s_nj():
    g = rd("nj_dep/nj_lake_bathy_contours.geojson")
    return finish(g, "NJ", g.WATBODNM, g.WATBODNM, g.VAL2NUM.astype(float) * FT, "contour", parse_note="metres_to_ft")


def s_oh():
    g = rd("oh_dow/oh_dow_lake_bathymetry.geojson"); d = g.DEPTH.abs().astype(float)
    return finish(g, "OH", g.LAKE_NAME, g.LAKE_NAME, d, "contour")


def s_ok():
    g = rd("ok_owrb/ok_owrb_contours.geojson"); d = g.depth.abs().astype(float)
    return finish(g, "OK", g.lake, g.lake, d, np.where(d <= 0, "shore", "contour"), parse_note=g.vert_datum.fillna("").values)


def s_tn():
    g = rd("tn_twra/tn_twra_lake_bathy.geojson")
    d = g.Name.str.extract(r"(\d+(?:\.\d+)?)")[0].astype(float)
    ok = d.notna(); g, d = g[ok], d[ok]
    return finish(g, "TN", g.Waterbody, g.Waterbody, d, "contour")


def s_wa():
    g = rd("wa_ecy/wa_ecy_lake_bathy_lines.geojson"); d = g.Depth.astype(float)
    return finish(g, "WA", g.GNIS_Name.fillna("") + "|" + g.ReachCode.fillna(""), g.GNIS_Name, d, np.where(d <= 0, "shore", "contour"))


def s_wv():
    g = rd("wv_dnr/wv_pfl_contours.geojson")
    return finish(g, "WV", g.LakeName, g.LakeName, g.Contour.astype(float), "contour")


def s_misc():
    out = []
    g = rd("misc_ago/ut_utah_lake_contours.geojson"); out.append(finish(g, "UT", "Utah Lake", "Utah Lake", (4489.045 - g.Contour.astype(float)).clip(lower=0), "contour", parse_note="elev_ft_to_depth_vs_4489.045"))
    g = rd("misc_ago/pa_harveys_lake_contours10ft.geojson"); out.append(finish(g, "PA", "Harveys Lake", "Harveys Lake", g.Depth_Ft.astype(float), "contour"))
    g = rd("misc_ago/wi_chippewa_flowage_contour5ft_DRAFT.geojson"); out.append(finish(g, "WI", "Chippewa Flowage", "Chippewa Flowage", g.Feet.astype(float), "contour", parse_note="DRAFT"))
    return pd.concat(out, ignore_index=True)


FUN = dict(CT=s_ct, IL=s_il, IN=s_in, KS=s_ks, MA=s_ma, MI=s_mi, MN=s_mn, MT=s_mt, ND=s_nd, NE=s_ne, NH=s_nh, NJ=s_nj, OH=s_oh, OK=s_ok, TN=s_tn, WA=s_wa, WV=s_wv, MISC=s_misc, FL=s_fl)


def group_table(o):
    rows = []
    for (s, k), sub in o.groupby(["src", "grp"], sort=False):
        c = sub[sub.kind == "contour"].depth_ft.dropna()
        lv = np.sort(c.unique())
        b = sub.total_bounds
        rows.append(dict(src=s, grp=k, grp_name=sub.grp_name.iloc[0], n_lines=len(sub), n_contour=len(c), has_shore=bool((sub.kind == "shore").any()),
                         n_band=int((sub.kind == "band").sum()), dmin=float(lv.min()) if len(lv) else np.nan, dmax=float(lv.max()) if len(lv) else np.nan,
                         n_levels=len(lv), interval=float(np.median(np.diff(lv))) if len(lv) > 1 else np.nan,
                         minx=b[0], miny=b[1], maxx=b[2], maxy=b[3]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    which = sys.argv[1:] or list(FUN)
    for k in which:
        t = time.time()
        o = FUN[k]()
        for s, sub in o.groupby("src"):
            sub.to_file(NORM / f"{s}.gpkg", driver="GPKG")
            group_table(sub).to_csv(NORM / f"{s}_groups.csv", index=False)
            print(k, s, len(sub), "lines", sub.grp.nunique(), "groups", round(time.time() - t), "s", flush=True)
