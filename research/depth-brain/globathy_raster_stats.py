#!/usr/bin/env python3
"""Depth-distribution stats from the actual GLOBathy rasters of matched fleet lakes -> docs/.../data/globathy_raster_stats.csv"""
import numpy as np, pandas as pd, rasterio, os
R = "/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/globathy/rasters/"
D = "/Users/mcather/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/"
m = pd.read_csv(D + "globathy_fleet_match.csv").dropna(subset=["hl_id"])
rows = []
for hid in m.hl_id.astype(int).unique():
    p = f"{R}{hid}.tif"
    if not os.path.exists(p): continue
    s = rasterio.open(p); a = s.read(1).astype("float64"); ok = (a != s.nodata) & (a > 0) & np.isfinite(a)
    if ok.sum() == 0: continue
    lat = s.bounds.top - (np.arange(a.shape[0]) + .5) * abs(s.res[1])
    w = np.cos(np.radians(lat))[:, None] * np.ones((1, a.shape[1]))
    d = a[ok]; ww = w[ok]; W = ww.sum()
    o = dict(hl_id=hid, rast_npix=int(ok.sum()), rast_max_m=d.max(), rast_mean_m=float((d * ww).sum() / W))
    for t in (1.2, 1.8, 3, 6): o[f"rast_frac_lt_{str(t).replace('.','p')}m"] = float(ww[d < t].sum() / W)
    # spatial: fraction of area deeper than half max, median depth
    o["rast_median_m"] = float(np.median(d)); o["rast_frac_gt_half_max"] = float(ww[d > d.max() / 2].sum() / W)
    rows.append(o)
pd.DataFrame(rows).round(5).to_csv(D + "globathy_raster_stats.csv", index=False); print(len(rows))
