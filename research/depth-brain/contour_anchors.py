#!/usr/bin/env python3
"""Depth Brain / contour truth: independent MAX-DEPTH anchors, verified by geometry (point inside the fleet polygon or <=300 m from it).
Used to judge whether contour max depth is believable (completeness) – not as bathymetry.
Sources: EPA NLA 2007 DEPTHMAX (index-site depth, m -> ft; lower bound of true max), OWRB lake points depth_max (ft), MI IFR Max_Depth (ft) points,
IL IDNR surveyed-lake polygons (max_dpth ft, mean_dpth ft), IN DNR lake_max_depth attribute (ft; per contour group), NH/NE/others none.
Output data/contour_anchors_verified.csv."""
import gzip, json
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
S = RAW / "depth-brain/sources"
EPSG = 5070
FT = 3.28084


def fleet():
    raw = json.loads(gzip.open(RAW / "lake-brain/geometry/engine_polygons_599.geojson.gz").read())
    g = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
    g["geometry"] = g.geometry.apply(lambda x: shapely.union_all([p for p in x.geoms if p.geom_type in ("Polygon", "MultiPolygon")]) if x.geom_type == "GeometryCollection" else x)
    g = g.to_crs(EPSG); g["geometry"] = g.geometry.make_valid()
    return g[["id", "geometry"]]


def pts_in(points, fl, buf=300):
    p = gpd.GeoDataFrame(points.drop(columns="geometry"), geometry=points.geometry.to_crs(EPSG), crs=EPSG)
    f2 = fl.copy(); f2["geometry"] = f2.geometry.buffer(buf)
    j = gpd.sjoin(p, f2, predicate="within", how="inner")
    return j.drop(columns="index_right")


def main():
    fl = fleet(); out = []
    n = pd.read_csv(S / "epa_nla/nla2007_sampledlakeinformation_20091113.csv", low_memory=False)
    n = n[n.DEPTHMAX.notna() & n.LAT_DD.notna()]
    g = gpd.GeoDataFrame(n[["SITE_ID", "LAKENAME", "ST", "DEPTHMAX", "DEPTH_X"]], geometry=gpd.points_from_xy(n.LON_DD, n.LAT_DD), crs=4326)
    j = pts_in(g, fl)
    j = j.groupby("id").agg(depth_ft=("DEPTHMAX", lambda s: s.max() * FT), nm=("LAKENAME", "first"), n=("SITE_ID", "size")).reset_index()
    j["anchor_src"] = "EPA_NLA2007_DEPTHMAX"; j["kind"] = "index_site_depth_lower_bound"; out.append(j.rename(columns={"id": "lakeId", "nm": "anchorName"}))
    ok = gpd.read_file(S / "ok_owrb/ok_owrb_lake_points.geojson")[["name_full", "depth_max", "depth_mean", "geometry"]]
    ok = ok[ok.depth_max.notna()]
    j = pts_in(ok, fl)
    j = j.rename(columns={"id": "lakeId", "name_full": "anchorName", "depth_max": "depth_ft"}); j["anchor_src"] = "OWRB_depth_max"; j["kind"] = "regulator_reported_max"; out.append(j[["lakeId", "anchorName", "depth_ft", "depth_mean", "anchor_src", "kind"]])
    mi = gpd.read_file(S / "mi_ifr/mi_lake_deep_points.geojson")[["Lake_Name", "Max_Depth", "geometry"]]
    j = pts_in(mi, fl).rename(columns={"id": "lakeId", "Lake_Name": "anchorName", "Max_Depth": "depth_ft"})
    j = j.groupby("lakeId").agg(depth_ft=("depth_ft", "max"), anchorName=("anchorName", "first")).reset_index(); j["anchor_src"] = "MI_IFR_max_depth"; j["kind"] = "agency_max_depth"; out.append(j)
    il = gpd.read_file(S / "il_idnr/il_lakes_surveyed.geojson").to_crs(EPSG); il["geometry"] = il.geometry.make_valid()
    jj = gpd.sjoin(il[["name", "max_dpth", "mean_dpth", "geometry"]], fl, predicate="intersects", how="inner")
    jj["ov"] = [a.intersection(fl.set_index("id").geometry[i]).area / a.area for a, i in zip(jj.geometry, jj.id)]
    jj = jj[jj.ov > 0.5].rename(columns={"id": "lakeId", "name": "anchorName", "max_dpth": "depth_ft", "mean_dpth": "depth_mean"})
    jj["anchor_src"] = "IL_IDNR_survey"; jj["kind"] = "survey_max_depth"; out.append(jj[["lakeId", "anchorName", "depth_ft", "depth_mean", "anchor_src", "kind"]])
    ind = gpd.read_file(S / "in_dnr/in_lake_bathy_contours.geojson", columns=["lake_name", "lake_max_depth"]).to_crs(EPSG)
    ind = ind[ind.lake_max_depth.notna() & (ind.lake_max_depth > 0)]
    ind["geometry"] = ind.geometry.representative_point()
    j = pts_in(ind, fl, 0).groupby("id").agg(depth_ft=("lake_max_depth", "max"), anchorName=("lake_name", "first")).reset_index().rename(columns={"id": "lakeId"})
    j["anchor_src"] = "IN_DNR_lake_max_depth"; j["kind"] = "agency_max_depth"; out.append(j)
    a = pd.concat(out, ignore_index=True)
    a["depth_ft"] = a.depth_ft.astype(float).abs().round(1)
    a.to_csv(REPO / "docs/research/depth-brain/data/contour_anchors_verified.csv", index=False)
    print(a.groupby("anchor_src").lakeId.nunique().to_dict(), a.lakeId.nunique())


if __name__ == "__main__":
    main()
