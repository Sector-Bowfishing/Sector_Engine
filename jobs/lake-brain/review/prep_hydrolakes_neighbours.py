#!/usr/bin/env python3
"""Offline prep step for the coordinate review pack: the water bodies (HydroLAKES v10, lakes of 10 ha and up) around every registry pin.

Needs pyogrio + shapely (the geometry research venv at <data>/geometry/venv) and the extracted shapefile in
<data>/geometry/hydrolakes/extracted/. Reads the cached registry index; writes <data>/coords-review/hydrolakes_neighbours.json
(lakeId -> [{id, name, areaKm2, type, geometry}]; polygons simplified to about 55 m). Nothing is fetched from the network.
    <data>/geometry/venv/bin/python prep_hydrolakes_neighbours.py [--data-dir DIR] [--half-deg 0.06]
The builder (build_coordinate_review_pack.py) uses the result as its scan of other waters near each pin.
"""
import argparse
import json
import os
import sys

DEFAULT_DATA = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DEFAULT_DATA)
    ap.add_argument("--half-deg", type=float, default=0.06, help="half side of the search box around each pin, degrees (0.06 = about 6.5 km)")
    args = ap.parse_args(argv)
    from pyogrio.raw import read as ogr_read
    from shapely import wkb
    from shapely.geometry import mapping
    shp = os.path.join(args.data_dir, "geometry", "hydrolakes", "extracted", "HydroLAKES_polys_v10_shp", "HydroLAKES_polys_v10.shp")
    idx = json.load(open(os.path.join(args.data_dir, "coords-review", "lakes.v1.json")))
    out = {}
    for l in idx["lakes"]:
        lat, lon = l["location"]["lat"], l["location"]["lon"]
        bbox = (lon - args.half_deg, lat - args.half_deg, lon + args.half_deg, lat + args.half_deg)
        meta, _i, geoms, fields = ogr_read(shp, bbox=bbox, columns=["Hylak_id", "Lake_name", "Lake_area", "Lake_type"])
        col = {str(n): k for k, n in enumerate(meta["fields"])}      # pyogrio returns the columns in FILE order, not in the order requested
        rows = []
        for i in range(len(geoms)):
            if geoms[i] is None:
                continue
            g = wkb.loads(bytes(geoms[i])).buffer(0).simplify(0.0005, preserve_topology=True)
            if g.is_empty:
                continue
            rows.append({"id": f"HL:{int(fields[col['Hylak_id']][i])}", "name": fields[col["Lake_name"]][i] or None, "areaKm2": round(float(fields[col["Lake_area"]][i]), 3),
                         "type": int(fields[col["Lake_type"]][i]),
                         "geometry": mapping(g)})
        out[l["lakeId"]] = rows
    dest = os.path.join(args.data_dir, "coords-review", "hydrolakes_neighbours.json")
    json.dump(out, open(dest, "w"), separators=(",", ":"))
    print("wrote", dest, "lakes:", len(out), "with neighbours:", sum(1 for v in out.values() if v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
