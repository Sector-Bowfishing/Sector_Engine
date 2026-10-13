#!/usr/bin/env python3
"""Depth Brain / contour truth, step 3: bowfishing truth per verified lake (contour_grid.py method).

For every (lake, source) pair verified_spatial in data/contour_matches_verified.csv: collect the lake's verified contour groups, build the depth raster inside
the fleet polygon, compute metrics, save the raster (outside git) and write one row per pair to
~/Desktop/Development/Sector_Research_Data/depth-brain/contour/truth_pairs.csv .  contour_truth_select.py then picks one source per lake and writes the git outputs.
Usage: contour_truth.py [SRC ...]    (default: all sources)  – run with the venv python, -I."""
import gc, gzip, json, sys, time, traceback
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).parent))
import contour_grid as cg

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
NORM = RAW / "depth-brain/contour/norm"
GRIDS = RAW / "depth-brain/contour/grids"; GRIDS.mkdir(parents=True, exist_ok=True)
OUTD = RAW / "depth-brain/contour"
EPSG = 5070


def safe(s): return "".join(ch if ch.isalnum() else "_" for ch in s)


def ladder(levels):
    """levels: sorted positive contour depths (ft). Returns (first_level, max_gap_to10, max_level)."""
    lv = [0.0] + sorted(set(float(x) for x in levels if x > 0))
    pre = []
    for x in lv:
        pre.append(x)
        if x >= 10: break
    gaps = np.diff(pre) if len(pre) > 1 else np.array([np.nan])
    return (lv[1] if len(lv) > 1 else np.nan), float(np.nanmax(gaps)), lv[-1]


def one_lake(args):
    lid, src, grps, poly_wkb, name = args
    t0 = time.time()
    try:
        poly = shapely.from_wkb(poly_wkb)
        lines = gpd.read_file(NORM / f"{src}.gpkg", where="grp IN (%s)" % ",".join("'" + g.replace("'", "''") + "'" for g in grps)).to_crs(EPSG)
        lines = lines[lines.kind.isin(["contour", "shore"]) & lines.depth_ft.notna()]
        row = dict(lakeId=lid, src=src, n_lines=len(lines), n_groups=len(grps))
        if len(lines) == 0:
            row["note"] = "no contour/shore lines (band-only or empty)"; return row
        lv = lines[lines.kind == "contour"].depth_ft.values
        first, gap10, mx = ladder(lv)
        uniq = np.unique(lv)
        row.update(first_level_ft=first, max_gap_to10_ft=gap10, max_contour_ft=mx, n_levels=len(uniq),
                   interval_ft=float(np.median(np.diff(uniq))) if len(uniq) > 1 else np.nan, has_dataset_shore=bool((lines.kind == "shore").any()))
        hull = shapely.union_all(lines.geometry.values).convex_hull
        row["cov_hull"] = hull.intersection(poly).area / poly.area
        cell = cg.pick_cell(poly.area, poly.bounds)
        glines = [(float(d), g) for d, g in zip(lines.depth_ft.values, lines.geometry.values)]
        g = cg.build_depth(poly, glines, cell)
        m = cg.metrics(g)
        row.update(m)
        row.update(nfaces=g.get("nfaces"), n_single=g.get("n_single"), n_single_resolved=g.get("n_single_resolved"))
        np.savez_compressed(GRIDS / f"{safe(lid)}__{src}.npz", depth_ft=g["depth"].astype(np.float16), transform=np.array(g["tr"])[:6], cell=cell, crs=EPSG)
        row["poly_area_km2"] = poly.area / 1e6
        row["secs"] = round(time.time() - t0, 1)
        return row
    except Exception as e:
        return dict(lakeId=lid, src=src, error=repr(e)[:300], tb=traceback.format_exc()[-400:])


def main():
    only = set(sys.argv[1:])
    m = pd.read_csv(D / "data/contour_matches_verified.csv", dtype={"grp": str})
    v = m[m.matchConfidence == "verified_spatial"]
    if only: v = v[v.src.isin(only)]
    raw = json.loads(gzip.open(RAW / "lake-brain/geometry/engine_polygons_599.geojson.gz").read())
    g = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
    g["geometry"] = g.geometry.apply(lambda x: shapely.union_all([p for p in x.geoms if p.geom_type in ("Polygon", "MultiPolygon")]) if x.geom_type == "GeometryCollection" else x)
    g = g.to_crs(EPSG); g["geometry"] = g.geometry.make_valid(); pm = dict(zip(g.id, g.geometry))
    tasks = []
    for (lid, src), sub in v.groupby(["lakeId", "src"]):
        if lid not in pm: continue                      # polygon-less lakes: handled as 'point' matches, no area truth
        tasks.append((lid, src, [str(x) for x in sub.grp.tolist()], shapely.to_wkb(pm[lid]), ""))
    tasks.sort(key=lambda t: -pm[t[0]].area)
    print(len(tasks), "pairs", flush=True)
    rows = []
    with Pool(6, maxtasksperchild=4) as pool:
        for r in pool.imap_unordered(one_lake, tasks):
            rows.append(r); print(r.get("lakeId"), r.get("src"), r.get("secs"), r.get("error", ""), flush=True)
            pd.DataFrame(rows).to_csv(OUTD / ("truth_pairs.csv" if not only else "truth_pairs_partial.csv"), index=False)
    print("done", len(rows))


if __name__ == "__main__":
    main()
