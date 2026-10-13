"""Station-coordinate facts: do NLA phab rows carry per-station coordinates, and where are they relative to the analysis polygon?"""
import numpy as np, pandas as pd, pyproj
from pathlib import Path
from shapely.geometry import Point
from shapely.ops import transform
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent))
import nlalib as L
H = L.H
cls = pd.read_csv(H/"out/nla_lake_classes.csv"); cls = cls[cls.n_stations > 0]
phab = pd.read_csv(L.ROOT.parent/"sources/nla_2017_phab/nla_2017_phab-data.csv", low_memory=False)
rows = []
for _, r in cls.iterrows():
    poly = L.load_poly(r.lakeKey); c = poly.representative_point()
    zone = int((c.x + 180) // 6) + 1; crs = f"EPSG:{32600 + zone if c.y >= 0 else 32700 + zone}"
    to = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    pu = transform(to, poly); bd = pu.boundary
    p = phab[phab.SITE_ID.isin(r.SITE_IDs.split(";")) & (phab.VISIT_NO == 1)]
    for _, s in p.iterrows():
        if pd.isna(s.LATITUDE): rows.append(dict(lakeKey=r.lakeKey, station=s.STATION, has_xy=False)); continue
        pt = transform(to, Point(s.LONGITUDE, s.LATITUDE))
        rows.append(dict(lakeKey=r.lakeKey, SITE_ID=s.SITE_ID, station=s.STATION, has_xy=True, lat=s.LATITUDE, lon=s.LONGITUDE, inside=bool(pu.contains(pt)), d_edge_m=float(bd.distance(pt)),
                         emerg=s.AM_EMERGENT, floating=s.AM_FLOATING, total=s.AM_TOTALCOVER))
d = pd.DataFrame(rows); d.to_csv(H/"out/nla_station_geometry.csv", index=False)
x = d[d.has_xy]
print("stations", len(d), "with xy", len(x), "inside polygon", int(x.inside.sum()))
print(x.d_edge_m.describe()); print("within 10 m of edge", int((x.d_edge_m <= 10).sum()), "within 90 m", int((x.d_edge_m <= 90).sum()), "inside & 10<d<=90", int((x.inside & (x.d_edge_m > 10) & (x.d_edge_m <= 90)).sum()))
