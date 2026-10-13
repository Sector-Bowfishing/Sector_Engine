#!/usr/bin/env python3
"""Depth Brain / contour truth: independent surface-area check of the fleet polygon vs the survey's own lake outline (shore rings in the contour file, or the agency's
reported acres: MN outline, OH lakes, NE shapes, IL surveyed, IN lake_acres).  A polygon much bigger/smaller than the surveyed lake biases the 0-3 ft share.
Output data/contour_survey_area.csv  (lakeId, src, survey_km2, how, poly_km2, ratio)."""
import gzip, json
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.ops import polygonize, unary_union

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
S = RAW / "depth-brain/sources"; N = RAW / "depth-brain/contour/norm"
AC = 4046.8564 / 1e6


def main():
    m = pd.read_csv(D / "contour_matches_verified.csv", dtype={"grp": str})
    v = m[(m.matchConfidence == "verified_spatial") & (m.src != "TWDB") & m.lakeAreaKm2.notna()]
    rows = []
    mn_out = gpd.read_file(S / "mn_dnr/mn_bathy_outline.geojson", ignore_geometry=True)
    oh = gpd.read_file(S / "oh_dow/oh_dow_lakes.geojson", ignore_geometry=True)
    ne = gpd.read_file(S / "ne_ngpc/ne_lake_shapes.geojson", ignore_geometry=True)
    il = gpd.read_file(S / "il_idnr/il_lakes_surveyed.geojson", ignore_geometry=True)
    for (lid, src), sub in v.groupby(["lakeId", "src"]):
        pk = sub.lakeAreaKm2.iloc[0]; out = None
        grps = sub.grp.astype(str).tolist()
        if src == "MN":
            o = mn_out[mn_out.dowlknum.isin(grps) & (mn_out.island.fillna("N") != "Y")]
            if len(o): out = (o.acres.sum() * AC, "MN outline acres", o.acres.max() * AC)
        elif src == "OH":
            o = oh[oh.LAKE_NAME.isin(grps)]
            if len(o): out = (o.ACRES.sum() * AC, "OH lake acres")
        elif src == "NE":
            o = ne[ne.Name.isin(grps)]
            if len(o): out = (o.Acres.sum() * AC, "NE shape acres")
        elif src == "IL":
            a = pd.read_csv(D / "contour_anchors_verified.csv")
        if out is None and src in ("CT", "MA", "NH", "ND", "WA", "MT", "MN", "OK", "KS", "FL", "WV", "IN"):
            try:
                gg = gpd.read_file(N / f"{src}.gpkg", where="grp IN (%s)" % ",".join("'" + g.replace("'", "''") + "'" for g in grps)).to_crs(5070)
                sh = gg[(gg.kind == "shore") | (gg.depth_ft == 0)]
                if len(sh):
                    pol = list(polygonize(unary_union(sh.geometry.values)))
                    if pol:
                        # outer shells minus nested islands approximated by even-odd union
                        pol = sorted(pol, key=lambda p: -p.area)
                        acc = pol[0]
                        for p in pol[1:]:
                            acc = acc.symmetric_difference(p) if p.within(acc.buffer(1)) else acc.union(p)
                        out = (acc.area / 1e6, "shore rings in contour file")
            except Exception as e:
                out = None
        if out:
            mx = out[2] if len(out) > 2 else out[0]
            rows.append(dict(lakeId=lid, src=src, survey_km2=out[0], survey_km2_max_group=mx, how=out[1], poly_km2=pk, ratio=pk / out[0] if out[0] > 0 else np.nan, ratio_max_group=pk / mx if mx > 0 else np.nan))
    r = pd.DataFrame(rows)
    r.to_csv(D / "contour_survey_area.csv", index=False, float_format="%.4f")
    print(len(r), r.ratio.describe().to_dict())
    print(r.sort_values("ratio").round(3).to_string())


if __name__ == "__main__":
    main()
