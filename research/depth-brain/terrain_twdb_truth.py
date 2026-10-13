#!/usr/bin/env python3
"""Depth Brain / terrain: turn each fetched TWDB survey into (a) a conservation-pool polygon (GeoJSON, EPSG:4326) and (b) hypsometric truth from the
area-capacity table: pool elevation (where table area == polygon area), area A(z) at pool-d, and 'shallow share' S_d = (A_pool - A_(pool-d)) / A_pool,
i.e. the fraction of the pool surface whose bottom is within d feet of the surface (0-d ft deep).  Also rel_per_ft = dA/dz / A  (comparable to CWMS truth).
Run with python -I.  Output: <RAW>/twdb_truth.json  and  <RAW>/specs/twdb.json (polygon files for terrain_dem_profile.py)."""
import json, re, sys
from pathlib import Path
import numpy as np
import geopandas as gpd

RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
M2_PER_FT2 = 0.09290304; M2_PER_AC = 4046.8564224


def read_table(p):
    a = []
    for line in open(p):
        try:
            e, ar, cap = [float(x) for x in line.strip().split(",")[:3]]
            a.append((abs(e), ar, cap))
        except Exception:
            pass
    a = np.array(sorted(a))
    return a


def pick_polygon(shpdir):
    cands = []
    for f in sorted(shpdir.glob("*.shp")):
        n = f.stem.lower()
        if any(k in n for k in ("land", "pts", "point", "line", "arc", "tin", "survey", "sediment", "sounding", "terr", "lidar")) and not ("lake" in n or "poly" in n or "bndy" in n):
            continue
        if any(k in n for k in ("land", "pts", "point", "survey", "sediment", "sounding")):
            continue
        try:
            g = gpd.read_file(f)
        except Exception:
            continue
        if len(g) == 0 or not all(t in ("Polygon", "MultiPolygon") for t in g.geom_type.unique()):
            continue
        cands.append((f, g))
    return cands


def main():
    out = {}; spec = {}
    for d in sorted((RAW / "twdb").iterdir()):
        if not (d / "table.txt").exists() or not (d / "shp").exists():
            continue
        key = d.name
        try:
            tab = read_table(d / "table.txt")
            if len(tab) < 20:
                out[key] = dict(status="table-unreadable"); continue
            cands = pick_polygon(d / "shp")
            if not cands:
                out[key] = dict(status="no-polygon"); continue
            best = None
            for f, g in cands:
                if g.crs is None:
                    continue
                gm = g.to_crs(5070)               # CONUS Albers equal-area
                area_m2 = float(gm.geometry.union_all().area) if hasattr(gm.geometry, "union_all") else float(gm.geometry.unary_union.area)
                # table unit: acres if the max area < 1e6 else ft2
                unit = M2_PER_AC if tab[:, 1].max() < 2e6 else M2_PER_FT2
                ta = tab[:, 1] * unit
                # pool = table elevation with area == polygon area (must lie inside table range, not at its very top)
                if area_m2 < ta[1] or area_m2 > ta[-1] * 1.03:
                    continue
                pool = float(np.interp(min(area_m2, ta[-1]), ta, tab[:, 0]))
                score = abs(pool - tab[-1, 0])      # prefer polygon closest to (but below) top-of-table = conservation pool at a mapped extent
                if best is None or area_m2 > best[0]:
                    best = (area_m2, pool, f, g, unit)
            if best is None:
                out[key] = dict(status="polygon-area-outside-table", polys=[c[0].name for c in cands]); continue
            area_m2, pool, f, g, unit = best
            z, A = tab[:, 0], tab[:, 1] * unit
            Ap = float(np.interp(pool, z, A))
            res = dict(status="ok", polygon=f.name, pool_ft=round(pool, 2), area_pool_ac=round(Ap / M2_PER_AC, 1), table_top_ft=float(z[-1]), table_bottom_ft=float(z[0]), table_unit="ac" if unit == M2_PER_AC else "ft2")
            for dft in (1, 2, 3, 4, 6, 10):
                Ad = float(np.interp(pool - dft, z, A, left=0.0))
                res[f"S{dft}"] = round((Ap - Ad) / Ap, 4)            # share of pool surface with depth <= dft
            # rel_per_ft: dA/dz over top 15 ft below pool, fit like the CWMS truth (quadratic A(z)); here A(z) is already differenced so use finite slope
            za = np.linspace(pool - 15, pool, 31); Aa = np.interp(za, z, A)
            slope = np.polyfit(za, Aa, 1)[0]
            res["rel_per_ft_15"] = round(float(slope / Ap), 5)
            res["rel_per_ft_5"] = round(float((Ap - np.interp(pool - 5, z, A)) / 5 / Ap), 5)
            zfrac = lambda frac: float(np.interp(frac * Ap, A, z))
            res["max_depth_ft"] = round(float(pool - z[np.argmax(A > 0)]), 1)
            # volume-based mean depth
            Cp = float(np.interp(pool, z, tab[:, 2])) * (unit if unit == M2_PER_FT2 else 1)
            out[key] = res
            gg = g.to_crs(4326)
            geom = gg.geometry.union_all() if hasattr(gg.geometry, "union_all") else gg.geometry.unary_union
            fp = RAW / "twdb" / key / "pool_polygon.geojson"
            fp.write_text(json.dumps(geom.__geo_interface__)); spec[key] = str(fp)
            print(key, res["pool_ft"], res["area_pool_ac"], res["S3"], res["S6"], f.name, flush=True)
        except Exception as e:
            out[key] = dict(status="error", err=repr(e)[:160]); print(key, "ERR", repr(e)[:100], flush=True)
    (RAW / "twdb_truth.json").write_text(json.dumps(out, indent=1))
    (RAW / "specs").mkdir(exist_ok=True)
    (RAW / "specs/twdb.json").write_text(json.dumps(spec, indent=1))
    print(sum(1 for v in out.values() if v.get("status") == "ok"), "ok of", len(out))


if __name__ == "__main__":
    main()
