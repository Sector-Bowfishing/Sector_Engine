#!/usr/bin/env python3
"""Depth Brain / contour truth: add TWDB area-capacity-table hypsometry (computed read-only by the terrain thread: terrain/twdb_truth.json + per-lake pool polygons)
as an independent truth source for FLEET lakes.  Verification is geometric: TWDB pool polygon vs fleet polygon (intersection over each area >= 0.5).
S_d = share of pool surface with bottom within d ft of the surface (0-d ft).  These are exact table values (not interpolated from contour lines).
Writes data/contour_twdb_truth.csv and rewrites the TWDB rows in data/contour_matches_verified.csv (verified / rejected for the scout's S-depth-001 name candidates)."""
import gzip, json, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import shape
from shapely import STRtree

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
T = RAW / "depth-brain/terrain"
EPSG = 5070


def main():
    truth = json.load(open(T / "twdb_truth.json"))
    raw = json.loads(gzip.open(RAW / "lake-brain/geometry/engine_polygons_599.geojson.gz").read())
    fl = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
    fl["geometry"] = fl.geometry.apply(lambda x: shapely.union_all([p for p in x.geoms if p.geom_type in ("Polygon", "MultiPolygon")]) if x.geom_type == "GeometryCollection" else x)
    fl = fl.to_crs(EPSG); fl["geometry"] = fl.geometry.make_valid(); fl = fl.set_index("id")
    tree = STRtree(fl.geometry.values)
    feat = pd.read_csv("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv").set_index("id")
    rows, mrows = [], []
    for k, v in truth.items():
        if v.get("status") != "ok": continue
        pp = T / "twdb" / k / "pool_polygon.geojson"
        if not pp.exists(): continue
        P = gpd.GeoSeries([shape(json.load(open(pp)))], crs=4326).to_crs(EPSG).make_valid().iloc[0]
        for h in tree.query(P, predicate="intersects"):
            lid = fl.index[h]; F = fl.geometry.iloc[h]
            inter = P.intersection(F).area
            fa, ta = inter / F.area, inter / P.area
            if fa < 0.2 and ta < 0.2: continue
            ok = fa >= 0.5 and ta >= 0.5
            mrows.append(dict(lakeId=lid, lakeName=feat.name.get(lid, ""), state=feat.state1.get(lid, ""), src="TWDB", grp=k, grp_name=k, fracLenIn=np.nan, hullCov=min(ta, 1.0), lakeAreaKm2=F.area / 1e6,
                              nameAgree=np.nan, matchBasis=f"polygon_overlap fleetIn={fa:.2f} twdbIn={ta:.2f}", matchConfidence="verified_spatial" if ok else "rejected",
                              reason="TWDB pool polygon overlaps fleet polygon (both fractions >= 0.5)" if ok else f"partial polygon overlap (fleet {fa:.2f}, twdb {ta:.2f})"))
            if ok:
                s3, s6, s10 = v["S3"], v["S6"], v["S10"]
                rows.append(dict(lakeId=lid, src="TWDB", twdbKey=k, pool_area_km2=v["area_pool_ac"] * 4046.8564 / 1e6, poly_area_km2=F.area / 1e6, survey=k.split("_")[-1],
                                 shr_0_3=s3, shr_3_6=s6 - s3, shr_6_10=s10 - s6, shr_gt10=1 - s10, S1=v["S1"], S2=v["S2"], S4=v["S4"], max_contour_ft=v["max_depth_ft"],
                                 rel_per_ft_15=v["rel_per_ft_15"], cov_hull=1.0, cov_raster=1.0, first_level_ft=1.0, max_gap_to10_ft=1.0))
    t = pd.DataFrame(rows)
    t.to_csv(D / "data/contour_twdb_truth.csv", index=False, float_format="%.4f")
    m = pd.read_csv(D / "data/contour_matches_verified.csv", dtype={"grp": str})
    m = m[~((m.src == "TWDB") | (m.src == "S-depth-001"))]
    m = pd.concat([m, pd.DataFrame(mrows)], ignore_index=True)
    m.to_csv(D / "data/contour_matches_verified.csv", index=False, float_format="%.4f")
    print("TWDB verified fleet lakes:", t.lakeId.nunique(), "pairs", len(t), "| rejected partial", sum(r["matchConfidence"] == "rejected" for r in mrows))
    print(t[["lakeId", "twdbKey", "poly_area_km2", "pool_area_km2", "shr_0_3"]].to_string())


if __name__ == "__main__":
    main()
