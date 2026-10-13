#!/usr/bin/env python3
"""Depth Brain / contour truth: validate the contour->shares METHOD itself.
 (1) REAL contours vs EXACT hypsometry: for every TWDB lake that has a 1/2/5-ft contour shapefile (fetched by the terrain thread) run contour_grid on (a) the native ladder,
     (b) every-5th-foot, (c) every-10th-foot contours, and compare shr<=3/<=6/<=10 ft with the area-capacity-table shares S3/S6/S10 (independent of any contour interpolation).
 (2) Same decimation applied to the dense-ladder FLEET lakes (native vs 5-ft vs 10-ft) – method sensitivity to contour interval where there is no table.
Output data/contour_method_check.json (+ csv).  Run with the venv python, -I."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import shape
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).parent))
import contour_grid as cg

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain/data"
T = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")


def elev_col(g):
    for c in g.columns:
        if c.lower() in ("contour", "elevation", "elev", "z", "value", "level", "cont", "contour_ft", "elev_ft"): return c
    num = [c for c in g.columns if c != "geometry" and np.issubdtype(g[c].dtype, np.number)]
    return num[0] if num else None


def decimate(lines, step):
    """keep levels closest to multiples of `step` ft (within 0.6 ft); shore (0) always kept."""
    if step is None: return lines
    lv = np.array(sorted({d for d, _ in lines if d > 0}))
    keep = set()
    for m in np.arange(step, lv.max() + step, step):
        j = np.argmin(np.abs(lv - m))
        if abs(lv[j] - m) <= 0.6: keep.add(lv[j])
    return [(d, g) for d, g in lines if d == 0 or d in keep]


def shares(g):
    d = g["depth"]; v = d[np.isfinite(d)]
    return dict(s3=float((v <= 3).mean()), s6=float((v <= 6).mean()), s10=float((v <= 10).mean()), cov=float(v.size / g["water"].sum()))


def twdb_one(args):
    key, = args
    try:
        tr = json.load(open(T / "twdb_truth.json"))[key]; pool = tr["pool_ft"]
        cdir = T / "twdb" / key / "contours"
        shp = sorted(cdir.glob("*.shp"))
        if not shp: return dict(key=key, error="no contour shp")
        g = gpd.read_file(shp[0]); ec = elev_col(g)
        g = g.to_crs(5070)
        poly = gpd.GeoSeries([shape(json.load(open(T / "twdb" / key / "pool_polygon.geojson")))], crs=4326).to_crs(5070).make_valid().iloc[0]
        depth = pool - g[ec].abs().values
        lines = [(float(round(d, 2)), geom) for d, geom in zip(depth, g.geometry) if geom is not None and not geom.is_empty and d > 0.05 and geom.intersects(poly)]
        if not lines: return dict(key=key, error="no lines")
        cell = cg.pick_cell(poly.area, poly.bounds)
        out = dict(key=key, area_km2=poly.area / 1e6, n_levels=len({d for d, _ in lines}), cell=cell, S3=tr["S3"], S6=tr["S6"], S10=tr["S10"])
        for tag, st in (("native", None), ("d5", 5.0), ("d10", 10.0)):
            L = decimate(lines, st)
            gr = cg.build_depth(poly, L, cell)
            for k, v in shares(gr).items(): out[f"{tag}_{k}"] = v
        return out
    except Exception as e:
        return dict(key=key, error=repr(e)[:200])


def fleet_one(args):
    lid, src, grps, poly_wkb = args
    try:
        poly = shapely.from_wkb(poly_wkb)
        lines = gpd.read_file(RAW / f"depth-brain/contour/norm/{src}.gpkg", where="grp IN (%s)" % ",".join("'" + x.replace("'", "''") + "'" for x in grps)).to_crs(5070)
        lines = lines[lines.kind.isin(["contour", "shore"])]
        L = [(float(d), g) for d, g in zip(lines.depth_ft, lines.geometry) if d > 0]
        cell = cg.pick_cell(poly.area, poly.bounds)
        out = dict(lakeId=lid, src=src, cell=cell)
        for tag, st in (("native", None), ("d5", 5.0), ("d10", 10.0)):
            gr = cg.build_depth(poly, decimate(L, st), cell)
            for k, v in shares(gr).items(): out[f"{tag}_{k}"] = v
        return out
    except Exception as e:
        return dict(lakeId=lid, error=repr(e)[:200])


def stats(df, a, b):
    e = df[a] - df[b]
    return dict(n=int(e.notna().sum()), bias=float(e.mean()), mae=float(e.abs().mean()), rmse=float(np.sqrt((e ** 2).mean())), p90_abs=float(e.abs().quantile(.9)), max_abs=float(e.abs().max()),
                spearman=float(df[[a, b]].corr(method="spearman").iloc[0, 1]))


def main():
    keys = [k for k, v in json.load(open(T / "twdb_truth.json")).items() if v.get("status") == "ok" and (T / "twdb" / k / "contours").exists() and list((T / "twdb" / k / "contours").glob("*.shp"))]
    print(len(keys), "TWDB lakes with contour shp", flush=True)
    with Pool(6, maxtasksperchild=2) as pool:
        rows = list(pool.imap_unordered(twdb_one, [(k,) for k in keys]))
    tw = pd.DataFrame(rows); tw.to_csv(D / "contour_method_check_twdb.csv", index=False, float_format="%.4f")
    ok = tw[tw.get("error").isna()] if "error" in tw else tw
    res = dict(twdb_n=int(len(ok)), twdb_errors=int(len(tw) - len(ok)))
    for tag in ("native", "d5", "d10"):
        res[f"twdb_{tag}"] = {s: stats(ok.assign(**{f"t{s}": ok[f"S{s[1:]}"]}), f"{tag}_{s}", f"t{s}") for s in ("s3", "s6", "s10")}
    # fleet decimation on dense ladders
    p = pd.read_csv(RAW / "depth-brain/contour/truth_pairs_flagged.csv")
    dense = p[(p.method == "contour_interp") & (p.ladder == "fine") & (p.hull_class == "full") & (p.interval_ft <= 2.5) & (p.max_contour_ft >= 8)]
    m = pd.read_csv(D / "contour_matches_verified.csv", dtype={"grp": str})
    import gzip
    raw = json.loads(gzip.open(RAW / "lake-brain/geometry/engine_polygons_599.geojson.gz").read())
    g = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
    g["geometry"] = g.geometry.apply(lambda x: shapely.union_all([q for q in x.geoms if q.geom_type in ("Polygon", "MultiPolygon")]) if x.geom_type == "GeometryCollection" else x)
    g = g.to_crs(5070); g["geometry"] = g.geometry.make_valid(); pm = dict(zip(g.id, g.geometry))
    tasks = []
    for r in dense.itertuples():
        sub = m[(m.lakeId == r.lakeId) & (m.src == r.src) & (m.matchConfidence == "verified_spatial")]
        tasks.append((r.lakeId, r.src, sub.grp.astype(str).tolist(), shapely.to_wkb(pm[r.lakeId])))
    with Pool(6, maxtasksperchild=2) as pool:
        fr = list(pool.imap_unordered(fleet_one, tasks))
    fl = pd.DataFrame(fr); fl.to_csv(D / "contour_method_check_fleet.csv", index=False, float_format="%.4f")
    okf = fl[fl.get("error").isna()] if "error" in fl else fl
    res["fleet_dense_n"] = int(len(okf))
    for tag in ("d5", "d10"):
        res[f"fleet_{tag}_vs_native"] = {s: stats(okf, f"{tag}_{s}", f"native_{s}") for s in ("s3", "s6", "s10")}
    json.dump(res, open(D / "contour_method_check.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
