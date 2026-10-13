#!/usr/bin/env python3
"""Depth Brain / contour truth: merge the per-source normalized contour layers (contour_ingest.py) into ONE table of contour segments with the verified fleet lake id.
Columns: lakeId ('' if unmatched), matchConfidence (verified_spatial | rejected | unmatched), src, grp, grp_name, depth_ft (positive down, ft, below water surface), kind, band_lo, band_hi, parse_note.
Output (NOT in git; FL FWC data must not be redistributed): ~/Desktop/Development/Sector_Research_Data/depth-brain/contour/contour_segments_normalized.gpkg  (EPSG:4326 lines)."""
from pathlib import Path
import pandas as pd, geopandas as gpd
REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/contour")
m = pd.read_csv(REPO / "docs/research/depth-brain/data/contour_matches_verified.csv", dtype={"grp": str})
m = m[m.grp.notna() & (m.src != "TWDB")]
v = m[m.matchConfidence == "verified_spatial"].sort_values("fracLenIn", ascending=False).drop_duplicates(["src", "grp"])
vmap = {(r.src, r.grp): r.lakeId for r in v.itertuples()}
rmap = {(r.src, r.grp) for r in m[m.matchConfidence == "rejected"].itertuples()}
out = RAW / "contour_segments_normalized.gpkg"
if out.exists(): out.unlink()
tot = 0
for gp in sorted((RAW / "norm").glob("*.gpkg")):
    g = gpd.read_file(gp)
    key = list(zip(g.src, g.grp.astype(str)))
    g["lakeId"] = [vmap.get(k, "") for k in key]
    g["matchConfidence"] = ["verified_spatial" if k in vmap else ("rejected" if k in rmap else "unmatched") for k in key]
    g.to_file(out, driver="GPKG", layer="segments", mode="a" if tot else "w")
    tot += len(g); print(gp.stem, len(g), (g.lakeId != "").sum(), flush=True)
print("total", tot, out, round(out.stat().st_size / 1e6), "MB")
